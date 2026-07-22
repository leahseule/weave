"""옵시디언 볼트 검색.

호스트 홈 폴더가 컨테이너의 /host 에 읽기전용으로 마운트된다.
사용자는 설정 UI에서 볼트의 (호스트) 절대경로를 입력하고, 여기서 그 경로를
컨테이너 내부 경로(/host/...)로 변환해 DB(settings)에 저장한다.
"""

from pathlib import Path

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Setting

_KEY_CONTAINER = "obsidian_vault"       # 변환된 컨테이너 경로 (/host/...)
_KEY_HOST = "obsidian_vault_host"       # 사용자가 입력한 원본 호스트 경로 (표시용)


class ObsidianError(Exception):
    """옵시디언 볼트 관련 오류(미설정, 경로 오류 등)."""


def _get(db: Session, user_id: int, key: str) -> str | None:
    s = db.get(Setting, (user_id, key))
    return s.value if s and s.value else None


def _set(db: Session, user_id: int, key: str, value: str) -> None:
    s = db.get(Setting, (user_id, key))
    if s is None:
        s = Setting(user_id=user_id, key=key)
        db.add(s)
    s.value = value


def _clean_path(raw: str) -> str:
    """탐색기 '경로로 복사'가 붙이는 따옴표·공백을 제거."""
    return (raw or "").strip().strip('"').strip("'").strip()


def _translate(host_path: str) -> str:
    """사용자가 입력한 호스트 경로 → 컨테이너 내부 경로(/host/...)."""
    home = settings.host_home
    if not home:
        raise ObsidianError("서버에 홈 폴더 마운트(HOST_HOME)가 설정되지 않았어요.")
    hp = _clean_path(host_path).replace("\\", "/").rstrip("/")
    hm = home.strip().replace("\\", "/").rstrip("/")
    if not hp:
        raise ObsidianError("볼트 경로를 입력하세요.")
    if not hp.lower().startswith(hm.lower()):
        raise ObsidianError(f"홈 폴더({home}) 안에 있는 볼트만 연결할 수 있어요.")
    rel = hp[len(hm):].lstrip("/")
    return f"/host/{rel}" if rel else "/host"


def _vault(db: Session, user_id: int) -> Path | None:
    cp = _get(db, user_id, _KEY_CONTAINER)
    return Path(cp) if cp else None


def is_configured(db: Session, user_id: int) -> bool:
    v = _vault(db, user_id)
    try:
        return v is not None and v.is_dir() and any(v.rglob("*.md"))
    except Exception:  # noqa: BLE001
        return False


def host_path(db: Session, user_id: int) -> str | None:
    """설정 화면 표시용: 사용자가 입력했던 원본 경로."""
    return _get(db, user_id, _KEY_HOST)


def set_vault(db: Session, user_id: int, raw_host_path: str) -> str:
    """볼트 경로 연결. 성공 시 저장하고 원본 호스트 경로를 반환."""
    container = _translate(raw_host_path)
    p = Path(container)
    if not p.is_dir():
        raise ObsidianError("그 경로에 폴더가 없어요. 볼트 폴더 경로가 정확한지 확인하세요.")
    try:
        has_md = any(p.rglob("*.md"))
    except Exception as exc:  # noqa: BLE001
        raise ObsidianError("폴더를 읽을 수 없어요.") from exc
    if not has_md:
        raise ObsidianError("그 폴더에서 .md 노트를 찾지 못했어요.")
    cleaned = _clean_path(raw_host_path)
    _set(db, user_id, _KEY_CONTAINER, container)
    _set(db, user_id, _KEY_HOST, cleaned)
    db.commit()
    return cleaned


def clear_vault(db: Session, user_id: int) -> None:
    for key in (_KEY_CONTAINER, _KEY_HOST):
        s = db.get(Setting, (user_id, key))
        if s is not None:
            db.delete(s)
    db.commit()


def _excerpt(text: str, q: str, radius: int = 70) -> str:
    low = text.lower()
    i = low.find(q.lower())
    if i < 0:
        return " ".join(text.split())[:140]
    start = max(0, i - radius)
    end = min(len(text), i + len(q) + radius)
    snippet = " ".join(text[start:end].split())
    return ("…" if start > 0 else "") + snippet + ("…" if end < len(text) else "")


def search(db: Session, user_id: int, query: str, limit: int = 25) -> list[dict]:
    """볼트의 .md 파일 중 파일명 또는 내용에 query가 포함된 것을 반환."""
    v = _vault(db, user_id)
    if v is None or not v.is_dir():
        raise ObsidianError("옵시디언 볼트가 연결되지 않았어요.")
    q = (query or "").strip().lower()
    if not q:
        return []
    out: list[dict] = []
    for p in v.rglob("*.md"):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            continue
        if q in p.stem.lower() or q in text.lower():
            out.append(
                {
                    "path": str(p.relative_to(v)).replace("\\", "/"),
                    "name": p.stem,
                    "excerpt": _excerpt(text, q),
                }
            )
            if len(out) >= limit:
                break
    return out


def _preview(text: str, length: int = 140) -> str:
    """검색어 없이 보여줄 노트 미리보기 (frontmatter 제거 후 앞부분)."""
    t = text
    if t.startswith("---"):
        end = t.find("\n---", 3)
        if end != -1:
            t = t[end + 4:]
    return " ".join(t.split())[:length]


def recent(db: Session, user_id: int, limit: int = 15) -> list[dict]:
    """최근 수정순 노트 목록 (검색 전 추천용)."""
    v = _vault(db, user_id)
    if v is None or not v.is_dir():
        raise ObsidianError("옵시디언 볼트가 연결되지 않았어요.")
    files: list[tuple[float, object]] = []
    for p in v.rglob("*.md"):
        try:
            files.append((p.stat().st_mtime, p))
        except Exception:  # noqa: BLE001
            continue
    files.sort(key=lambda x: x[0], reverse=True)
    out: list[dict] = []
    for _, p in files[:limit]:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:  # noqa: BLE001
            text = ""
        out.append({
            "path": str(p.relative_to(v)).replace("\\", "/"),
            "name": p.stem,
            "excerpt": _preview(text),
        })
    return out


def read_note(db: Session, user_id: int, rel_path: str) -> str:
    """볼트 내 상대경로의 노트 내용을 읽는다(경로 탈출 방지)."""
    v = _vault(db, user_id)
    if v is None:
        raise ObsidianError("옵시디언 볼트가 연결되지 않았어요.")
    v = v.resolve()
    p = (v / rel_path).resolve()
    if v != p and v not in p.parents:
        raise ObsidianError("잘못된 경로입니다.")
    if not p.is_file():
        raise ObsidianError("노트를 찾을 수 없어요.")
    return p.read_text(encoding="utf-8", errors="ignore")
