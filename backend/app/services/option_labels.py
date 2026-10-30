"""Preserve source option letters separately from option position/text."""

import json
import re
import unicodedata

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# A bare Chinese enumeration comma also occurs inside real option bodies
# (e.g. nucleotide pairs A、G / U、A). Only a Markdown bullet makes that
# separator an explicit option-label boundary. Dots/closing brackets remain
# supported for labelled lines, including legacy JSON arrays of such lines.
_PREFIX = re.compile(
    r"^\s*(?:(?P<bullet>[-*])\s+)?(?P<label>[A-ZＡ-Ｚ])\s*"
    r"(?(bullet)[.、．)）:：]|[.．)）:：])\s*(?P<text>.*)$", re.S,
)


def labels_for(options, labels=None) -> list[str]:
    """Only missing/empty legacy metadata falls back to contiguous labels."""
    if len(options) > 26:
        raise ValueError("选项最多26个")
    if isinstance(labels, str):
        try:
            labels = json.loads(labels)
        except ValueError as error:
            raise ValueError("选项标签必须是字母数组") from error
    if labels is None or labels == []:
        return list(LETTERS[:len(options)])
    if not isinstance(labels, list) or len(labels) != len(options):
        raise ValueError("选项标签数量必须与选项一致")
    if any(not isinstance(label, str) or not re.fullmatch(r"[A-Z]", label) for label in labels):
        raise ValueError("选项标签必须为单个大写A-Z字母")
    if len(set(labels)) != len(labels):
        raise ValueError("选项标签不能重复")
    return list(labels)


def answer_letters(answer) -> set[str]:
    raw = unicodedata.normalize("NFKC", str(answer or "")).upper().strip()
    if not re.fullmatch(r"[A-Z]+(?:[\s,，、/;；]+[A-Z]+)*", raw):
        return set()
    return set(re.findall(r"[A-Z]", raw))


def import_options(options, explicit_labels=None) -> tuple[list[str], list[str]]:
    """Read explicit JSON labels or fully labelled Markdown lines, never guess gaps."""
    if isinstance(explicit_labels, str):
        explicit_labels = json.loads(explicit_labels)
    if isinstance(options, str):
        options = options.splitlines()
    options = [str(option) for option in (options or [])]
    pairs = [_PREFIX.fullmatch(option) for option in options]
    embedded = [unicodedata.normalize("NFKC", pair.group("label")) for pair in pairs] if options and all(pairs) else []
    marked_lines = options and all(re.match(r"^\s*[-*]\s+[A-ZＡ-Ｚ]\s*[.、．)）:：]", option) for option in options)
    if embedded and (marked_lines or embedded[0] == "A" or explicit_labels == embedded):
        labels = labels_for(options, explicit_labels if explicit_labels else embedded)
        if labels != embedded:
            raise ValueError("显式标签与Markdown选项标签不一致")
        return [pair.group("text") for pair in pairs], labels
    return options, labels_for(options, explicit_labels)


def parse_markdown_options(markdown: str) -> tuple[list[str], list[str]]:
    lines = [line for line in markdown.splitlines() if line.strip()]
    if any(not _PREFIX.fullmatch(line) for line in lines):
        raise ValueError("Markdown选项每行必须有明确字母标签")
    return import_options(lines)
