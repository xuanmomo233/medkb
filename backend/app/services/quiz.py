import hashlib
import json
import re
import time
import unicodedata
from collections import defaultdict, deque
from dataclasses import replace
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.render import card_md, md
from app.models import Attempt, Card, CardQuestion, Question, QuestionProgress as QP, User
from app.schemas import quiz as S
from app.services import plan_queue, provenance, question_links, schedule_progress
from app.services.glm import glm_call
from app.services.quiz_filters import LEVELS, SEP, QuizParams, all_conditions, answered_condition, hides_merged_aliases, level_conditions, pool_flt_condition, scoped_question_roots
from app.services.question_groups import batches, complete_question_ids, flatten_groups, group_key, legacy_case_parts, ordered_groups
from app.services.card_merges import visible
from app.services.option_labels import LETTERS, answer_letters, labels_for

SUBJECT_DIR = {
    "生理学": "01-生理学", "生物化学": "02-生物化学", "病理学": "03-病理学", "诊断学": "04-诊断学",
    "内科学": "05-内科学", "外科学": "06-外科学", "医学人文": "07-医学人文",
}
DEFAULT_LIMIT, MAX_LIMIT, RANDOM_LIMIT = 400, 5000, 120


def ans_set(ans: str | None) -> set[str]:
    return answer_letters(ans)


def picked_letters(picked: list[int], labels: list[str] | None = None) -> str:
    labels = list(LETTERS) if labels is None else labels
    if any(not isinstance(i, int) or isinstance(i, bool) or not 0 <= i < len(labels) for i in picked):
        raise HTTPException(400, "选择的选项下标超出范围")
    return "".join(sorted({labels[i] for i in picked}))


def derive_state(qp: QP | None) -> str:
    if qp is None:
        return ""
    if qp.mastered:
        return "mastered"
    if qp.in_wrongbook:
        return "again"
    if qp.in_plan:
        return "plan"
    return ""


