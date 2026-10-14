import calendar as _cal
import re
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import case, delete, func, select, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Attempt,
    Card,
    CardProgress,
    CardQuestion,
    Chapter,
    Checkin,
    Question,
    QuestionProgress,
    ScheduleItem,
    SiteConfig,
    User,
    UserPlan,
    UserPlanItem,
    UserPrefs,
)
from app.services.card_merges import original_ids, redirects, resolve, visible

DEFAULT_EXAM_DATE = date(2026, 12, 19)


async def get_exam_date(session: AsyncSession) -> date | None:
    """考研日期：站点级统一设置，未设置时用默认 2026-12-19。"""
    row = (await session.execute(select(SiteConfig.value).where(SiteConfig.key == "exam_date"))).first()
    if row and row[0]:
        try:
            return date.fromisoformat(row[0])
        except ValueError:
            pass
    return DEFAULT_EXAM_DATE


async def set_exam_date(session: AsyncSession, value: str | None) -> date:
    row = await session.get(SiteConfig, "exam_date")
    if value:
        d = date.fromisoformat(value)
        if row is None:
            session.add(SiteConfig(key="exam_date", value=d.isoformat()))
        else:
            row.value = d.isoformat()
        await session.commit()
        return d
    if row is not None:
        await session.delete(row)
        await session.commit()
    return DEFAULT_EXAM_DATE

try:
    from zoneinfo import ZoneInfo

    LOCAL_TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    LOCAL_TZ = timezone(timedelta(hours=8))

SUBJECT_DIR = {
    "生理学": "01-生理学",
    "生物化学": "02-生物化学",
    "病理学": "03-病理学",
    "诊断学": "04-诊断学",
    "内科学": "05-内科学",
    "外科学": "06-外科学",
    "医学人文": "07-医学人文",
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def local_today() -> date:
    return datetime.now(LOCAL_TZ).date()


def day_start_utc(d: date) -> datetime:
    return datetime.combine(d, time.min, tzinfo=LOCAL_TZ).astimezone(timezone.utc)


def to_local_day(dt: datetime) -> date:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ).date()


def _rate(correct: int, total: int) -> float:
    return round(correct / total, 4) if total else 0.0


# ---------------- prefs ----------------
async def get_prefs(session: AsyncSession, user_id: int) -> UserPrefs:
    prefs = await session.get(UserPrefs, user_id)
    if prefs is None:
        prefs = UserPrefs(user_id=user_id, daily_goal=30, weak_min_samples=10, weak_max_rate=0.6)
        session.add(prefs)
        await session.commit()
    return prefs


async def update_prefs(session: AsyncSession, user_id: int, data: dict) -> UserPrefs:
    prefs = await get_prefs(session, user_id)
    for k, v in data.items():
        if k == "exam_date":
            continue  # exam_date 改为站点级，管理员在后台统一设置
        if v is not None:
            setattr(prefs, k, v)
    await session.commit()
    return prefs


async def prefs_out(session: AsyncSession, user_id: int) -> dict:
    prefs = await get_prefs(session, user_id)
    return {
        "daily_goal": prefs.daily_goal,
        "exam_date": await get_exam_date(session),
        "weak_min_samples": prefs.weak_min_samples,
        "weak_max_rate": prefs.weak_max_rate,
    }


# ---------------- checkin ----------------
def _streak(days: set[date], today: date) -> int:
    cur = today if today in days else today - timedelta(days=1)
    n = 0
    while cur in days:
        n += 1
        cur -= timedelta(days=1)
    return n


async def _checkin_days(session: AsyncSession, user_id: int) -> set[date]:
    rows = await session.execute(select(Checkin.day).where(Checkin.user_id == user_id))
    return {r[0] for r in rows}


async def do_checkin(session: AsyncSession, user_id: int) -> int:
    today = local_today()
    days = await _checkin_days(session, user_id)
    if today not in days:
        session.add(Checkin(user_id=user_id, day=today, created_at=utcnow()))
        await session.commit()
        days.add(today)
    return _streak(days, today)


