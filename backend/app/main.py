import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api import admin, auth, cards, chat, content, files, health, notes, progress, quiz, today
from app.core.db import dispose_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await dispose_engine()


_EXPOSE_DOCS = os.environ.get("MEDKB_EXPOSE_DOCS", "").lower() in ("1", "true", "yes")

app = FastAPI(
    title="MedKB API",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/docs" if _EXPOSE_DOCS else None,
    redoc_url="/redoc" if _EXPOSE_DOCS else None,
    openapi_url="/openapi.json" if _EXPOSE_DOCS else None,
)

_SEC_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; "
        "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    ),
}


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    for k, v in _SEC_HEADERS.items():
        resp.headers.setdefault(k, v)
    return resp


for module in (health, auth, content, cards, quiz, progress, notes, today, chat, admin):
    app.include_router(module.router, prefix="/api")
app.include_router(files.router)