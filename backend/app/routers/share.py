"""OKF 컨텍스트 공유 링크: 발급(로그인) · 공개 조회(text/plain) · 해제."""

import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.auth import access_project, access_source, get_current_user
from app.db import get_db
from app.models import Project, ProjectRole, ShareLink, Source, User
from app.services import okf

router = APIRouter(tags=["share"])

_TTL_HOURS = 24  # 공유 링크 유효 시간


def _new_link(db: Session, user: User, kind: str, *, source_id=None, project_id=None) -> ShareLink:
    link = ShareLink(
        token=secrets.token_urlsafe(24),
        kind=kind,
        source_id=source_id,
        project_id=project_id,
        created_by=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=_TTL_HOURS),
    )
    db.add(link)
    db.commit()
    db.refresh(link)
    return link


@router.post("/sources/{source_id}/share")
def share_source(
    source_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """회의/메모 하나의 OKF 공유 링크 발급."""
    access_source(db, source_id, user, ProjectRole.VIEWER)
    link = _new_link(db, user, "meeting", source_id=source_id)
    return {"token": link.token, "expires_at": link.expires_at}


@router.post("/projects/{project_id}/share")
def share_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """프로젝트 전체의 OKF 공유 링크 발급."""
    access_project(db, project_id, user, ProjectRole.VIEWER)
    link = _new_link(db, user, "project", project_id=project_id)
    return {"token": link.token, "expires_at": link.expires_at}


@router.get("/sources/{source_id}/okf", response_class=PlainTextResponse)
def okf_source(
    source_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """회의/메모 OKF 텍스트 (본인용 복사, 공개 링크 없음)."""
    source = access_source(db, source_id, user, ProjectRole.VIEWER)
    return PlainTextResponse(okf.okf_for_source(source), media_type="text/plain; charset=utf-8")


@router.get("/projects/{project_id}/okf", response_class=PlainTextResponse)
def okf_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """프로젝트 OKF 다이제스트 텍스트 (본인용 복사, 공개 링크 없음)."""
    project = access_project(db, project_id, user, ProjectRole.VIEWER)
    return PlainTextResponse(okf.okf_for_project(project), media_type="text/plain; charset=utf-8")


@router.delete("/share/{token}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_share(
    token: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """공유 링크 해제(비활성화)."""
    link = db.query(ShareLink).filter(ShareLink.token == token).first()
    if link and link.created_by == user.id:
        link.revoked = True
        db.commit()


@router.get("/share/{token}", response_class=PlainTextResponse)
def read_share(token: str, db: Session = Depends(get_db)):
    """공개: 유효한 토큰이면 OKF 텍스트를 반환 (로그인 불필요)."""
    link = db.query(ShareLink).filter(ShareLink.token == token).first()
    now = datetime.now(timezone.utc)
    expired = link and link.expires_at and link.expires_at <= now
    if link is None or link.revoked or expired:
        return PlainTextResponse(
            "이 공유 링크는 만료되었거나 존재하지 않습니다.", status_code=404
        )

    if link.kind == "meeting":
        source = db.get(Source, link.source_id) if link.source_id else None
        if source is None:
            return PlainTextResponse("원본을 찾을 수 없습니다.", status_code=404)
        text = okf.okf_for_source(source)
    else:
        project = db.get(Project, link.project_id) if link.project_id else None
        if project is None:
            return PlainTextResponse("원본을 찾을 수 없습니다.", status_code=404)
        text = okf.okf_for_project(project)

    return PlainTextResponse(text, media_type="text/plain; charset=utf-8")
