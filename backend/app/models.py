from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class SourceType(str, enum.Enum):
    NOTE = "NOTE"
    MEETING = "MEETING"
    DOCUMENT = "DOCUMENT"


class MeetingOrigin(str, enum.Enum):
    """회의가 어떻게 만들어졌는지 (PRD §8)."""

    AUDIO = "audio"
    PASTED = "pasted"


class ContextKind(str, enum.Enum):
    OBJECTIVE = "OBJECTIVE"
    DECISION = "DECISION"
    TAG = "TAG"


class ContextStatus(str, enum.Enum):
    """AI 제안 → 사람 큐레이션 (PRD §5-3)."""

    PROPOSED = "proposed"
    ACCEPTED = "accepted"


class ProjectRole(str, enum.Enum):
    """프로젝트 멤버 권한. OWNER > EDITOR > VIEWER."""

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class User(Base):
    """가입 사용자. 프로젝트 소유권의 주체."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    # Google 로그인 사용자는 비밀번호가 없어 nullable
    password_hash: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(primary_key=True)
    # 소유자. 기존 데이터 호환을 위해 nullable (첫 가입자가 orphan을 인수).
    owner_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    # 비워두면 첫 회의에서 자동 추출 (PRD §13-3)
    objective: Mapped[str | None] = mapped_column(Text)
    # 활성/비활성(보관). 비활성 프로젝트는 홈 기본 목록에서 숨김
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    sources: Mapped[list[Source]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="Source.created_at",
    )
    context_items: Mapped[list[ContextItem]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Source(Base):
    """타임라인 항목. MEETING 또는 DOCUMENT."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[SourceType] = mapped_column(Enum(SourceType, name="source_type"))
    title: Mapped[str] = mapped_column(String(300))
    # MEETING: 전사문 또는 붙여넣은 원문 / DOCUMENT: 파일 설명
    body: Mapped[str | None] = mapped_column(Text)
    # AI가 생성한 요약 (P3에서 채워짐)
    summary: Mapped[str | None] = mapped_column(Text)
    # 사용자 메모 (주로 문서: "어떤 문서인지" 설명)
    note: Mapped[str | None] = mapped_column(Text)
    # AI가 뽑은 키워드 (P4 Drive 검색 재료). JSON 문자열 배열.
    keywords: Mapped[list | None] = mapped_column(JSON)
    # 회의 참석자 이름 목록 (녹음 시 사용자가 지정). JSON 문자열 배열.
    attendees: Mapped[list | None] = mapped_column(JSON)
    origin: Mapped[MeetingOrigin | None] = mapped_column(
        Enum(MeetingOrigin, name="meeting_origin")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="sources")
    action_items: Mapped[list[ActionItem]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    references: Mapped[list[MeetingReference]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    # 캘린더용 마감일 (선택)
    due_date: Mapped[date | None] = mapped_column(Date)

    source: Mapped[Source] = relationship(back_populates="action_items")


class MeetingReference(Base):
    """회의 검토 중 pin한 Google Drive 문서 (PRD §8)."""

    __tablename__ = "meeting_references"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="CASCADE"), index=True
    )
    drive_file_id: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)

    source: Mapped[Source] = relationship(back_populates="references")


class ContextItem(Base):
    """Project Context 패널 항목. AI 제안 → 사람 큐레이션."""

    __tablename__ = "context_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[ContextKind] = mapped_column(Enum(ContextKind, name="context_kind"))
    content: Mapped[str] = mapped_column(Text)
    # 출처 추적(provenance) — 어느 소스에서 나왔는지 (PRD §5-4)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL")
    )
    status: Mapped[ContextStatus] = mapped_column(
        Enum(ContextStatus, name="context_status"),
        default=ContextStatus.PROPOSED,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    project: Mapped[Project] = relationship(back_populates="context_items")


class ProjectMember(Base):
    """프로젝트 멤버십 + 권한. 접근 제어의 원천 ((project_id, user_id) 복합 PK)."""

    __tablename__ = "project_members"

    project_id: Mapped[int] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    role: Mapped[ProjectRole] = mapped_column(Enum(ProjectRole, name="project_role"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Setting(Base):
    """사용자별 키-값 설정 (예: 옵시디언 볼트 경로). (user_id, key) 복합 PK."""

    __tablename__ = "settings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str | None] = mapped_column(Text)


class DriveConnection(Base):
    """Google Drive OAuth 토큰. 사용자당 1개(user_id unique)."""

    __tablename__ = "drive_connections"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
