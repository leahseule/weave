import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import ContextItem, ContextKind, User
from app.services import drive as drive_svc

router = APIRouter(prefix="/drive", tags=["drive"])
logger = logging.getLogger("weave.drive")


@router.get("/search")
def search(
    q: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """Drive 자유 검색 → 후보 문서 목록."""
    try:
        return {"files": drive_svc.search_query(db, user.id, q)}
    except drive_svc.DriveError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/recommend")
def recommend(
    project_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """프로젝트 태그를 키워드로 Drive를 검색해 추천 문서를 반환(검색 전 미리보기)."""
    tags = [
        ci.content
        for ci in db.query(ContextItem)
        .filter(
            ContextItem.project_id == project_id,
            ContextItem.kind == ContextKind.TAG,
        )
        .all()
    ]
    if not tags:
        return {"files": [], "tags": []}
    try:
        return {"files": drive_svc.search(db, user.id, tags, limit=15), "tags": tags}
    except drive_svc.DriveError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/status")
def status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return {
        "configured": drive_svc.is_configured(),
        "connected": drive_svc.is_connected(db, user.id),
    }


@router.get("/connect")
def connect(user: User = Depends(get_current_user)):
    """Google 동의 화면으로 리다이렉트."""
    try:
        return RedirectResponse(drive_svc.auth_url())
    except drive_svc.DriveError:
        return RedirectResponse("/?drive=error")


@router.get("/callback")
def callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Google이 인증 후 되돌려보내는 콜백. code를 토큰으로 교환해 저장."""
    if error or not code:
        return RedirectResponse("/?drive=denied")
    try:
        drive_svc.exchange_code(db, user.id, code, state)
    except Exception:  # noqa: BLE001
        logger.exception("Drive OAuth 콜백 실패")
        return RedirectResponse("/?drive=error")
    return RedirectResponse("/?drive=connected")


@router.delete("/disconnect")
def disconnect(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    drive_svc.disconnect(db, user.id)
    return {"connected": False}
