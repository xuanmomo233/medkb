import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Card, CardMerge, CardOriginal, CardProgress, CardQuestion, CardRelation,
    Chapter, EditorialBatch, EditorialExecution, EditorialReview,
)
from app.services.editorial import catalog

CARD_FIELDS = ("id", "subject", "part", "section", "term", "hint", "body", "source_file")
PROGRESS_FIELDS = (
    "user_id", "card_id", "in_wrongbook", "mastered", "in_plan", "starred",
    "reps", "ease", "interval_days", "due_at", "last_seen_at",
)


def digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode()).hexdigest()


def card_data(card: Card) -> dict:
    return {field: getattr(card, field) for field in CARD_FIELDS}


def _date(value):
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _progress_data(row) -> dict:
    return {
        field: _date(getattr(row, field)) if field in ("due_at", "last_seen_at")
        else getattr(row, field) for field in PROGRESS_FIELDS
    }


def _patch(card: Card, patch: dict) -> None:
    limits = {"subject": 32, "part": 64, "section": 128, "term": 200, "hint": 2000, "body": 20000}
    for key, value in patch.items():
        if key not in limits or not isinstance(value, str) or len(value) > limits[key]:
            raise ValueError(f"无效卡片字段：{key}")
        if key in ("term", "subject") and not value.strip():
            raise ValueError(f"卡片 {key} 不得为空")
        setattr(card, key, value)


