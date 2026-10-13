from html.parser import HTMLParser

import pytest

from app.core.render import card_md, md


class Capture(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.attrs = []
        self.data = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.attrs.append((tag, dict(attrs)))

    def handle_data(self, text):
        self.data.append(text)


@pytest.mark.parametrize("text", [
    "首选", "金标准", "确诊", "特征性", "特异性", "典型表现", "禁用", "必须",
])
def test_positive_keywords(text):
    assert f'<mark class="kw">{text}</mark>' in md(text)


@pytest.mark.parametrize("text", [
    "非特异性", "不典型表现", "未确诊", "尚未确诊", "无法确诊",
    "不是金标准", "不建议首选", "不能作为标志物", "不具有特征性", "无特异性",
    "明确诊断", "非**特异性**", "尚未**确诊**", "不具有**特征性**",
    "&#38750;特异性", "<span>非</span>特异性",
])
def test_negated_keywords(text):
    assert 'class="kw"' not in md(text)


def test_negation_stops_at_clause_and_paragraph_boundaries():
    html = md("非特异性，首选\n\n金标准")
    assert '<mark class="kw">首选</mark>' in html
    assert '<mark class="kw">金标准</mark>' in html


@pytest.mark.parametrize("text", ["重点中文", " word ", "首选与金标准", "**重要**机制", "第一行\n第二行", "😀中文"])
def test_manual_highlight(text):
    html = md(f"前=={text}==后")
    assert '<mark class="manual">' in html
    assert 'class="kw"' not in html
    assert "==" not in "".join(Capture(html).data)


def test_manual_highlight_does_not_rewrite_code_or_url_attributes():
    html = md('`==首选==` [首选](https://example.org/首选?tag=★ "首选") ![首选](https://example.org/★.png)')
    captured = Capture(html)
    assert '<code>==首选==</code>' in html
    link = next(a for t, a in captured.attrs if t == "a")
    image = next(a for t, a in captured.attrs if t == "img")
    assert link["href"] == "https://example.org/首选?tag=★"
    assert link["title"] == "首选"
    assert image["src"] == "https://example.org/★.png"
    assert image["alt"] == "首选"


def test_fenced_code_is_protected_from_highlighting():
    html = md("```\n==首选==\n特异性 ★\n```")
    assert "<pre><code>" in html
    assert "<mark" not in html and 'class="ex"' not in html


def test_legacy_manual_markup_and_sanitization():
    html = md('<mark class="manual" onclick="bad()">首选</mark> <script>alert(1)</script> [bad](javascript:alert)')
    assert '<mark class="manual">首选</mark>' in html
    assert "onclick" not in html and "alert(1)" not in html and "javascript:" not in html


def test_table_keeps_cells_entities_and_inline_formatting():
    html = md("| 名称 | 机制 |\n| --- | --- |\n| A&#124;B | ==重点==<br>第二行 &amp; &lt;b&gt; |\n| 正常 | **首选** |")
    capture = Capture(html)
    assert sum(t == "td" for t, _ in capture.attrs) == 4
    assert "<table>" in html and '<mark class="manual">重点</mark>' in html
    assert "A|B" in "".join(capture.data)
    assert "<b>" in "".join(capture.data)
    assert "<strong>" in html


def test_empty_highlight_unmatched_markers_and_empty_content():
    assert "<mark" not in md("==   ==")
    assert "==未闭合" in md("==未闭合")
    assert md(None) == ""
    assert md("") == ""


def test_card_formatting_preserves_manual_and_legacy_tags():
    html = card_md("==机制==（易错）；第二项；第三项")
    assert '<mark class="manual">机制</mark>' in html
    assert 'class="tag"' in html
    assert "<li>" in html


def test_card_reflow_does_not_split_a_manual_highlight():
    html = card_md("==第一项；第二项；第三项==")
    assert '<mark class="manual">' in html
    assert "<li>" not in html
