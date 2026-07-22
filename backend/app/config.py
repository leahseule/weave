from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, sourced from environment variables."""

    database_url: str = (
        "postgresql+psycopg2://weave:weave@localhost:5432/weave"
    )
    # 음성 전사(Whisper)에 필요. 없으면 음성 경로만 비활성, 나머지는 정상.
    openai_api_key: str | None = None

    # Google Drive OAuth (P4). 없으면 Drive 연동만 비활성.
    google_client_id: str | None = None
    google_client_secret: str | None = None
    google_redirect_uri: str = "http://localhost:8000/drive/callback"
    # Google 로그인(OpenID) 콜백. Drive와 같은 OAuth 클라이언트 재사용.
    google_auth_redirect_uri: str = "http://localhost:8000/auth/google/callback"

    # 옵시디언: 호스트 홈 폴더가 컨테이너 /host 에 마운트됨. host_home으로 경로 변환.
    host_home: str | None = None

    # 세션 쿠키 서명 키. 운영에서는 반드시 환경변수로 강력한 값 지정.
    secret_key: str = "dev-insecure-secret-change-me"
    # 운영(https)에서는 True로 → 쿠키를 https 전용(secure)으로. 로컬(http)은 False.
    session_https_only: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
