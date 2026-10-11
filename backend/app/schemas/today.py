from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field


class PrefsOut(BaseModel):
    daily_goal: int
    exam_date: date | None
    weak_min_samples: int
    weak_max_rate: float


class PrefsUpdate(BaseModel):
    daily_goal: int | None = Field(default=None, ge=5, le=500)
    exam_date: date | None = None
    weak_min_samples: int | None = Field(default=None, ge=3, le=50)
    weak_max_rate: float | None = Field(default=None, ge=0.3, le=0.9)


class Counts(BaseModel):
    due: int
    wrong: int
    starred: int
    mastered: int


class TodaySummary(BaseModel):
    streak: int
    checked_in: bool
    daily_goal: int
    done_today: int
    exam_days_left: int | None
    exam_date: date | None
    counts: Counts


class CheckinOut(BaseModel):
    streak: int


class CalendarMonth(BaseModel):
    days: list[int]
    streak: int


class PlanOverviewDay(BaseModel):
    no: int
    title: str
    card_count: int


class PlanToday(BaseModel):
    start: date
    total_days: int
    today_no: int
    finished: bool
    title: str
    card_ids: list[int]
    question_ids: list[int]
    card_done: int
    question_done: int
    overview: list[PlanOverviewDay]


class PlanCardBrief(BaseModel):
    id: int
    term: str
    part: str


class PlanQuestionGroup(BaseModel):
    chapter: str
    ids: list[int]


class PlanDayDetail(BaseModel):
    no: int
    title: str
    cards: list[PlanCardBrief]
    question_groups: list[PlanQuestionGroup]


class WeakSpot(BaseModel):
    system: str
    chapter: str
    total: int
    correct: int
    rate: float
    last_attempt_at: datetime | None


class ScheduleItemOut(BaseModel):
    id: int
    item_type: Literal["question", "card"]
    item_id: int
    reason: Literal["due", "weak"]
    title: str
    done: bool


class ScheduleToday(BaseModel):
    day: date
    goal: int
    items: list[ScheduleItemOut]
    done_count: int


class SystemStat(BaseModel):
    system: str
    total: int
    correct: int
    rate: float


class DailyStat(BaseModel):
    day: date
    count: int
    correct: int


class StatsOverview(BaseModel):
    total_questions: int
    total_cards: int
    total_chapters: int
    attempted: int
    accuracy: float
    by_system: list[SystemStat]
    daily: list[DailyStat]