def iso(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return v.isoformat()


def _opts(q: Question) -> list:
    o = q.options
    if isinstance(o, str):
        import json

        try:
            o = json.loads(o)
        except ValueError:
            o = []
    return list(o or [])


def remap_picked_to_target(picked: str, source_options, source_labels, target_options, target_labels) -> str | None:
    """Translate a preserved attempt's letters when a merged alias reorders options.

    Attempt rows remain attached to their original question IDs. Read-time
    translation keeps their selected option meaning aligned with the canonical
    question. Ambiguous or unmatched choices are left unmapped rather than
    being assigned a potentially incorrect canonical letter.
    """
    if not picked:
        return ""
    selected = answer_letters(picked)
    try:
        source_labels = labels_for(source_options, source_labels)
        target_labels = labels_for(target_options, target_labels)
    except ValueError:
        return None
    if not selected or not selected.issubset(set(source_labels)):
        return None

    def option_key(value):
        text = unicodedata.normalize("NFC", str(value or ""))
        text = "".join(chr(ord(ch) - 0xFEE0) if 0xFF01 <= ord(ch) <= 0xFF5E else ch for ch in text)
        text = text.translate(str.maketrans({
            "Ⅰ": "I", "Ⅱ": "II", "Ⅲ": "III", "Ⅳ": "IV", "Ⅴ": "V",
            "Ⅵ": "VI", "Ⅶ": "VII", "Ⅷ": "VIII", "Ⅸ": "IX", "Ⅹ": "X",
            "Ⅺ": "XI", "Ⅻ": "XII", "ⅰ": "i", "ⅱ": "ii", "ⅲ": "iii",
            "ⅳ": "iv", "ⅴ": "v", "ⅵ": "vi", "ⅶ": "vii", "ⅷ": "viii",
            "ⅸ": "ix", "ⅹ": "x", "ⅺ": "xi", "ⅻ": "xii",
        }))
        return re.sub(r"\s+", "", text)

    source_by_label = dict(zip(source_labels, source_options))
    target_by_text = defaultdict(list)
    for label, option in zip(target_labels, target_options):
        target_by_text[option_key(option)].append(label)

    translated = []
    for label in selected:
        matches = target_by_text.get(option_key(source_by_label[label]), [])
        if len(matches) != 1:
            return None
        translated.append(matches[0])
    return "".join(sorted(set(translated)))


def _tags(q: Question) -> list[str]:
    t = q.tags
    return [str(x) for x in t] if isinstance(t, list) else []


# ---------------- facets ----------------
async def facets(session: AsyncSession, uid: int, p: QuizParams) -> dict:
    out: dict[str, dict[str, list[int]]] = {}
    done = func.coalesce(func.sum(case((answered_condition(uid), 1), else_=0)), 0)
    for i, lv in enumerate(LEVELS):
        col = getattr(Question, lv)
        conditions = level_conditions(p, i)
        if hides_merged_aliases(p):
            members = scoped_question_roots(conditions, lv).subquery()
            # A root may belong to several source groups. Count once within
            # each group, and once again within their shared top-level bank.
            if lv == "bank_group":
                rows = (await session.execute(
                    select(members.c.value, Question.id, answered_condition(uid))
                    .join(Question, Question.id == members.c.qid)
                )).all()
                grouped: dict[str, dict[int, bool]] = defaultdict(dict)
                for name, qid, answered in rows:
                    if name:
                        grouped[name.split(SEP)[0]][qid] = bool(answered)
                        if SEP in name:
                            grouped[name][qid] = bool(answered)
                out[lv] = dict(sorted((name, [len(ids), sum(ids.values())]) for name, ids in grouped.items()))
                continue
            col = members.c.value
            conditions = []
            source = Question.__table__.join(members, Question.id == members.c.qid)
        else:
            source = Question
        stmt = (
            select(col, func.count(Question.id), done)
            .select_from(source)
            .outerjoin(QP, and_(QP.question_id == Question.id, QP.user_id == uid))
            .where(*conditions)
            .group_by(col)
        )
        rows = (await session.execute(stmt)).all()
        res: dict[str, list[int]] = {}
        if lv == "bank_group":
            for name, t, d in rows:
                if not name:
                    continue
                t, d = int(t), int(d)
                bare = name.split(SEP)[0]
                if SEP in name:
                    res[name] = [t, d]
                a = res.setdefault(bare, [0, 0])
                a[0] += t
                a[1] += d
        else:
            for name, t, d in rows:
                if name:
                    res[name] = [int(t), int(d)]
        out[lv] = dict(sorted(res.items()))
    return out


# ---------------- questions ----------------
async def plan_day_qids(session: AsyncSession, user_id: int, day_no: int) -> list[int]:
    return await plan_queue.targets(session, user_id, day_no, "question")


async def _latest_attempts(session: AsyncSession, uid: int, qids: list[int]) -> dict[int, Attempt]:
    if not qids:
        return {}
    out = {}
    for chunk in batches(qids):
        sub = (
            select(func.max(Attempt.id))
            .where(Attempt.user_id == uid, Attempt.question_id.in_(chunk), Attempt.picked != "")
            .group_by(Attempt.question_id)
        )
        rows = (await session.execute(select(Attempt).where(Attempt.id.in_(sub)))).scalars().all()
        out.update((a.question_id, a) for a in rows)
    return out


async def _latest_attempts_by_root(
    session: AsyncSession, uid: int, roots: list[int], mapping: dict[int, int], canonical_questions: dict[int, Question]
) -> dict[int, tuple[str, bool | None]]:
    members = question_links.identity_members(mapping, roots)
    member_ids = sorted({qid for group in members.values() for qid in group})
    latest = await _latest_attempts(session, uid, member_ids)

    source_questions = dict(canonical_questions)
    alias_ids = [qid for qid in member_ids if qid not in source_questions]
    for chunk in batches(alias_ids):
        rows = (await session.scalars(select(Question).where(Question.id.in_(chunk)))).all()
        source_questions.update((q.id, q) for q in rows)

    out = {}
    for root, qids in members.items():
        attempts = [latest[qid] for qid in qids if qid in latest]
        if not attempts:
            continue
        attempt = max(attempts, key=lambda row: row.id)
        source = source_questions.get(attempt.question_id)
        target = source_questions.get(root)
        picked = remap_picked_to_target(
            attempt.picked, _opts(source), source.option_labels, _opts(target), target.option_labels,
        ) if source is not None and target is not None else None
        out[root] = (picked or "", attempt.is_correct)
    return out


async def _progress_by_root(session: AsyncSession, uid: int, roots: list[int], mapping: dict[int, int]) -> dict[int, dict[str, bool]]:
    roots = {question_links.resolve(mapping, qid) for qid in roots}
    out = {root: {"in_wrongbook": False, "starred": False, "in_plan": False, "mastered": False}
           for root in roots}
    rows = (await session.execute(select(QP).where(QP.user_id == uid))).scalars().all()
    for qp in rows:
        root = question_links.resolve(mapping, qp.question_id)
        if root not in out:
            continue
        for field in out[root]:
            out[root][field] = out[root][field] or bool(getattr(qp, field))
    return out


async def list_questions(session: AsyncSession, uid: int, p: QuizParams, lite: bool) -> list[S.QuestionOut]:
    plan_ids = None
    if p.plan_day is not None:
        plan_ids = await plan_day_qids(session, uid, p.plan_day)
        if not plan_ids:
            return []
        if p.ids is not None:
            mapping = await plan_queue.question_mapping(session, uid, p.ids)
            p = replace(p, ids=list(dict.fromkeys(question_links.resolve(mapping, qid) for qid in p.ids)))
    # Apply filters to lightweight seeds, then complete cases WITHOUT applying
    # progress/type filters to siblings. Only selected children load full content.
    stmt = (
        select(Question.id)
        .outerjoin(QP, and_(QP.question_id == Question.id, QP.user_id == uid))
        .where(*all_conditions(p, plan_ids))
    )
    unbounded = p.ids is not None or p.plan_day is not None
    limit = None
    if p.random and p.ids is None:
        stmt = stmt.where(or_(QP.mastered.is_(None), QP.mastered.is_(False))).order_by(func.random())
        limit = min(p.limit or RANDOM_LIMIT, RANDOM_LIMIT)
    elif p.shuffle and p.ids is None:
        stmt = stmt.order_by(func.random())
        if not unbounded:
            limit = min(p.limit or DEFAULT_LIMIT, MAX_LIMIT)
    else:
        stmt = stmt.order_by(Question.id)
        if not unbounded:
            limit = min(p.limit or DEFAULT_LIMIT, MAX_LIMIT)
    if limit is not None:
        stmt = stmt.limit(limit)
    seed_ids = list((await session.execute(stmt)).scalars().all())
    if p.ids is not None:
        eligible = set(seed_ids)
        seed_ids = [qid for qid in p.ids if qid in eligible]
    if hides_merged_aliases(p):
        # Case completion may add aliases. Replace them with their reviewed
        # root as well, so a case never serves a superseded answer.
        mapping = await question_links.redirects(session)
        groups = await ordered_groups(session, seed_ids)
        seen = set()
        canonical_groups = []
        for group in groups:
            members = []
            for qid in group:
                root = question_links.resolve(mapping, qid)
                if root not in seen:
                    seen.add(root)
                    members.append(root)
            canonical_groups.append(members)
        qids = flatten_groups(canonical_groups, limit)
    else:
        qids = await complete_question_ids(session, seed_ids, limit)
    if plan_ids is not None:
        # The persisted queue already contains the full case. Never bring a
        # completed child back merely to expand its unfinished sibling.
        selected = set(qids)
        qids = [qid for qid in plan_ids if qid in selected]
    elif p.fresh:
        mapping = await question_links.redirects(session)
        done = await question_links.answered(session, uid, mapping)
        used = set(done)
        fresh_ids = []
        for qid in qids:
            root = question_links.resolve(mapping, qid)
            if root not in used:
                used.add(root)
                # Keep the representative stable when a duplicate group has
                # historical answer variants.
                fresh_ids.append(root)
        qids = fresh_ids
    rows_by_id = {}
    for chunk in batches(qids):
        rows = (await session.execute(
            select(Question, QP)
            .outerjoin(QP, and_(QP.question_id == Question.id, QP.user_id == uid))
            .where(Question.id.in_(chunk))
        )).all()
        rows_by_id.update((q.id, (q, qp)) for q, qp in rows)
    rows = [rows_by_id[qid] for qid in qids if qid in rows_by_id]
    legacy = await legacy_case_parts(session, [q.id for q, _ in rows if not (q.parent_stem or "").strip()])
    mapping = await question_links.redirects(session)
    canonical_questions = {q.id: q for q, _ in rows}
    last_by_root = await _latest_attempts_by_root(
        session, uid, list(canonical_questions), mapping, canonical_questions,
    )
    done = await question_links.answered(session, uid, mapping)
    progress = await _progress_by_root(session, uid, [q.id for q, _ in rows], mapping)
    case_members = defaultdict(list)
    for q, _ in rows:
        parent = "\n".join((legacy[q.id][2], legacy[q.id][0])) if q.id in legacy else q.parent_stem
        key = group_key(q.bank_group, q.bank, q.source_file, parent)
        if key is not None:
            case_members[key].append(q.id)
    case_meta = {}
    for key, ids in case_members.items():
        token = hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()[:24]
        for index, qid in enumerate(ids, 1):
            case_meta[qid] = (token, index, len(ids))
    out = []
    for q, qp in rows:
        root = question_links.resolve(mapping, q.id)
        root_progress = progress.get(root, {"mastered": False, "in_wrongbook": False, "in_plan": False, "starred": False})
        last_picked, last_correct = last_by_root.get(root, ("", None))
        empty = not (q.analysis or "").strip()
        case_group, case_index, case_total = case_meta.get(q.id, ("", 0, 0))
        out.append(
            S.QuestionOut(
                id=q.id, qid=q.qid, chapter=q.chapter or "", system=q.system or "", qtype=q.qtype or "",
                stem_html=md(legacy.get(q.id, (q.parent_stem, q.stem))[1]),
                parent_html=md(legacy.get(q.id, (q.parent_stem, q.stem))[0]),
                case_group=case_group, case_index=case_index, case_total=case_total,
                options_html=[md(str(o)) for o in _opts(q)],
                option_labels=labels_for(_opts(q), q.option_labels),
                answer=q.answer or "",
                analysis_html="" if (lite or empty) else md(q.analysis),
                analysis_empty=empty, tags=_tags(q),
                state=("mastered" if root_progress["mastered"] else "again" if root_progress["in_wrongbook"] else "plan" if root_progress["in_plan"] else ""),
                starred=root_progress["starred"],
                done=root in done,
                last_picked=last_picked, last_correct=last_correct,
            )
        )
    return out


# ---------------- stat / full ----------------
async def question_stat(session: AsyncSession, qid: int) -> S.QuestionStat:
    mapping = await question_links.redirects(session)
    roots = question_links.identity_members(mapping, [qid])
    root = question_links.resolve(mapping, qid)
    qids = list(roots.get(root, {qid}))
    total, correct = (
        await session.execute(
            select(func.count(Attempt.id), func.coalesce(func.sum(case((Attempt.is_correct.is_(True), 1), else_=0)), 0))
            .where(Attempt.question_id.in_(qids))
        )
    ).one()
    rows = (
        await session.execute(
            select(Attempt.question_id, Attempt.picked, func.count(Attempt.id))
            .where(Attempt.question_id.in_(qids), Attempt.picked != "")
            .group_by(Attempt.question_id, Attempt.picked)
        )
    ).all()
    source_questions = {}
    for chunk in batches(qids):
        qs = (await session.scalars(select(Question).where(Question.id.in_(chunk)))).all()
        source_questions.update((question.id, question) for question in qs)
    target = source_questions.get(root)
    dist: dict[str, int] = defaultdict(int)
    for source_id, picked, n in rows:
        source = source_questions.get(source_id)
        canonical_picked = remap_picked_to_target(
            picked, _opts(source), source.option_labels, _opts(target), target.option_labels,
        ) if source is not None and target is not None else None
        if canonical_picked is None:
            # Keep the stored attempt, but do not assign its option letters to
            # the wrong canonical choices when source options are ambiguous.
            continue
        for ch in canonical_picked:
            dist[ch] += int(n)
    return S.QuestionStat(total=int(total), correct=int(correct), dist=dict(sorted(dist.items())))


async def _related_cards(session: AsyncSession, qid: int, limit: int) -> list[Card]:
    stmt = (
        select(Card).join(CardQuestion, CardQuestion.card_id == Card.id)
        .where(visible(), CardQuestion.question_id == qid).order_by(Card.id).limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def question_full(session: AsyncSession, uid: int, qid: int) -> S.QuestionFull:
    q = await session.get(Question, qid)
    if q is None:
        raise HTTPException(404, "题目不存在")
    qp = await session.get(QP, (uid, qid))
    empty = not (q.analysis or "").strip()
    cards = await _related_cards(session, qid, 4) if empty else []
    legacy = await legacy_case_parts(session, [qid]) if not (q.parent_stem or "").strip() else {}
    return S.QuestionFull(
        id=q.id, system=q.system or "", stem_html=md(legacy.get(qid, (q.parent_stem, q.stem))[1]), answer=q.answer or "",
        options_html=[md(str(o)) for o in _opts(q)], option_labels=labels_for(_opts(q), q.option_labels),
        analysis_html="" if empty else md(q.analysis), analysis_empty=empty,
        related_cards=[S.RelatedCard(id=c.id, term=c.term, term_html=md(c.term), hint=c.hint or "", body_html=card_md(c.body)) for c in cards],
        stat=await question_stat(session, qid), tags=_tags(q),
        state=derive_state(qp), starred=bool(qp and qp.starred),
        citations=await provenance.citations_for_target(session, "question", q.id),
    )


# ---------------- AI 解析 ----------------
_ANA_SYS = (
    "你是西医综合考研教研员，按人卫第十版教材口径写题解。"
    "格式：①先一句点明答案与核心机制；②逐项点评各选项对错原因；"
    "③末尾可一句点出考点口诀。200~350字，中文，直接输出解析正文。"
    "若附【知识卡】参考片段，以其为据；与记忆冲突时以知识卡/十版为准。"
)
_ai_hits: dict[int, deque] = defaultdict(deque)
AI_LIMIT, AI_WINDOW = 12, 60.0


def _ai_rate_ok(uid: int) -> bool:
    now = time.monotonic()
    dq = _ai_hits[uid]
    while dq and now - dq[0] > AI_WINDOW:
        dq.popleft()
    if len(dq) >= AI_LIMIT:
        return False
    dq.append(now)
    return True


def _plain(s: str) -> str:
    return re.sub(r"<[^>]+>|\s+", " ", s or "").strip()


async def ai_analysis(session: AsyncSession, uid: int, qid: int) -> str:
    mapping = await question_links.redirects(session)
    qid = question_links.resolve(mapping, qid)
    q = await session.get(Question, qid)
    if q is None:
        raise HTTPException(404, "题目不存在")
    if (q.analysis or "").strip():
        return md(q.analysis)
    if not _ai_rate_ok(uid):
        raise HTTPException(429, "请求太频繁，请稍后再试")
    cards = await _related_cards(session, qid, 3)
    ref = "\n".join("【%s】%s" % (c.term, re.sub(r"\s+", " ", c.body or "")[:900]) for c in cards)
    user = "题干：{}\n\n选项：\n{}\n\n答案：{}".format(
        _plain(q.stem),
        "\n".join(f"{label}. {_plain(str(o))}" for label, o in zip(labels_for(_opts(q), q.option_labels), _opts(q))),
        q.answer or "（无）",
    )
    if ref:
        user += "\n\n知识卡参考：\n" + ref
    msg = await glm_call(
        [{"role": "system", "content": _ANA_SYS}, {"role": "user", "content": user}],
        temperature=0.4, max_tokens=2500,
    )
    text = ((msg or {}).get("content") or "").strip()
    if len(text) < 30:
        raise HTTPException(502, "AI 解析生成失败，请稍后再试")
    text += "\n\n> 解析由 AI 依据知识库补全"
    res = await session.execute(
        update(Question)
        .where(Question.id == qid, or_(Question.analysis.is_(None), func.trim(Question.analysis) == ""))
        .values(analysis=text)
    )
    await session.commit()
    if res.rowcount == 0:
        await session.refresh(q)
        return md(q.analysis)
    return md(text)


# ---------------- 判分 / 进度 ----------------
class Recorder:
    """批量判分并写 Attempt/进度，同一题多次出现时复用进度对象。"""

    def __init__(self, session: AsyncSession, uid: int, qps: dict[int, QP]):
        self.session, self.uid, self.qps = session, uid, qps
        self.now = datetime.now(timezone.utc)

    @classmethod
    async def create(cls, session: AsyncSession, uid: int, qids: list[int]) -> "Recorder":
        # Same lock order as daily schedule generation. Concurrent alias writes
        # must serialize before touching their separate progress records.
        await session.execute(select(User.id).where(User.id == uid).with_for_update(key_share=True))
        existing = {}
        for chunk in batches(list(set(qids))):
            rows = (await session.execute(
                select(QP).where(QP.user_id == uid, QP.question_id.in_(chunk))
            )).scalars().all()
            existing.update((r.question_id, r) for r in rows)
        return cls(session, uid, existing)

    def touch(self, qid: int, ok: bool | None) -> None:
        qp = self.qps.get(qid)
        if qp is None:
            qp = QP(
                user_id=self.uid, question_id=qid, in_wrongbook=False, mastered=False, in_plan=False,
                starred=False, reps=0, ease=2.5, interval_days=0,
            )
            self.session.add(qp)
            self.qps[qid] = qp
        if ok is False:
            qp.in_wrongbook = True
        elif ok is True and qp.in_wrongbook:
            qp.in_wrongbook = False
        qp.last_seen_at = self.now

    def judge(self, q: Question, picked: list[int], exam_id: int | None = None) -> bool | None:
        ans = ans_set(q.answer)
        labels = labels_for(_opts(q), q.option_labels)
        letters = picked_letters(picked, labels)
        if not ans or not ans <= set(labels) or not letters:
            self.touch(q.id, None)
            return None
        ok = set(letters) == ans
        self.session.add(Attempt(user_id=self.uid, question_id=q.id, exam_id=exam_id, picked=letters, is_correct=ok))
        self.touch(q.id, ok)
        return ok


def submission_indices(source: Question, target: Question, picked: list[int]) -> list[int]:
    """A cached alias submission carries positions in its own source options."""
    source_labels = labels_for(_opts(source), source.option_labels)
    letters = picked_letters(picked, source_labels)
    if source.id == target.id or not letters:
        return picked
    target_labels = labels_for(_opts(target), target.option_labels)
    translated = remap_picked_to_target(
        letters, _opts(source), source_labels, _opts(target), target_labels,
    )
    if translated is None or len(translated) != len(letters):
        raise HTTPException(409, "题目选项已变化，请刷新题目后重新作答")
    return [target_labels.index(letter) for letter in translated]


async def attempt(session: AsyncSession, uid: int, qid: int, picked: list[int]) -> S.AttemptResult:
    mapping = await question_links.redirects(session)
    source = await session.get(Question, qid)
    qid = question_links.resolve(mapping, qid)
    q = await session.get(Question, qid)
    if q is None or source is None:
        raise HTTPException(404, "题目不存在")
    picked = submission_indices(source, q, picked)
    rec = await Recorder.create(session, uid, [qid])
    ok = rec.judge(q, picked)
    await session.flush()
    if ok is not None:
        await plan_queue.complete_questions(session, uid, [qid])
        await schedule_progress.questions(session, uid, [(qid, ok)])
    stat = await question_stat(session, qid)
    await session.commit()
    return S.AttemptResult(correct=ok, answer=q.answer or "", stat=stat)


# ---------------- 题池 / 错题本 / 考试记录 ----------------
_SNIP_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def snippet(s: str | None) -> str:
    return re.sub(r"\s+", " ", _SNIP_IMG.sub("[图]", s or "")).strip()[:110]


async def pool(session: AsyncSession, uid: int, p: QuizParams, flt: str | None, offset: int, size: int) -> S.PoolPage:
    plan_ids = None
    if p.plan_day is not None:
        plan_ids = await plan_day_qids(session, uid, p.plan_day)
        if p.ids is not None:
            mapping = await plan_queue.question_mapping(session, uid, p.ids)
            p = replace(p, ids=list(dict.fromkeys(question_links.resolve(mapping, qid) for qid in p.ids)))
    conds = all_conditions(p, plan_ids if plan_ids else None, pool_filter=flt)
    if p.plan_day is not None and not plan_ids:
        conds.append(Question.id.in_([]))
    join_qp = and_(QP.question_id == Question.id, QP.user_id == uid)

    def cnt(cond):
        return func.coalesce(func.sum(case((cond, 1), else_=0)), 0)

    st = (
        await session.execute(
            select(
                func.count(Question.id), cnt(answered_condition(uid)), cnt(QP.in_wrongbook.is_(True)),
                cnt(QP.starred.is_(True)), cnt(QP.in_plan.is_(True)), cnt(QP.mastered.is_(True)),
            ).select_from(Question).outerjoin(QP, join_qp).where(*conds)
        )
    ).one()
    stats = S.PoolStats(
        total=int(st[0]), done=int(st[1]), wrong=int(st[2]), starred=int(st[3]), plan=int(st[4]), mastered=int(st[5])
    )
    att = (
        select(
            Attempt.question_id.label("qid"),
            func.count(Attempt.id).label("n"),
            func.sum(case((Attempt.is_correct.is_(False), 1), else_=0)).label("w"),
            func.max(case((Attempt.is_correct.is_(False), Attempt.created_at))).label("wts"),
        )
        .where(Attempt.user_id == uid, Attempt.picked != "").group_by(Attempt.question_id).subquery()
    )
    stmt = (
        select(Question, QP, att.c.n, att.c.w, att.c.wts, answered_condition(uid))
        .outerjoin(QP, join_qp).outerjoin(att, att.c.qid == Question.id).where(*conds)
    )
    fc = pool_flt_condition(flt, uid=uid)
    if fc is not None:
        stmt = stmt.where(fc)
    rows = (await session.execute(stmt.order_by(Question.id).offset(offset).limit(size))).all()
    items = [
        S.PoolItem(
            id=q.id, qid=q.qid, stem=snippet(q.stem), answer=q.answer or "", source=q.source_file or "",
            tags=_tags(q), state=derive_state(qp), starred=bool(qp and qp.starred),
            in_plan=bool(qp and qp.in_plan), done=bool(done),
            attempts=int(n or 0), wrong_count=int(w or 0), last_wrong_at=iso(wts),
        )
        for q, qp, n, w, wts, done in rows
    ]
    return S.PoolPage(stats=stats, items=items)


async def wrongbook(session: AsyncSession, uid: int) -> list[S.WrongBookGroup]:
    qs = (
        await session.execute(
            select(Question.id, Question.chapter).join(QP, QP.question_id == Question.id)
            .where(QP.user_id == uid, QP.in_wrongbook.is_(True))
        )
    ).all()
    if not qs:
        return []
    att = {
        qid: (int(n), ts)
        for qid, n, ts in (
            await session.execute(
                select(Attempt.question_id, func.count(Attempt.id), func.max(Attempt.created_at))
                .join(QP, and_(QP.question_id == Attempt.question_id, QP.user_id == uid, QP.in_wrongbook.is_(True)))
                .where(Attempt.user_id == uid, Attempt.is_correct.is_(False))
                .group_by(Attempt.question_id)
            )
        ).all()
    }
    groups: dict[str, list] = {}
    for qid, ch in qs:
        g = groups.setdefault(ch or "未分类", [0, 0, None])
        g[0] += 1
        n, ts = att.get(qid, (0, None))
        g[1] += n
        if ts is not None and (g[2] is None or iso(ts) > iso(g[2])):
            g[2] = ts
    return [
        S.WrongBookGroup(chapter=ch, count=g[0], wrong_total=g[1], last_wrong_at=iso(g[2]))
        for ch, g in sorted(groups.items(), key=lambda kv: -kv[1][0])
    ]


# ---------------- 管理员改题 ----------------
async def get_question(session: AsyncSession, qid: int):
    from app.schemas.admin import AdminQuestion

    q = await session.get(Question, qid)
    if q is None:
        raise HTTPException(404, "题目不存在")
    return AdminQuestion(
        id=q.id, subject_dir=q.subject_dir or "", system=q.system or "", stem=q.stem or "",
        options=[str(option) for option in _opts(q)], answer=q.answer or "", analysis=q.analysis or "", tags=_tags(q),
        option_labels=labels_for(_opts(q), q.option_labels),
        citations=await provenance.citations_for_target(session, "question", q.id),
    )


async def update_question(session: AsyncSession, admin_id: int, qid: int, patch) -> int:
    import json

    from app.models import QuestionEdit

    q = await session.get(Question, qid)
    if q is None:
        raise HTTPException(404, "题目不存在")
    old_options = [str(option) for option in _opts(q)]
    next_options = [option.strip() for option in patch.options] if patch.options is not None else old_options
    incoming_labels = patch.option_labels
    try:
        # A noncontiguous source map must never be silently regenerated after
        # an old editor changes the option count.
        if incoming_labels is None and q.option_labels and len(next_options) != len(old_options):
            raise ValueError("修改选项数量时必须同时填写选项标签")
        next_labels = labels_for(next_options, incoming_labels if incoming_labels is not None else q.option_labels)
    except ValueError as error:
        raise HTTPException(400, str(error)) from error
    if patch.answer is not None:
        next_answer = "".join(sorted(ans_set(patch.answer)))
        if not next_answer:
            raise HTTPException(400, "正确答案必须填写选项字母")
        if not set(next_answer) <= set(next_labels):
            raise HTTPException(400, "正确答案超出当前选项范围")
    elif patch.options is not None or incoming_labels is not None:
        current_answer = ans_set(q.answer)
        if not current_answer or not current_answer <= set(next_labels):
            raise HTTPException(400, "修改选项后，请同时填写有效的正确答案")
    changes: list[tuple[str, str, str]] = []
    if patch.system is not None:
        new = patch.system.strip()
        if len(new) > 64:
            raise HTTPException(400, "system 长度不能超过 64")
        if new != (q.system or ""):
            changes.append(("system", q.system or "", new))
            q.system = new
    if patch.stem is not None:
        if not patch.stem.strip():
            raise HTTPException(400, "题干不能为空")
        if len(patch.stem) > 20000:
            raise HTTPException(400, "题干过长（最多 20000 字）")
        if patch.stem != (q.stem or ""):
            changes.append(("stem", q.stem or "", patch.stem))
            q.stem = patch.stem
    if patch.options is not None:
        next_options = [option.strip() for option in patch.options]
        if len(next_options) < 2:
            raise HTTPException(400, "至少需要 2 个选项")
        if any(not option for option in next_options):
            raise HTTPException(400, "选项不能为空")
        if any(len(option) > 5000 for option in next_options):
            raise HTTPException(400, "单个选项过长（最多 5000 字）")
        if next_options != [str(option) for option in _opts(q)]:
            changes.append(("options", json.dumps(_opts(q), ensure_ascii=False), json.dumps(next_options, ensure_ascii=False)))
            q.options = next_options
    if patch.answer is not None:
        if next_answer != (q.answer or ""):
            changes.append(("answer", q.answer or "", next_answer))
            q.answer = next_answer
    if incoming_labels is not None and next_labels != (q.option_labels or []):
        changes.append(("option_labels", json.dumps(q.option_labels or [], ensure_ascii=False), json.dumps(next_labels, ensure_ascii=False)))
        q.option_labels = next_labels
    if patch.analysis is not None:
        if len(patch.analysis) > 20000:
            raise HTTPException(400, "解析内容过长（最多 20000 字）")
        if patch.analysis != (q.analysis or ""):
            changes.append(("analysis", q.analysis or "", patch.analysis))
            q.analysis = patch.analysis
    if patch.tags is not None:
        new_tags = []
        for t in patch.tags:
            t = t.strip()
            if len(t) > 32:
                raise HTTPException(400, "单个标签不能超过 32 字")
            if t and t not in new_tags:
                new_tags.append(t)
        if len(new_tags) > 20:
            raise HTTPException(400, "标签最多 20 个")
        if new_tags != _tags(q):
            changes.append(("tags", json.dumps(_tags(q), ensure_ascii=False), json.dumps(new_tags, ensure_ascii=False)))
            q.tags = new_tags
    if patch.citations is not None:
        citation_changed = await provenance.replace_citations(
            session, "question", qid, patch.citations, admin_id,
        )
    else:
        citation_changed = 0
    for field, old, new in changes:
        session.add(QuestionEdit(user_id=admin_id, question_id=qid, field=field, old_value=old, new_value=new))
    await session.commit()
    return len(changes) + citation_changed
