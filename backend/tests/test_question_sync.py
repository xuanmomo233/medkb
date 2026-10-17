"""Behavioral checks for staged sync, conflicts and explicit publication."""
import json

import pytest
from sqlalchemy import func, select

from app.models import Card, CardQuestion, Chapter, ContentCitation, Question, QuestionMerge, SyncCursor, SyncDocument, SyncProposal, SyncRevision, SyncRun, TextbookSource, User
from app.services.question_sync.analysis import analyze, report
from app.services.question_sync.normalize import identity, normalize
from app.services.question_sync.publish import publish
from app.services.question_sync.schemas import ReviewPlan, Suggestion
from app.services.question_sync.store import acquire, catalog, ingest, release, scan
from app.services.question_sync.upstream import MissingQuestion, UpstreamError, WcykClient, rows


META = dict(bank_id="10", chapter_id="20", bank_title="内科练习", chapter_title="肺炎")


def raw(qid=100, **changes):
    return dict(id=qid, type=1, qBankId=10, chapterId=20, stem="肺炎链球菌肺炎首选药物？",
                options=["青霉素", "阿奇霉素", "替考拉宁", "氟康唑"], answer=[0], analysis="根据肺炎考点选择", **changes)


async def seed(session):
    question = Question(qid="99", **normalize(raw(99), META))
    question.bank_group, question.subject_dir, question.system = "综合", "05-内科学", "呼吸系统"
    card = Card(subject="内科学", part="呼吸系统", term="肺炎链球菌肺炎", body="肺炎链球菌肺炎的表现与治疗")
    chapter = Chapter(kind="mindmap", subject="内科学", title="肺炎", content_md="肺炎链球菌肺炎表现与治疗")
    session.add_all([User(id=1, username="admin", password_hash="unused", is_admin=True), question, card, chapter,
                     TextbookSource(key="internal-10", title="内科学", subject="内科学")])
    await session.flush()
    reference = ContentCitation(target_type="chapter", target_id=chapter.id, source_key="internal-10",
                                chapter="肺炎", page_start=46, page_end=47, status="verified")
    session.add(reference)
    await session.commit()
    return question, card, reference


async def fake_ai(revision, context):
    return Suggestion.model_validate(dict(
        classification=dict(bank_group="综合", subject_dir="05-内科学", system="呼吸系统",
                            tags=["肺炎选药"], reason="题干要求选择肺炎的治疗药物"),
        relations=[], cards=[dict(id=context["cards"][0]["id"], reason="该卡片包含肺炎链球菌肺炎治疗考点")],
        citations=[dict(id=context["citations"][0]["id"], reason="该出处定位肺炎章节，仍需核对原页与本题对应性")], warnings=[]))


def approval(item, **changes):
    decision = dict(proposal_id=item["proposal_id"], proposal_hash=item["proposal_hash"], action="publish",
                    fields=item["suggestion"]["field_changes"], accept_classification=True, note="已核对本次字段和来源")
    decision.update(changes)
    return ReviewPlan.model_validate(dict(version=1, decisions=[decision]))


@pytest.mark.asyncio
async def test_staging_is_idempotent_and_does_not_publish(session):
    await seed(session)
    assert await ingest(session, raw(), META) == "new"
    assert await ingest(session, raw(studCount=100), META) == "unchanged"
    assert await session.scalar(select(func.count()).select_from(Question)) == 1
    assert await session.scalar(select(func.count()).select_from(SyncRevision)) == 1
    updated = raw()
    updated["analysis"] = "上游修订解析"
    assert await ingest(session, updated, META) == "changed"
    assert await session.scalar(select(func.count()).select_from(SyncRevision)) == 2
    updated["source_annotation"] = "上游新增但转换器暂不识别的标注"
    assert await ingest(session, updated, META) == "changed"
    assert await session.scalar(select(func.count()).select_from(SyncRevision)) == 3


@pytest.mark.asyncio
async def test_invalid_record_is_preserved_and_excluded_from_analysis(session):
    await seed(session)
    unknown = raw()
    unknown["type"] = 999
    assert await ingest(session, unknown, META) == "invalid"
    await session.commit()
    document = await session.scalar(select(SyncDocument))
    assert document.raw == unknown and document.validation_error
    assert await analyze(session) == []
    assert await ingest(session, raw(), META) == "changed"
    await session.commit()
    assert len(await analyze(session)) == 1


@pytest.mark.asyncio
async def test_only_explicit_publication_adds_question_links_and_unverified_citation(session):
    original, card, citation = await seed(session)
    await ingest(session, raw(), META)
    await session.commit()
    await analyze(session, use_ai=True, ai=fake_ai)
    item = (await report(session))[0]
    assert original.id in item["candidates"]["exact_ids"]
    assert await session.scalar(select(func.count()).select_from(Question)) == 1
    plan = approval(item, duplicate_of=original.id, card_ids=[card.id], citation_ids=[citation.id], remember_classification=True)
    outcome = await publish(session, plan, 1)
    await session.commit()
    new_id = outcome[0]["question_id"]
    assert (await session.get(QuestionMerge, new_id)).canonical_id == original.id
    assert await session.get(CardQuestion, (card.id, new_id)) is not None
    added = await session.scalar(select(ContentCitation).where(ContentCitation.target_type == "question"))
    assert added.status == "unverified" and added.verified_by is None
    assert (await publish(session, plan, 1))[0]["idempotent"]
    assert await session.scalar(select(func.count()).select_from(Question)) == 2
    # Confirmed source chapter mapping can be reused without another model call.
    await ingest(session, raw(101), META)
    await session.commit()
    await analyze(session)
    next_item = (await report(session))[0]
    assert next_item["suggestion"]["suggested"]["classification"]["system"] == "呼吸系统"


