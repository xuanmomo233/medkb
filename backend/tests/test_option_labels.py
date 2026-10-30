import json

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Attempt, Question, User
from app.schemas.admin import AdminQuestionPatch
from app.schemas.quiz import SubmitItem
from app.services import exam, quiz
from app.services.option_labels import import_options, parse_markdown_options
from app.services.question_sync.normalize import compatible_data, identity, normalize, snapshot
from scripts.backfill_option_labels import assess, source_index


LABELS = list("ABCDEFGHJK")
OPTIONS = [f"选项{i}" for i in range(10)]




def test_markdown_and_sync_preserve_noncontiguous_source_letters():
    markdown = "\n".join(f"- {label}. {option}" for label, option in zip(LABELS, OPTIONS))
    options, labels = parse_markdown_options(markdown)
    assert (options, labels) == (OPTIONS, LABELS)
    assert import_options([f"{l}. {o}" for l, o in zip(LABELS, OPTIONS)], "[]") == (OPTIONS, LABELS)
    normalized = normalize({"id": 1, "type": 2, "stem": "题干", "options": options,
                            "option_labels": labels, "answer": [8, 9]}, {})
    assert normalized["answer"] == "J、K"
    assert normalized["option_labels"] == LABELS
    assert identity(normalized) != identity(dict(normalized, option_labels=list("ABCDEFGHIJ")))
    question = Question(qid="source", **normalized)
    assert snapshot(question)["option_labels"] == LABELS
    assert import_options(["E. coli", "S. aureus"]) == (["E. coli", "S. aureus"], ["A", "B"])






@pytest.mark.parametrize("encode_json", [False, True])
@pytest.mark.parametrize("explicit", [None, ["A", "J", "K", "L"]])
def test_legacy_import_preserves_nucleotide_bodies(encode_json, explicit):
    from app.services.legacy_import import map_question
    bodies = ["A、G", "G、A", "U、C", "U、A"]
    source = dict(id=1, qid="nucleotides", stem="核苷酸组合", options=json.dumps(bodies, ensure_ascii=False) if encode_json else bodies,
                  answer="K" if explicit else "C", option_labels=explicit)
    mapped = map_question(source)
    assert mapped["options"] == bodies
    assert mapped["option_labels"] == (explicit or list("ABCD"))
    assert mapped["answer"] == source["answer"]


@pytest.mark.parametrize("explicit", [None, [], ["A", "J", "K", "L"]])
def test_sync_normalize_preserves_nucleotide_bodies_and_answer_position(explicit):
    bodies = ["A、G", "G、A", "U、C", "U、A"]
    raw = dict(id=919, type=1, stem="核苷酸组合", options=bodies, option_labels=explicit, answer=[2])
    mapped = normalize(raw, {})
    assert mapped["options"] == bodies and raw["options"] == bodies
    assert mapped["option_labels"] == (explicit or list("ABCD"))
    assert mapped["answer"] == ("K" if explicit else "C")






def test_legacy_revision_read_compatibility_does_not_rewrite_historical_payload():
    original = {"options": ["甲", "乙"], "answer": "B"}
    upgraded = compatible_data(original)
    assert upgraded["option_labels"] == ["A", "B"]
    assert "option_labels" not in original


def test_legacy_import_preserves_markdown_labels_and_existing_card_mapping():
    from app.services.legacy_import import card_section, map_question
    markdown = "\n".join(f"- {label}. {option}" for label, option in zip(LABELS, OPTIONS))
    mapped = map_question({"id": 1, "qid": "99", "stem": "题干", "options": markdown, "answer": "J、K"})
    assert mapped["options"] == OPTIONS and mapped["option_labels"] == LABELS
    assert mapped["answer"] == "J、K"
    assert card_section("数字·口诀", "填空", "填写心率") == "填空练习"


async def seed(session):
    session.add(User(id=7, username="label-editor", password_hash="x", is_admin=True))
    session.add_all([Question(id=1, qid="source", stem="题干", options=OPTIONS,
                             option_labels=LABELS, answer="J、K", qtype="多选"),
                     Question(id=2, qid="legacy", stem="旧题", options=["甲", "乙"], answer="B")])
    await session.commit()


