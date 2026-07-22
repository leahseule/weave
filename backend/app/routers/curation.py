from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    access_action,
    access_context,
    access_project,
    access_source,
    get_current_user,
)
from app.db import get_db
from app.models import ActionItem, ContextItem, ProjectRole, User
from app.schemas import (
    ActionItemCreate,
    ActionItemOut,
    ActionItemUpdate,
    ContextItemCreate,
    ContextItemOut,
    ContextItemUpdate,
)

router = APIRouter(tags=["curation"])


# --- Context items (목표/결정/태그 큐레이션) --------------------------------


@router.post(
    "/projects/{project_id}/context-items",
    response_model=ContextItemOut,
    status_code=status.HTTP_201_CREATED,
)
def create_context_item(
    project_id: int,
    payload: ContextItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """사람이 직접 Context 항목 추가 (status=accepted)."""
    access_project(db, project_id, user, ProjectRole.EDITOR)
    item = ContextItem(project_id=project_id, **payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/context-items/{item_id}", response_model=ContextItemOut)
def update_context_item(
    item_id: int,
    payload: ContextItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """수락(status=accepted) 또는 내용 수정."""
    item = access_context(db, item_id, user, ProjectRole.EDITOR)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/context-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_context_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """제안 거절 / 항목 삭제."""
    item = access_context(db, item_id, user, ProjectRole.EDITOR)
    db.delete(item)
    db.commit()


# --- Action items (체크 토글) ----------------------------------------------


@router.post(
    "/sources/{source_id}/action-items",
    response_model=ActionItemOut,
    status_code=status.HTTP_201_CREATED,
)
def create_action_item(
    source_id: int,
    payload: ActionItemCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """회의에 액션아이템 직접 추가."""
    access_source(db, source_id, user, ProjectRole.EDITOR)
    item = ActionItem(
        source_id=source_id, content=payload.content, due_date=payload.due_date
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/action-items/{item_id}", response_model=ActionItemOut)
def update_action_item(
    item_id: int,
    payload: ActionItemUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = access_action(db, item_id, user, ProjectRole.EDITOR)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/action-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_action_item(
    item_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    item = access_action(db, item_id, user, ProjectRole.EDITOR)
    db.delete(item)
    db.commit()
