from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.auth import access_project, get_current_user
from app.db import get_db
from app.models import (
    ActionItem,
    ContextItem,
    ContextKind,
    ContextStatus,
    MeetingOrigin,
    ProjectRole,
    Source,
    SourceType,
    User,
)
from pathlib import Path

from app.schemas import DocumentCreate, NoteCreate, ObsidianNoteCreate, SourceOut
from app.services import link_title
from app.services import obsidian as obs_svc
from app.services.extraction import extract_meeting
from app.services.transcription import TranscriptionError, transcribe

router = APIRouter(tags=["sources"])


def _as_text(item) -> str:
    """추출 결과 항목을 문자열로. GPT가 객체({담당자, 할일})로 줘도 살린다."""
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        return " · ".join(str(v).strip() for v in item.values() if v).strip()
    return str(item).strip() if item is not None else ""


def _enrich_source(db: Session, source: Source, ai_title: bool = True) -> None:
    """메모/회의 저장 직후 LLM 추출을 적용한다. 실패해도 소스는 그대로 유지(best-effort).

    ai_title=False면 제목을 AI로 덮어쓰지 않는다(옵시디언 파일명 유지 등).
    """
    project = source.project
    needs_objective = not (project.objective and project.objective.strip())

    kind = "note" if source.type == SourceType.NOTE else "meeting"
    try:
        data = extract_meeting(source.body or "", needs_objective, kind=kind)
    except Exception:  # noqa: BLE001 — 추출 실패가 소스 저장을 막지 않게
        return

    source.summary = data.get("summary")
    keywords = data.get("keywords")
    source.keywords = keywords if isinstance(keywords, list) else None

    # AI 제목: 메모는 항상, 그 외엔 제목이 비어있을 때만 채운다
    title = data.get("title")
    if ai_title and isinstance(title, str) and title.strip() and (
        source.type == SourceType.NOTE or not (source.title or "").strip()
    ):
        source.title = title.strip()[:300]

    for item in data.get("action_items") or []:
        text = _as_text(item)
        if text:
            db.add(ActionItem(source_id=source.id, content=text))

    for decision in data.get("decisions") or []:
        text = _as_text(decision)
        if text:
            db.add(
                ContextItem(
                    project_id=project.id,
                    kind=ContextKind.DECISION,
                    content=text,
                    source_id=source.id,
                    status=ContextStatus.PROPOSED,
                )
            )

    # 키워드를 프로젝트 태그로 누적 (기존 태그와 중복 제거, 대소문자 무시)
    if isinstance(keywords, list):
        existing = {
            ci.content.strip().lower()
            for ci in project.context_items
            if ci.kind == ContextKind.TAG
        }
        for kw in keywords:
            if isinstance(kw, str) and kw.strip() and kw.strip().lower() not in existing:
                db.add(
                    ContextItem(
                        project_id=project.id,
                        kind=ContextKind.TAG,
                        content=kw.strip(),
                        source_id=source.id,
                        status=ContextStatus.ACCEPTED,
                    )
                )
                existing.add(kw.strip().lower())

    if needs_objective:
        objective = data.get("objective")
        if isinstance(objective, str) and objective.strip():
            project.objective = objective.strip()

    db.commit()
    db.refresh(source)


def _save_source(
    db: Session,
    project_id: int,
    source_type: SourceType,
    title: str,
    body: str,
    origin: MeetingOrigin | None = None,
    enrich: bool = True,
    ai_title: bool = True,
    attendees: list[str] | None = None,
    note: str | None = None,
) -> Source:
    source = Source(
        project_id=project_id,
        type=source_type,
        origin=origin,
        title=title,
        body=body,
        attendees=attendees or None,
        note=(note or None),
    )
    db.add(source)
    db.commit()
    db.refresh(source)
    if enrich:
        _enrich_source(db, source, ai_title=ai_title)
    return source


@router.post(
    "/projects/{project_id}/notes",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    project_id: int,
    payload: NoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """메모(md) 붙여넣기 → NOTE. 제목은 AI 생성(추출 실패 시 첫 줄 폴백)."""
    access_project(db, project_id, user, ProjectRole.EDITOR)
    fallback = (payload.title or "").strip() or (
        payload.text.strip().splitlines()[0][:40] if payload.text.strip() else "메모"
    )
    return _save_source(
        db, project_id, SourceType.NOTE, fallback, payload.text, MeetingOrigin.PASTED
    )


@router.post(
    "/projects/{project_id}/obsidian-notes",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_note_from_obsidian(
    project_id: int,
    payload: ObsidianNoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """옵시디언 노트를 읽어 메모(NOTE)로 추가. 파일명을 제목으로 유지."""
    access_project(db, project_id, user, ProjectRole.EDITOR)
    try:
        content = obs_svc.read_note(db, user.id, payload.path)
    except obs_svc.ObsidianError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    title = Path(payload.path).stem or "옵시디언 노트"
    return _save_source(
        db, project_id, SourceType.NOTE, title, content, MeetingOrigin.PASTED,
        ai_title=False,
    )


@router.post(
    "/projects/{project_id}/documents",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_document(
    project_id: int,
    payload: DocumentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """관련문서 참조 추가 → DOCUMENT. 제목을 비우면 페이지 제목을 자동으로 가져옴."""
    access_project(db, project_id, user, ProjectRole.EDITOR)
    url = (payload.url or "").strip()
    if url:
        dup = (
            db.query(Source)
            .filter(
                Source.project_id == project_id,
                Source.type == SourceType.DOCUMENT,
                Source.body == url,
            )
            .first()
        )
        if dup:
            return dup

    title = (payload.title or "").strip()
    if not title and url:
        title = link_title.fetch_page_title(url) or ""
    if not title:  # 그래도 없으면 호스트명 폴백
        try:
            from urllib.parse import urlparse
            title = urlparse(url).hostname or url or "링크"
        except Exception:  # noqa: BLE001
            title = url or "링크"

    return _save_source(
        db, project_id, SourceType.DOCUMENT, title, url, enrich=False
    )


@router.post(
    "/projects/{project_id}/meetings/audio",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_meeting_from_audio(
    project_id: int,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    attendees: str | None = Form(default=None),
    note: str | None = Form(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """녹음/음성파일 업로드 → Whisper 전사 → MEETING. attendees는 콤마 구분, note는 녹음 중 메모."""
    access_project(db, project_id, user, ProjectRole.EDITOR)

    content = file.file.read()
    try:
        transcript = transcribe(file.filename or "audio", content)
    except TranscriptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    names = [n.strip() for n in (attendees or "").split(",") if n.strip()]
    meeting_title = title or f"회의 녹음 ({file.filename})"
    return _save_source(
        db, project_id, SourceType.MEETING, meeting_title, transcript,
        MeetingOrigin.AUDIO, attendees=names, note=(note or "").strip() or None,
    )
