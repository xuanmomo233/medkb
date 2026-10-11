"""知识库：md 文件索引 + 分块 + 中文单字/bigram BM25 检索。懒加载，线程安全；全部为同步函数，异步调用方请用 asyncio.to_thread。"""
import math
import os
import re
import threading
from dataclasses import dataclass, field

from app.core.config import get_settings

ALIAS = {
    "心梗": "冠心病", "心肌梗死": "冠心病", "心衰": "心衰",
    "心力衰竭": "心衰", "肾衰": "肾衰", "肾功能衰竭": "肾衰",
    "肺心": "慢性肺心病", "支扩": "支气管扩张", "哮喘": "支气管哮喘",
    "慢阻肺": "COPD", "肺栓塞": "急性肺血栓栓塞", "肺栓": "急性肺血栓栓塞",
    "甲亢": "甲状腺功能亢进", "甲减": "甲状腺功能减退",
    "溃结": "溃疡性结肠炎", "再障": "再生障碍性贫血",
    "缺铁贫": "缺铁性贫血", "巨幼贫": "巨幼细胞贫血",
    "慢粒": "慢性粒细胞白血病", "慢淋": "慢性淋巴细胞白血病",
    "急淋": "急性淋巴细胞白血病", "胆石": "胆石症",
    "糖尿": "糖尿病", "乙肝": "病毒性肝炎", "丙肝": "病毒性肝炎",
    "房颤": "心房颤动", "室速": "室性心动过速", "房早": "房性期前收缩",
    "高钾": "高钾血症", "低钾": "低钾血症", "呼衰": "呼吸衰竭",
    "肾综": "肾病综合征", "肾炎": "肾小球肾炎", "瓣膜": "心脏瓣膜病",
    "癌症": "肿瘤", "癌肿": "肿瘤", "肿瘤分期": "肿瘤", "分期": "肿瘤",
}

_SKIP_FILES = {"INDEX.md", "SYSTEM_INDEX.md"}
_CHUNK_MAX = 900
_K1 = 2.2


def expand_aliases(msg: str) -> str:
    exp = msg
    for a, full in ALIAS.items():
        if a in msg:
            exp += " " + full
    return exp


def tokenize(s: str) -> list[str]:
    toks: list[str] = []
    for m in re.finditer(r"[a-zA-Z0-9]+|[一-鿿]+", s.lower()):
        t = m.group(0)
        if t[0].isascii():
            toks.append(t)
        else:
            toks += list(t)
            toks += [t[i:i + 2] for i in range(len(t) - 1)]
    return toks


def _read(path: str, limit: int | None = None) -> str:
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read(limit) if limit else f.read()
    except OSError:
        return ""


def _chunk_text(txt: str, name: str) -> list[tuple[str, str]]:
    parts = re.split(r"(?m)^(#{1,4}\s+.+)$", txt)
    out: list[tuple[str, str]] = []

    def emit(title: str, body: str) -> None:
        body = body.strip()
        while len(body) > _CHUNK_MAX:
            cut = body.rfind("\n", 0, _CHUNK_MAX)
            if cut < 300:
                cut = _CHUNK_MAX
            if body[:cut].strip():
                out.append((title, body[:cut].strip()))
            body = body[cut:]
        if len(body) >= 30:
            out.append((title, body))

    if len(parts) == 1:
        emit(name, parts[0])
    else:
        if parts[0].strip():
            emit(name, parts[0])
        for i in range(1, len(parts), 2):
            h = parts[i].lstrip("#").strip()
            emit(h or name, parts[i + 1] if i + 1 < len(parts) else "")
    return out


@dataclass
class _Snapshot:
    kb_dir: str = ""
    index: dict[str, str] = field(default_factory=dict)
    names_by_len: list[str] = field(default_factory=list)
    chunks: list[dict] = field(default_factory=list)
    post: dict[str, dict[int, int]] = field(default_factory=dict)
    lens: list[int] = field(default_factory=list)
    idf: dict[str, float] = field(default_factory=dict)
    avg: float = 1.0


