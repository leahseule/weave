from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy.orm import Session

from app.config import settings
from app.models import DriveConnection

# 읽기 전용: 검색 + 파일 메타 접근
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_TOKEN_URI = "https://oauth2.googleapis.com/token"


class DriveError(Exception):
    """Drive 연동 관련 오류(미설정, 미연결, API 실패)."""


# 인증 요청 시 만든 PKCE code_verifier를 콜백까지 보관 (state → verifier).
# 싱글 유저·단일 프로세스라 메모리 보관으로 충분.
_pending: dict[str, str] = {}


def is_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def is_connected(db: Session, user_id: int) -> bool:
    return (
        db.query(DriveConnection).filter(DriveConnection.user_id == user_id).first()
        is not None
    )


def _flow() -> Flow:
    if not is_configured():
        raise DriveError("Google OAuth가 설정되지 않았습니다 (GOOGLE_CLIENT_ID/SECRET).")
    client_config = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": _TOKEN_URI,
            "redirect_uris": [settings.google_redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    return flow


def auth_url() -> str:
    flow = _flow()
    url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )
    _pending[state] = flow.code_verifier or ""
    return url


def exchange_code(db: Session, user_id: int, code: str, state: str | None = None) -> None:
    flow = _flow()
    verifier = _pending.pop(state, None) if state else None
    if verifier:
        flow.code_verifier = verifier
    flow.fetch_token(code=code)
    creds = flow.credentials
    conn = (
        db.query(DriveConnection).filter(DriveConnection.user_id == user_id).first()
    )
    if conn is None:
        conn = DriveConnection(
            user_id=user_id,
            access_token=creds.token,
            refresh_token=creds.refresh_token,
        )
        db.add(conn)
    else:
        conn.access_token = creds.token
        if creds.refresh_token:
            conn.refresh_token = creds.refresh_token
    db.commit()


def disconnect(db: Session, user_id: int) -> None:
    conn = (
        db.query(DriveConnection).filter(DriveConnection.user_id == user_id).first()
    )
    if conn:
        db.delete(conn)
        db.commit()


def _credentials(db: Session, user_id: int) -> Credentials:
    conn = (
        db.query(DriveConnection).filter(DriveConnection.user_id == user_id).first()
    )
    if conn is None:
        raise DriveError("Google Drive가 연결되지 않았습니다.")
    creds = Credentials(
        token=conn.access_token,
        refresh_token=conn.refresh_token,
        token_uri=_TOKEN_URI,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )
    if not creds.valid and creds.refresh_token:
        creds.refresh(Request())
        conn.access_token = creds.token
        db.commit()
    return creds


def search_query(db: Session, user_id: int, q: str, limit: int = 15) -> list[dict]:
    """사용자 자유 검색: 파일명 또는 내용에 q가 포함된 문서."""
    q = (q or "").strip().replace("'", "")
    if not q:
        return []
    creds = _credentials(db, user_id)
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    try:
        resp = (
            service.files()
            .list(
                q=f"(name contains '{q}' or fullText contains '{q}') and trashed = false",
                pageSize=limit,
                fields="files(id,name,webViewLink,mimeType,modifiedTime,iconLink)",
                spaces="drive",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise DriveError(f"Drive 검색 실패: {exc}") from exc
    return resp.get("files", [])


def search(db: Session, user_id: int, keywords: list[str], limit: int = 5) -> list[dict]:
    """키워드로 Drive 전체를 라이브 검색해 관련 문서 후보를 반환."""
    terms = [k.strip().replace("'", "") for k in keywords if k and k.strip()][:6]
    if not terms:
        return []

    creds = _credentials(db, user_id)
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    query = " or ".join(f"fullText contains '{t}'" for t in terms)
    try:
        resp = (
            service.files()
            .list(
                q=f"({query}) and trashed = false",
                pageSize=limit,
                fields="files(id,name,webViewLink,mimeType,modifiedTime)",
                spaces="drive",
                orderBy="modifiedTime desc",
            )
            .execute()
        )
    except Exception as exc:  # noqa: BLE001
        raise DriveError(f"Drive 검색 실패: {exc}") from exc
    return resp.get("files", [])
