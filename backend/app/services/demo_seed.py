"""체험(데모) 계정과 샘플 데이터. OpenAI 호출 없이 하드코딩된 현실적 데이터를 심는다.

get_or_create_demo_user() 로 데모 계정을 만들고, reseed() 로 매 진입 시
샘플을 초기화해 누구나 항상 깔끔하게 채워진 앱을 둘러볼 수 있게 한다.
"""

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import (
    ActionItem,
    ContextItem,
    ContextKind,
    ContextStatus,
    MeetingOrigin,
    Project,
    ProjectMember,
    ProjectRole,
    Source,
    SourceType,
    User,
)

DEMO_EMAIL = "demo@weave.app"


def get_or_create_demo_user(db: Session) -> User:
    user = db.query(User).filter(User.email == DEMO_EMAIL).first()
    if user is None:
        user = User(email=DEMO_EMAIL, password_hash=None, is_demo=True)
        db.add(user)
        db.commit()
        db.refresh(user)
    elif not user.is_demo:
        user.is_demo = True
        db.commit()
    return user


def _project(db: Session, user: User, name: str, objective: str) -> Project:
    p = Project(name=name, objective=objective, owner_id=user.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    db.add(ProjectMember(project_id=p.id, user_id=user.id, role=ProjectRole.OWNER))
    db.commit()
    return p


def _meeting(db: Session, p: Project, **kw) -> Source:
    s = Source(project_id=p.id, type=SourceType.MEETING, origin=MeetingOrigin.AUDIO, **kw)
    db.add(s)
    db.commit()
    db.refresh(s)
    return s


def reseed(db: Session, user: User) -> None:
    """데모 계정의 기존 데이터를 지우고 샘플을 새로 심는다."""
    for p in db.query(Project).filter(Project.owner_id == user.id).all():
        db.delete(p)  # sources·context·members는 cascade로 정리
    db.commit()

    today = date.today()

    # ── 프로젝트 1: 신제품 앱 런칭 TF ───────────────────────────────
    p = _project(
        db, user, "신제품 앱 런칭 TF",
        "3분기 내 신규 모바일 앱을 출시하고 초기 사용자 1만 명을 확보한다.",
    )

    m1 = _meeting(
        db, p, title="킥오프 회의",
        attendees=["김지훈(PM)", "이서연(디자인)", "박민수(개발)"],
        keywords=["출시 일정", "베타 테스트", "온보딩"],
        summary=(
            "9월 3주차 정식 출시를 목표로 8월 중 베타 테스트를 진행하기로 했다. "
            "온보딩 플로우를 최우선으로 다듬고, 마케팅 예산은 베타 피드백 이후 확정한다."
        ),
        body=(
            "[00:00] 김지훈: 신제품 앱 킥오프 시작하겠습니다. 목표는 3분기 출시예요.\n"
            "[00:14] 이서연: 디자인은 8월 첫째 주까지 온보딩 화면 시안을 마무리할게요.\n"
            "[00:32] 박민수: 개발은 로그인·핵심 플로우를 먼저 붙이고 베타를 8월 중순에 열죠.\n"
            "[01:05] 김지훈: 좋아요. 정식 출시는 9월 3주차, 마케팅 예산은 베타 반응 보고 정합시다.\n"
            "[01:28] 이서연: 온보딩 이탈이 걱정이라 첫 3화면을 최대한 단순하게 갈게요.\n"
            "[01:50] 박민수: 베타 대상은 사내 50명 + 외부 신청자 200명으로 제안합니다."
        ),
    )
    db.add_all([
        ActionItem(source_id=m1.id, content="이서연: 온보딩 화면 시안 마무리", due_date=today + timedelta(days=5)),
        ActionItem(source_id=m1.id, content="박민수: 로그인·핵심 플로우 구현 후 베타 오픈", due_date=today + timedelta(days=12)),
        ActionItem(source_id=m1.id, content="김지훈: 베타 대상자 모집 공지", due_date=today + timedelta(days=3), done=True),
    ])
    db.add_all([
        ContextItem(project_id=p.id, kind=ContextKind.DECISION, source_id=m1.id, status=ContextStatus.ACCEPTED, content="정식 출시일은 9월 3주차로 확정"),
        ContextItem(project_id=p.id, kind=ContextKind.DECISION, source_id=m1.id, status=ContextStatus.ACCEPTED, content="마케팅 예산은 베타 피드백 이후 결정"),
    ])
    for kw in ["출시 일정", "베타 테스트", "온보딩"]:
        db.add(ContextItem(project_id=p.id, kind=ContextKind.TAG, source_id=m1.id, status=ContextStatus.ACCEPTED, content=kw))

    m2 = _meeting(
        db, p, title="베타 피드백 리뷰",
        attendees=["김지훈(PM)", "이서연(디자인)", "박민수(개발)"],
        keywords=["온보딩 이탈", "푸시 알림", "성능"],
        summary=(
            "베타 사용자 온보딩 3단계 이탈률이 높아 화면을 2단계로 축소하기로 했다. "
            "푸시 알림 동의 요청 시점을 뒤로 미루기로 결정."
        ),
        body=(
            "[00:00] 김지훈: 베타 결과 공유할게요. 가입은 잘 되는데 온보딩 3단계에서 40%가 이탈했어요.\n"
            "[00:20] 이서연: 3단계를 없애고 2단계로 줄이는 게 좋겠어요. 권한 요청도 너무 일러요.\n"
            "[00:44] 박민수: 푸시 동의는 실제 알림이 필요한 시점에 요청하도록 바꿀게요.\n"
            "[01:10] 김지훈: 좋습니다. 성능은요?\n"
            "[01:18] 박민수: 목록 스크롤이 버벅여서 이미지 로딩을 지연 처리로 개선하겠습니다."
        ),
    )
    db.add_all([
        ActionItem(source_id=m2.id, content="이서연: 온보딩 2단계로 축소 재설계", due_date=today + timedelta(days=7)),
        ActionItem(source_id=m2.id, content="박민수: 푸시 동의 시점 변경 + 이미지 지연 로딩", due_date=today + timedelta(days=9)),
    ])
    # 일부러 '제안' 상태로 두어 큐레이션(수락/거절)을 시연
    db.add(ContextItem(project_id=p.id, kind=ContextKind.DECISION, source_id=m2.id, status=ContextStatus.PROPOSED, content="온보딩을 3단계 → 2단계로 축소"))

    note = Source(
        project_id=p.id, type=SourceType.NOTE, origin=MeetingOrigin.PASTED,
        title="경쟁사 온보딩 리서치",
        keywords=["경쟁사", "온보딩", "레퍼런스"],
        summary="주요 경쟁 앱 3종의 온보딩은 모두 2~3단계로 짧고, 가치 제안을 첫 화면에서 바로 보여준다.",
        body=(
            "## 경쟁사 온보딩 정리\n"
            "- **A앱**: 2단계. 첫 화면에서 핵심 가치 1문장 + 바로 시작\n"
            "- **B앱**: 3단계지만 각 단계가 매우 짧음 (스킵 가능)\n"
            "- **C앱**: 소셜 로그인 우선, 권한 요청은 나중에\n\n"
            "> 시사점: 첫 화면에서 **가치 제안**을 명확히, 권한 요청은 뒤로 미루자."
        ),
    )
    db.add(note)

    db.add(Source(
        project_id=p.id, type=SourceType.DOCUMENT, origin=MeetingOrigin.PASTED,
        title="런칭 체크리스트 (Google Docs)",
        body="https://docs.google.com/document/d/EXAMPLE_LAUNCH_CHECKLIST/edit",
        note="출시 전 QA·스토어 심사·공지 항목 정리",
    ))

    # ── 프로젝트 2: 주간 팀 싱크 ───────────────────────────────────
    p2 = _project(db, user, "주간 팀 싱크", "매주 팀 진행 상황과 리스크를 공유한다.")
    w = _meeting(
        db, p2, title="8월 2주차 위클리",
        attendees=["팀 전체"],
        keywords=["진행상황", "리스크"],
        summary="대부분 일정대로 진행 중. 디자인 QA 리소스 부족이 유일한 리스크로 공유됨.",
        body=(
            "[00:00] 진행상황: 개발 70%, 디자인 80% 완료.\n"
            "[00:22] 리스크: 디자인 QA 인력이 부족해 다음 주 지원 요청.\n"
            "[00:40] 다음 주 목표: 베타 빌드 배포."
        ),
    )
    db.add(ActionItem(source_id=w.id, content="디자인 QA 지원 인력 요청", due_date=today + timedelta(days=2)))

    db.commit()
