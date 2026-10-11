from pydantic import BaseModel


class AdminQuestion(BaseModel):
    id: int
    system: str
    analysis: str
    tags: list[str]


class AdminQuestionPatch(BaseModel):
    system: str | None = None
    analysis: str | None = None
    tags: list[str] | None = None


class ChangedOut(BaseModel):
    changed: int


class InviteOut(BaseModel):
    code: str
    created_by: int
    used_by: int | None
    used_at: str | None
    created_at: str | None


class InviteCreate(BaseModel):
    count: int = 1


class SiteConfigOut(BaseModel):
    exam_date: str


class SiteConfigPatch(BaseModel):
    exam_date: str | None = None
