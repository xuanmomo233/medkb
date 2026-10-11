"""服务端 Markdown → 安全 HTML 渲染（移植自旧 server_cloud.py 的 md/card_md/sanitize_html）。"""
import re
import urllib.parse
from html.parser import HTMLParser

import markdown

_KW = re.compile(
    r"(首选|金标准|(?<![明未])确诊(?!断)|最可能|禁忌|禁用|(?<![非不])特征性"
    r"|(?<!非)特异性|标志物|(?<!不)典型表现|必须|不可)"
)
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
_MD_CLS = {"ex", "yr", "kw", "sec", "tag"}
_MD_URL = re.compile(r"(?i)^\s*(/|https?:|data:image/|#|mailto:)")
_MD_DROP = {"script", "style", "iframe", "object", "embed", "form", "link", "meta", "base"}
_MD_VOID = {"br", "hr", "img"}
_IMG_HOSTS = r"(?:ixunke\.com|ixunke\.cn|youjiangt\.top)"


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


def md(s: str | None) -> str:
    if not s:
        return ""
    lines: list[str] = []
    in_table = False
    for ln in s.split("\n"):
        if "](" not in ln:
            ln = _STAR.sub(r'<span class="ex">\g<0></span>', ln)
            ln = _YR.sub(r'<span class="yr">\g<0></span>', ln)
            ln = _KW.sub(r'<mark class="kw">\1</mark>', ln)
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
    html = markdown.markdown("\n".join(lines), extensions=["tables"])
    html = re.sub(r"<!--.*?-->", "", html).replace("**", "")
    html = re.sub(
        r'src="(https?://[^"]*' + _IMG_HOSTS + r'/[^"]+)"',
        lambda m: 'src="/img_proxy?u=' + urllib.parse.quote(m.group(1), safe="") + '"',
        html,
    )
    return sanitize_html(html)


def _split_semi(b: str) -> list[str]:
    parts, cur, bold, i = [], [], False, 0
    while i < len(b):
        if b[i : i + 2] == "**":
            bold = not bold
            cur.append("**")
            i += 2
            continue
        if b[i] == "；" and not bold:
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
