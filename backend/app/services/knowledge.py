"""AI 使用的数据库知识检索；运行时内容与网页/App 共用同一数据源。"""

import json
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
    # Only remove markup, not medical comparison signs such as K < 3.3 or pH > 7.1.
    text = re.sub(r"!\[[^]]*]\([^)]*\)", " ", content)
    # An arbitrary '<letters ... >' can be a comparison (e.g. AB<SB), not HTML.
    # Only recognize known presentation tags with an actual tag-name boundary.
    text = re.sub(
        r"</?(?:a|abbr|b|blockquote|br|caption|code|del|div|em|h[1-6]|hr|i|img|li|ol|p|pre|"
        r"s|small|span|strong|sub|sup|table|tbody|td|th|thead|tr|u|ul)(?=\s|/?>)[^<>]*>",
        " ", text, flags=re.I,
    )
    text = re.sub(r"(?m)^\s*#{1,6}\s+", "", text)
    text = text.replace("**", "").replace("`", "").replace("|", " ")
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _terms(query: str) -> list[str]:
    query = (query or "").strip()[:100]
    if not query:
        return []
    return list(dict.fromkeys([query, *expand_aliases(query).split()]))[:4]


def _window(text: str, limit: int, terms: list[str], offset: int | None = None) -> tuple[int, int, int | None]:
    """Return a bounded slice in body-character coordinates, not flattened text."""
    limit = max(1, min(limit, 8000))
    hit = None
    if offset is not None:
        start = max(0, min(offset, len(text)))
    else:
        lower = text.lower()
        candidates = []
        for term in terms:
            position = 0
            # Bound work even when a common term occurs thousands of times.
            for _ in range(16):
                position = lower.find(term.lower(), position)
                if position < 0:
                    break
                candidates.append(position)
                position += max(1, len(term))
        if candidates:
            def score(position):
                start = max(0, position - limit // 4)
                fragment = lower[start:start + limit]
                return (sum(term.lower() in fragment for term in terms), -position)
            hit = max(candidates, key=score)
        start = max(0, hit - limit // 4) if hit is not None else 0
        if start and hit is not None:
            # Prefer a paragraph/line boundary before the hit when one is nearby.
            boundary = text.find("\n", start, hit)
            if boundary >= 0:
                start = boundary + 1
    end = min(len(text), start + limit)
    if end < len(text):
        boundary = text.rfind("\n", start + limit // 2, end)
        if boundary >= 0 and (hit is None or boundary > hit):
            end = boundary + 1
    return start, end, hit


def _located_text(text: str, start: int, end: int, hit: int | None, *, chapter_id: int | None, plain: bool) -> str:
    """Expose stable offsets so the agent can fetch omitted context explicitly."""
    location = f"原文范围：[{start}, {end}) / {len(text)} 字符（正文去除前置元数据，offset 从 0 起）"
    anchor = hit if hit is not None else start
    headings = [match for match in re.finditer(r"(?m)^#{1,6}\s+(.+)$", text) if match.start() <= anchor]
    if headings:
        location += f"\n定位小节：{headings[-1].group(1).strip()}"
    fragment = text[start:end]
    if plain:
        fragment = _plain(fragment)
    navigation = []
    if chapter_id is not None:
        if start:
            navigation.append(f'前文未展示；可用 kb_read(name="#{chapter_id}", offset=0) 从头读取')
        if end < len(text):
            navigation.append(f'续读：kb_read(name="#{chapter_id}", offset={end})')
        else:
            navigation.append("已到正文末尾")
    elif start or end < len(text):
        navigation.append("仅展示命中附近片段，非完整背卡")
    return "\n".join([location, fragment, *navigation])


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
    terms = _terms(query)
    if not terms:
        return []
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
        body = _body(chapter.content_md)
        start, end, hit = _window(body, 1500, terms)
        text = _located_text(body, start, end, hit, chapter_id=chapter.id, plain=True)
        score = (8 if title.lower() == ql else 5 if ql in title.lower() else 1)
        candidates.append((score, "chapter", chapter.id, f"章节 #{chapter.id} · {chapter.subject} · {title}", text))
    for card in cards:
        term = card.term or ""
        body = _body(card.body)
        start, end, hit = _window(body, 1500, terms)
        text = _located_text(body, start, end, hit, chapter_id=None, plain=True)
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


async def read(
    session: AsyncSession, name: str, limit: int = 4000, *, query: str = "", offset: int | None = None,
) -> str:
    name = (name or "").strip()[:200]
    if not name:
        return ""
    chapter_id = re.fullmatch(r"#([0-9]+)", name)
    if chapter_id:
        row = await session.get(Chapter, int(chapter_id.group(1)))
    else:
        row = (await session.execute(
            select(Chapter).where(Chapter.title == name).order_by(Chapter.id).limit(1)
        )).scalar_one_or_none()
    if row is None and not chapter_id:
        row = (await session.execute(
            select(Chapter).where(Chapter.title.contains(name, autoescape=True)).order_by(Chapter.id).limit(1)
        )).scalar_one_or_none()
    if row is None:
        return ""
    citations = await provenance.citations_for_target(session, "chapter", row.id)
    body = _body(row.content_md)
    terms = _terms(query)
    start, end, hit = _window(body, limit, terms, offset)
    text = _located_text(body, start, end, hit, chapter_id=row.id, plain=False)
    if terms and offset is None and hit is None:
        text = f"正文未命中定位词 {json.dumps(query[:100], ensure_ascii=False)}，以下为开头片段。\n{text}"
    return _with_sources(f"章节 #{row.id} · {row.subject} · {row.title}", text, citations)