async def calendar_month(session: AsyncSession, user_id: int, month: str) -> dict:
    m = re.fullmatch(r"(\d{4})-(\d{2})", month or "")
    if not m or not 1 <= int(m.group(2)) <= 12:
        raise HTTPException(400, "month 格式应为 YYYY-MM")
    y, mo = int(m.group(1)), int(m.group(2))
    days = await _checkin_days(session, user_id)
    in_month = sorted(d.day for d in days if d.year == y and d.month == mo and d.day <= _cal.monthrange(y, mo)[1])
    return {"days": in_month, "streak": _streak(days, local_today())}


# ---------------- today ----------------
async def _flag_counts(session: AsyncSession, model, user_id: int, now: datetime) -> tuple[int, int, int, int]:
    row = (
        await session.execute(
            select(
                func.coalesce(func.sum(case((model.in_plan.is_(True) & (model.due_at <= now), 1), else_=0)), 0),
                func.coalesce(func.sum(case((model.in_wrongbook.is_(True), 1), else_=0)), 0),
                func.coalesce(func.sum(case((model.starred.is_(True), 1), else_=0)), 0),
                func.coalesce(func.sum(case((model.mastered.is_(True), 1), else_=0)), 0),
            ).where(model.user_id == user_id,
                    visible(model.card_id) if model is CardProgress else True)
        )
    ).one()
    return tuple(int(x) for x in row)


async def _count_seen_since(session: AsyncSession, model, user_id: int, since: datetime) -> int:
    return int(
        (
            await session.execute(
                select(func.count()).select_from(model).where(
                    model.user_id == user_id, model.last_seen_at >= since,
                    visible(model.card_id) if model is CardProgress else True,
                )
            )
        ).scalar_one()
    )


async def today_summary(session: AsyncSession, user: User) -> dict:
    prefs = await get_prefs(session, user.id)
    today = local_today()
    now = utcnow()
    since = day_start_utc(today)
    days = await _checkin_days(session, user.id)
    q = await _flag_counts(session, QuestionProgress, user.id, now)
    c = await _flag_counts(session, CardProgress, user.id, now)
    done = await _count_seen_since(session, QuestionProgress, user.id, since) + await _count_seen_since(
        session, CardProgress, user.id, since
    )
    exam = await get_exam_date(session)
    left = (exam - today).days if exam else None
    return {
        "streak": _streak(days, today),
        "checked_in": today in days,
        "daily_goal": prefs.daily_goal,
        "done_today": done,
        "exam_days_left": max(left, 0) if left is not None else None,
        "exam_date": exam,
        "counts": {"due": q[0] + c[0], "wrong": q[1] + c[1], "starred": q[2] + c[2], "mastered": q[3] + c[3]},
    }


# ---------------- plan ----------------
async def _plan_items(session: AsyncSession, user_id: int) -> list[UserPlanItem]:
    return (
        await session.execute(
            select(UserPlanItem).where(UserPlanItem.user_id == user_id).order_by(UserPlanItem.ord, UserPlanItem.id)
        )
    ).scalars().all()


def _item_key(subject: str, part: str) -> str:
    return f"{subject}|{part}"


async def _item_content(session: AsyncSession, items: list[UserPlanItem]) -> dict[str, tuple[list[int], list[int]]]:
    """每个 (subject,part) 项的卡片 id 与经卡片关联的题目 id。"""
    if not items:
        return {}
    keys = {(i.subject, i.part) for i in items}
    pair = tuple_(Card.subject, Card.part).in_(keys)
    crows = (await session.execute(select(Card.subject, Card.part, Card.id).where(pair, visible()))).all()
    dirs = {SUBJECT_DIR[s] for s, _ in keys if s in SUBJECT_DIR}
    qrows = (
        (
            await session.execute(
                select(Card.subject, Card.part, Question.id)
                .join(CardQuestion, CardQuestion.card_id == Card.id)
                .join(Question, Question.id == CardQuestion.question_id)
                .where(pair, visible(), Question.subject_dir.in_(dirs))
                .distinct()
            )
        ).all()
        if dirs
        else []
    )
    out: dict[str, tuple[list[int], list[int]]] = {_item_key(s, p): ([], []) for s, p in keys}
    for s, p, cid in crows:
        out[_item_key(s, p)][0].append(cid)
    for s, p, qid in qrows:
        out[_item_key(s, p)][1].append(qid)
    return out


