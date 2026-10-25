"""服务端 Markdown → 安全 HTML 渲染（移植自旧 server_cloud.py 的 md/card_md/sanitize_html）。"""
import re
import urllib.parse
import xml.etree.ElementTree as etree
from html import escape, unescape
from html.parser import HTMLParser

import markdown
from markdown.extensions import Extension
from markdown.inlinepatterns import InlineProcessor

_KW = re.compile(
    r"(首选|金标准|(?<![明未])确诊(?!断)|最可能|禁忌|禁用|(?<![非不])特征性"
    r"|(?<!非)特异性|标志物|(?<!不)典型表现|必须|不可)"
)
_NEGATED = re.compile(r"(?:并非|不是|不能|不宜|不应|未能|尚未|无需|没有|不|未|非|无)[^，。；：！？\n]{0,6}$")
_YR = re.compile(r"(?<=[（(])(?:19|20)\d{2}(?:[,、．](?:19|20)\d{2})*(?=[)）])")
_STAR = re.compile(r"★+")
_TAG = re.compile(r"（(重复[^）]*|争议[^）]*|易错[^）]*|口诀[^）]*|正确率低[^）]*|死记[^）]*|高频[^）]*)）")

_MD_TAGS = {
    "p", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "li", "blockquote", "pre", "code",
    "em", "strong", "b", "i", "u", "s", "del", "ins", "mark", "span", "a", "img", "table", "thead",
    "tbody", "tr", "th", "td", "sup", "sub", "small", "div", "details", "summary",
}
_MD_ATTR = {
    "a": {"href", "title", "class"}, "img": {"src", "alt", "title", "loading"},
    "mark": {"class"}, "span": {"class"}, "li": {"class"}, "code": {"class"}, "div": {"class"},
    "td": {"colspan", "rowspan"}, "th": {"colspan", "rowspan"}, "details": {"open"},
}
_MD_CLS = {"ex", "yr", "kw", "sec", "tag", "manual"}
_MD_URL = re.compile(r"(?i)^\s*(/|https?:|data:image/|#|mailto:)")
_MD_DROP = {"script", "style", "iframe", "object", "embed", "form", "link", "meta", "base"}
_MD_VOID = {"br", "hr", "img"}
_IMG_HOSTS = r"(?:ixunke\.com|ixunke\.cn|youjiangt\.top)"
_DETAILS = re.compile(r"<details(?P<attrs>\s[^>]*)?>(?P<body>.*?)</details\s*>", re.I | re.S)
_SUMMARY = re.compile(r"<summary(?:\s[^>]*)?>(?P<text>.*?)</summary\s*>", re.I | re.S)


