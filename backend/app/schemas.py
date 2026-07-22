from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ContextKind, ContextStatus, MeetingOrigin, SourceType


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Auth ------------------------------------------------------------------


class Credentials(BaseModel):
    """회원가입·로그인 공용 입력."""

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=6, max_length=128)


class UserOut(ORMModel):
    id: int
    email: str


# --- Project ---------------------------------------------------------------


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    objective: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    objective: str | None = None
    active: bool | None = None


class ProjectListItem(ORMModel):
    """홈 화면 프로젝트 카드 (PRD §9.1)."""

    id: int
    name: str
    objective: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
    meeting_count: int
    document_count: int
    role: str | None = None  # 현재 사용자의 권한 (owner/editor/viewer)


# --- Members ---------------------------------------------------------------


class ProjectMemberOut(BaseModel):
    user_id: int
    email: str
    role: str


class MemberInvite(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    role: str = "editor"  # editor | viewer


class MemberRoleUpdate(BaseModel):
    role: str  # editor | viewer


# --- Source & children -----------------------------------------------------


class ActionItemOut(ORMModel):
    id: int
    content: str
    done: bool
    due_date: date | None = None


class ActionItemUpdate(BaseModel):
    content: str | None = None
    done: bool | None = None
    due_date: date | None = None


class ActionItemCreate(BaseModel):
    content: str = Field(min_length=1)
    due_date: date | None = None


class CalendarItem(BaseModel):
    """캘린더에 표시할, 마감일이 지정된 액션아이템 + 출처 맥락."""

    id: int
    content: str
    done: bool
    due_date: date
    source_id: int
    source_title: str
    project_id: int
    project_name: str


class MeetingReferenceOut(ORMModel):
    id: int
    drive_file_id: str
    title: str
    url: str
    snippet: str | None
    note: str | None


class SourceCreate(BaseModel):
    type: SourceType
    title: str = Field(min_length=1, max_length=300)
    body: str | None = None
    summary: str | None = None
    origin: MeetingOrigin | None = None


class SourceUpdate(BaseModel):
    project_id: int | None = None
    title: str | None = None
    body: str | None = None
    note: str | None = None
    attendees: list[str] | None = None


class NoteCreate(BaseModel):
    """메모(md) 붙여넣기 → NOTE 소스. 제목은 비우면 AI가 생성."""

    title: str | None = Field(default=None, max_length=300)
    text: str = Field(min_length=1)


class DocumentCreate(BaseModel):
    """관련문서 참조 추가 → DOCUMENT 소스."""

    title: str = Field(min_length=1, max_length=300)
    url: str | None = None


class ObsidianNoteCreate(BaseModel):
    """옵시디언 노트를 메모(NOTE)로 추가."""

    path: str = Field(min_length=1)


class ObsidianConfig(BaseModel):
    """볼트 연결 설정 (사용자가 입력한 호스트 경로)."""

    path: str = Field(min_length=1)


class SourceOut(ORMModel):
    id: int
    type: SourceType
    title: str
    body: str | None
    summary: str | None
    note: str | None = None
    keywords: list[str] | None = None
    attendees: list[str] | None = None
    origin: MeetingOrigin | None
    created_at: datetime
    action_items: list[ActionItemOut] = []
    references: list[MeetingReferenceOut] = []


# --- Context ---------------------------------------------------------------


class ContextItemOut(ORMModel):
    id: int
    kind: ContextKind
    content: str
    status: ContextStatus
    source_id: int | None


class ContextItemCreate(BaseModel):
    kind: ContextKind
    content: str = Field(min_length=1)
    status: ContextStatus = ContextStatus.ACCEPTED


class ContextItemUpdate(BaseModel):
    content: str | None = None
    status: ContextStatus | None = None


# --- Project detail (타임라인 + Context 한 번에) ----------------------------


class ProjectDetail(ORMModel):
    id: int
    name: str
    objective: str | None
    active: bool = True
    created_at: datetime
    updated_at: datetime | None = None
    role: str | None = None  # 현재 사용자의 권한
    sources: list[SourceOut] = []
    context_items: list[ContextItemOut] = []
