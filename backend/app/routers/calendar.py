from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import ActionItem, Project, ProjectMember, Source, User
from app.schemas import CalendarItem

router = APIRouter(tags=["calendar"])


@router.get("/calendar", response_model=list[CalendarItem])
def calendar(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """마감일이 지정된 (내가 멤버인 프로젝트의) 액션아이템을 출처와 함께 반환."""
    stmt = (
        select(ActionItem, Source.title, Source.project_id, Project.name)
        .join(Source, ActionItem.source_id == Source.id)
        .join(Project, Source.project_id == Project.id)
        .join(
            ProjectMember,
            (ProjectMember.project_id == Project.id)
            & (ProjectMember.user_id == user.id),
        )
        .where(ActionItem.due_date.is_not(None))
        .order_by(ActionItem.due_date)
    )
    return [
        CalendarItem(
            id=a.id,
            content=a.content,
            done=a.done,
            due_date=a.due_date,
            source_id=a.source_id,
            source_title=title,
            project_id=project_id,
            project_name=project_name,
        )
        for a, title, project_id, project_name in db.execute(stmt).all()
    ]
