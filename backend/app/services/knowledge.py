"""AI 使用的数据库知识检索；运行时内容与网页/App 共用同一数据源。"""

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Card, Chapter
from app.services import provenance
from app.services.card_merges import visible

ALIAS = {
    "心梗": "冠心病", "心肌梗死": "冠心病", "心衰": "心力衰竭",
    "肾衰": "肾功能衰竭", "肺心": "慢性肺心病", "支扩": "支气管扩张",
    "哮喘": "支气管哮喘", "慢阻肺": "COPD", "肺栓塞": "急性肺血栓栓塞",
    "肺栓": "急性肺血栓栓塞", "甲亢": "甲状腺功能亢进", "甲减": "甲状腺功能减退",
    "溃结": "溃疡性结肠炎", "再障": "再生障碍性贫血", "缺铁贫": "缺铁性贫血",
    "巨幼贫": "巨幼细胞贫血", "慢粒": "慢性粒细胞白血病", "慢淋": "慢性淋巴细胞白血病",
    "急淋": "急性淋巴细胞白血病", "胆石": "胆石症", "糖尿": "糖尿病",
    "乙肝": "病毒性肝炎", "丙肝": "病毒性肝炎", "房颤": "心房颤动",
    "室速": "室性心动过速", "房早": "房性期前收缩", "高钾": "高钾血症",
    "低钾": "低钾血症", "呼衰": "呼吸衰竭", "肾综": "肾病综合征",
    "肾炎": "肾小球肾炎", "瓣膜": "心脏瓣膜病", "癌症": "肿瘤",
    "癌肿": "肿瘤", "肿瘤分期": "肿瘤", "分期": "肿瘤",
}
KNOWN_NAMES = sorted(set(ALIAS.values()) | {
    "生理学", "生物化学", "病理学", "诊断学", "内科学", "外科学", "医学人文",
}, key=len, reverse=True)


def expand_aliases(message: str) -> str:
    expanded = message
    for alias, full in ALIAS.items():
        if alias in message and full not in expanded:
            expanded += " " + full
    return expanded


def find_names(message: str) -> list[str]:
    return [name for name in KNOWN_NAMES if name in message]


def _like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _body(content: str) -> str:
    text = content or ""
    if text.startswith("---"):
        match = re.match(r"^---\s*\n.*?\n---\s*\n?", text, re.S)
        if match:
            text = text[match.end():]
    return text.strip()


def _plain(content: str, limit: int = 1500) -> str:
    text = re.sub(r"!\[[^]]*]\([^)]*\)|<[^>]+>|[#*`>|]+", " ", _body(content))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _with_sources(label: str, text: str, citations: list[dict]) -> str:
    refs = "；".join(provenance.citation_label(c) for c in citations)
    source_line = refs if refs else "尚无结构化教材出处（内容待按人卫第十版核验）"
    return f"【{label}】\n{text}\n教材出处：{source_line}"


async def toc(session: AsyncSession, limit: int = 6000) -> str:
    rows = (await session.execute(
        select(Chapter.id, Chapter.subject, Chapter.title).order_by(Chapter.subject, Chapter.title)
    )).all()
    grouped: dict[str, list[str]] = {}
    for row in rows:
        grouped.setdefault(row.subject or "未分类", []).append(f"#{row.id} {row.title}")
    return "\n".join(
        f"{subject}：" + "、".join(titles) for subject, titles in grouped.items()
    )[:limit]


async def search(session: AsyncSession, query: str, limit: int = 3) -> list[str]:
    query = (query or "").strip()[:100]
    if not query:
        return []
    terms = [query]
    expanded = expand_aliases(query)
    terms.extend(x for x in expanded.split() if x != query)
    terms = list(dict.fromkeys(terms))[:4]
    conditions_chapter = []
    conditions_card = []
    for term in terms:
        pat = _like(term)
        conditions_chapter.extend((Chapter.title.ilike(pat, escape="\\"), Chapter.content_md.ilike(pat, escape="\\")))
        conditions_card.extend((Card.term.ilike(pat, escape="\\"), Card.body.ilike(pat, escape="\\")))
    from sqlalchemy import or_

    chapters = (await session.execute(
        select(Chapter).where(or_(*conditions_chapter)).order_by(Chapter.id).limit(12)
    )).scalars().all()
    cards = (await session.execute(
        select(Card).where(visible(), or_(*conditions_card)).order_by(Card.id).limit(12)
    )).scalars().all()
    candidates = []
    ql = query.lower()
    for chapter in chapters:
        title = chapter.title or ""
        text = _plain(chapter.content_md)
        score = (8 if title.lower() == ql else 5 if ql in title.lower() else 1)
        candidates.append((score, "chapter", chapter.id, f"章节 #{chapter.id} · {chapter.subject} · {title}", text))
    for card in cards:
        term = card.term or ""
        text = _plain(card.body)
        score = (7 if term.lower() == ql else 4 if ql in term.lower() else 1)
        candidates.append((score, "card", card.id, f"背卡 #{card.id} · {card.subject} · {term}", text))
    candidates.sort(key=lambda row: (-row[0], row[1], row[2]))
    chosen = candidates[:max(1, min(limit, 8))]
    by_type: dict[str, list[int]] = {}
    for _, target_type, target_id, _, _ in chosen:
        by_type.setdefault(target_type, []).append(target_id)
    citations = {
        target_type: await provenance.citations_for_targets(session, target_type, ids)
        for target_type, ids in by_type.items()
    }
    return [
        _with_sources(label, text, citations.get(target_type, {}).get(target_id, []))
        for _, target_type, target_id, label, text in chosen
    ]


async def read(session: AsyncSession, name: str, limit: int = 4000) -> str:
    name = (name or "").strip()[:200]
    if not name:
        return ""
    exact = (await session.execute(
        select(Chapter).where(Chapter.title == name).order_by(Chapter.id).limit(1)
    )).scalar_one_or_none()
    row = exact
    if row is None:
        row = (await session.execute(
            select(Chapter).where(Chapter.title.contains(name, autoescape=True)).order_by(Chapter.id).limit(1)
        )).scalar_one_or_none()
    if row is None:
        return ""
    citations = await provenance.citations_for_target(session, "chapter", row.id)
    return _with_sources(f"章节 #{row.id} · {row.subject} · {row.title}", _body(row.content_md)[:limit], citations)
