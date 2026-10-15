from typing import Literal

from pydantic import BaseModel, Field, model_validator

CitationTarget = Literal["chapter", "question", "card"]
CitationStatus = Literal["unverified", "verified", "disputed"]


class TextbookSourceOut(BaseModel):
    key: str
    title: str
    subject: str
    publisher: str
    edition: str


class ContentCitationIn(BaseModel):
    source_key: str = Field(min_length=1, max_length=64)
    chapter: str = Field(default="", max_length=200)
    section: str = Field(default="", max_length=200)
    page_start: int | None = Field(default=None, ge=1)
    page_end: int | None = Field(default=None, ge=1)
    note: str = Field(default="", max_length=1000)
    status: CitationStatus = "unverified"

    @model_validator(mode="after")
    def validate_pages(self):
        if self.page_end is not None and self.page_start is None:
            raise ValueError("填写结束页时必须填写起始页")
        if self.page_end is not None and self.page_end < self.page_start:
            raise ValueError("结束页不能早于起始页")
        if self.status in ("verified", "disputed") and not (
            self.chapter.strip() or self.section.strip() or self.page_start is not None
        ):
            raise ValueError("已核验或争议出处必须填写教材章节、小节或页码")
        return self


class ContentCitationOut(ContentCitationIn):
    id: int
    title: str
    subject: str
    publisher: str
    edition: str
    verified_by: int | None = None
    verified_at: str | None = None


class ContentCitationBatch(BaseModel):
    citations: list[ContentCitationIn] = Field(default_factory=list, max_length=12)
