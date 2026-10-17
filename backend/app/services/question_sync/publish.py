from sqlalchemy import select

from app.models import Card, CardQuestion, ContentCitation, Question, QuestionMerge, QuestionRelation, SyncClassificationRule, SyncDocument, SyncProposal, SyncRevision, TextbookSource, User
from app.services.question_links import redirects, resolve
from .analysis import validate_suggestion
from .normalize import digest, identity, snapshot
from .schemas import ReviewPlan, Suggestion
from .store import utcnow


def require(condition, message):
    if not condition:
        raise ValueError(message)


async def unchanged_question(session, context, question_id):
    expected = next((q["data"] for q in context["questions"] if q["id"] == question_id), None)
    question = await session.scalar(select(Question).where(Question.id == question_id).with_for_update().execution_options(populate_existing=True))
    require(question is not None and expected is not None and digest(snapshot(question)) == digest(expected), "候选题已变化，请重新分析")
    return question


async def publish(session, plan: ReviewPlan, actor_id: int):
    """Caller commits once: any failed decision rolls back the entire review plan."""
    actor = await session.get(User, actor_id)
    require(actor is not None and actor.is_admin, "发布人必须是现有管理员")
    ids = [decision.proposal_id for decision in plan.decisions]
    require(len(ids) == len(set(ids)), "复核清单包含重复提案")
    result = []
    # Stable locking order avoids conflicting multi-proposal publication deadlocks.
    for decision in sorted(plan.decisions, key=lambda d: d.proposal_id):
        proposal = await session.scalar(select(SyncProposal).where(SyncProposal.id == decision.proposal_id).with_for_update().execution_options(populate_existing=True))
        require(proposal is not None and proposal.digest == decision.proposal_hash, "提案不存在或复核版本已变化")
        approved = decision.model_dump()
        if proposal.status != "pending":
            require(proposal.decision.get("approval") == approved, "该提案已被其他决定处理")
            result.append(dict(proposal_id=proposal.id, status=proposal.status, idempotent=True))
            continue
        revision = await session.get(SyncRevision, proposal.revision_id)
        document = await session.scalar(select(SyncDocument).where(SyncDocument.id == revision.document_id).with_for_update().execution_options(populate_existing=True))
        if decision.action == "reject":
            proposal.status = "rejected"
            proposal.decision = {"approval": approved}
            proposal.reviewed_by, proposal.reviewed_at = actor_id, utcnow()
            result.append(dict(proposal_id=proposal.id, status="rejected"))
            continue
        require(document.latest_version == revision.version, "上游已有更新版本，请重新分析")
        require(not document.validation_error, "最新上游数据转换失败，需先修复转换规则")
        q = await session.scalar(select(Question).where(Question.id == document.question_id).with_for_update().execution_options(populate_existing=True)) if document.question_id else None
        require(digest(snapshot(q) if q else {}) == digest(proposal.local_snapshot), "题目已被人工修改，请重新分析")
        require(set(decision.fields) <= set(proposal.suggestion["field_changes"]), "只能选择提案中列出的上游变化字段")
        if proposal.suggestion["conflict_fields"] or proposal.context["answer_conflict_ids"] or proposal.suggestion["first_baseline"]:
            require(decision.acknowledge_conflicts, "需明确确认首次基线或答案/人工校订冲突")
        suggestion = Suggestion.model_validate(proposal.suggestion["suggested"])
        if decision.classification_override:
            suggestion.classification = decision.classification_override
        validate_suggestion(suggestion, proposal.context)
        if q is None:
            require(await session.scalar(select(Question.id).where(Question.qid == document.external_id)) is None, "该上游题号已被其他流程导入，请重新绑定分析")
            require(set(proposal.suggestion["field_changes"]) <= set(decision.fields), "新增题必须确认完整题干、选项、答案和来源字段")
            require(decision.accept_classification and suggestion.classification is not None, "新增题必须确认分类")
            q = Question(qid=document.external_id, **revision.normalized)
            session.add(q)
            await session.flush()
            document.question_id = q.id
        before = dict(proposal.local_snapshot)
        for field in decision.fields:
            setattr(q, field, revision.normalized[field])
        if decision.accept_classification:
            classification = suggestion.classification
            require(classification is not None, "没有可接受的分类建议")
            for field in ("bank_group", "subject_dir", "system", "tags"):
                setattr(q, field, getattr(classification, field))
        require(q.stem and q.qtype and q.subject_dir and q.system and q.bank_group, "发布题目缺少题干、题型或分类")
        if q.qtype in ("单选", "多选"):
            require(len(q.options) >= 2 and q.answer, "选择题缺少选项或答案")
            letters = set(q.answer.replace("、", "").replace(",", "").replace(" ", ""))
            require(letters and letters <= set("ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:len(q.options)]), "选择题答案与选项不匹配")
        introduced = dict(merge=None, relation_ids=[], card_ids=[], citation_ids=[])
        if decision.duplicate_of is not None:
            require(decision.duplicate_of in proposal.context["exact_ids"], "合并目标必须来自严格重复候选")
            target = await unchanged_question(session, proposal.context, decision.duplicate_of)
            mapping = await redirects(session)
            root = resolve(mapping, target.id)
            target = await session.get(Question, root)
            require(root != q.id and resolve(mapping, root) != q.id, "不能生成题目合并循环")
            require(identity(snapshot(q)) is not None and identity(snapshot(q)) == identity(snapshot(target)), "当前题目与主题内容不完全一致，不能合并")
            existing = await session.get(QuestionMerge, q.id)
            require(existing is None or existing.canonical_id == root, "该题已有不同合并目标")
            if existing is None:
                session.add(QuestionMerge(alias_id=q.id, canonical_id=root, reason=decision.note))
                introduced["merge"] = root
        relations = {r.question_id: r for r in suggestion.relations}
        require(set(decision.relation_ids) <= relations.keys(), "同类题未出现在已复核建议内")
        for target_id in sorted(set(decision.relation_ids)):
            await unchanged_question(session, proposal.context, target_id)
            require(target_id != q.id, "不能关联题目自身")
            relation = relations[target_id]
            left, right = sorted((q.id, target_id))
            exists = await session.scalar(select(QuestionRelation).where(
                QuestionRelation.left_id == left, QuestionRelation.right_id == right, QuestionRelation.kind == relation.kind))
            if exists is None:
                row = QuestionRelation(left_id=left, right_id=right, kind=relation.kind, reason=relation.reason)
                session.add(row)
                await session.flush()
                introduced["relation_ids"].append(row.id)
        require(set(decision.card_ids) <= {c.id for c in suggestion.cards}, "卡片未出现在已复核建议内")
        for card_id in sorted(set(decision.card_ids)):
            card = await session.get(Card, card_id, populate_existing=True)
            expected = next((c for c in proposal.context["cards"] if c["id"] == card_id), None)
            current = dict(id=card.id, subject=card.subject, part=card.part, term=card.term, body=card.body) if card else None
            require(current == expected and current is not None, "候选卡片已变化，请重新分析")
            if await session.get(CardQuestion, (card_id, q.id)) is None:
                session.add(CardQuestion(card_id=card_id, question_id=q.id))
                introduced["card_ids"].append(card_id)
        refs = {c.id: c for c in suggestion.citations}
        require(set(decision.citation_ids) <= refs.keys(), "教材定位未出现在已复核建议内")
        for citation_id in sorted(set(decision.citation_ids)):
            citation = await session.get(ContentCitation, citation_id, populate_existing=True)
            expected = next((c for c in proposal.context["citations"] if c["id"] == citation_id), None)
            require(citation is not None and expected is not None, "教材出处已不存在")
            current = {key: getattr(citation, key) for key in expected}
            require(current == expected and citation.status == "verified", "原教材出处已变化，请重新分析")
            book = await session.get(TextbookSource, citation.source_key)
            require(book is not None and book.active, "教材书目已停用")
            # A verified chapter citation is not proof that this new question was verified.
            exists = await session.scalar(select(ContentCitation.id).where(
                ContentCitation.target_type == "question", ContentCitation.target_id == q.id,
                ContentCitation.source_key == citation.source_key, ContentCitation.chapter == citation.chapter,
                ContentCitation.section == citation.section, ContentCitation.page_start == citation.page_start,
                ContentCitation.page_end == citation.page_end))
            if exists is None:
                row = ContentCitation(target_type="question", target_id=q.id, source_key=citation.source_key,
                    chapter=citation.chapter, section=citation.section, page_start=citation.page_start,
                    page_end=citation.page_end, note="同步复核定位线索，待核对该题与教材原页：" + refs[citation_id].reason,
                    status="unverified")
                session.add(row)
                await session.flush()
                introduced["citation_ids"].append(row.id)
        if decision.remember_classification:
            require(decision.accept_classification, "保存映射前必须接受分类")
            bank_id, chapter_id = (str(revision.source_meta.get(key, "")) for key in ("bank_id", "chapter_id"))
            require(bank_id and chapter_id, "上游题库或章节 ID 缺失")
            key = (document.source, bank_id, chapter_id)
            rule = await session.get(SyncClassificationRule, key)
            if rule is None:
                rule = SyncClassificationRule(source=key[0], bank_id=bank_id, chapter_id=chapter_id)
                session.add(rule)
            for field in ("bank_group", "subject_dir", "system"):
                setattr(rule, field, getattr(suggestion.classification, field))
            rule.proposal_id = proposal.id
        document.published_version = revision.version
        proposal.status = "applied"
        proposal.decision = dict(approval=approved, question_id=q.id, before=before, after=snapshot(q), introduced=introduced)
        proposal.reviewed_by, proposal.reviewed_at = actor_id, utcnow()
        await session.flush()
        result.append(dict(proposal_id=proposal.id, question_id=q.id, status="applied"))
    return result
