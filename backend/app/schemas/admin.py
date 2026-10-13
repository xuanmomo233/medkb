from pydantic import BaseModel


class AdminQuestion(BaseModel):
    id: int
    system: str
    stem: str
    analysis: str
    tags: list[str]


class AdminQuestionPatch(BaseModel):
    system: str | None = None
    stem: str | None = None
    analysis: str | None = None
    tags: list[str] | None = None


class AdminCard(BaseModel):
    id: int
    subject: str
    part: str
    section: str
    term: str
    hint: str
    body: str


class AdminCardPatch(BaseModel):
    section: str | None = None
    term: str | None = None
    hint: str | None = None
    body: str | None = None


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
