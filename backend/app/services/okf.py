"""회의/프로젝트 컨텍스트를 OKF(마크다운) 텍스트로 직렬화.

ChatGPT 등 외부 AI가 링크로 읽어 바로 컨텍스트로 쓸 수 있는 형태.
"""

from datetime import datetime

from app.models import ContextKind, ContextStatus, Project, Source, SourceType


def _fmt_date(dt: datetime | None) -> str:
    return dt.strftime("%Y-%m-%d") if dt else ""


def _action_lines(source: Source) -> list[str]:
    out = []
    for a in source.action_items:
        box = "x" if a.done else " "
        due = f" (기한 {a.due_date.isoformat()})" if a.due_date else ""
        out.append(f"- [{box}] {a.content}{due}")
    return out


def _decisions_for(source: Source) -> list[str]:
    return [
        c.content
        for c in source.project.context_items
        if c.source_id == source.id and c.kind == ContextKind.DECISION
    ]


def okf_for_source(source: Source) -> str:
    """회의(또는 메모) 하나의 OKF 컨텍스트."""
    proj = source.project
    is_meeting = source.type == SourceType.MEETING
    lines: list[str] = [
        f"# OKF · {'회의' if is_meeting else '메모'} 컨텍스트",
        f"project: {proj.name}",
    ]
    if proj.objective:
        lines.append(f"objective: {proj.objective}")
    lines.append(f"{'meeting' if is_meeting else 'note'}: {source.title}")
    lines.append(f"date: {_fmt_date(source.created_at)}")
    if source.attendees:
        lines.append(f"attendees: [{', '.join(source.attendees)}]")
    if source.keywords:
        lines.append(f"tags: [{', '.join(source.keywords)}]")
    lines.append("")

    if source.summary:
        lines += ["## 요약", source.summary, ""]

    decisions = _decisions_for(source)
    if decisions:
        lines += ["## 결정", *[f"- {d}" for d in decisions], ""]

    if source.action_items:
        lines += ["## 액션아이템", *_action_lines(source), ""]

    if source.body and source.body.strip():
        lines += [f"## {'전사' if is_meeting else '내용'}", source.body.strip(), ""]

    return "\n".join(lines).strip() + "\n"


def okf_for_project(project: Project) -> str:
    """프로젝트 전체의 OKF 다이제스트 (전사 원문은 제외, 요약·결정·미해결 액션 중심)."""
    lines: list[str] = ["# OKF · 프로젝트 컨텍스트", f"project: {project.name}"]
    if project.objective:
        lines.append(f"objective: {project.objective}")
    tags = sorted({
        c.content for c in project.context_items if c.kind == ContextKind.TAG
    })
    if tags:
        lines.append(f"tags: [{', '.join(tags)}]")
    lines.append("")

    decisions = [
        c.content
        for c in project.context_items
        if c.kind == ContextKind.DECISION and c.status == ContextStatus.ACCEPTED
    ]
    if decisions:
        lines += ["## 프로젝트 결정 (누적)", *[f"- {d}" for d in decisions], ""]

    open_actions = []
    for s in project.sources:
        for a in s.action_items:
            if not a.done:
                due = f" (기한 {a.due_date.isoformat()})" if a.due_date else ""
                open_actions.append(f"- [ ] {a.content}{due}  · 출처: {s.title}")
    if open_actions:
        lines += ["## 미해결 액션아이템 (전체)", *open_actions, ""]

    meetings = [s for s in project.sources if s.type == SourceType.MEETING]
    if meetings:
        lines.append("## 회의")
        for s in meetings:
            lines.append(f"### {s.title}  ({_fmt_date(s.created_at)})")
            if s.summary:
                lines.append(s.summary)
            d = _decisions_for(s)
            if d:
                lines.append("결정: " + "; ".join(d))
            lines.append("")

    notes = [s for s in project.sources if s.type == SourceType.NOTE]
    if notes:
        lines.append("## 메모")
        for s in notes:
            lines.append(f"### {s.title}")
            if s.summary:
                lines.append(s.summary)
            lines.append("")

    docs = [s for s in project.sources if s.type == SourceType.DOCUMENT]
    if docs:
        lines.append("## 참고 문서")
        lines += [f"- {s.title}: {s.body}" for s in docs]
        lines.append("")

    return "\n".join(lines).strip() + "\n"
