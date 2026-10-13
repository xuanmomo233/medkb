import hashlib
import json
import re
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.render import card_md, md
from app.models import Attempt, Card, CardQuestion, Question, QuestionProgress as QP
from app.schemas import quiz as S
from app.services import study
from app.services.glm import glm_call
from app.services.quiz_filters import LEVELS, SEP, QuizParams, all_conditions, level_conditions, pool_flt_condition
from app.services.question_groups import batches, complete_question_ids, group_key

LETTERS = "ABCDEFGHIJ"
SUBJECT_DIR = {
    "生理学": "01-生理学", "生物化学": "02-生物化学", "病理学": "03-病理学", "诊断学": "04-诊断学",
    "内科学": "05-内科学", "外科学": "06-外科学", "医学人文": "07-医学人文",
}
DEFAULT_LIMIT, MAX_LIMIT, RANDOM_LIMIT = 400, 5000, 120


def ans_set(ans: str | None) -> set[str]:
    return set(re.findall(r"[A-J]", (ans or "").upper()))


def picked_letters(picked: list[int]) -> str:
    return "".join(sorted({LETTERS[i] for i in picked if isinstance(i, int) and 0 <= i < len(LETTERS)}))


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


def _tags(q: Question) -> list[str]:
    t = q.tags
    return [str(x) for x in t] if isinstance(t, list) else []


