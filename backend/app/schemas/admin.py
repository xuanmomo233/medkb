from typing import Literal

from pydantic import BaseModel, Field


from app.schemas.provenance import ContentCitationIn, ContentCitationOut


class MarkdownPreviewIn(BaseModel):
    text: str = Field(max_length=20000)
    kind: Literal["markdown", "card"] = "markdown"


class MarkdownPreviewOut(BaseModel):
    html: str


class AdminQuestion(BaseModel):
    id: int
    subject_dir: str
    system: str
    stem: str
    options: list[str]
    answer: str
    analysis: str
    tags: list[str]
    citations: list[ContentCitationOut] = Field(default_factory=list)


class AdminQuestionPatch(BaseModel):
    system: str | None = None
    stem: str | None = None
    options: list[str] | None = Field(default=None, max_length=10)
    answer: str | None = Field(default=None, max_length=32)
    analysis: str | None = None
    tags: list[str] | None = None
    citations: list[ContentCitationIn] | None = Field(default=None, max_length=12)


class AdminCard(BaseModel):
    id: int
    subject: str
    part: str
    section: str
    term: str
    hint: str
    body: str
    citations: list[ContentCitationOut] = Field(default_factory=list)


class AdminCardPatch(BaseModel):
    section: str | None = None
    term: str | None = None
    hint: str | None = None
    body: str | None = None
    citations: list[ContentCitationIn] | None = Field(default=None, max_length=12)


class ChangedOut(BaseModel):
    changed: int


class InviteOut(BaseModel):
    code: str
    created_by: int
    used_by: int | None
    used_by_username: str | None
    used_at: str | None
    created_at: str | None


class InviteCreate(BaseModel):
    count: int = 1


class AdminUserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    created_at: str | None
    last_login_at: str | None
    invite_code: str | None


class AdminUserDelete(BaseModel):
    password: str


class SiteConfigOut(BaseModel):
    exam_date: str


class SiteConfigPatch(BaseModel):
    exam_date: str | None = None