@pytest.mark.asyncio
async def test_changed_local_question_and_changed_upstream_invalidate_approval(session):
    question, _, _ = await seed(session)
    upstream = raw(99)
    upstream["analysis"] = "来自上游的新解析"
    await ingest(session, upstream, META)
    await session.commit()
    await analyze(session, use_ai=True, ai=fake_ai)
    item = (await report(session))[0]
    question.analysis = "人工在复核期间更正解析"
    await session.commit()
    with pytest.raises(ValueError, match="人工修改"):
        await publish(session, approval(item, acknowledge_conflicts=True), 1)
    await session.rollback()
    # Refresh reuses the pending proposal but makes its prior approval hash stale.
    await analyze(session, use_ai=True, ai=fake_ai, refresh_pending=True)
    refreshed = (await report(session))[0]
    assert refreshed["proposal_hash"] != item["proposal_hash"]
    upstream["analysis"] = "上游再次修订"
    await ingest(session, upstream, META)
    await session.commit()
    with pytest.raises(ValueError, match="上游已有更新"):
        await publish(session, approval(refreshed, acknowledge_conflicts=True), 1)


@pytest.mark.asyncio
async def test_three_way_diff_preserves_editorial_analysis_and_flags_shared_edits(session):
    await seed(session)
    await ingest(session, raw(), META)
    await session.commit()
    await analyze(session, use_ai=True, ai=fake_ai)
    item = (await report(session))[0]
    result = await publish(session, approval(item), 1)
    await session.commit()
    question = await session.get(Question, result[0]["question_id"])
    question.analysis = "经过教材核对的人工解析"
    await session.commit()
    changed = raw()
    changed["stem"] += "（新提问形式）"
    await ingest(session, changed, META)
    await session.commit()
    await analyze(session, use_ai=True, ai=fake_ai)
    item = (await report(session))[0]
    assert "analysis" not in item["suggestion"]["field_changes"]
    await publish(session, approval(item), 1)
    await session.commit()
    assert question.analysis == "经过教材核对的人工解析"
    changed["analysis"] = "上游也改了解析"
    await ingest(session, changed, META)
    await session.commit()
    await analyze(session, use_ai=True, ai=fake_ai)
    item = (await report(session))[0]
    assert "analysis" in item["suggestion"]["conflict_fields"]
    with pytest.raises(ValueError, match="明确确认"):
        await publish(session, approval(item), 1)


@pytest.mark.asyncio
async def test_ai_cannot_invent_candidate_ids(session):
    await seed(session)
    await ingest(session, raw(), META)
    await session.commit()
    async def invented(revision, context):
        suggestion = await fake_ai(revision, context)
        suggestion.cards[0].id = 99999
        return suggestion
    with pytest.raises(ValueError, match="候选集以外"):
        await analyze(session, use_ai=True, ai=invented)
    assert await session.scalar(select(func.count()).select_from(SyncProposal)) == 0


@pytest.mark.asyncio
async def test_answer_conflict_is_not_strict_duplicate(session):
    question, _, _ = await seed(session)
    changed = raw()
    changed["answer"] = [1]
    await ingest(session, changed, META)
    await session.commit()
    await analyze(session, use_ai=True, ai=fake_ai)
    item = (await report(session))[0]
    assert question.id in item["candidates"]["answer_conflict_ids"]
    assert question.id not in item["candidates"]["exact_ids"]
    with pytest.raises(ValueError, match="严格重复"):
        await publish(session, approval(item, duplicate_of=question.id, acknowledge_conflicts=True), 1)
    await session.rollback()
    assert await session.scalar(select(func.count()).select_from(Question)) == 1


class FakeSource:
    def __init__(self, fail_at=None):
        self.fail_at = fail_at
    async def question(self, external_id):
        if external_id == self.fail_at:
            raise UpstreamError()
        raise MissingQuestion()


@pytest.mark.asyncio
async def test_zero_new_and_many_holes_advance_but_network_failure_does_not(session):
    result = await scan(session, FakeSource(), start=1000, count=70)
    assert result["next_id"] == 1070 and result["new"] == 0
    with pytest.raises(UpstreamError):
        await scan(session, FakeSource(fail_at=1072), count=10)
    cursor = await session.get(SyncCursor, ("wcyk", "frontier"), populate_existing=True)
    assert cursor.next_id == 1072 and cursor.lease_token is None
    run = await session.scalar(select(SyncRun).order_by(SyncRun.id.desc()))
    assert run.status == "failed" and run.error == "UpstreamError"
    assert (await scan(session, FakeSource(), count=1))["next_id"] == 1073


