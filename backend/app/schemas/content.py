from pydantic import BaseModel


class ChapterBrief(BaseModel):
    id: int
    subject: str
    title: str


class QuestionChapterBrief(BaseModel):
    chapter: str
    subject_dir: str
    system: str


class ContentTree(BaseModel):
    mindmaps: list[ChapterBrief]
    notes: list[ChapterBrief]
    question_chapters: list[QuestionChapterBrief]


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
