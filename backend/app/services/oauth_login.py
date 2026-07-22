"""Google 로그인(OpenID Connect). Drive와 같은 OAuth 클라이언트를 재사용하되
scope는 openid/email/profile, 콜백은 google_auth_redirect_uri."""

from google.auth.transport import requests as g_requests
from google.oauth2 import id_token as g_id_token
from google_auth_oauthlib.flow import Flow

from app.config import settings

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]
_TOKEN_URI = "https://oauth2.googleapis.com/token"

# state → PKCE code_verifier (콜백까지 보관)
_pending: dict[str, str] = {}


class GoogleAuthError(Exception):
    """Google 로그인 오류(미설정, 토큰 실패 등)."""


def is_configured() -> bool:
    return bool(settings.google_client_id and settings.google_client_secret)


def _flow() -> Flow:
    if not is_configured():
        raise GoogleAuthError("Google OAuth가 설정되지 않았습니다.")
    cfg = {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": _TOKEN_URI,
            "redirect_uris": [settings.google_auth_redirect_uri],
        }
    }
    flow = Flow.from_client_config(cfg, scopes=SCOPES)
    flow.redirect_uri = settings.google_auth_redirect_uri
    return flow


def login_url() -> str:
    flow = _flow()
    url, state = flow.authorization_url(
        access_type="online",
        include_granted_scopes="true",
        prompt="select_account",
    )
    _pending[state] = flow.code_verifier or ""
    return url


def exchange(code: str, state: str | None = None) -> dict:
    """인증 코드 → 토큰 → ID 토큰 검증 → {email, name}."""
    flow = _flow()
    verifier = _pending.pop(state, None) if state else None
    if verifier:
        flow.code_verifier = verifier
    flow.fetch_token(code=code)
    raw_id = getattr(flow.credentials, "id_token", None)
    if not raw_id:
        raise GoogleAuthError("ID 토큰을 받지 못했습니다.")
    info = g_id_token.verify_oauth2_token(
        raw_id, g_requests.Request(), settings.google_client_id, clock_skew_in_seconds=10
    )
    email = (info.get("email") or "").strip().lower()
    if not email or not info.get("email_verified", False):
        raise GoogleAuthError("이메일을 확인할 수 없습니다.")
    return {"email": email, "name": info.get("name")}
