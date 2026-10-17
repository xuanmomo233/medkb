from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Classification(StrictModel):
    bank_group: str = Field(max_length=64)
    subject_dir: str = Field(max_length=32)
    system: str = Field(max_length=64)
    tags: list[str] = Field(default_factory=list, max_length=12)
    reason: str = Field(min_length=5, max_length=1200)


class Relation(StrictModel):
    question_id: int
    kind: Literal["variant", "same_concept", "contrast"]
    reason: str = Field(min_length=5, max_length=1200)


class EvidenceLink(StrictModel):
    id: int
    reason: str = Field(min_length=5, max_length=1200)


class Suggestion(StrictModel):
    _model: str = PrivateAttr(default="")
    classification: Classification | None = None
    relations: list[Relation] = Field(default_factory=list, max_length=12)
    cards: list[EvidenceLink] = Field(default_factory=list, max_length=12)
    citations: list[EvidenceLink] = Field(default_factory=list, max_length=12)
    warnings: list[str] = Field(default_factory=list, max_length=12)


class Decision(StrictModel):
    proposal_id: int
    proposal_hash: str
    action: Literal["publish", "reject"]
    fields: list[str] = Field(default_factory=list)
    accept_classification: bool = False
    classification_override: Classification | None = None
    acknowledge_conflicts: bool = False
    remember_classification: bool = False
    duplicate_of: int | None = None
    relation_ids: list[int] = Field(default_factory=list)
    card_ids: list[int] = Field(default_factory=list)
    citation_ids: list[int] = Field(default_factory=list)
    note: str = Field(min_length=1, max_length=2000)


class ReviewPlan(StrictModel):
    version: Literal[1] = 1
    decisions: list[Decision] = Field(min_length=1, max_length=500)
