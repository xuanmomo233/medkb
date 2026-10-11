from datetime import datetime
from typing import Literal

from pydantic import BaseModel, field_validator


class NoteOut(BaseModel):
    id: int
    target_type: str
    target_id: int
    body: str
    is_public: bool
    created_at: datetime
    stem_preview: str | None = None


class PublicNoteOut(BaseModel):
    id: int
    body: str
    created_at: datetime
    username: str
    likes: int
    liked: bool
    mine: bool


class NoteCreate(BaseModel):
    target_type: Literal["question", "card"]
    target_id: int
    body: str
    is_public: bool = False

    @field_validator("body")
    @classmethod
    def _body(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("笔记内容不能为空")
        if len(v) > 5000:
            raise ValueError("笔记内容不能超过 5000 字")
        return v


class LikeOut(BaseModel):
    likes: int
    liked: bool
