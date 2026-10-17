import re

import pytest

from app.models import Card, Chapter, User
from app.schemas.provenance import ContentCitationIn
from app.services import chat_agent, knowledge, provenance


def chapter(chapter_id, body, title="内分泌代谢"):
    return Chapter(id=chapter_id, kind="note", subject="内科学", title=title, content_md=body, pages=[])


async def cite(session, target_type, target_id):
    if await session.get(User, 7) is None:
        session.add(User(id=7, username="editor", password_hash="x", is_admin=True))
        await session.flush()
    await provenance.seed_textbooks(session)
    await provenance.replace_citations(session, target_type, target_id, [ContentCitationIn(
        source_key="rjws-internal-medicine-10", chapter="内分泌和代谢性疾病",
        section="糖尿病", page_start=745, page_end=746, status="verified",
    )], admin_id=7)
    await session.commit()


def extract_range(result):
    match = re.search(r"原文范围：\[(\d+), (\d+)\) / (\d+) 字符", result)
    assert match is not None
    return tuple(map(int, match.groups()))


@pytest.mark.asyncio
async def test_search_long_chapter_returns_actual_hit_and_intact_citation(session):
    body = "# 内分泌代谢\n" + "无关基础内容。\n" * 1800 + "## DKA处理\n补钾定位词：血钾 < 3.3 时先补钾。\n" + "尾部说明。\n" * 300
    session.add(chapter(6, body))
    await session.commit()
    await cite(session, "chapter", 6)

    result = (await knowledge.search(session, "补钾定位词"))[0]

    assert "补钾定位词：血钾 < 3.3 时先补钾。" in result
    assert "定位小节：DKA处理" in result
    start, end, total = extract_range(result)
    assert start > 10000
    assert start <= body.index("补钾定位词") < end
    assert end - start <= 1500
    assert total == len(body.strip())
    assert 'kb_read(name="#6", offset=' in result
    assert "人民卫生出版社《内科学》第十版" in result
    assert "第 745-746 页（已核验）" in result


@pytest.mark.asyncio
async def test_search_long_card_returns_alias_hit_and_comparison_symbols(session):
    body = "既有背卡内容。\n" * 1000 + "## 病因\n慢性肺心病的血气：PaCO2 > 50，PaO2 < 60。"
    session.add(Card(id=21, subject="内科学", part="呼吸", section="", term="呼吸综合", hint="", body=body))
    await session.commit()
    await cite(session, "card", 21)

    result = (await knowledge.search(session, "肺心"))[0]

    assert "慢性肺心病的血气：PaCO2 > 50，PaO2 < 60。" in result
    assert "定位小节：病因" in result
    assert extract_range(result)[0] > 4000
    assert "仅展示命中附近片段，非完整背卡" in result
    assert "已核验" in result


@pytest.mark.asyncio
async def test_search_literal_wildcards_do_not_match_unrelated_content(session):
    session.add_all([chapter(1, "普通内容"), chapter(2, "标记_%的原文")])
    await session.commit()
    result = await knowledge.search(session, "_%")
    assert len(result) == 1
    assert "章节 #2" in result[0]


@pytest.mark.asyncio
async def test_read_paginates_without_omissions_and_strips_frontmatter_once(session):
    body = "## 目录\n" + "逐行正文，包含 < 与 > 比较符。\n" * 550 + "正文最后一句。"
    session.add(chapter(6, "---\nsource: metadata-only\n---\n" + body))
    await session.commit()
    await cite(session, "chapter", 6)

    offset = 0
    pieces = []
    for _ in range(10):
        result = await knowledge.read(session, "#6", offset=offset)
        start, end, total = extract_range(result)
        assert start == offset
        assert 0 < end - start <= 4000
        assert total == len(body)
        assert body[start:end] in result
        assert "metadata-only" not in result
        assert "已核验" in result
        pieces.append(body[start:end])
        if end == total:
            assert "已到正文末尾" in result
            break
        assert f'续读：kb_read(name="#6", offset={end})' in result
        offset = end
    else:
        pytest.fail("pagination did not reach the end")
    assert "".join(pieces) == body


@pytest.mark.asyncio
async def test_read_query_lands_in_tail_and_explicit_offset_takes_precedence(session):
    body = "前部内容。\n" * 2200 + "## 胰岛素瘤\n尾部定位词和第十版校注。\n" + "后续细节。\n" * 1000
    session.add(chapter(6, body))
    await session.commit()

    result = await knowledge.read(session, "内分泌代谢", query="尾部定位词")
    start, end, total = extract_range(result)
    assert start > 10000
    assert "尾部定位词和第十版校注。" in result
    assert "定位小节：胰岛素瘤" in result
    assert end < total

    following = await knowledge.read(session, "#6", query="尾部定位词", offset=end)
    assert extract_range(following)[0] == end
    assert "尾部定位词" not in following


@pytest.mark.asyncio
async def test_read_missing_query_reports_fallback_and_ids_disambiguate_titles(session):
    session.add_all([chapter(1, "第一个同名章节"), chapter(2, "第二个同名章节")])
    await session.commit()
    result = await knowledge.read(session, "#2", query="并不存在的词")
    assert "第二个同名章节" in result
    assert "第一个同名章节" not in result
    assert "正文未命中定位词" in result
    assert "开头片段" in result
    assert await knowledge.read(session, "#999") == ""


