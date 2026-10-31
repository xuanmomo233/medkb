from pydantic import BaseModel


from app.schemas.provenance import ContentCitationOut, TextbookSourceOut
from pydantic import Field


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


class TextbookPageGallery(BaseModel):
    source_key: str
    title: str
    pages: list[int]


class ChapterDetail(BaseModel):
    id: int
    title: str
    subject: str
    html: str
    meta: dict[str, str]
    pages: list[int]
    citations: list[ContentCitationOut] = Field(default_factory=list)
    textbook_pages: list[TextbookPageGallery] = Field(default_factory=list)


class TextbookCatalog(BaseModel):
    sources: list[TextbookSourceOut]


class SearchHit(BaseModel):
    kind: str
    id: int
    title: str
    snippet: str
    state: str
    starred: bool
