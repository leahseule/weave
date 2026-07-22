from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings


def _normalize_db_url(url: str) -> str:
    """Render 등은 postgres://·postgresql:// 형식을 주므로 psycopg2 드라이버로 통일."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg2://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg2://" + url[len("postgresql://"):]
    return url


engine = create_engine(_normalize_db_url(settings.database_url), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 의존성: 요청 하나당 세션 하나."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db() -> bool:
    """Return True if a trivial query against Postgres succeeds."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