async def test_practice_mock_full_admin_and_attempt_distribution_use_actual_labels(session):
    await seed(session)
    result = await quiz.attempt(session, 7, 1, [8, 9])
    assert result.correct is True
    assert result.stat.dist == {"J": 1, "K": 1}
    assert (await session.scalar(select(Attempt).where(Attempt.question_id == 1))).picked == "JK"
    report = await exam.submit(session, 7, "标签模考", [SubmitItem(question_id=1, picked=[8, 9])])
    assert report.correct == report.total == 1
    full = await quiz.question_full(session, 7, 1)
    assert full.option_labels == LABELS and len(full.options_html) == 10
    admin = await quiz.get_question(session, 1)
    assert admin.option_labels == LABELS
    legacy = await quiz.attempt(session, 7, 2, [1])
    assert legacy.correct is True
    with pytest.raises(HTTPException, match="下标"):
        await quiz.attempt(session, 7, 1, [8, 99])


async def test_all_26_choices_can_be_graded_and_persisted(session):
    await seed(session)
    labels = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    session.add(Question(id=3, qid="all26", stem="全选", options=labels, option_labels=labels,
                         qtype="多选", answer="、".join(labels)))
    await session.commit()
    result = await quiz.attempt(session, 7, 3, list(range(26)))
    assert result.correct is True
    assert (await session.scalar(select(Attempt).where(Attempt.question_id == 3))).picked == "".join(labels)


def test_mock_uses_same_fullwidth_answer_parser_and_real_label_membership():
    assert exam.type_rank("多选", "ｊ、Ｋ") == 3
    assert exam.judgeable_answer("ｊ、Ｋ", LABELS, 10) is True
    assert exam.judgeable_answer("I", LABELS, 10) is False
    assert exam.judgeable_answer("K", [], 10) is False


async def test_chat_quiz_keys_and_grading_preserve_real_labels(session, monkeypatch):
    from app.services import chat_agent, chat_quiz
    await seed(session)
    q = await session.get(Question, 1)
    card = chat_quiz.question_card(q)
    assert [option["key"] for option in card["options"]] == LABELS

    async def limited(*_):
        return True
    monkeypatch.setattr(chat_agent, "is_rate_limited", limited)
    response = await chat_agent.answer_quiz(session, 7, "source", "ｊ、Ｋ")
    assert response["correct"] is True and response["answer"] == "JK"
    with pytest.raises(HTTPException, match="选项标签"):
        await chat_agent.answer_quiz(session, 7, "source", "I")

    async def llm(*_, **__):
        return {"content": json.dumps([dict(stem="生成测试", options=OPTIONS, option_labels=LABELS, answer="JK")])}
    monkeypatch.setattr(chat_quiz.glm, "glm_call", llm)
    generated = await chat_quiz.gen_llm_quizzes(7, "测试", 1)
    assert [option["key"] for option in generated[0]["options"]] == LABELS
    assert (await chat_agent.answer_quiz(session, 7, generated[0]["qid"], "JK"))["correct"] is True


async def test_admin_text_patch_preserves_labels_and_invalid_relabel_is_atomic(session):
    await seed(session)
    await quiz.update_question(session, 7, 1, AdminQuestionPatch(analysis="新解析"))
    q = await session.get(Question, 1)
    assert q.option_labels == LABELS and q.answer == "J、K"
    with pytest.raises(HTTPException, match="同时填写"):
        await quiz.update_question(session, 7, 1, AdminQuestionPatch(options=OPTIONS, option_labels=list("ABCDEFGHIJ")))
    assert q.option_labels == LABELS and q.options == OPTIONS
    with pytest.raises(HTTPException, match="当前选项范围"):
        await quiz.update_question(session, 7, 1, AdminQuestionPatch(options=OPTIONS, option_labels=LABELS, answer="I"))
    changed = [*OPTIONS]
    changed[8] = "新J文本"
    await quiz.update_question(session, 7, 1, AdminQuestionPatch(options=changed, option_labels=LABELS, answer="JK"))
    assert q.option_labels == LABELS and q.options[8] == "新J文本" and q.answer == "JK"


async def test_admin_labels_only_preserves_still_valid_original_answer(session):
    await seed(session)
    q = await session.get(Question, 2)
    q.answer = "A"
    await session.commit()
    await quiz.update_question(session, 7, 2, AdminQuestionPatch(option_labels=["A", "J"]))
    assert q.option_labels == ["A", "J"] and q.answer == "A"
    with pytest.raises(HTTPException, match="同时填写有效的正确答案"):
        await quiz.update_question(session, 7, 2, AdminQuestionPatch(option_labels=["B", "J"]))
    assert q.option_labels == ["A", "J"] and q.answer == "A"




