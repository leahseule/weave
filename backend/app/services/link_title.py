"""URL에서 페이지 제목(og:title 또는 <title>)을 가져온다. SSRF 방지 포함."""

import html as html_mod
import ipaddress
import re
import socket
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_UA = "Mozilla/5.0 (compatible; WeaveBot/1.0; +https://weaveapp.duckdns.org)"
_MAX_BYTES = 500_000
_TIMEOUT = 6


def _is_public_url(url: str) -> bool:
    """http(s)이고 호스트가 공인 IP로 해석되는지 검사 (내부/사설망 차단)."""
    try:
        p = urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    if p.scheme not in ("http", "https") or not p.hostname:
        return False
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or 80)
    except Exception:  # noqa: BLE001
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (
            ip.is_private or ip.is_loopback or ip.is_link_local
            or ip.is_reserved or ip.is_multicast or ip.is_unspecified
        ):
            return False
    return True


def fetch_page_title(url: str) -> str | None:
    """공인 URL이면 페이지를 가져와 제목을 반환. 실패하면 None."""
    if not _is_public_url(url):
        return None
    try:
        req = Request(url, headers={"User-Agent": _UA})
        with urlopen(req, timeout=_TIMEOUT) as resp:  # noqa: S310 — 위에서 스킴/IP 검증
            ctype = resp.headers.get("Content-Type", "")
            if "html" not in ctype.lower():
                return None
            raw = resp.read(_MAX_BYTES)
    except Exception:  # noqa: BLE001
        return None

    text = raw.decode("utf-8", errors="ignore")
    # og:title 우선, 없으면 <title>
    m = re.search(
        r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
        text, re.I,
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:title["\']',
        text, re.I,
    ) or re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
    if not m:
        return None
    title = re.sub(r"\s+", " ", html_mod.unescape(m.group(1))).strip()
    return title[:300] or None
