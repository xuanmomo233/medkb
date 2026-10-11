from pydantic import BaseModel


class ChapterBrief(BaseModel):
    id: int
    subject: str
    title: str


class QuestionChapter(BaseModel):
    name: str
    count: int


class QuestionSystem(BaseModel):
    name: str
    chapters: list[QuestionChapter]


class QuestionSubject(BaseModel):
    subject_dir: str
    systems: list[QuestionSystem]


class ContentTree(BaseModel):
    mindmaps: list[ChapterBrief]
    notes: list[ChapterBrief]
    question_tree: list[QuestionSubject]


class ChapterDetail(BaseModel):
    id: int
    title: str
    subject: str
    html: str
    meta: dict[str, str]
    pages: list[int]


class SearchHit(BaseModel):
    kind: str
    id: int
    title: str
    snippet: str
    state: str
    starred: bool
