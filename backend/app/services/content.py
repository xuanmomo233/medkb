import re

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.render import md
from app.models import Card, CardProgress, Chapter, Question, QuestionProgress
from app.services.progress import derive_state
from app.services.card_merges import visible

_IMG = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_MD_NOISE = re.compile(r"[#*`>|]+|<[^>]+>")
SEARCH_CAPS = {"question": 150, "card": 150, "chapter": 80}
SEARCH_TOTAL = 200


def split_fm(content: str | None) -> tuple[dict[str, str], str]:
    meta: dict[str, str] = {}
    body = content or ""
    if body.startswith("---"):
        m = re.match(r"^---\s*\n(.*?)\n---\s*\n?", body, re.S)
        if m:
            for ln in m.group(1).split("\n"):
                if ":" in ln:
                    k, v = ln.split(":", 1)
                    meta[k.strip()] = v.strip().strip("[]")
            body = body[m.end():]
    body = re.sub(r"^>[^\n]*考频[^\n]*\n?", "", body, count=1, flags=re.M)
    return meta, body


def plain(text: str | None) -> str:
    t = _IMG.sub("", text or "")
    t = _MD_NOISE.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def snippet(text: str | None, q: str, width: int = 60) -> str:
    t = plain(text)
    i = t.lower().find(q.lower())
    if i < 0:
        return t[: width * 2]
    s = max(0, i - width // 2)
    e = min(len(t), i + len(q) + width)
    return ("…" if s else "") + t[s:e] + ("…" if e < len(t) else "")


_SHORT = re.compile(r"^\d+-")


def _short(x: str) -> str:
    return _SHORT.sub("", (x or "").strip())


async def tree(session: AsyncSession) -> dict:
    chs = (
        await session.execute(select(Chapter.id, Chapter.kind, Chapter.subject, Chapter.title).order_by(Chapter.subject, Chapter.title))
    ).all()
    qrows = (
        await session.execute(
            select(Question.subject_dir, Question.system, Question.chapter, func.count())
            .group_by(Question.subject_dir, Question.system, Question.chapter)
        )
    ).all()

    # 导图标题（去编号）→ 顺序，用于给题库 system/chapter 排教材序
    morder: dict[str, dict[str, int]] = {}
    for i, r in enumerate([c for c in chs if c.kind == "mindmap"]):
        morder.setdefault(r.subject, {})[_short(r.title)] = i

    def rank(subject_dir: str, chapter: str) -> int:
        suf = chapter.split(" · ", 1)[1] if " · " in chapter else chapter
        return morder.get(_short(subject_dir), {}).get(suf, 1 << 20)

    groups: dict[str, dict[str, list[tuple[str, int]]]] = {}
    for subjdir, system, chapter, cnt in qrows:
        groups.setdefault(subjdir or "未分类", {}).setdefault(system or "未细分", []).append((chapter, cnt))

    question_tree = []
    for subjdir in sorted(groups):
        systems = []
        for name, chapters in groups[subjdir].items():
            chapters.sort(key=lambda c: (rank(subjdir, c[0]), c[0]))
            systems.append({
                "name": name,
                "rank": min(rank(subjdir, c) for c, _ in chapters),
                "chapters": [{"name": c, "count": n} for c, n in chapters],
            })
        systems.sort(key=lambda s: (s["rank"], s["name"]))
        for s in systems:
            del s["rank"]
        question_tree.append({"subject_dir": subjdir, "systems": systems})

    brief = lambda r: {"id": r.id, "subject": r.subject, "title": r.title}  # noqa: E731
    return {
        "mindmaps": [brief(r) for r in chs if r.kind == "mindmap"],
        "notes": [brief(r) for r in chs if r.kind == "note"],
        "question_tree": question_tree,
    }


async def chapter_detail(session: AsyncSession, cid: int) -> dict | None:
    ch = await session.get(Chapter, cid)
    if ch is None:
        return None
    meta, body = split_fm(ch.content_md)
    return {
        "id": ch.id, "title": ch.title, "subject": ch.subject, "html": md(body),
        "meta": meta, "pages": [int(x) for x in (ch.pages or [])],
    }


def _like(q: str):
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def _states(session, model, fk, user_id, ids):
    if not ids:
        return {}
    rows = (
        await session.execute(select(model).where(model.user_id == user_id, getattr(model, fk).in_(ids)))
    ).scalars()
    return {getattr(p, fk): p for p in rows}


async def search(session: AsyncSession, user_id: int, q: str, kind: str | None) -> list[dict]:
    q = (q or "").strip()
    if not q:
        return []
    pat = _like(q)
    hits: list[dict] = []
    if kind in (None, "", "question"):
        rows = (
            await session.execute(
                select(Question.id, Question.qid, Question.chapter, Question.stem, Question.analysis)
                .where(
                    (Question.qid == q)
                    | Question.stem.ilike(pat, escape="\\")
                    | Question.analysis.ilike(pat, escape="\\")
                )
                .order_by(Question.id)
                .limit(SEARCH_CAPS["question"])
            )
        ).all()
        pm = await _states(session, QuestionProgress, "question_id", user_id, [r.id for r in rows])
        for r in rows:
            src = r.stem if q.lower() in (r.stem or "").lower() else (r.analysis or r.stem)
            p = pm.get(r.id)
            hits.append({
                "kind": "question", "id": r.id, "title": f"{r.qid} {r.chapter}".strip(),
                "snippet": snippet(src, q), "state": derive_state(p), "starred": bool(p and p.starred),
            })
    if kind in (None, "", "card"):
        rows = (
            await session.execute(
                select(Card.id, Card.term, Card.body)
                .where(visible(), Card.term.ilike(pat, escape="\\") | Card.body.ilike(pat, escape="\\"))
                .order_by(Card.id)
                .limit(SEARCH_CAPS["card"])
            )
        ).all()
        pm = await _states(session, CardProgress, "card_id", user_id, [r.id for r in rows])
        for r in rows:
            p = pm.get(r.id)
            hits.append({
                "kind": "card", "id": r.id, "title": r.term,
                "snippet": snippet(r.body if q.lower() in (r.body or "").lower() else r.term, q),
                "state": derive_state(p), "starred": bool(p and p.starred),
            })
    if kind in (None, "", "chapter"):
        rows = (
            await session.execute(
                select(Chapter.id, Chapter.title, Chapter.content_md)
                .where(Chapter.content_md.ilike(pat, escape="\\"))
                .order_by(Chapter.id)
                .limit(SEARCH_CAPS["chapter"])
            )
        ).all()
        for r in rows:
            hits.append({
                "kind": "chapter", "id": r.id, "title": r.title,
                "snippet": snippet(split_fm(r.content_md)[1], q), "state": "", "starred": False,
            })
    return hits[:SEARCH_TOTAL]
