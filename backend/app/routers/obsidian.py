from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.db import get_db
from app.models import User
from app.schemas import ObsidianConfig
from app.services import obsidian as obs

router = APIRouter(prefix="/obsidian", tags=["obsidian"])


@router.get("/status")
def status(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    return {
        "configured": obs.is_configured(db, user.id),
        "host_path": obs.host_path(db, user.id),
    }


@router.post("/config")
def set_config(
    payload: ObsidianConfig,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """볼트 경로를 입력받아 연결."""
    try:
        host = obs.set_vault(db, user.id, payload.path)
    except obs.ObsidianError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"configured": True, "host_path": host}


@router.delete("/config")
def clear_config(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    obs.clear_vault(db, user.id)
    return {"configured": False, "host_path": None}


@router.get("/recent")
def recent(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """검색 전 추천: 최근 수정순 노트."""
    try:
        return {"notes": obs.recent(db, user.id)}
    except obs.ObsidianError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/search")
def search(
    q: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """볼트에서 파일명·내용 검색 → 노트 후보."""
    try:
        return {"notes": obs.search(db, user.id, q)}
    except obs.ObsidianError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
