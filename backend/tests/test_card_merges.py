from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models import (
    Card, CardMerge, CardOriginal, CardProgress, CardQuestion, CardRelation,
    EditorialBatch, EditorialExecution, EditorialReview, Note,
)
from app.services import cards, notes, progress, study
from app.services.card_merges import canonical_id, details, resolve
from app.services.editorial import catalog, detail
from app.services.editorial_apply import apply, card_data, digest, rollback


async def seed(session):
    for card_id in (101, 102, 103):
        session.add(Card(id=card_id, subject="生理学", part="08-泌尿", section="核心考点",
                         term="受体", hint=f"提示{card_id}", body=f"原文{card_id}", source_file="original"))
    await session.commit()
    current = (await session.scalars(select(Card))).all()
    return {
        "id": "test-content-batch", "dataset_id": catalog()[0], "expected_opinions": {},
        "expected_cards": {str(c.id): digest(card_data(c)) for c in current},
        "frozen_ids": [], "merges": [{"target_id": 101, "members": [101, 102],
                                     "patch": {"body": "完整合并原文101和原文102"}}],
        "patches": [], "relations": [{"left_id": 102, "right_id": 103, "reason": "机制和临床互引"}],
        "chapters": [], "executions": [{"group_id": "TERM-0192", "status": "merged",
                                       "description": "保留历史并合并", "card_ids": [101, 102]}],
    }


@pytest.mark.asyncio
async def test_merge_preserves_originals_progress_notes_sources_and_rolls_back(session):
    plan = await seed(session)
    now = datetime.now(timezone.utc)
    session.add_all([
        CardProgress(user_id=1, card_id=101, starred=True, reps=2, in_plan=True,
                     due_at=now - timedelta(days=1), last_seen_at=now - timedelta(days=2)),
        CardProgress(user_id=1, card_id=102, starred=False, reps=5, in_plan=True,
                     due_at=now + timedelta(days=2), last_seen_at=now),
        CardProgress(user_id=2, card_id=102, mastered=True, reps=3, last_seen_at=now),
        CardQuestion(card_id=101, question_id=201),
        CardQuestion(card_id=102, question_id=202),
        Note(user_id=1, target_type="card", target_id=102, body="原卡私有笔记", is_public=False),
    ])
    await session.commit()
    result = await apply(session, plan)
    await session.commit()
    assert result["hidden_duplicates"] == 1
    assert await canonical_id(session, 102) == 101
    assert (await session.get(Card, 102)).body == "原文102"
    assert (await session.get(CardOriginal, 101)).data["body"] == "原文101"
    assert (await session.get(CardProgress, (1, 102))).reps == 5
    p = await session.get(CardProgress, (1, 101))
    assert p.reps == 5 and p.starred and p.in_plan
    assert p.due_at.replace(tzinfo=timezone.utc) == now - timedelta(days=1)
    assert (await session.get(CardProgress, (2, 101))).mastered
    assert sum(i["count"] for i in await cards.index(session)) == 2
    assert (await study._flag_counts(session, CardProgress, 1, now))[2] == 1
    assert len(await notes.list_for_target(session, 1, "card", 101)) == 1
    assert await session.scalar(select(func.count()).select_from(CardQuestion)) == 3
    info = await details(session, [101, 103])
    assert [i["id"] for i in info[101]["related_cards"]] == [103]
    assert [i["id"] for i in info[103]["related_cards"]] == [101]
    assert (await session.get(CardOriginal, 102)).data["body"] == "原文102"
    assert all("original_cards" not in card for card in info.values())
    assert await apply(session, plan) == {"already_applied": True, "batch_id": plan["id"]}
    executed = await detail(session, "TERM-0192")
    assert executed["executed"] and executed["execution"]["status"] == "merged"
    await rollback(session, plan["id"])
    await session.commit()
    assert (await session.get(Card, 101)).body == "原文101"
    assert await canonical_id(session, 102) == 102
    assert (await session.get(CardProgress, (1, 101))).reps == 2
    assert await session.get(CardProgress, (2, 101)) is None
    assert await session.scalar(select(func.count()).select_from(CardQuestion)) == 2
    assert await session.scalar(select(func.count()).select_from(CardRelation)) == 0


@pytest.mark.asyncio
async def test_dry_run_rollback_leaves_cards_and_progress_unchanged(session):
    plan = await seed(session)
    await apply(session, plan)
    await session.rollback()
    assert (await session.get(Card, 101)).body == "原文101"
    assert await session.scalar(select(func.count()).select_from(CardMerge)) == 0
    assert await session.scalar(select(func.count()).select_from(EditorialExecution)) == 0


@pytest.mark.asyncio
async def test_standalone_revision_preserves_private_original_and_rolls_back(session):
    plan = await seed(session)
    plan["merges"] = []
    plan["patches"] = [{"id": 103, "patch": {"body": "根据管理员意见修订"}}]
    await apply(session, plan)
    await session.commit()
    original = await session.get(CardOriginal, 103)
    assert original.data["body"] == "原文103"
    info = await details(session, [103])
    assert "original_cards" not in info[103]
    await rollback(session, plan["id"])
    await session.commit()
    assert (await session.get(Card, 103)).body == "原文103"