async def _item_done_counts(
    session: AsyncSession, user_id: int, card_ids: list[int], q_ids: list[int], since: datetime
) -> tuple[int, int]:
    cdone = qdone = 0
    if card_ids:
        cdone = int(
            (
                await session.execute(
                    select(func.count()).select_from(CardProgress).where(
                        CardProgress.user_id == user_id,
                        CardProgress.card_id.in_(card_ids),
                        CardProgress.last_seen_at >= since,
                    )
                )
            ).scalar_one()
        )
    if q_ids:
        qdone = int(
            (
                await session.execute(
                    select(func.count()).select_from(QuestionProgress).where(
                        QuestionProgress.user_id == user_id,
                        QuestionProgress.question_id.in_(q_ids),
                        QuestionProgress.last_seen_at >= since,
                    )
                )
            ).scalar_one()
        )
    return cdone, qdone


async def _plan_state(session: AsyncSession, user_id: int) -> dict | None:
    plan = await session.get(UserPlan, user_id)
    items = await _plan_items(session, user_id)
    if plan is None or not items:
        return None
    today = local_today()
    elapsed = (today - plan.start_day).days
    days_left = max(1, plan.total_days - elapsed)
    since = day_start_utc(plan.start_day)
    content = await _item_content(session, items)
    out_items = []
    for it in items:
        key = _item_key(it.subject, it.part)
        cids, qids = content.get(key, ([], []))
        cdone, qdone = await _item_done_counts(session, user_id, cids, qids, since)
        done = cdone >= len(cids) and qdone >= len(qids)
        out_items.append({
            "key": key,
            "subject": it.subject,
            "part": it.part,
            "label": f"{it.subject} · {it.part}",
            "cards": len(cids),
            "card_done": cdone,
            "questions": len(qids),
            "question_done": qdone,
            "done": done,
            "day": None,
        })
    remaining = [i for i in out_items if not i["done"]]
    batch = -(-len(remaining) // days_left) if remaining else 0
    for idx, i in enumerate(remaining):
        i["day"] = idx // batch + 1
    return {
        "plan": plan,
        "elapsed": elapsed,
        "days_left": days_left,
        "items": out_items,
        "today_items": [i for i in remaining if i["day"] == 1],
        "remaining": len(remaining),
        "finished": not remaining or elapsed >= plan.total_days,
    }


async def plan_today(session: AsyncSession, user_id: int) -> dict:
    st = await _plan_state(session, user_id)
    if st is None:
        return {"configured": False}
    plan = st["plan"]
    return {
        "configured": True,
        "start": plan.start_day,
        "total_days": plan.total_days,
        "day_no": st["elapsed"] + 1,
        "days_left": st["days_left"],
        "remaining": st["remaining"],
        "finished": st["finished"],
        "today_items": st["today_items"],
        "items": st["items"],
    }


async def plan_options(session: AsyncSession) -> list[dict]:
    crows = (
        await session.execute(
            select(Card.subject, Card.part, func.count(Card.id)).where(visible()).group_by(Card.subject, Card.part)
        )
    ).all()
    qcounts = {
        (s, p): int(n)
        for s, p, n in (
            await session.execute(
                select(Card.subject, Card.part, func.count(func.distinct(CardQuestion.question_id)))
                .join(CardQuestion, CardQuestion.card_id == Card.id)
                .where(visible())
                .group_by(Card.subject, Card.part)
            )
        ).all()
    }
    by_subj: dict[str, list[dict]] = defaultdict(list)
    for s, p, n in crows:
        by_subj[s].append({"part": p, "cards": int(n), "questions": qcounts.get((s, p), 0)})
    for parts in by_subj.values():
        parts.sort(key=lambda x: x["part"])
    return [{"subject": s, "parts": by_subj[s]} for s in sorted(by_subj)]


async def set_plan(session: AsyncSession, user_id: int, items: list[tuple[str, str]], total_days: int) -> None:
    await session.execute(delete(UserPlanItem).where(UserPlanItem.user_id == user_id))
    for i, (subject, part) in enumerate(items):
        session.add(UserPlanItem(user_id=user_id, subject=subject, part=part, ord=i))
    plan = await session.get(UserPlan, user_id)
    if plan is None:
        session.add(UserPlan(user_id=user_id, start_day=local_today(), total_days=total_days))
    else:
        plan.start_day = local_today()
        plan.total_days = total_days
    await session.commit()


async def clear_plan(session: AsyncSession, user_id: int) -> None:
    await session.execute(delete(UserPlanItem).where(UserPlanItem.user_id == user_id))
    await session.execute(delete(UserPlan).where(UserPlan.user_id == user_id))
    await session.commit()


async def plan_day_parts(session: AsyncSession, user_id: int, day_no: int) -> list[tuple[str, str]]:
    """相对第 day_no 天（1=今天批次）应学的 (subject,part)。"""
    st = await _plan_state(session, user_id)
    if st is None:
        return []
    return [
        (i["subject"], i["part"])
        for i in st["items"]
        if i["day"] == day_no
    ]


async def _parts_card_rows(session: AsyncSession, parts: list[tuple[str, str]]) -> list[tuple[int, str, str]]:
    if not parts:
        return []
    rows = await session.execute(
        select(Card.id, Card.term, Card.part)
        .where(visible(), tuple_(Card.subject, Card.part).in_(parts))
        .order_by(Card.id)
    )
    return [tuple(r) for r in rows]


async def _parts_question_rows(session: AsyncSession, parts: list[tuple[str, str]]) -> list[tuple[int, str]]:
    if not parts:
        return []
    dirs = {SUBJECT_DIR[s] for s, _ in parts if s in SUBJECT_DIR}
    if not dirs:
        return []
    rows = await session.execute(
        select(Question.id, Question.chapter)
        .join(CardQuestion, CardQuestion.question_id == Question.id)
        .join(Card, Card.id == CardQuestion.card_id)
        .where(tuple_(Card.subject, Card.part).in_(parts), Question.subject_dir.in_(dirs), visible())
        .distinct()
        .order_by(Question.id)
    )
    return [tuple(r) for r in rows]


async def plan_day_detail(session: AsyncSession, user_id: int, n: int) -> dict:
    parts = await plan_day_parts(session, user_id, n)
    if not parts:
        raise HTTPException(404, "这一天没有计划内容")
    cards = [{"id": i, "term": t, "part": p} for i, t, p in await _parts_card_rows(session, parts)]
    groups: dict[str, list[int]] = defaultdict(list)
    for qid, ch in await _parts_question_rows(session, parts):
        groups[ch].append(qid)
    return {
        "no": n,
        "title": "、".join(p for _, p in parts),
        "cards": cards,
        "question_groups": [{"chapter": ch, "ids": ids} for ch, ids in groups.items()],
    }


async def plan_restart(session: AsyncSession, user_id: int) -> None:
    plan = await session.get(UserPlan, user_id)
    if plan is None:
        return
    plan.start_day = local_today()
    await session.commit()


# ---------------- stats ----------------
async def stats_overview(session: AsyncSession, user_id: int) -> dict:
    async def count(model) -> int:
        return int((await session.execute(select(func.count()).select_from(model))).scalar_one())

    correct_expr = func.coalesce(func.sum(case((Attempt.is_correct.is_(True), 1), else_=0)), 0)
    total_a, correct_a, attempted = (
        await session.execute(
            select(func.count(), correct_expr, func.count(func.distinct(Attempt.question_id))).where(
                Attempt.user_id == user_id
            )
        )
    ).one()
    by_sys_rows = (
        await session.execute(
            select(Question.system, func.count(), correct_expr)
            .join(Question, Question.id == Attempt.question_id)
            .where(Attempt.user_id == user_id)
            .group_by(Question.system)
            .order_by(Question.system)
        )
    ).all()
    today = local_today()
    first = today - timedelta(days=29)
    rows = (
        await session.execute(
            select(Attempt.created_at, Attempt.is_correct).where(
                Attempt.user_id == user_id, Attempt.created_at >= day_start_utc(first)
            )
        )
    ).all()
    buckets: dict[date, list[int]] = {first + timedelta(days=i): [0, 0] for i in range(30)}
    for ts, ok in rows:
        d = to_local_day(ts)
        if d in buckets:
            buckets[d][0] += 1
            buckets[d][1] += 1 if ok else 0
    return {
        "total_questions": await count(Question),
        "total_cards": await count(Card),
        "total_chapters": await count(Chapter),
        "attempted": int(attempted),
        "accuracy": _rate(int(correct_a), int(total_a)),
        "by_system": [
            {"system": s, "total": int(t), "correct": int(c), "rate": _rate(int(c), int(t))} for s, t, c in by_sys_rows
        ],
        "daily": [{"day": d, "count": v[0], "correct": v[1]} for d, v in sorted(buckets.items())],
    }


async def weak_spots(session: AsyncSession, user_id: int, prefs: UserPrefs | None = None) -> list[dict]:
    prefs = prefs or await get_prefs(session, user_id)
    correct_expr = func.coalesce(func.sum(case((Attempt.is_correct.is_(True), 1), else_=0)), 0)
    rows = (
        await session.execute(
            select(Question.system, Question.chapter, func.count(), correct_expr, func.max(Attempt.created_at))
            .join(Question, Question.id == Attempt.question_id)
            .where(Attempt.user_id == user_id)
            .group_by(Question.system, Question.chapter)
        )
    ).all()
    out = []
    for system, chapter, total, correct, last in rows:
        total, correct = int(total), int(correct)
        rate = _rate(correct, total)
        if total >= prefs.weak_min_samples and rate < prefs.weak_max_rate:
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            out.append(
                {"system": system, "chapter": chapter, "total": total, "correct": correct, "rate": rate,
                 "last_attempt_at": last}
            )
    out.sort(key=lambda x: (x["rate"], -x["total"]))
    return out


# ---------------- schedule ----------------
_TAG_RE = re.compile(r"<[^>]+>")
_MD_RE = re.compile(r"[*_`#>\[\]!]|\s+")


def _plain(text: str, n: int = 40) -> str:
    return _MD_RE.sub(" ", _TAG_RE.sub("", text or "")).strip()[:n]


async def _weak_question_ids(session: AsyncSession, user_id: int, prefs: UserPrefs, exclude: set[int], limit: int):
    spots = await weak_spots(session, user_id, prefs)
    if not spots or limit <= 0:
        return []
    pairs = {(s["system"], s["chapter"]) for s in spots}
    order = {(s["system"], s["chapter"]): i for i, s in enumerate(spots)}
    chapters = {c for _, c in pairs}
    wrong = (
        await session.execute(
            select(Question.id, Question.system, Question.chapter, func.max(Attempt.created_at))
            .join(Attempt, Attempt.question_id == Question.id)
            .where(Attempt.user_id == user_id, Attempt.is_correct.is_(False), Question.chapter.in_(chapters))
            .group_by(Question.id, Question.system, Question.chapter)
        )
    ).all()
    cand: dict[int, tuple[int, float]] = {}
    for qid, sys_, ch, ts in wrong:
        if (sys_, ch) in pairs:
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            cand[qid] = (order[(sys_, ch)], -ts.timestamp())
    book = (
        await session.execute(
            select(Question.id, Question.system, Question.chapter)
            .join(QuestionProgress, QuestionProgress.question_id == Question.id)
            .where(
                QuestionProgress.user_id == user_id,
                QuestionProgress.in_wrongbook.is_(True),
                Question.chapter.in_(chapters),
            )
        )
    ).all()
    for qid, sys_, ch in book:
        if (sys_, ch) in pairs and qid not in cand:
            cand[qid] = (order[(sys_, ch)], 0.0)
    if not cand:
        return []
    mastered = set(
        (
            await session.execute(
                select(QuestionProgress.question_id).where(
                    QuestionProgress.user_id == user_id,
                    QuestionProgress.mastered.is_(True),
                    QuestionProgress.question_id.in_(list(cand)),
                )
            )
        ).scalars()
    )
    ids = [q for q in sorted(cand, key=lambda q: cand[q]) if q not in mastered and q not in exclude]
    return ids[:limit]


async def _generate_schedule(session: AsyncSession, user_id: int, day: date, prefs: UserPrefs) -> None:
    now = utcnow()
    goal = prefs.daily_goal
    items: list[tuple[str, int, str]] = []
    due_q = (
        await session.execute(
            select(QuestionProgress.question_id)
            .where(QuestionProgress.user_id == user_id, QuestionProgress.in_plan.is_(True), QuestionProgress.due_at <= now)
            .order_by(QuestionProgress.due_at)
            .limit(goal)
        )
    ).scalars().all()
    items += [("question", i, "due") for i in due_q]
    if len(items) < goal:
        due_c = (
            await session.execute(
                select(CardProgress.card_id)
                .where(visible(CardProgress.card_id), CardProgress.user_id == user_id,
                       CardProgress.in_plan.is_(True), CardProgress.due_at <= now)
                .order_by(CardProgress.due_at)
                .limit(goal - len(items))
            )
        ).scalars().all()
        items += [("card", i, "due") for i in due_c]
    if len(items) < goal:
        weak = await _weak_question_ids(session, user_id, prefs, set(due_q), goal - len(items))
        items += [("question", i, "weak") for i in weak]
    for t, i, r in items:
        session.add(ScheduleItem(user_id=user_id, day=day, item_type=t, item_id=i, reason=r))
    await session.flush()


async def schedule_today(session: AsyncSession, user_id: int) -> dict:
    prefs = await get_prefs(session, user_id)
    day = local_today()
    rows = (
        await session.execute(
            select(ScheduleItem).where(ScheduleItem.user_id == user_id, ScheduleItem.day == day).order_by(ScheduleItem.id)
        )
    ).scalars().all()
    if not rows:
        await _generate_schedule(session, user_id, day, prefs)
        await session.commit()
        rows = (
            await session.execute(
                select(ScheduleItem)
                .where(ScheduleItem.user_id == user_id, ScheduleItem.day == day)
                .order_by(ScheduleItem.id)
            )
        ).scalars().all()
    qids = [r.item_id for r in rows if r.item_type == "question"]
    mapping = await redirects(session)
    cids = list(dict.fromkeys(resolve(mapping, r.item_id) for r in rows if r.item_type == "card"))
    qt: dict[int, str] = {}
    ct: dict[int, str] = {}
    if qids:
        qt = {i: _plain(s) for i, s in (await session.execute(select(Question.id, Question.stem).where(Question.id.in_(qids)))).all()}
    if cids:
        ct = {i: t for i, t in (await session.execute(select(Card.id, Card.term).where(Card.id.in_(cids)))).all()}
    items_by_key = {}
    for r in rows:
        target = resolve(mapping, r.item_id) if r.item_type == "card" else r.item_id
        key = (r.item_type, target)
        if key in items_by_key:
            items_by_key[key]["done"] |= r.done_at is not None
            continue
        items_by_key[key] = {
            "id": r.id,
            "item_type": r.item_type,
            "item_id": target,
            "reason": r.reason,
            "title": (qt if r.item_type == "question" else ct).get(target, ""),
            "done": r.done_at is not None,
        }
    items = list(items_by_key.values())
    return {"day": day, "goal": prefs.daily_goal, "items": items, "done_count": sum(1 for i in items if i["done"])}


async def schedule_done(session: AsyncSession, user_id: int, item_id: int) -> None:
    item = await session.get(ScheduleItem, item_id)
    if item is None or item.user_id != user_id:
        raise HTTPException(404, "日程条目不存在")
    if item.item_type == "card":
        ids = await original_ids(session, item.item_id)
        await session.execute(update(ScheduleItem).where(
            ScheduleItem.user_id == user_id, ScheduleItem.day == item.day,
            ScheduleItem.item_type == "card", ScheduleItem.item_id.in_(ids),
            ScheduleItem.done_at.is_(None),
        ).values(done_at=utcnow()))
        await session.commit()
    elif item.done_at is None:
        item.done_at = utcnow()
        await session.commit()