def test_source_backfill_checks_all_noncontiguous_records_and_refuses_drift(tmp_path):
    source = tmp_path / "题库" / "source.md"
    source.parent.mkdir()
    source.write_text("### 第1题 `id:99`\n\n题干\n\n" + "\n".join(f"- {l}. {o}" for l, o in zip(LABELS, OPTIONS)) + "\n\n**答案：J、K**\n", encoding="utf-8")
    index, counts = source_index(tmp_path)
    assert counts["noncontiguous_records"] == 1
    row = dict(id=1, qid="99", stem="题干", parent_stem="", options=OPTIONS, answer="J、K", source_file="题库/source.md", option_labels=[])
    ready = assess(row, index)
    assert ready["status"] == "ready" and ready["proposed_labels"] == LABELS
    assert assess(dict(row, option_labels=LABELS), index)["status"] == "already_applied"
    assert assess(dict(row, answer="J"), index)["status"] == "source_content_mismatch"
    assert assess(dict(row, options=list(reversed(OPTIONS))), index)["status"] == "source_content_mismatch"
    assert assess(dict(row, stem="不同题干"), index)["status"] == "source_content_mismatch"
    assert assess(dict(row, analysis="后加解析"), index)["before_sha256"] != ready["before_sha256"]
    original_hash = index["99"][0]["record_sha256"]
    source.write_text(source.read_text(encoding="utf-8").replace("第1题", "第2题"), encoding="utf-8")
    changed, _ = source_index(tmp_path)
    assert changed["99"][0]["record_sha256"] != original_hash


def test_source_index_does_not_mistake_analysis_bullets_for_noncontiguous_options(tmp_path):
    (tmp_path / "source.md").write_text(
        "### 第1题 `id:205014`\n\n题干\n\n- A. 甲\n- B. 乙\n- C. 丙\n- D. 丁\n\n"
        "**答案：C**\n\n**解析**：- A. 甲\n说明\n- B. 乙\n- C. 丙\n- D. 丁\n", encoding="utf-8")
    index, counts = source_index(tmp_path)
    assert index == {} and counts.get("noncontiguous_records", 0) == 0


def test_source_index_empty_option_never_consumes_next_label_line(tmp_path):
    (tmp_path / "source.md").write_text(
        "### 第1题 `id:227906`\n\n题干\n\n- A. \n- B. -CH₂-\n- C. -CH=\n- D. CO₂\n\n**答案：D**\n"
        "### 第2题 `id:gap`\n", encoding="utf-8")
    index, counts = source_index(tmp_path)
    assert index == {} and counts.get("noncontiguous_records", 0) == 0
    # An actual source gap with an empty A is still retained without losing B.
    (tmp_path / "source.md").write_text(
        "### 第1题 `id:99`\n\n题干\n\n- A. \n- B. 乙\n- J. 丙\n\n**答案：J**\n", encoding="utf-8")
    index, counts = source_index(tmp_path)
    assert index["99"][0]["option_labels"] == ["A", "B", "J"]
    assert index["99"][0]["options"] == ["", "乙", "丙"]


async def test_legacy_staged_proposal_requires_reingest_without_mutating_old_version(session):
    from app.models import SyncDocument, SyncRevision
    from app.services.question_sync.analysis import analyze, report
    from app.services.question_sync.normalize import digest
    from app.services.question_sync.publish import publish
    from app.services.question_sync.store import ingest
    from test_question_sync import META, approval, fake_ai, raw, seed as seed_sync

    await seed_sync(session)
    upstream = raw()
    await ingest(session, upstream, META)
    revision = await session.scalar(select(SyncRevision))
    document = await session.scalar(select(SyncDocument))
    old = dict(revision.normalized)
    old.pop("option_labels")
    old_hash = digest({"data": old, "raw_content": upstream, "source_meta": META})
    revision.normalized, revision.digest, document.latest_hash = old, old_hash, old_hash
    revision_id = revision.id
    await session.commit()
    await analyze(session, use_ai=True, ai=fake_ai)
    item = (await report(session))[0]
    assert (await session.get(SyncRevision, revision_id)).normalized == old
    assert (await session.get(SyncRevision, revision_id)).digest == old_hash
    with pytest.raises(ValueError, match="旧提案缺少选项标签"):
        await publish(session, approval(item, acknowledge_conflicts=True), 1)
    await session.rollback()
    assert await ingest(session, upstream, META) == "changed"
    await session.commit()
    await analyze(session, use_ai=True, ai=fake_ai)
    newest = next(item for item in await report(session) if item["version"] == 2)
    assert newest["version"] == 2
    assert "option_labels" in newest["suggestion"]["field_changes"]
    preserved = await session.get(SyncRevision, revision_id)
    assert preserved.normalized == old and preserved.digest == old_hash
