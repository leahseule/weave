"""인증·소유권 공통 로직 (세션 쿠키 + bcrypt)."""

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    ActionItem,
    ContextItem,
    Project,
    ProjectMember,
    ProjectRole,
    Source,
    User,
)


def hash_password(pw: str) -> str:
    # bcrypt는 72바이트까지만 사용 → 초과분은 잘라 오류 방지
    return bcrypt.hashpw(pw.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode("utf-8")[:72], hashed.encode("utf-8"))
    except Exception:  # noqa: BLE001
        return False


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """세션 쿠키의 user_id로 현재 사용자를 로드. 없으면 401."""
    uid = request.session.get("user_id")
    if not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요해요"
        )
    user = db.get(User, uid)
    if user is None:
        request.session.clear()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="로그인이 필요해요"
        )
    return user


# 권한 서열: VIEWER < EDITOR < OWNER
_RANK = {ProjectRole.VIEWER: 1, ProjectRole.EDITOR: 2, ProjectRole.OWNER: 3}


def project_role(db: Session, project_id: int, user_id: int) -> ProjectRole | None:
    m = db.get(ProjectMember, (project_id, user_id))
    return m.role if m else None


def access_project(
    db: Session, project_id: int, user: User, need: ProjectRole = ProjectRole.VIEWER
) -> Project:
    """멤버가 아니면 404(존재 숨김), 권한 부족이면 403."""
    project = db.get(Project, project_id)
    role = project_role(db, project_id, user.id) if project else None
    if project is None or role is None:
        raise HTTPException(status_code=404, detail="Project not found")
    if _RANK[role] < _RANK[need]:
        raise HTTPException(status_code=403, detail="이 작업을 할 권한이 없어요")
    return project


def access_source(
    db: Session, source_id: int, user: User, need: ProjectRole = ProjectRole.VIEWER
) -> Source:
    source = db.get(Source, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found")
    access_project(db, source.project_id, user, need)
    return source


def access_action(
    db: Session, item_id: int, user: User, need: ProjectRole = ProjectRole.VIEWER
) -> ActionItem:
    item = db.get(ActionItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Action item not found")
    access_source(db, item.source_id, user, need)
    return item


def access_context(
    db: Session, item_id: int, user: User, need: ProjectRole = ProjectRole.VIEWER
) -> ContextItem:
    item = db.get(ContextItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Context item not found")
    access_project(db, item.project_id, user, need)
    return item