async def apply(session: AsyncSession, plan: dict) -> dict:
    batch_id, plan_hash = plan["id"], digest(plan)
    if len(batch_id) > 64 or plan["dataset_id"] != catalog()[0]:
        raise ValueError("审核数据集已变更")
    previous = await session.get(EditorialBatch, batch_id)
    if previous:
        if previous.plan_hash == plan_hash and previous.status == "applied":
            return {"already_applied": True, "batch_id": batch_id}
        raise ValueError("批次编号已被使用")
    reviews = (await session.scalars(select(EditorialReview).where(
        EditorialReview.key.startswith(plan["dataset_id"] + ":")
    ).with_for_update())).all()
    actual = {r.key: {"status": r.status, "note": r.note, "version": r.version} for r in reviews}
    if actual != plan["expected_opinions"]:
        raise ValueError("管理员审核意见已更新，需要重新核对；没有执行内容修改")
    frozen = set(plan.get("frozen_ids", []))
    for review in reviews:
        if review.status == "rejected":
            item = catalog()[2].get(review.key.split(":", 1)[1], {})
            frozen.update(item.get("card_ids", []))
    touched = set()
    members_seen = set()
    aliases = {}
    for merge in plan.get("merges", []):
        target, members = merge["target_id"], set(merge["members"])
        if target not in members or len(members) < 2 or members & members_seen:
            raise ValueError("合并组缺少主卡或有重复成员")
        members_seen.update(members)
        touched.update(members)
        aliases.update({card_id: target for card_id in members if card_id != target})
    touched.update(p["id"] for p in plan.get("patches", []))
    touched.update(i for edge in plan.get("relations", []) for i in (edge["left_id"], edge["right_id"]))
    if touched & frozen:
        raise ValueError("执行方案触及不采纳的冻结卡片")
    if any(i in aliases for i in aliases.values()):
        raise ValueError("合并指向另一原卡，存在跨组合并冲突")
    ids = set(map(int, plan["expected_cards"]))
    if not touched.issubset(ids):
        raise ValueError("执行方案包含未核对卡片")
    cards = {c.id: c for c in (await session.scalars(
        select(Card).where(Card.id.in_(ids)).with_for_update()
    )).all()}
    if len(cards) != len(ids) or any(
        digest(card_data(cards[i])) != plan["expected_cards"][str(i)] for i in ids
    ):
        raise ValueError("线上卡片已修改，需要重新审查；没有执行内容修改")
    existing_aliases = set((await session.scalars(select(CardMerge.alias_id).where(
        CardMerge.alias_id.in_(members_seen)
    ))).all())
    if existing_aliases:
        raise ValueError("执行方案引用已合并的旧卡")
    before = {"cards": [card_data(cards[i]) for i in sorted(touched)],
              "progress": [], "new_progress": [], "question_links": [], "relations": [], "chapters": []}
    progress_after = []
    changed_ids = members_seen | {p["id"] for p in plan.get("patches", [])}
    for card_id in sorted(changed_ids):
        if await session.get(CardOriginal, card_id) is None:
            session.add(CardOriginal(card_id=card_id, data=card_data(cards[card_id])))
    for merge in plan.get("merges", []):
        target, members = merge["target_id"], sorted(set(merge["members"]))
        _patch(cards[target], merge["patch"])
        for card_id in members:
            if card_id != target:
                session.add(CardMerge(alias_id=card_id, canonical_id=target, batch_id=batch_id))
        existing = set((await session.scalars(select(CardQuestion.question_id).where(
            CardQuestion.card_id == target
        ))).all())
        union = set((await session.scalars(select(CardQuestion.question_id).where(
            CardQuestion.card_id.in_(members)
        ))).all())
        for question_id in sorted(union - existing):
            session.add(CardQuestion(card_id=target, question_id=question_id))
            before["question_links"].append([target, question_id])
        rows = (await session.scalars(select(CardProgress).where(
            CardProgress.card_id.in_(members)
        ).with_for_update())).all()
        by_user = defaultdict(list)
        for row in rows:
            by_user[row.user_id].append(row)
        for user_id, states in by_user.items():
            current = next((p for p in states if p.card_id == target), None)
            if current:
                before["progress"].append(_progress_data(current))
            else:
                current = CardProgress(user_id=user_id, card_id=target)
                session.add(current)
                before["new_progress"].append([user_id, target])
            latest = max(states, key=lambda p: (
                _date(p.last_seen_at) or "", p.reps, p.card_id == target,
            ))
            starred = any(p.starred for p in states)
            in_plan = any(p.in_plan for p in states)
            due = [p.due_at for p in states if p.in_plan and p.due_at is not None]
            for field in PROGRESS_FIELDS[2:]:
                setattr(current, field, getattr(latest, field))
            current.starred = starred
            current.in_plan = in_plan
            if due:
                current.due_at = min(due, key=_date)
            await session.flush()
            progress_after.append(_progress_data(current))
    for patch in plan.get("patches", []):
        if patch["id"] in aliases:
            raise ValueError("修改草案指向旧卡而非最终主卡")
        _patch(cards[patch["id"]], patch["patch"])
    for edge in plan.get("relations", []):
        left, right = sorted((aliases.get(edge["left_id"], edge["left_id"]),
                              aliases.get(edge["right_id"], edge["right_id"])))
        if left == right:
            continue
        if await session.get(CardRelation, (left, right)) is None:
            session.add(CardRelation(left_id=left, right_id=right,
                                     reason=edge["reason"], batch_id=batch_id))
            before["relations"].append([left, right])
    chapter_after = {}
    for change in plan.get("chapters", []):
        chapter = await session.get(Chapter, change["id"], with_for_update=True)
        if chapter is None:
            raise ValueError("待修改章节已不存在")
        saved = {"id": chapter.id, "subject": chapter.subject, "title": chapter.title,
                 "content_md": chapter.content_md, "pages": chapter.pages}
        if digest(saved) != change["before_hash"]:
            raise ValueError(f"章节 #{chapter.id} 已变更，请重新核对")
        before["chapters"].append(saved)
        chapter.content_md = change["content_md"]
        if "pages" in change:
            chapter.pages = change["pages"]
        chapter_after[str(chapter.id)] = digest({
            "id": chapter.id, "subject": chapter.subject, "title": chapter.title,
            "content_md": chapter.content_md, "pages": chapter.pages,
        })
    for result in plan["executions"]:
        key = plan["dataset_id"] + ":" + result["group_id"]
        if await session.get(EditorialExecution, key) is not None:
            raise ValueError("审核项已有执行结果，需明确修订而非覆盖记录")
        session.add(EditorialExecution(
            key=key, review_version=actual.get(key, {}).get("version", 0),
            status=result["status"], description=result["description"],
            affected_ids=result.get("card_ids", []), batch_id=batch_id,
        ))
    await session.flush()
    session.add(EditorialBatch(
        id=batch_id, plan_hash=plan_hash, status="applied", before=before,
        after={"cards": {str(i): digest(card_data(cards[i])) for i in touched},
               "chapters": chapter_after, "progress": progress_after},
    ))
    await session.flush()
    return {"batch_id": batch_id, "changed_cards": len(touched), "hidden_duplicates": len(aliases),
            "question_links_added": len(before["question_links"]),
            "relations_added": len(before["relations"]), "chapters_updated": len(chapter_after),
            "review_results": len(plan["executions"]), "progress_rows": len(progress_after)}