@pytest.mark.asyncio
async def test_deferred_execution_can_be_resumed_with_exact_guard_and_rollback(session):
    plan = await seed(session)
    key = plan["dataset_id"] + ":TERM-0192"
    previous = EditorialExecution(
        key=key, review_version=0, status="deferred", description="等待补充证据",
        affected_ids=[101, 102], batch_id="earlier-batch",
    )
    session.add(previous)
    await session.commit()
    plan["expected_executions"] = {key: {
        "status": "deferred", "description": "等待补充证据",
        "affected_ids": [101, 102], "batch_id": "earlier-batch", "review_version": 0,
    }}

    await apply(session, plan)
    await session.commit()
    execution = await session.get(EditorialExecution, key)
    assert execution.status == "merged"
    assert execution.batch_id == plan["id"]

    await rollback(session, plan["id"])
    await session.commit()
    execution = await session.get(EditorialExecution, key)
    assert execution.status == "deferred"
    assert execution.description == "等待补充证据"
    assert execution.affected_ids == [101, 102]
    assert execution.batch_id == "earlier-batch"
    assert execution.review_version == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("guard", ["missing", "stale", "finished"])
async def test_existing_execution_resume_requires_exact_deferred_guard(session, guard):
    plan = await seed(session)
    key = plan["dataset_id"] + ":TERM-0192"
    status = "merged" if guard == "finished" else "deferred"
    session.add(EditorialExecution(
        key=key, review_version=0, status=status, description="原执行结果",
        affected_ids=[101, 102], batch_id="earlier-batch",
    ))
    await session.commit()
    if guard != "missing":
        plan["expected_executions"] = {key: {
            "status": status, "description": "错误快照" if guard == "stale" else "原执行结果",
            "affected_ids": [101, 102], "batch_id": "earlier-batch", "review_version": 0,
        }}

    with pytest.raises(ValueError):
        await apply(session, plan)
    await session.rollback()
    assert await session.scalar(select(func.count()).select_from(CardMerge)) == 0
    execution = await session.get(EditorialExecution, key)
    assert execution.status == status and execution.batch_id == "earlier-batch"


@pytest.mark.asyncio
async def test_rejected_card_requires_explicit_audited_override(session):
    dataset_id = catalog()[0]
    cards_to_add = [
        Card(id=9514, subject="生理学", part="12-口诀速记", section="数字·口诀",
             term="梦到异国他乡", hint="", body="原文9514", source_file="口诀"),
        Card(id=9913, subject="生理学", part="12-口诀速记", section="数字·口诀",
             term="梦到异国他乡", hint="", body="原文9913", source_file="口诀"),
    ]
    session.add_all(cards_to_add)
    review_key = dataset_id + ":MECH-05"
    session.add(EditorialReview(
        key=review_key, status="rejected", note="保持原卡", version=1,
    ))
    await session.commit()
    plan = {
        "id": "test-rejection-override", "dataset_id": dataset_id,
        "expected_opinions": {
            review_key: {"status": "rejected", "note": "保持原卡", "version": 1},
        },
        "expected_cards": {
            str(card.id): digest(card_data(card)) for card in cards_to_add
        },
        "merges": [{
            "target_id": 9514, "members": [9514, 9913],
            "patch": {"body": "经用户明确授权后的完整合并正文"},
        }],
        "patches": [], "relations": [], "chapters": [],
        "executions": [{
            "group_id": "TERM-0451", "status": "merged",
            "description": "用户明确授权解除保护", "card_ids": [9514, 9913],
        }],
    }

    with pytest.raises(ValueError, match="冻结卡片"):
        await apply(session, plan)
    await session.rollback()

    plan["rejection_overrides"] = [{
        "card_id": 9514,
        "review_key": review_key,
        "reason": "用户明确要求无视该条冻结保护并完成合并",
    }]
    await apply(session, plan)
    await session.commit()
    assert await canonical_id(session, 9913) == 9514
    batch = await session.get(EditorialBatch, plan["id"])
    assert batch.before["rejection_overrides"] == plan["rejection_overrides"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["frozen", "stale_card", "stale_review", "overlap"])
async def test_invalid_plan_cannot_modify_content(session, failure):
    plan = await seed(session)
    if failure == "frozen":
        plan["frozen_ids"] = [102]
    elif failure == "stale_card":
        (await session.get(Card, 103)).body = "管理员刚编辑"
        await session.commit()
    elif failure == "stale_review":
        session.add(EditorialReview(key=plan["dataset_id"] + ":TERM-0192",
                                    status="needs_revision", note="新意见", version=1))
        await session.commit()
    else:
        plan["merges"].append({"target_id": 103, "members": [102, 103], "patch": {"body": "x"}})
    with pytest.raises(ValueError):
        await apply(session, plan)
    await session.rollback()
    assert (await session.get(Card, 101)).body == "原文101"
    assert await session.scalar(select(func.count()).select_from(CardMerge)) == 0


@pytest.mark.asyncio
async def test_old_id_marks_canonical_and_new_progress_blocks_rollback(session):
    plan = await seed(session)
    await apply(session, plan)
    await session.commit()
    await progress.mark(session, 1, "card", 102, "star")
    assert (await session.get(CardProgress, (1, 101))).starred
    assert await session.get(CardProgress, (1, 102)) is None
    # A user without previous progress must also block restoration.
    with pytest.raises(ValueError, match="新学习进度"):
        await rollback(session, plan["id"])
    await session.rollback()


def test_redirect_cycle_is_rejected():
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        resolve({101: 102, 102: 101}, 101)
