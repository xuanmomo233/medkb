import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from app.core.config import get_settings

router = APIRouter(tags=["files"])

IMG_HOSTS = ("ixunke.com", "ixunke.cn", "youjiangt.top")
_EXTS = (".png", ".jpg", ".webp", ".gif", ".svg")
_PAGE = re.compile(r"page_\d+\.webp")
_UIMG = re.compile(r"[\w.-]+\.(png|jpe?g|webp|gif)")
_CACHE_HEADERS = {"Cache-Control": "public, max-age=2592000"}


def _safe_file(base: str, name: str) -> Path:
    root = Path(base).resolve()
    fp = (root / name).resolve()
    if fp.parent != root or not fp.is_file():
        raise HTTPException(404, "文件不存在")
    return fp


@router.get("/img/{name}")
async def img(name: str):
    if not _PAGE.fullmatch(name):
        raise HTTPException(404, "文件不存在")
    return FileResponse(_safe_file(get_settings().img_dir, name), media_type="image/webp", headers=_CACHE_HEADERS)


@router.get("/uimg/{name}")
async def uimg(name: str):
    if not _UIMG.fullmatch(name):
        raise HTTPException(404, "文件不存在")
    return FileResponse(_safe_file(get_settings().upload_dir, name), headers=_CACHE_HEADERS)


def _host_ok(u: str) -> bool:
    try:
        p = urlparse(u)
    except ValueError:
        return False
    h = (p.hostname or "").lower()
    return p.scheme in ("http", "https") and any(h == d or h.endswith("." + d) for d in IMG_HOSTS)


def _ext(data: bytes, u: str) -> str:
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    if data[:5].lower().startswith(b"<svg") or b"<svg" in data[:200]:
        return ".svg"
    low = u.lower()
    for e in (".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"):
        if e in low:
            return ".jpg" if e == ".jpeg" else e
    return ".jpg"


@router.get("/img_proxy")
async def img_proxy(u: str = Query("", max_length=2000)):
    if not _host_ok(u):
        raise HTTPException(403, "不允许的图片来源")
    cache = Path(get_settings().img_cache_dir)
    h = hashlib.sha1(u.encode()).hexdigest()[:16]
    for e in _EXTS:
        fp = cache / (h + e)
        if fp.is_file():
            return FileResponse(fp, headers=_CACHE_HEADERS)
    url = u
    if "ixunke.com" in (urlparse(u).hostname or ""):
        url += ("&" if "?" in u else "?") + "tads=1"
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"}) as c:
            r = await c.get(url)
            r.raise_for_status()
            data = r.content
    except Exception:
        raise HTTPException(502, "图片抓取失败")
    if data[:1] == b"<" and b"<svg" not in data[:200].lower():
        return Response(data, media_type="text/html")
    fp = cache / (h + _ext(data, u))
    try:
        cache.mkdir(parents=True, exist_ok=True)
        tmp = fp.with_suffix(fp.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(fp)
    except OSError:
        return Response(data, media_type=_mime(fp.suffix))
    return FileResponse(fp, headers=_CACHE_HEADERS)


@router.get("/app.apk")
async def app_apk():
    fp = Path(get_settings().img_dir).parent / "app-release.apk"
    if not fp.is_file():
        raise HTTPException(404, "暂无更新包")
    return FileResponse(fp, media_type="application/vnd.android.package-archive",
                        filename="medkb.apk", headers={"Cache-Control": "no-cache"})


def _mime(ext: str) -> str:
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp",
        ".gif": "image/gif", ".svg": "image/svg+xml",
    }.get(ext, "application/octet-stream")


@router.get("/{path:path}", include_in_schema=False)
async def spa(path: str):
    if path == "api" or path.startswith("api/"):
        raise HTTPException(404, "Not Found")
    root = Path(get_settings().web_dist_dir)
    if not root.is_dir():
        raise HTTPException(404, "Not Found")
    root = root.resolve()
    if path:
        fp = (root / path).resolve()
        if fp.is_file() and root in fp.parents:
            return FileResponse(fp)
    index = root / "index.html"
    if index.is_file():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    raise HTTPException(404, "Not Found")
