"""抽背：从题库按多级候选选题，不足时由 GLM 生成题卡；内存缓存均带容量上限、按用户隔离。"""
import json
import re
import secrets
import time
from collections import OrderedDict, deque

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.render import md
from app.models import Question
from app.services import glm, knowledge as kb
from app.services.chat_agent import GUARD_RE
from app.services.option_labels import answer_letters, import_options, labels_for

SUBJ_KW = {"生理": "生理学", "生化": "生物化学", "病理": "病理学",
           "内科": "内科学", "外科": "外科学", "人文": "医学人文"}
_CNT = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5}

_MAX_USERS = 5000
_SHOWN_PER_USER = 60
_PENDING_MAX = 2000
_PENDING_TTL = 2 * 3600


class _LRU:
    def __init__(self, cap: int) -> None:
        self.cap = cap
        self.d: OrderedDict = OrderedDict()

    def get(self, k):
        v = self.d.get(k)
        if v is not None:
            self.d.move_to_end(k)
        return v

    def set(self, k, v) -> None:
        self.d[k] = v
        self.d.move_to_end(k)
        while len(self.d) > self.cap:
            self.d.popitem(last=False)

    def pop(self, k):
        return self.d.pop(k, None)


_SHOWN_Q = _LRU(_MAX_USERS)
_LAST_WH = _LRU(_MAX_USERS)
_PENDING = _LRU(_PENDING_MAX)


def put_pending(uid: int, data: dict) -> str:
    now = time.time()
    while _PENDING.d:
        k = next(iter(_PENDING.d))
        if _PENDING.d[k]["exp"] < now:
            _PENDING.pop(k)
        else:
            break
    qid = "L" + secrets.token_hex(4)
    _PENDING.set(qid, {**data, "uid": uid, "exp": now + _PENDING_TTL})
    return qid


def get_pending(uid: int, qid: str) -> dict | None:
    p = _PENDING.get(qid)
    if not p or p["uid"] != uid or p["exp"] < time.time():
        return None
    return p


def _remember_shown(uid: int, qids: list[str]) -> None:
    dq = _SHOWN_Q.get(uid)
    if dq is None:
        dq = deque(maxlen=_SHOWN_PER_USER)
        _SHOWN_Q.set(uid, dq)
    dq.extend(qids)


def norm_answer(a: str | None) -> str:
    return "".join(sorted(answer_letters(a)))


def quiz_count(msg: str) -> int:
    m = re.search(r"([一二两三四五\d])\s*[道个题]", msg)
    if not m:
        return 1
    c = m.group(1)
    n = int(c) if c.isdigit() else _CNT.get(c, 1)
    return max(1, min(n, 5))


def msg_grams(msg: str) -> list[list[str]]:
    msg = re.sub(r"[一二两三四五\d]{1,2}\s*[道个题]", "", msg)
    core = re.sub(
        r"[给我来道出个题目把以下吧呢啊呀的了是吗对不我你他她这那想要再请帮说问答考点背诵起来下一继续换这种些个和与或，。！？、：:;；\s0-9a-zA-Z]",
        "", msg)
    if not core:
        return []
    groups = [[core]]
    for n in (4, 3, 2):
        if len(core) > n:
            groups.append([core[i:i + n] for i in range(len(core) - n + 1)])
    return groups


def _quiz_topic(msg: str, hist_text: str = "") -> str:
    exp = kb.expand_aliases(msg)
    kws = kb.find_names(exp)
    if kws:
        return kws[0]
    for a, full in kb.ALIAS.items():
        if a in msg:
            return full
    g = msg_grams(msg)
    if g and g[0]:
        return g[0][0]
    if hist_text:
        hk = kb.find_names(hist_text)
        if hk:
            return max(hk, key=lambda n: hist_text.rfind(n))
    return "西医综合"


# 候选: (字段, 匹配方式, 模式列表, 类别)；字段 None = 全库
Cand = tuple[str | None, str, tuple[str, ...], str]


def _candidates(msg: str, uid: int, hist_text: str) -> list[Cand]:
    cands: list[Cand] = []
    exp = kb.expand_aliases(msg)
    kws = kb.find_names(exp)
    if kws:
        cands.append(("system", "contains", tuple(kws[:4]), "sys"))
    else:
        for a, full in kb.ALIAS.items():
            if a in msg:
                cands.append(("system", "contains", (full,), "sys"))
                break
        for short, pat in SUBJ_KW.items():
            if short in msg:
                cands.append(("system", "prefix", (pat,), "sys"))
                break
    for grp in msg_grams(msg):
        cands.append(("stem", "contains", tuple(grp), "gram"))
    if hist_text:
        hk = kb.find_names(hist_text)
        if hk:
            hk.sort(key=lambda n: hist_text.rfind(n), reverse=True)
            cands.append(("system", "contains", (hk[0],), "sys"))
        else:
            ah = sorted(((hist_text.rfind(a), full) for a, full in kb.ALIAS.items() if a in hist_text), reverse=True)
            if ah:
                cands.append(("system", "contains", (ah[0][1],), "sys"))
    last = _LAST_WH.get(uid)
    if last:
        cands.append((*last, "sys"))
    cands.append((None, "contains", (), "any"))
    return cands


