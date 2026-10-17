from pydantic import BaseModel, Field


from app.schemas.provenance import ContentCitationOut


class QuestionOut(BaseModel):
    id: int
    qid: str
    chapter: str
    system: str
    qtype: str
    stem_html: str
    parent_html: str
    case_group: str = ""
    case_index: int = 0
    case_total: int = 0
    options_html: list[str]
    answer: str
    analysis_html: str
    analysis_empty: bool
    tags: list[str]
    state: str
    starred: bool
    done: bool
    last_picked: str
    last_correct: bool | None


class QuestionStat(BaseModel):
    total: int
    correct: int
    dist: dict[str, int]


class RelatedCard(BaseModel):
    id: int
    term: str
    term_html: str
    hint: str
    body_html: str


class RelatedQuestion(BaseModel):
    id: int
    qid: str
    chapter: str
    qtype: str
    stem: str
    kind: str
    label: str
    reason: str
    in_plan: bool


class QuestionFull(BaseModel):
    id: int
    system: str
    stem_html: str
    answer: str
    analysis_html: str
    analysis_empty: bool
    related_cards: list[RelatedCard]
    stat: QuestionStat
    tags: list[str]
    state: str
    starred: bool
    citations: list[ContentCitationOut] = Field(default_factory=list)


class AiAnalysisOut(BaseModel):
    analysis_html: str


class AttemptIn(BaseModel):
    question_id: int
    picked: list[int] = Field(default_factory=list)


class AttemptResult(BaseModel):
    correct: bool | None
    answer: str
    stat: QuestionStat


class SubmitItem(BaseModel):
    question_id: int
    picked: list[int] = Field(default_factory=list)


class SubmitIn(BaseModel):
    title: str = ""
    items: list[SubmitItem] = Field(default_factory=list)


class ChapterScore(BaseModel):
    chapter: str
    total: int
    correct: int
    rate: int


class SubmitResult(BaseModel):
    question_id: int
    judged: bool
    correct: bool | None = None
    answer: str


class ExamReport(BaseModel):
    total: int
    correct: int
    score_100: int
    score_300: int
    wrong_ids: list[int]
    by_chapter: list[ChapterScore]
    results: list[SubmitResult]


class MockOut(BaseModel):
    ids: list[int]


class PoolItem(BaseModel):
    id: int
    qid: str
    stem: str
    answer: str
    source: str
    tags: list[str]
    state: str
    starred: bool
    in_plan: bool
    done: bool
    attempts: int
    wrong_count: int
    last_wrong_at: str | None


class PoolStats(BaseModel):
    total: int
    done: int
    wrong: int
    starred: int
    plan: int
    mastered: int


class PoolPage(BaseModel):
    stats: PoolStats
    items: list[PoolItem]


class WrongBookGroup(BaseModel):
    chapter: str
    count: int
    wrong_total: int
    last_wrong_at: str | None


class ExamRecord(BaseModel):
    id: int
    created_at: str
    title: str
    total: int
    correct: int
    rate: int
