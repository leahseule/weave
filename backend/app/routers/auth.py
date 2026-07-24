import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user, hash_password, verify_password
from app.db import get_db
from app.models import Project, ProjectMember, ProjectRole, User
from app.schemas import Credentials, UserOut
from app.services import oauth_login

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("weave.auth")


def _claim_orphans_if_first(db: Session, user: User) -> None:
    """첫 가입자는 소유자 없는 기존 프로젝트(테스트 데이터)를 인수 + OWNER 멤버 등록."""
    if db.query(User).count() == 1:
        orphans = db.query(Project).filter(Project.owner_id.is_(None)).all()
        for pr in orphans:
            pr.owner_id = user.id
            db.add(
                ProjectMember(
                    project_id=pr.id, user_id=user.id, role=ProjectRole.OWNER
                )
            )
        db.commit()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: Credentials, request: Request, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if "@" not in email or "." not in email.split("@")[-1]:
        raise HTTPException(status_code=400, detail="올바른 이메일을 입력하세요")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="이미 가입된 이메일이에요")

    user = User(email=email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    _claim_orphans_if_first(db, user)

    request.session["user_id"] = user.id
    return user


@router.get("/config")
def auth_config():
    """로그인 화면용 공개 설정 (Google 로그인 사용 가능 여부 등)."""
    return {"google": oauth_login.is_configured()}


@router.get("/google/login")
def google_login():
    """Google 동의 화면으로 리다이렉트."""
    try:
        return RedirectResponse(oauth_login.login_url())
    except oauth_login.GoogleAuthError:
        return RedirectResponse("/?auth=error")


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
):
    """Google 인증 콜백: 이메일로 사용자 찾거나 생성 후 세션 설정."""
    if error or not code:
        return RedirectResponse("/?auth=denied")
    try:
        info = oauth_login.exchange(code, state)
    except Exception:  # noqa: BLE001
        logger.exception("Google 로그인 콜백 교환 실패")  # 원인 추적용
        return RedirectResponse("/?auth=error")

    email = info["email"]
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        user = User(email=email, password_hash=None)
        db.add(user)
        db.commit()
        db.refresh(user)
        _claim_orphans_if_first(db, user)

    request.session["user_id"] = user.id
    return RedirectResponse("/")


@router.post("/login", response_model=UserOut)
def login(payload: Credentials, request: Request, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=401, detail="이메일 또는 비밀번호가 올바르지 않아요"
        )
    request.session["user_id"] = user.id
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request):
    request.session.clear()


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user
