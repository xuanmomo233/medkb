import hashlib
import html
import json
import re
import unicodedata

FIELDS = (
    "bank_group", "bank", "subject_dir", "system", "chapter", "qtype", "stem", "options",
    "answer", "analysis", "parent_stem", "meta", "source_file", "tags", "is_real_exam",
)
TYPES = {"1": "单选", "2": "多选", "3": "多选", "5": "口诀", "6": "病例串", "7": "填空"}


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def plain_html(value) -> str:
    value = str(value or "")
    value = re.sub(r'<img\b[^>]*?\bsrc=["\']([^"\']+)["\'][^>]*>', r'![图](\1)', value, flags=re.I)
    value = re.sub(r"<br\s*/?>|</p\s*>", "\n", value, flags=re.I)
    value = re.sub(r"</(?:tr|li|div|h[1-6])\s*>", "\n", value, flags=re.I)
    value = re.sub(r"</(?:td|th)\s*>", " | ", value, flags=re.I)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(re.sub(r"<[^>]+>", "", value))).strip()


def normalize(raw: dict, meta: dict) -> dict:
    """Keep source data and images; leave uncertain classification for review."""
    if not str(raw.get("id", "")).isdigit():
        raise ValueError("上游题目缺少有效数字 id")
    if str(raw.get("type")) not in TYPES:
        raise ValueError("未知上游题型，需补充转换规则")
    stem = plain_html(raw.get("stem"))
    if not stem:
        raise ValueError("上游题干为空")
    options = raw.get("options") or []
    if not isinstance(options, list) or len(options) > 26:
        raise ValueError("上游选项格式不受支持")
    options = [plain_html(item) for item in options]
    answers = raw.get("answer") or []
    answers = answers if isinstance(answers, list) else [answers]
    converted = []
    for answer in answers:
        if isinstance(answer, int) and not isinstance(answer, bool):
            if not 0 <= answer < len(options):
                raise ValueError("上游答案索引越界")
            converted.append(chr(65 + answer))
        else:
            converted.append(plain_html(answer))
    bank = str(meta.get("bank_title", ""))
    chapter = str(meta.get("chapter_title", ""))
    if len(bank) > 64 or len(chapter) > 200 or len("、".join(converted)) > 255:
        raise ValueError("上游题库名、章节或答案超出当前题库字段长度，需人工拆分转换")
    return dict(bank_group="", bank=bank, subject_dir="", system="", chapter=chapter,
                qtype=TYPES[str(raw["type"])], stem=stem, options=options, answer="、".join(converted),
                analysis=plain_html(raw.get("analysis")), parent_stem=plain_html(meta.get("parent_stem")),
                meta="", source_file=f"wcyk:{raw['id']}", tags=[], is_real_exam=bool(meta.get("is_real_exam", False)))


def snapshot(question) -> dict:
    return {field: getattr(question, field) for field in FIELDS}


def identity(value: dict, *, include_answer=True) -> str | None:
    # Empty-answer/image-only recall prompts must not become automatic duplicate groups.
    if not value.get("stem") or not value.get("answer"):
        return None
    fields = [value.get(k, "") for k in ("qtype", "parent_stem", "stem")]
    fields += [value.get("options", [])]
    if include_answer:
        fields += [value["answer"]]

    def norm(item):
        if isinstance(item, list):
            return [norm(x) for x in item]
        return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(item)))

    return digest(norm(fields))


def tokens(text: str) -> set[str]:
    result = set(re.findall(r"[a-z][a-z0-9-]{1,30}", text.lower()))
    for word in re.findall(r"[\u4e00-\u9fff]+", text):
        result.update(word[i:i + 2] for i in range(len(word) - 1))
    return result
