from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, selectinload

from app.auth import access_project, get_current_user, project_role
from app.db import get_db
from app.models import (
    Project,
    ProjectMember,
    ProjectRole,
    Source,
    SourceType,
    User,
)
from app.schemas import (
    MemberInvite,
    MemberRoleUpdate,
    ProjectCreate,
    ProjectDetail,
    ProjectListItem,
    ProjectMemberOut,
    ProjectUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])


def _with_updated_at(project: Project, role: ProjectRole | None = None) -> Project:
    """최종 업데이트 = 프로젝트/소스/Context 중 가장 최근 created_at (transient)."""
    times = [project.created_at]
    times += [s.created_at for s in project.sources]
    times += [c.created_at for c in project.context_items]
    project.updated_at = max(times)
    if role is not None:
        project.role = role.value
    return project


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = Project(name=payload.name, objective=payload.objective, owner_id=user.id)
    db.add(project)
    db.commit()
    db.refresh(project)
    # 생성자를 OWNER 멤버로 등록
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role=ProjectRole.OWNER))
    db.commit()
    return _with_updated_at(project, ProjectRole.OWNER)


@router.get("", response_model=list[ProjectListItem])
def list_projects(
    active: bool | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """내가 멤버인 프로젝트 목록 + 회의/문서 개수(집계) + 내 권한."""
    meetings = func.count(Source.id).filter(Source.type == SourceType.MEETING)
    documents = func.count(Source.id).filter(Source.type == SourceType.DOCUMENT)
    updated = func.coalesce(func.max(Source.created_at), Project.created_at)

    stmt = (
        select(
            Project,
            meetings.label("meeting_count"),
            documents.label("document_count"),
            updated.label("updated_at"),
            ProjectMember.role.label("role"),
        )
        .join(
            ProjectMember,
            and_(
                ProjectMember.project_id == Project.id,
                ProjectMember.user_id == user.id,
            ),
        )
        .outerjoin(Source, Source.project_id == Project.id)
    )
    if active is not None:
        stmt = stmt.where(Project.active == active)
    stmt = stmt.group_by(Project.id, ProjectMember.role).order_by(updated.desc())

    return [
        ProjectListItem(
            id=project.id,
            name=project.name,
            objective=project.objective,
            active=project.active,
            created_at=project.created_at,
            updated_at=updated_at,
            meeting_count=meeting_count,
            document_count=document_count,
            role=role.value,
        )
        for project, meeting_count, document_count, updated_at, role in db.execute(
            stmt
        ).all()
    ]


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """프로젝트 상세: 타임라인(sources) + Context를 한 번에."""
    access_project(db, project_id, user)  # 멤버 검증 (뷰어 이상)
    role = project_role(db, project_id, user.id)
    stmt = (
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.sources).selectinload(Source.action_items),
            selectinload(Project.sources).selectinload(Source.references),
            selectinload(Project.context_items),
        )
    )
    project = db.execute(stmt).scalar_one_or_none()
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Project not found"
        )
    return _with_updated_at(project, role)


@router.patch("/{project_id}", response_model=ProjectDetail)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = access_project(db, project_id, user, ProjectRole.EDITOR)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    db.commit()
    db.refresh(project)
    return _with_updated_at(project, project_role(db, project_id, user.id))


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    project = access_project(db, project_id, user, ProjectRole.OWNER)
    db.delete(project)
    db.commit()


# --- 멤버 관리 -------------------------------------------------------------


@router.get("/{project_id}/members", response_model=list[ProjectMemberOut])
def list_members(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """프로젝트 멤버 목록 (멤버 누구나 조회 가능)."""
    access_project(db, project_id, user)
    rows = (
        db.query(ProjectMember, User)
        .join(User, User.id == ProjectMember.user_id)
        .filter(ProjectMember.project_id == project_id)
        .all()
    )
    order = {ProjectRole.OWNER: 0, ProjectRole.EDITOR: 1, ProjectRole.VIEWER: 2}
    members = [
        ProjectMemberOut(user_id=u.id, email=u.email, role=m.role.value)
        for m, u in rows
    ]
    members.sort(key=lambda x: order.get(ProjectRole(x.role), 9))
    return members


@router.post(
    "/{project_id}/members",
    response_model=ProjectMemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(
    project_id: int,
    payload: MemberInvite,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """소유자가 이메일로 멤버 초대 (editor/viewer)."""
    access_project(db, project_id, user, ProjectRole.OWNER)
    if payload.role not in (ProjectRole.EDITOR.value, ProjectRole.VIEWER.value):
        raise HTTPException(status_code=400, detail="역할은 editor 또는 viewer만 가능해요")
    email = payload.email.strip().lower()
    target = db.query(User).filter(User.email == email).first()
    if target is None:
        raise HTTPException(status_code=404, detail="가입된 사용자가 아니에요")
    if db.get(ProjectMember, (project_id, target.id)) is not None:
        raise HTTPException(status_code=409, detail="이미 멤버예요")
    m = ProjectMember(
        project_id=project_id, user_id=target.id, role=ProjectRole(payload.role)
    )
    db.add(m)
    db.commit()
    return ProjectMemberOut(user_id=target.id, email=target.email, role=m.role.value)


@router.patch(
    "/{project_id}/members/{member_user_id}", response_model=ProjectMemberOut
)
def update_member_role(
    project_id: int,
    member_user_id: int,
    payload: MemberRoleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """소유자가 멤버 권한 변경 (editor/viewer). 소유자 자신은 변경 불가."""
    project = access_project(db, project_id, user, ProjectRole.OWNER)
    if member_user_id == project.owner_id:
        raise HTTPException(status_code=400, detail="소유자의 권한은 바꿀 수 없어요")
    if payload.role not in (ProjectRole.EDITOR.value, ProjectRole.VIEWER.value):
        raise HTTPException(status_code=400, detail="역할은 editor 또는 viewer만 가능해요")
    m = db.get(ProjectMember, (project_id, member_user_id))
    if m is None:
        raise HTTPException(status_code=404, detail="멤버가 아니에요")
    m.role = ProjectRole(payload.role)
    db.commit()
    target = db.get(User, member_user_id)
    return ProjectMemberOut(user_id=member_user_id, email=target.email, role=m.role.value)


@router.delete(
    "/{project_id}/members/{member_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_member(
    project_id: int,
    member_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """소유자가 멤버 제거. 소유자 자신은 제거 불가."""
    project = access_project(db, project_id, user, ProjectRole.OWNER)
    if member_user_id == project.owner_id:
        raise HTTPException(status_code=400, detail="소유자는 제거할 수 없어요")
    m = db.get(ProjectMember, (project_id, member_user_id))
    if m is None:
        raise HTTPException(status_code=404, detail="멤버가 아니에요")
    db.delete(m)
    db.commit()
