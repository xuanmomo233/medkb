import pytest
from fastapi import HTTPException

from app.models import Card, Chapter, ContentCitation, User
from app.schemas.provenance import ContentCitationIn
from app.services import knowledge, provenance


async def seed(session):
    session.add(User(id=7, username="editor", password_hash="x", is_admin=True))
    session.add(Chapter(
        id=11, kind="note", subject="内科学", title="心力衰竭",
        content_md="# 心力衰竭\n数据库当前章节内容", source_file="知识点/内科学.md", pages=[],
    ))
    session.add(Card(
        id=21, subject="内科学", part="循环系统", section="心力衰竭",
        term="射血分数降低的心力衰竭", hint="", body="数据库当前背卡内容", source_file="batch",
    ))
    await session.commit()
    await provenance.seed_textbooks(session)


@pytest.mark.asyncio
async def test_verified_textbook_citation_is_structured_and_visible_to_ai(session):
    await seed(session)
    sources = await provenance.list_sources(session)
    assert len(sources) == 13
    assert any(source["title"] == "妇产科学" for source in sources)
    changed = await provenance.replace_citations(session, "card", 21, [ContentCitationIn(
        source_key="rjws-internal-medicine-10", chapter="循环系统疾病", section="心力衰竭",
        page_start=166, page_end=168, note="按教材表述核对", status="verified",
    )], admin_id=7)
    await session.commit()
    assert changed == 1

    citations = await provenance.citations_for_target(session, "card", 21)
    assert citations[0]["publisher"] == "人民卫生出版社"
    assert citations[0]["edition"] == "第十版"
    assert citations[0]["verified_by"] == 7
    assert citations[0]["verified_at"] is not None

    snippets = await knowledge.search(session, "射血分数降低", 3)
    assert any("数据库当前背卡内容" in snippet for snippet in snippets)
    assert any("人民卫生出版社《内科学》第十版" in snippet and "已核验" in snippet for snippet in snippets)


@pytest.mark.asyncio
async def test_unverified_citation_does_not_claim_verification_and_unknown_source_is_rejected(session):
    await seed(session)
    await provenance.replace_citations(session, "chapter", 11, [ContentCitationIn(
        source_key="rjws-internal-medicine-10", chapter="循环系统疾病", status="unverified",
    )], admin_id=7)
    await session.commit()
    citation = (await provenance.citations_for_target(session, "chapter", 11))[0]
    assert citation["verified_by"] is None
    assert citation["verified_at"] is None
    text = await knowledge.read(session, "心力衰竭")
    assert "数据库当前章节内容" in text
    assert "待核验" in text

    with pytest.raises(HTTPException, match="未知或停用的教材"):
        await provenance.replace_citations(session, "chapter", 11, [ContentCitationIn(
            source_key="invented-book", chapter="循环系统疾病", status="verified",
        )], admin_id=7)


@pytest.mark.asyncio
async def test_replacing_citations_is_idempotent_and_rejects_duplicate_locations(session):
    await seed(session)
    item = ContentCitationIn(source_key="rjws-internal-medicine-10", chapter="循环系统疾病")
    assert await provenance.replace_citations(session, "card", 21, [item], 7) == 1
    await session.commit()
    assert await provenance.replace_citations(session, "card", 21, [item], 7) == 0
    assert await session.get(ContentCitation, 1) is not None
    with pytest.raises(HTTPException, match="不能重复添加"):
        await provenance.replace_citations(session, "card", 21, [item, item], 7)