async def rollback(session: AsyncSession, batch_id: str) -> dict:
    batch = await session.get(EditorialBatch, batch_id, with_for_update=True)
    if batch is None or batch.status != "applied":
        raise ValueError("批次未执行或已撤销")
    ids = set(map(int, batch.after["cards"]))
    cards = {c.id: c for c in (await session.scalars(
        select(Card).where(Card.id.in_(ids)).with_for_update()
    )).all()}
    if any(digest(card_data(cards[i])) != value for key, value in batch.after["cards"].items()
           for i in [int(key)]):
        raise ValueError("内容在整理后又有修改，不能自动撤销")
    targets = set((await session.scalars(select(CardMerge.canonical_id).where(
        CardMerge.batch_id == batch_id
    ))).all())
    if await session.scalar(select(CardMerge.alias_id).where(
        CardMerge.alias_id.in_(targets), CardMerge.batch_id != batch_id,
    ).limit(1)):
        raise ValueError("主卡已参与后续合并，不能单独撤销此前批次")
    states = (await session.scalars(select(CardProgress).where(
        CardProgress.card_id.in_(targets)
    ).with_for_update())).all()
    expected = {(p["user_id"], p["card_id"]): p for p in batch.after["progress"]}
    current = {(p.user_id, p.card_id): _progress_data(p) for p in states}
    if current != expected:
        raise ValueError("整理后产生新学习进度，不能自动撤销")
    for state in batch.after["progress"]:
        row = await session.get(CardProgress, (state["user_id"], state["card_id"]), with_for_update=True)
        if row is None or _progress_data(row) != state:
            raise ValueError("整理后产生新学习进度，不能自动撤销")
    for saved in batch.before["cards"]:
        card = cards[saved["id"]]
        for key, value in saved.items():
            if key != "id":
                setattr(card, key, value)
    for saved in batch.before["progress"]:
        row = await session.get(CardProgress, (saved["user_id"], saved["card_id"]))
        for key, value in saved.items():
            if key not in ("user_id", "card_id"):
                setattr(row, key, datetime.fromisoformat(value)
                        if key in ("due_at", "last_seen_at") and value else value)
    for user_id, card_id in batch.before["new_progress"]:
        await session.execute(delete(CardProgress).where(
            CardProgress.user_id == user_id, CardProgress.card_id == card_id,
        ))
    for card_id, question_id in batch.before["question_links"]:
        await session.execute(delete(CardQuestion).where(
            CardQuestion.card_id == card_id, CardQuestion.question_id == question_id,
        ))
    for left, right in batch.before["relations"]:
        await session.execute(delete(CardRelation).where(
            CardRelation.left_id == left, CardRelation.right_id == right,
        ))
    for saved in batch.before["chapters"]:
        chapter = await session.get(Chapter, saved["id"], with_for_update=True)
        current = {"id": chapter.id, "subject": chapter.subject, "title": chapter.title,
                   "content_md": chapter.content_md, "pages": chapter.pages}
        if digest(current) != batch.after["chapters"][str(chapter.id)]:
            raise ValueError("章节在整理后又有修改，不能自动撤销")
        chapter.content_md, chapter.pages = saved["content_md"], saved["pages"]
    await session.execute(delete(CardMerge).where(CardMerge.batch_id == batch_id))
    records = (await session.scalars(select(EditorialExecution).where(
        EditorialExecution.batch_id == batch_id
    ))).all()
    for record in records:
        record.status = "rolled_back"
    batch.status = "rolled_back"
    await session.flush()
    return {"batch_id": batch_id, "rolled_back": True}