# ---------------- facets ----------------
async def facets(session: AsyncSession, uid: int, p: QuizParams) -> dict:
    out: dict[str, dict[str, list[int]]] = {}
    done = func.coalesce(func.sum(case((QP.last_seen_at.isnot(None), 1), else_=0)), 0)
    for i, lv in enumerate(LEVELS):
        col = getattr(Question, lv)
        stmt = (
            select(col, func.count(Question.id), done)
            .select_from(Question)
            .outerjoin(QP, and_(QP.question_id == Question.id, QP.user_id == uid))
            .where(*level_conditions(p, i))
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
    parts = await study.plan_day_parts(session, user_id, day_no)
    if not parts:
        return []
    ids: set[int] = set()
    for subject, part in parts:
        sd = SUBJECT_DIR.get(subject)
        if not sd:
            continue
        stmt = (
            select(CardQuestion.question_id)
            .join(Card, Card.id == CardQuestion.card_id)
            .join(Question, Question.id == CardQuestion.question_id)
            .where(Card.subject == subject, Card.part == part, Question.subject_dir == sd)
        )
        ids.update((await session.execute(stmt)).scalars().all())
    return sorted(ids)


async def _latest_attempts(session: AsyncSession, uid: int, qids: list[int]) -> dict[int, Attempt]:
    if not qids:
        return {}
    out = {}
    for chunk in batches(qids):
        sub = (
            select(func.max(Attempt.id))
            .where(Attempt.user_id == uid, Attempt.question_id.in_(chunk))
            .group_by(Attempt.question_id)
        )
        rows = (await session.execute(select(Attempt).where(Attempt.id.in_(sub)))).scalars().all()
        out.update((a.question_id, a) for a in rows)
    return out


async def list_questions(session: AsyncSession, uid: int, p: QuizParams, lite: bool) -> list[S.QuestionOut]:
    plan_ids = None
    if p.plan_day is not None:
        plan_ids = await plan_day_qids(session, uid, p.plan_day)
        if not plan_ids:
            return []
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
    qids = await complete_question_ids(session, seed_ids, limit)
    rows_by_id = {}
    for chunk in batches(qids):
        rows = (await session.execute(
            select(Question, QP)
            .outerjoin(QP, and_(QP.question_id == Question.id, QP.user_id == uid))
            .where(Question.id.in_(chunk))
        )).all()
        rows_by_id.update((q.id, (q, qp)) for q, qp in rows)
    rows = [rows_by_id[qid] for qid in qids if qid in rows_by_id]
    last = await _latest_attempts(session, uid, [q.id for q, _ in rows])
    case_members = defaultdict(list)
    for q, _ in rows:
        key = group_key(q.bank_group, q.bank, q.source_file, q.parent_stem)
        if key is not None:
            case_members[key].append(q.id)
    case_meta = {}
    for key, ids in case_members.items():
        token = hashlib.sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()[:24]
        for index, qid in enumerate(ids, 1):
            case_meta[qid] = (token, index, len(ids))
    out = []
    for q, qp in rows:
        a = last.get(q.id)
        empty = not (q.analysis or "").strip()
        case_group, case_index, case_total = case_meta.get(q.id, ("", 0, 0))
        out.append(
            S.QuestionOut(
                id=q.id, qid=q.qid, chapter=q.chapter or "", system=q.system or "", qtype=q.qtype or "",
                stem_html=md(q.stem), parent_html=md(q.parent_stem),
                case_group=case_group, case_index=case_index, case_total=case_total,
                options_html=[md(str(o)) for o in _opts(q)],
                answer=q.answer or "",
                analysis_html="" if (lite or empty) else md(q.analysis),
                analysis_empty=empty, tags=_tags(q),
                state=derive_state(qp), starred=bool(qp and qp.starred),
                done=bool(qp and qp.last_seen_at is not None),
                last_picked=a.picked if a else "", last_correct=a.is_correct if a else None,
            )
        )
    return out


# ---------------- stat / full ----------------
async def question_stat(session: AsyncSession, qid: int) -> S.QuestionStat:
    total, correct = (
        await session.execute(
            select(func.count(Attempt.id), func.coalesce(func.sum(case((Attempt.is_correct.is_(True), 1), else_=0)), 0))
            .where(Attempt.question_id == qid)
        )
    ).one()
    rows = (
        await session.execute(
            select(Attempt.picked, func.count(Attempt.id))
            .where(Attempt.question_id == qid, Attempt.picked != "")
            .group_by(Attempt.picked)
        )
    ).all()
    dist: dict[str, int] = defaultdict(int)
    for picked, n in rows:
        for ch in picked:
            dist[ch] += int(n)
    return S.QuestionStat(total=int(total), correct=int(correct), dist=dict(sorted(dist.items())))


async def _related_cards(session: AsyncSession, qid: int, limit: int) -> list[Card]:
    stmt = (
        select(Card).join(CardQuestion, CardQuestion.card_id == Card.id)
        .where(CardQuestion.question_id == qid).order_by(Card.id).limit(limit)
    )
    return list((await session.execute(stmt)).scalars().all())


async def question_full(session: AsyncSession, uid: int, qid: int) -> S.QuestionFull:
    q = await session.get(Question, qid)
    if q is None:
        raise HTTPException(404, "题目不存在")
    qp = await session.get(QP, (uid, qid))
    empty = not (q.analysis or "").strip()
    cards = await _related_cards(session, qid, 4) if empty else []
    return S.QuestionFull(
        id=q.id, system=q.system or "", stem_html=md(q.stem), answer=q.answer or "",
        analysis_html="" if empty else md(q.analysis), analysis_empty=empty,
        related_cards=[S.RelatedCard(id=c.id, term=c.term, term_html=md(c.term), hint=c.hint or "", body_html=card_md(c.body)) for c in cards],
        stat=await question_stat(session, qid), tags=_tags(q),
        state=derive_state(qp), starred=bool(qp and qp.starred),
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
        "\n".join(f"{LETTERS[i]}. {_plain(str(o))}" for i, o in enumerate(_opts(q)[:10])),
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
        letters = picked_letters(picked)
        if not ans or not letters:
            self.touch(q.id, None)
            return None
        ok = set(letters) == ans
        self.session.add(Attempt(user_id=self.uid, question_id=q.id, exam_id=exam_id, picked=letters, is_correct=ok))
        self.touch(q.id, ok)
        return ok


async def attempt(session: AsyncSession, uid: int, qid: int, picked: list[int]) -> S.AttemptResult:
    q = await session.get(Question, qid)
    if q is None:
        raise HTTPException(404, "题目不存在")
    rec = await Recorder.create(session, uid, [qid])
    ok = rec.judge(q, picked)
    await session.flush()
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
    conds = all_conditions(p, plan_ids if plan_ids else None)
    if p.plan_day is not None and not plan_ids:
        conds.append(Question.id.in_([]))
    join_qp = and_(QP.question_id == Question.id, QP.user_id == uid)

    def cnt(cond):
        return func.coalesce(func.sum(case((cond, 1), else_=0)), 0)

    st = (
        await session.execute(
            select(
                func.count(Question.id), cnt(QP.last_seen_at.isnot(None)), cnt(QP.in_wrongbook.is_(True)),
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
        .where(Attempt.user_id == uid).group_by(Attempt.question_id).subquery()
    )
    stmt = (
        select(Question, QP, att.c.n, att.c.w, att.c.wts)
        .outerjoin(QP, join_qp).outerjoin(att, att.c.qid == Question.id).where(*conds)
    )
    fc = pool_flt_condition(flt)
    if fc is not None:
        stmt = stmt.where(fc)
    rows = (await session.execute(stmt.order_by(Question.id).offset(offset).limit(size))).all()
    items = [
        S.PoolItem(
            id=q.id, qid=q.qid, stem=snippet(q.stem), answer=q.answer or "", source=q.source_file or "",
            tags=_tags(q), state=derive_state(qp), starred=bool(qp and qp.starred),
            in_plan=bool(qp and qp.in_plan), done=bool(qp and qp.last_seen_at is not None),
            attempts=int(n or 0), wrong_count=int(w or 0), last_wrong_at=iso(wts),
        )
        for q, qp, n, w, wts in rows
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
    return AdminQuestion(id=q.id, system=q.system or "", stem=q.stem or "", analysis=q.analysis or "", tags=_tags(q))


async def update_question(session: AsyncSession, admin_id: int, qid: int, patch) -> int:
    import json

    from app.models import QuestionEdit

    q = await session.get(Question, qid)
    if q is None:
        raise HTTPException(404, "题目不存在")
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
    for field, old, new in changes:
        session.add(QuestionEdit(user_id=admin_id, question_id=qid, field=field, old_value=old, new_value=new))
    await session.commit()
    return len(changes)
