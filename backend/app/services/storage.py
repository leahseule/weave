"""S3 파일 저장. presigned URL로 브라우저가 S3와 직접 업/다운로드 (서버 미경유)."""

import re
import uuid

import boto3
from botocore.config import Config

from app.config import settings

_PUT_EXPIRE = 300      # 업로드 URL 유효 5분
_GET_EXPIRE = 60 * 60  # 다운로드 URL 유효 1시간


class StorageError(Exception):
    """S3 관련 오류 (미설정, 서명 실패 등)."""


def is_configured() -> bool:
    return bool(
        settings.s3_bucket
        and settings.aws_access_key_id
        and settings.aws_secret_access_key
        and settings.aws_region
    )


def _client():
    if not is_configured():
        raise StorageError("S3가 설정되지 않았습니다.")
    return boto3.client(
        "s3",
        region_name=settings.aws_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        config=Config(signature_version="s3v4"),
    )


def _safe_name(name: str) -> str:
    name = (name or "file").replace("\\", "/").split("/")[-1]
    name = re.sub(r"[^\w.\-가-힣 ]", "_", name).strip() or "file"
    return name[:120]


def presign_put(filename: str, content_type: str) -> dict:
    """업로드용 presigned PUT URL + 저장 키를 발급."""
    key = f"uploads/{uuid.uuid4().hex}/{_safe_name(filename)}"
    url = _client().generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.s3_bucket,
            "Key": key,
            "ContentType": content_type or "application/octet-stream",
        },
        ExpiresIn=_PUT_EXPIRE,
    )
    return {"upload_url": url, "key": key}


def presign_get(key: str) -> str:
    """다운로드용 presigned GET URL을 발급."""
    return _client().generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=_GET_EXPIRE,
    )
