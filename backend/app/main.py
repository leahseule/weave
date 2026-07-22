from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.config import settings
from app.db import check_db
from app.routers import (
    auth,
    calendar,
    curation,
    drive,
    meetings,
    obsidian,
    projects,
    sources,
)

app = FastAPI(title="Weave API")

# 세션 쿠키(httpOnly, 서명됨). 로컬 http라 https_only=False.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    same_site="lax",
    https_only=settings.session_https_only,  # 운영(https)에서 True
    max_age=60 * 60 * 24 * 14,  # 2주
)


@app.middleware("http")
async def no_cache(request, call_next):
    """개발 편의: 브라우저가 정적 자산/응답을 캐싱해 stale 되지 않도록."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache"
    return response


app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(sources.router)
app.include_router(meetings.router)
app.include_router(curation.router)
app.include_router(calendar.router)
app.include_router(drive.router)
app.include_router(obsidian.router)


@app.get("/health")
def health():
    """Liveness + DB connectivity probe."""
    db_ok = check_db()
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}


# 프론트엔드(바닐라)를 FastAPI가 직접 서빙. API 라우트 뒤에 마운트해야
# /projects 등 API 경로가 정적파일보다 우선한다.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
