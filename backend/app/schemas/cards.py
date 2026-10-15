from pydantic import BaseModel, Field


from app.schemas.provenance import ContentCitationOut


class RelatedCard(BaseModel):
    id: int
    term: str
    subject: str
    part: str
    reason: str


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
    citations: list[ContentCitationOut] = Field(default_factory=list)
