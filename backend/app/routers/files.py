from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.auth import get_current_user
from app.models import User
from app.schemas import PresignRequest
from app.services import storage

router = APIRouter(tags=["files"])


@router.get("/uploads/status")
def upload_status(user: User = Depends(get_current_user)):
    return {"configured": storage.is_configured()}


@router.post("/uploads/presign")
def presign_upload(
    payload: PresignRequest, user: User = Depends(get_current_user)
):
    """브라우저가 S3로 직접 올릴 presigned PUT URL을 발급."""
    if not storage.is_configured():
        raise HTTPException(status_code=400, detail="파일 업로드가 설정되지 않았어요.")
    try:
        return storage.presign_put(payload.filename, payload.content_type)
    except storage.StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/files/{key:path}")
def download_file(key: str, user: User = Depends(get_current_user)):
    """저장 키 → presigned GET URL로 리다이렉트 (임시 다운로드 링크)."""
    if not storage.is_configured():
        raise HTTPException(status_code=404, detail="Not found")
    try:
        return RedirectResponse(storage.presign_get(key))
    except storage.StorageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
