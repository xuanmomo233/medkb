from datetime import datetime, timedelta

MIN_EASE = 1.3


def rate(action: str, reps: int, ease: float, interval: float, now: datetime) -> tuple[int, float, float, datetime]:
    """返回 (reps, ease, interval_days, due_at)。action: rate_again|rate_hard|rate_good"""
    reps = reps or 0
    ease = ease or 2.5
    interval = interval or 0
    if action == "rate_again":
        reps, interval, ease = 0, 0.02, max(MIN_EASE, ease - 0.2)
    elif action == "rate_hard":
        reps += 1
        interval = 1.0 if interval < 0.5 else interval * 1.2
        ease = max(MIN_EASE, ease - 0.15)
    elif action == "rate_good":
        reps += 1
        if reps == 1:
            interval = 1.0
        elif reps == 2:
            interval = 3.0
        else:
            interval = max(interval, 1.0) * ease
        ease += 0.05
    else:
        raise ValueError(action)
    return reps, ease, interval, now + timedelta(days=interval)


def first_due(now: datetime) -> datetime:
    return now + timedelta(days=1)