def _clause(c: Cand):
    field, mode, pats, _ = c
    if field is None:
        return None
    col = getattr(Question, field)
    conds = [col.startswith(p, autoescape=True) if mode == "prefix" else col.contains(p, autoescape=True) for p in pats]
    return or_(*conds)


def _options(q: Question) -> list:
    ops = q.options
    if isinstance(ops, str):
        try:
            ops = json.loads(ops)
        except ValueError:
            ops = []
    return ops if isinstance(ops, list) else []


def question_card(q) -> dict:
    return {
        "qid": str(q.qid),
        "system": q.system or "",
        "multi": len(norm_answer(q.answer)) > 1,
        "stem_html": md(q.stem),
        "options": [{"key": label, "html": md(str(o))} for label, o in zip(labels_for(_options(q), q.option_labels), _options(q))],
    }


async def cards_by_qids(session: AsyncSession, qids: list[str]) -> list[dict]:
    if not qids:
        return []
    rows = (await session.execute(select(Question).where(Question.qid.in_(qids)))).scalars().all()
    by = {r.qid: r for r in rows}
    return [question_card(by[q]) for q in qids if q in by]


async def pick_quizzes(session: AsyncSession, msg: str, uid: int, hist_text: str = "", n: int = 1) -> list[dict]:
    excl = re.findall(r"题号(\w+)", hist_text)[-20:]
    excl += list(_SHOWN_Q.get(uid) or [])[-20:]
    excl = list(dict.fromkeys(excl))
    rows: list[Question] = []
    kind = ""
    for cand in _candidates(msg, uid, hist_text):
        kind = cand[3]
        stmt = select(Question)
        cl = _clause(cand)
        if cl is not None:
            stmt = stmt.where(cl)
        if excl:
            stmt = stmt.where(Question.qid.not_in(excl))
        rows = list((await session.execute(stmt.order_by(func.random()).limit(n))).scalars().all())
        if rows:
            _LAST_WH.set(uid, cand[:3])
            break
    out = [question_card(r) for r in rows]
    if kind == "gram" and len(out) > 1:
        core = (msg_grams(msg) or [[""]])[0][0]
        strong = [q for q in out if core and core in (q["system"] or "")]
        weak = [q for q in out if q not in strong]
        out = strong + weak[:1]
    need = n - len(out)
    if need > 0:
        out += await gen_llm_quizzes(uid, _quiz_topic(msg, hist_text), need)
    if out:
        _remember_shown(uid, [q["qid"] for q in out])
    return out


async def gen_llm_quizzes(uid: int, topic: str, n: int) -> list[dict]:
    if GUARD_RE.search(topic or ""):
        return []
    p = ("出%d道西医综合选择题，考点：%s。" % (n, topic)
         + "只输出JSON数组，不要任何多余文字。每题格式 "
         '{"stem":"题干","options":["选项1","选项2","选项3","选项4"],'
         '"answer":"B","explain":"考点一句话"}；options 不要带字母前缀；'
         '多选题 answer 写多个字母如 "AC"。')
    m = await glm.glm_call([{"role": "user", "content": p}])
    mm = re.search(r"\[.*\]", ((m or {}).get("content") or ""), re.S)
    if not mm:
        return []
    try:
        arr = json.loads(mm.group(0))
    except ValueError:
        return []
    if not isinstance(arr, list):
        return []
    out: list[dict] = []
    for it in arr[:n]:
        try:
            opts, labels = import_options([str(o).strip() for o in it["options"]], it.get("option_labels"))
            ans = norm_answer(str(it.get("answer", "")))
            stem = str(it["stem"])
        except (KeyError, TypeError, AttributeError, ValueError):
            continue
        if len(opts) < 2 or not ans or not set(ans) <= set(labels):
            continue
        qid = put_pending(uid, {"answer": ans, "stem": stem, "opts": opts, "option_labels": labels, "explain": str(it.get("explain", ""))})
        out.append({
            "qid": qid, "system": "AI生成·" + topic, "multi": len(ans) > 1,
            "stem_html": md(stem),
            "options": [{"key": label, "html": md(o)} for label, o in zip(labels, opts)],
        })
    return out
