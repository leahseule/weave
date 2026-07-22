from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import access_project, access_source, get_current_user
from app.db import get_db
from app.models import ContextItem, ProjectRole, Source, User
from app.schemas import SourceCreate, SourceOut, SourceUpdate

router = APIRouter(tags=["sources"])


@router.get("/projects/{project_id}/sources", response_model=list[SourceOut])
def list_sources(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """타임라인: 프로젝트의 소스를 시간순으로."""
    access_project(db, project_id, user)

    stmt = (
        select(Source)
        .where(Source.project_id == project_id)
        .options(
            selectinload(Source.action_items),
            selectinload(Source.references),
        )
        .order_by(Source.created_at)
    )
    return db.execute(stmt).scalars().all()


@router.post(
    "/projects/{project_id}/sources",
    response_model=SourceOut,
    status_code=status.HTTP_201_CREATED,
)
def create_source(
    project_id: int,
    payload: SourceCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """소스 수동 추가. P2~P4에서 녹음·문서 업로드가 이 위에 얹힌다."""
    access_project(db, project_id, user, ProjectRole.EDITOR)

    source = Source(project_id=project_id, **payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source(
    source_id: int,
    payload: SourceUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """소스 수정. project_id 변경 시 다른 프로젝트로 이동하며,
    이 회의에서 파생된 Context(결정·태그)도 함께 옮긴다."""
    source = access_source(db, source_id, user, ProjectRole.EDITOR)

    data = payload.model_dump(exclude_unset=True)
    new_pid = data.get("project_id")
    if new_pid is not None and new_pid != source.project_id:
        access_project(db, new_pid, user, ProjectRole.EDITOR)  # 대상도 편집권 필요
        # 이 회의에서 나온 결정/태그도 새 프로젝트로 이동 (provenance 유지)
        db.query(ContextItem).filter(ContextItem.source_id == source_id).update(
            {ContextItem.project_id: new_pid}
        )
        source.project_id = new_pid
    if "title" in data:
        source.title = data["title"]
    if "body" in data:
        source.body = data["body"]
    if "note" in data:
        source.note = data["note"]
    if "attendees" in data:
        source.attendees = data["attendees"] or None

    db.commit()
    db.refresh(source)
    return source


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(
    source_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    source = access_source(db, source_id, user, ProjectRole.EDITOR)
    db.delete(source)
    db.commit()