@pytest.mark.asyncio
async def test_read_bounds_limit_and_end_offset(session):
    body = "全文" * 10000
    session.add(chapter(6, body))
    await session.commit()

    result = await knowledge.read(session, "#6", 100000)
    assert extract_range(result) == (0, 8000, 20000)
    after_end = await knowledge.read(session, "#6", offset=50000)
    assert extract_range(after_end) == (20000, 20000, 20000)
    assert "已到正文末尾" in after_end
    assert "续读：" not in after_end


@pytest.mark.asyncio
async def test_tool_read_supports_locator_and_continuation(session):
    body = "前文。\n" * 3000 + "## 尾部\n工具定位词。\n" + "后文。\n" * 1200
    session.add(chapter(6, body))
    await session.commit()
    result = await chat_agent._tool_exec("kb_read", {"name": "#6", "query": "工具定位词"}, session, [])
    start, end, _ = extract_range(result)
    assert start > 4000 and "工具定位词。" in result
    continuation = await chat_agent._tool_exec("kb_read", {"name": "#6", "offset": end}, session, [])
    assert extract_range(continuation)[0] == end
    invalid = await chat_agent._tool_exec("kb_read", {"name": "#6", "offset": "invalid"}, session, [])
    assert "offset 必须" in invalid


@pytest.mark.asyncio
async def test_tool_search_does_not_cut_third_result_citations(session):
    for chapter_id in range(1, 4):
        session.add(chapter(chapter_id, "共同检索词" + "完整正文" * 500, title=f"章节{chapter_id}"))
    await session.commit()
    for chapter_id in range(1, 4):
        await cite(session, "chapter", chapter_id)

    result = await chat_agent._tool_exec("kb_search", {"query": "共同检索词"}, session, [])
    assert len(result) > 4000
    assert result.count("教材出处：") == 3
    assert result.count("第 745-746 页（已核验）") == 3
    assert result.count("续读：") == 3


def test_kb_tool_contract_is_truthful_and_exposes_offsets():
    functions = {item["function"]["name"]: item["function"] for item in chat_agent.TOOLS}
    assert "BM25" not in functions["kb_search"]["description"]
    read = functions["kb_read"]
    assert "分段" in read["description"]
    assert {"name", "query", "offset"} <= read["parameters"]["properties"].keys()
    assert read["parameters"]["properties"]["offset"]["minimum"] == 0


@pytest.mark.parametrize("text", ["> 50 为比较条件", "< 3.3 时先处理"])
def test_plain_preserves_line_leading_medical_comparisons(text):
    assert knowledge._plain(text) == text


@pytest.mark.parametrize("text", [
    "AB>SB呼酸、AB<SB呼碱。ARDS：PAWP<12，心源性>18",
    "Hb<110g/L，PaO2<60mmHg、PaCO2>50mmHg；AB<SB提示呼碱，AB>SB提示呼酸。",
    "Hb<100且PaO2<60；pH<7.35；HCO3<22，K>5.5；AB<SB，SB>AB。",
])
def test_plain_preserves_mixed_medical_comparison_expressions(text):
    assert knowledge._plain(text) == text


def test_plain_removes_known_html_tags_without_swallowing_medical_text():
    text = '<p class="note"><strong>AB>SB</strong>呼酸、AB<SB呼碱。<br/>Hb<110；PaO<sub>2</sub><60。</p>'
    result = knowledge._plain(text)
    assert "<p" not in result and "<strong>" not in result and "<sub>" not in result
    assert "AB>SB" in result and "AB<SB呼碱" in result and "Hb<110" in result
    assert "PaO 2 <60" in result


@pytest.mark.parametrize("query", ["CKD分期", "教材校注·透析时机与历史分期", "心功能分期"])
def test_generic_staging_does_not_expand_to_tumor(query):
    assert "肿瘤" not in knowledge.expand_aliases(query)
    assert knowledge.expand_aliases("肿瘤分期") == "肿瘤分期"


@pytest.mark.parametrize("short_name", ["心衰", "高钾", "肾炎"])
def test_window_prefers_literal_query_over_earlier_alias(short_name):
    alias = knowledge.ALIAS[short_name]
    query = "教材" + short_name + "定位小节"
    body = (alias + "相关内容。\n") * 600 + "\n## 精确小节\n" + query + "原文定位。"
    start, end, hit = knowledge._window(body, 500, knowledge._terms(query))
    assert hit == body.index(query)
    assert query + "原文定位。" in body[start:end]


@pytest.mark.asyncio
async def test_read_and_ai_tool_prefer_exact_heading_over_aliases(session):
    query = "教材校注·透析时机与历史分期"
    body = "## 肿瘤\n" + "肿瘤基础知识。\n" * 1200 + "## " + query + "\n精确校注内容。"
    session.add(chapter(6, body))
    await session.commit()
    for result in [
        await knowledge.read(session, "#6", query=query),
        await chat_agent._tool_exec("kb_read", {"name": "#6", "query": query}, session, []),
    ]:
        assert query in result
        assert "精确校注内容。" in result
        assert extract_range(result)[0] > 4000


@pytest.mark.asyncio
async def test_search_preserves_real_respiratory_comparison_content(session):
    original = "AB>SB呼酸、AB<SB呼碱。ARDS：PAWP<12，心源性>18"
    session.add(chapter(1, "# 呼吸系统疾病\n" + "其他内容。\n" * 1000 + original))
    await session.commit()
    result = (await knowledge.search(session, "ARDS"))[0]
    assert original in result