class _Sanitizer(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in _MD_DROP:
            self.skip += 1
            return
        if tag not in _MD_TAGS:
            return
        keep = []
        for k, v in attrs:
            k = k.lower()
            if k not in _MD_ATTR.get(tag, ()):
                continue
            v = v or ""
            if k in ("href", "src"):
                if re.sub(r"[\s\x00-\x1f]+", "", v).lower().startswith("javascript:") or not _MD_URL.match(v):
                    continue
            elif k == "class":
                v = " ".join(x for x in v.split() if x in _MD_CLS)
                if not v:
                    continue
            keep.append((k, v))
        at = "".join(' {}="{}"'.format(k, v.replace("&", "&amp;").replace('"', "&quot;")) for k, v in keep)
        self.out.append("<{}{}{}>".format(tag, at, "/" if tag in _MD_VOID else ""))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in _MD_VOID and tag in _MD_TAGS:
            self.out.append("</{}>".format(tag))

    def handle_endtag(self, tag):
        if tag in _MD_DROP:
            self.skip = max(0, self.skip - 1)
            return
        if tag in _MD_TAGS and tag not in _MD_VOID:
            self.out.append("</{}>".format(tag))

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def sanitize_html(html: str) -> str:
    p = _Sanitizer()
    p.feed(html or "")
    p.close()
    return "".join(p.out)


class _ManualHighlight(InlineProcessor):
    def handleMatch(self, match, data):
        if not match.group(1).strip():
            return None, None, None
        element = etree.Element("mark", {"class": "manual"})
        element.text = match.group(1)
        return element, match.start(0), match.end(0)


class _HighlightExtension(Extension):
    def extendMarkdown(self, md):
        md.inlinePatterns.register(
            _ManualHighlight(r"(?<![=])==((?:(?!==).)+?)==(?![=])", md),
            "manual-highlight", 175,
        )


class _TextHighlights(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out: list[str] = []
        self.stack: list[str] = []
        self.context = ""

    def handle_starttag(self, tag, attrs):
        self.out.append(self.get_starttag_text())
        if tag in {"p", "br", "li", "th", "td", "h1", "h2", "h3", "h4", "pre"}:
            self.context = ""
        if tag not in _MD_VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.out.append(f"</{tag}>")
        if tag in self.stack:
            del self.stack[len(self.stack) - 1 - self.stack[::-1].index(tag):]

    def handle_entityref(self, name):
        self.out.append(f"&{name};")
        self.context = (self.context + unescape(f"&{name};"))[-32:]

    def handle_charref(self, name):
        self.out.append(f"&#{name};")
        self.context = (self.context + unescape(f"&#{name};"))[-32:]

    def handle_data(self, data):
        if any(tag in {"mark", "code", "pre", "span"} for tag in self.stack):
            self.out.append(escape(data, quote=False))
            self.context = (self.context + data)[-32:]
            return
        matches = [(m.start(), m.end(), "kw") for m in _KW.finditer(data)
                   if not _NEGATED.search((self.context + data[:m.start()])[-12:])]
        matches += [(m.start(), m.end(), "yr") for m in _YR.finditer(data)]
        matches += [(m.start(), m.end(), "ex") for m in _STAR.finditer(data)]
        pos = 0
        for start, end, cls in sorted(matches):
            if start < pos:
                continue
            self.out.append(escape(data[pos:start], quote=False))
            tag = "mark" if cls == "kw" else "span"
            self.out.append(f'<{tag} class="{cls}">{escape(data[start:end], quote=False)}</{tag}>')
            pos = end
        self.out.append(escape(data[pos:], quote=False))
        self.context = (self.context + data)[-32:]


def _text_highlights(html: str) -> str:
    parser = _TextHighlights()
    parser.feed(html)
    parser.close()
    return "".join(parser.out)


def _markdown_source(s: str) -> str:
    """Keep the app's hard-break and table cleanup rules for nested blocks too."""
    lines: list[str] = []
    in_table = False
    for ln in s.split("\n"):
        stripped = ln.strip()
        tbl = re.sub(r"^[-*•]\s+", "", stripped)
        if tbl == "|":
            continue
        if tbl.startswith("|") and tbl.endswith("|") and tbl.count("|") >= 2:
            if not in_table and lines and lines[-1].strip() != "":
                lines.append("")
            in_table = True
            lines.append(re.sub(r"\|+$", "|", tbl))
            continue
        if in_table and stripped:
            lines.append("")
        in_table = False
        lines.append(ln + "  " if stripped else ln)
    return "\n".join(lines)


def _markdown_html(s: str) -> str:
    return markdown.markdown(
        _markdown_source(s),
        extensions=["tables", "fenced_code", _HighlightExtension()],
    )


def _render_details(s: str) -> tuple[str, list[tuple[str, str]]]:
    """Render Markdown inside HTML details blocks before the outer Markdown pass.

    Python-Markdown treats a raw HTML block as opaque, so Markdown images and
    links inside <details> otherwise leak to clients as literal source text.
    Comment placeholders keep the rendered block intact during the outer pass.
    """
    blocks: list[tuple[str, str]] = []

    def replace(match: re.Match[str]) -> str:
        body = match.group("body")
        summary_match = _SUMMARY.search(body)
        if summary_match:
            summary_html = _markdown_html(summary_match.group("text")).strip()
            if summary_html.startswith("<p>") and summary_html.endswith("</p>"):
                summary_html = summary_html[3:-4]
            summary = "<summary>" + summary_html + "</summary>"
            body = body[:summary_match.start()] + body[summary_match.end():]
        else:
            summary = ""
        rendered = _markdown_html(body)
        attrs = match.group("attrs") or ""
        block = f"<details{attrs}>{summary}{rendered}</details>"
        marker = f"<!--MEDKBDETAILBLOCK{len(blocks)}-->"
        blocks.append((marker, block))
        return marker

    return _DETAILS.sub(replace, s), blocks


def md(s: str | None) -> str:
    if not s:
        return ""
    source, detail_blocks = _render_details(s)
    html = _markdown_html(source)
    for marker, block in detail_blocks:
        html = html.replace(marker, block)
    html = re.sub(r"<!--.*?-->", "", html)
    html = re.sub(
        r'src="(https?://[^"]*' + _IMG_HOSTS + r'/[^"]+)"',
        lambda m: 'src="/img_proxy?u=' + urllib.parse.quote(m.group(1), safe="") + '"',
        html,
    )
    return _text_highlights(sanitize_html(html))


def _split_semi(b: str) -> list[str]:
    parts, cur, bold, manual, i = [], [], False, False, 0
    while i < len(b):
        if b[i : i + 2] == "==":
            manual = not manual
            cur.append("==")
            i += 2
            continue
        if b[i : i + 2] == "**":
            bold = not bold
            cur.append("**")
            i += 2
            continue
        if b[i] == "；" and not bold and not manual:
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(b[i])
        i += 1
    parts.append("".join(cur))
    return parts


def card_md(body: str | None) -> str:
    """考点卡正文排版：清残留标记、分号拆列表行、括号提示转小标签。"""
    b = re.sub(r"`", "", body or "").strip()
    b = _TAG.sub(r'<span class="tag">\1</span>', b)
    if "；" in b and "\n" not in b:
        parts = [p.strip().rstrip("；") for p in _split_semi(b) if p.strip()]
        if len(parts) >= 3:
            b = "\n".join("- " + p for p in parts)
    return md(b)
