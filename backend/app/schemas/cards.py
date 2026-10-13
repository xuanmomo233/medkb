from pydantic import BaseModel


class CardPartIndex(BaseModel):
    subject: str
    part: str
    count: int


class CardOut(BaseModel):
    id: int
    subject: str
    part: str
    section: str
    term: str
    term_html: str
    hint: str
    body_html: str
    state: str
    starred: bool


class SourceQuestion(BaseModel):
    id: int
    qid: str
    system: str
    stem_html: str
    answer: str
    analysis_html: str
