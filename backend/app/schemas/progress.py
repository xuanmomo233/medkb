from typing import Literal

from pydantic import BaseModel

MarkAction = Literal[
    "star", "unstar", "plan", "unplan", "seen", "wrong", "unwrong", "master", "unmaster",
    "rate_again", "rate_hard", "rate_good",
]


class MarkBody(BaseModel):
    target_type: Literal["question", "card"]
    target_id: int
    action: MarkAction