def _build(kb_dir: str) -> _Snapshot:
    s = _Snapshot(kb_dir=kb_dir)
    if not kb_dir or not os.path.isdir(kb_dir):
        return s
    for dp, dn, fs in os.walk(kb_dir):
        dn.sort()
        for f in sorted(fs):
            if not f.endswith(".md") or f in _SKIP_FILES:
                continue
            p = os.path.join(dp, f)
            name = re.sub(r"^\d+-", "", os.path.splitext(f)[0])
            for part in re.split(r"[、&＆，,;；\s]+", name):
                if len(part) >= 2:
                    s.index[part] = p
            s.index[name] = p
            for title, body in _chunk_text(_read(p), name):
                tf: dict[str, int] = {}
                for t in tokenize(title + "\n" + body):
                    tf[t] = tf.get(t, 0) + 1
                idx = len(s.chunks)
                s.chunks.append({"src": name, "title": title, "text": body[:1000]})
                s.lens.append(sum(tf.values()))
                for t, c in tf.items():
                    s.post.setdefault(t, {})[idx] = c
    n = len(s.chunks)
    if n:
        s.avg = sum(s.lens) / n
        for t, post in s.post.items():
            s.idf[t] = math.log((n - len(post) + 0.5) / (len(post) + 0.5) + 1)
    s.names_by_len = sorted(s.index, key=len, reverse=True)
    return s


_lock = threading.Lock()
_snap: _Snapshot | None = None


def _get() -> _Snapshot:
    global _snap
    kb_dir = get_settings().kb_dir
    snap = _snap
    if snap is not None and snap.kb_dir == kb_dir:
        return snap
    with _lock:
        if _snap is None or _snap.kb_dir != kb_dir:
            _snap = _build(kb_dir)
        return _snap


def reload() -> None:
    global _snap
    with _lock:
        _snap = None


def names() -> list[str]:
    return _get().names_by_len


def find_names(text: str, min_len: int = 2) -> list[str]:
    return [n for n in _get().names_by_len if len(n) >= min_len and n in text]


def find_path(name: str) -> str | None:
    idx = _get().index
    p = idx.get(name)
    if p:
        return p
    for k, v in idx.items():
        if name and (name in k or k in name):
            return v
    return None


def read_file(name: str, limit: int = 4000) -> str | None:
    p = find_path(name)
    if not p:
        return None
    return _read(p, limit)


def toc() -> str:
    kb_dir = get_settings().kb_dir
    out = []
    for f in ("INDEX.md", "SYSTEM_INDEX.md"):
        p = os.path.join(kb_dir, f)
        if os.path.isfile(p):
            t = _read(p, 4000)
            if t:
                out.append(t)
    return "\n\n".join(out)


def snippets(msg: str, limit: int = 4) -> list[str]:
    s = _get()
    if not s.chunks and not s.index:
        return []
    exp = expand_aliases(msg)
    hits: list[str] = []
    seen_file: set[str] = set()
    for name in s.names_by_len:
        if name in exp and s.index[name] not in seen_file:
            seen_file.add(s.index[name])
            txt = _read(s.index[name], 1200)
            if not txt:
                continue
            hits.append("——【%s】——\n%s" % (name, txt))
            if len(hits) >= 2:
                break
    scores: dict[int, float] = {}
    for t in set(tokenize(exp)):
        post = s.post.get(t)
        if not post:
            continue
        idf = s.idf.get(t, 0.0)
        for idx, tf in post.items():
            dl = s.lens[idx]
            scores[idx] = scores.get(idx, 0.0) + idf * tf * _K1 / (tf + _K1 * (0.25 + 0.75 * dl / s.avg))
    top = sorted(scores.items(), key=lambda x: -x[1])[:limit]
    vmax = top[0][1] if top else 0
    for idx, sc in top:
        if sc < max(vmax * 0.3, 0.8):
            continue
        c = s.chunks[idx]
        hits.append("——【%s · %s】——\n%s" % (c["src"], c["title"], c["text"]))
    return hits[: limit + 1]