@pytest.mark.asyncio
async def test_active_lease_prevents_another_runner(session):
    token, _ = await acquire(session, "frontier", 1)
    with pytest.raises(ValueError, match="正在运行"):
        await acquire(session, "frontier", 1)
    await release(session, "frontier", token)
    await session.commit()
    assert await acquire(session, "frontier", 1)


@pytest.mark.asyncio
async def test_catalog_discovers_lower_ids_and_old_question_updates(session):
    await seed(session)
    class CatalogSource:
        async def chapters(self):
            yield {"id": 10}, {"id": 20}
        async def chapter_page(self, bank, chapter, page):
            return [(raw(12), META)], False
    assert (await catalog(session, CatalogSource()))["new"] == 1
    assert (await catalog(session, CatalogSource()))["unchanged"] == 1
    cursor = await session.get(SyncCursor, ("wcyk", "catalog:10:20"), populate_existing=True)
    assert cursor.next_id == 1


def test_normalization_retains_image_urls_and_rejects_answer_overflow():
    record = raw()
    record["stem"] = '<p>检查所示：<img src="https://example.com/a.png"></p>'
    data = normalize(record, META)
    assert "![图](https://example.com/a.png)" in data["stem"]
    record["answer"] = [8]
    with pytest.raises(ValueError, match="越界"):
        normalize(record, META)
    assert identity({"stem": "未给出答案", "answer": ""}) is None


def test_upstream_pagination_does_not_assume_unknown_envelopes_are_empty():
    assert rows({"data": {"data": [1], "total": 2}}, page=1, size=1) == ([1], True)
    assert rows({"data": [1, 2]}, page=1, size=2) == ([1, 2], True)
    with pytest.raises(UpstreamError):
        rows({"data": {"data": [1]}}, page=1, size=500)


@pytest.mark.asyncio
async def test_auth_error_is_not_missing_question():
    import httpx
    client = WcykClient("not-a-real-token", client=httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json={"errno": 401, "data": None}))), delay=0)
    try:
        with pytest.raises(UpstreamError, match="返回错误"):
            await client.request("/api/q_bank", auth=False)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_whole_review_transaction_rolls_back_when_later_item_fails(session):
    await seed(session)
    for qid in (100, 101):
        await ingest(session, raw(qid), META)
    await session.commit()
    await analyze(session, use_ai=True, ai=fake_ai)
    items = await report(session)
    decisions = [approval(item).decisions[0] for item in items]
    decisions[1].proposal_hash = "obsolete"
    with pytest.raises(ValueError, match="复核版本"):
        await publish(session, ReviewPlan(decisions=decisions), 1)
    await session.rollback()
    assert await session.scalar(select(func.count()).select_from(Question)) == 1
    assert set((await session.scalars(select(SyncProposal.status))).all()) == {"pending"}


@pytest.mark.asyncio
async def test_dry_run_rolls_back_all_publication_writes(session):
    await seed(session)
    await ingest(session, raw(), META)
    await session.commit()
    await analyze(session, use_ai=True, ai=fake_ai)
    item = (await report(session))[0]
    await publish(session, approval(item), 1)
    await session.rollback()
    assert await session.scalar(select(func.count()).select_from(Question)) == 1
    assert await session.scalar(select(SyncProposal.status)) == "pending"


@pytest.mark.asyncio
async def test_only_confirmed_upstream_missing_response_is_skipped():
    import httpx
    payloads = [{"errno": 1001, "errmsg": "题目不存在", "data": None}, {"data": None}]
    client = WcykClient("not-a-real-token", client=httpx.AsyncClient(transport=httpx.MockTransport(
        lambda _: httpx.Response(200, json=payloads.pop(0)))), delay=0)
    try:
        with pytest.raises(MissingQuestion):
            await client.request("/api/question", {"id": 999999999}, auth=False)
        with pytest.raises(UpstreamError):
            await client.request("/api/question", {"id": 999999999}, auth=False)
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_failed_ai_item_does_not_starve_other_questions(session):
    await seed(session)
    for qid in (100, 101):
        await ingest(session, raw(qid), META)
    await session.commit()
    async def partial_failure(revision, context):
        if revision.raw["id"] == 100:
            raise ValueError("invalid model response")
        return await fake_ai(revision, context)
    errors = []
    ids = await analyze(session, use_ai=True, ai=partial_failure, errors=errors)
    assert len(ids) == len(errors) == 1
    failed = await session.scalar(select(SyncRevision).where(SyncRevision.analysis_error != ""))
    assert failed.analysis_attempts == 1
    assert len(await analyze(session, use_ai=True, ai=fake_ai, errors=[])) == 1


@pytest.mark.asyncio
async def test_empty_catalog_still_records_a_completed_run(session):
    class EmptyCatalog:
        async def chapters(self):
            if False:
                yield None
    assert (await catalog(session, EmptyCatalog()))["chapters"] == 0
    run = await session.scalar(select(SyncRun).where(SyncRun.scope == "catalog"))
    assert run.status == "completed" and run.counts["pages"] == 0
