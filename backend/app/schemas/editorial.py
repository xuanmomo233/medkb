from typing import Literal

from pydantic import BaseModel, Field

ReviewStatus = Literal["pending", "approved", "rejected", "needs_revision"]


class ReviewDecisionIn(BaseModel):
    status: ReviewStatus
    note: str = Field(default="", max_length=4000)
    expected_version: int = Field(ge=0)
