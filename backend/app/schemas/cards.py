from pydantic import BaseModel, Field


class RelatedCard(BaseModel):
    id: int
    term: str
    subject: str
    part: str
    reason: str


class OriginalCard(BaseModel):
    id: int
    term: str
    subject: str
    part: str
    section: str = ""
    hint: str = ""
    source_file: str
    body_html: str


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
    related_cards: list[RelatedCard] = Field(default_factory=list)
    original_cards: list[OriginalCard] = Field(default_factory=list)


class SourceQuestion(BaseModel):
    id: int
    qid: str
    system: str
    stem_html: str
    answer: str
    analysis_html: str
