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
