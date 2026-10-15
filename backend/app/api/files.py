import asyncio
import hashlib
import ipaddress
import re
import socket
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, Response

from app.core.config import get_settings
from app.api.deps import CurrentUser

router = APIRouter(tags=["files"])

IMG_HOSTS = ("ixunke.com", "ixunke.cn", "youjiangt.top")
_EXTS = (".png", ".jpg", ".webp", ".gif")
_IMG_MAX = 10 * 1024 * 1024
_PAGE = re.compile(r"page_\d+\.webp")
_UIMG = re.compile(r"[\w.-]+\.(png|jpe?g|webp|gif)")
_TEXTBOOK_SOURCE = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
_CACHE_HEADERS = {"Cache-Control": "public, max-age=2592000"}
_PRIVATE_HEADERS = {"Cache-Control": "private, no-store"}


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


@router.get("/api/textbook-images/{source_key}/{page}.webp")
async def textbook_image(source_key: str, page: int, user: CurrentUser):
    """已登录用户读取已发布、且有教材出处关联的页图。

    浏览器端以带 X-Token 的 fetch 读取，避免把教材图暴露为可匿名访问的静态 URL。
    """
    del user  # 依赖本身负责鉴权；所有已登录用户均可查看。
    if not _TEXTBOOK_SOURCE.fullmatch(source_key) or not 1 <= page <= 9999:
        raise HTTPException(404, "文件不存在")
    source_dir = Path(get_settings().textbook_img_dir) / source_key
    return FileResponse(
        _safe_file(str(source_dir), f"page_{page:04d}.webp"),
        media_type="image/webp",
        headers=_PRIVATE_HEADERS,
    )


@router.get("/uimg/{name}")
async def uimg(name: str):
    if not _UIMG.fullmatch(name):
        raise HTTPException(404, "文件不存在")
    return FileResponse(_safe_file(get_settings().upload_dir, name), headers=_CACHE_HEADERS)


def _host_ok(u: str) -> bool:
    """白名单域名校验 + DNS 必须解析到公网 IP（防内网/DNS 重绑定）。"""
    try:
        p = urlparse(u)
    except ValueError:
        return False
    h = (p.hostname or "").lower().rstrip(".")
    if p.scheme not in ("http", "https") or not any(h == d or h.endswith("." + d) for d in IMG_HOSTS):
        return False
    try:
        infos = socket.getaddrinfo(h, None)
        ips = [ipaddress.ip_address(a[4][0].split("%")[0]) for a in infos]
    except (OSError, ValueError):
        return False
    return bool(ips) and all(ip.is_global for ip in ips)


def _img_ext(data: bytes) -> str | None:
    """只认真实位图魔数；svg/html 等一律拒收。"""
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if data[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return ".gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None


async def _fetch_image(u: str) -> tuple[bytes, str]:
    """手动跟随重定向（每跳都做域名校验），流式读入并有体积上限。"""
    url = u
    if "ixunke.com" in (urlparse(u).hostname or ""):
        url += ("&" if "?" in u else "?") + "tads=1"
    try:
        async with httpx.AsyncClient(timeout=20, headers={"User-Agent": "Mozilla/5.0"}) as c:
            for _ in range(5):
                async with c.stream("GET", url, follow_redirects=False) as r:
                    if r.status_code in (301, 302, 303, 307, 308):
                        url = urljoin(url, r.headers.get("location") or "")
                        if not await asyncio.to_thread(_host_ok, url):
                            raise HTTPException(403, "不允许的图片来源")
                        continue
                    r.raise_for_status()
                    chunks, n = [], 0
                    async for chunk in r.aiter_bytes(65536):
                        n += len(chunk)
                        if n > _IMG_MAX:
                            raise HTTPException(413, "图片过大")
                        chunks.append(chunk)
                    data = b"".join(chunks)
                    ext = _img_ext(data)
                    if ext is None:
                        raise HTTPException(415, "非图片内容")
                    return data, ext
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "图片抓取失败")
    raise HTTPException(502, "图片抓取失败")


@router.get("/img_proxy")
async def img_proxy(u: str = Query("", max_length=2000)):
    if not await asyncio.to_thread(_host_ok, u):
        raise HTTPException(403, "不允许的图片来源")
    cache = Path(get_settings().img_cache_dir)
    h = hashlib.sha1(u.encode()).hexdigest()[:16]
    for e in _EXTS:
        fp = cache / (h + e)
        if fp.is_file():
            return FileResponse(fp, headers=_CACHE_HEADERS)
    data, ext = await _fetch_image(u)
    fp = cache / (h + ext)
    try:
        cache.mkdir(parents=True, exist_ok=True)
        tmp = fp.with_suffix(fp.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(fp)
    except OSError:
        pass
    return Response(data, media_type=_mime(ext), headers=_CACHE_HEADERS)


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
        ".gif": "image/gif",
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
