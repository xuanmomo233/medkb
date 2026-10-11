from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import admin, auth, cards, chat, content, files, health, notes, progress, quiz, today
from app.core.db import dispose_engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await dispose_engine()


app = FastAPI(title="MedKB API", version="2.0.0", lifespan=lifespan)

for module in (health, auth, content, cards, quiz, progress, notes, today, chat, admin):
    app.include_router(module.router, prefix="/api")
app.include_router(files.router)