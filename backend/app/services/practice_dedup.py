"""Collapse equivalent exercises inside a study plan, without declaring identity.

Original questions, attempts, and reviewed QuestionMerge relationships stay intact.
Only exact displayed content and the same selected option content can share work.
"""
import re
import unicodedata
from collections import defaultdict

from sqlalchemy import select

from app.models import Attempt, Question
from app.services import question_links
from app.services.question_groups import batches


def width_normalized(value):
    # NFKC would turn 10² into 102 and change medical quantities. Fold only ASCII width.
    value = unicodedata.normalize("NFC", str(value or ""))
    return "".join(chr(ord(ch) - 0xFEE0) if 0xFF01 <= ord(ch) <= 0xFF5E else ch for ch in value)


def normalized(value):
    # Preserve case, negation, numbers, decimal punctuation and mathematical signs.
    return re.sub(r"\s+", "", width_normalized(value))


def stem_text(value):
    value = width_normalized(value).strip()
    # Some imported exam questions use a leading source marker like "009--X.".
    # It is numbering metadata, not part of the question text.
    source_marker = r"^\s*(?:\d{1,4}\s*--\s*)?X\s*[.．、:：]\s*(?!\d)"
    exam = r"^(?:[【\[(]\s*(?:19|20)\d{2}\s*[nN]\s*\d{1,3}\s*[aAbBxX]?\s*[】\])]\s*|(?:19|20)\d{2}\s*[nN]\s*\d{1,3}\s*[aAbBxX]?\s*[.、:]\s*)"
    number = r"^\d{1,4}\s*[.．、:：)](?!\d)\s*"
    for _ in range(3):
        revised = re.sub(number, "", re.sub(exam, "", re.sub(source_marker, "", value, flags=re.I)))
        if revised == value:
            break
        value = revised
    return normalized(value)


def practice_key(row):
    options = [normalized(v) for v in (row.options or [])]
    labels = list(row.option_labels or "ABCDEFGHIJKLMNOPQRSTUVWXYZ"[:len(options)])
    if (len(options) < 2 or not all(options) or len(labels) != len(options)
            or len(set(labels)) != len(labels) or any(not re.fullmatch(r"[A-Z]", v) for v in labels)):
        return None
    raw = width_normalized(row.answer).strip()
    letters = re.sub(r"[\s,，、/;；]+", "", raw)
    if re.fullmatch(r"[A-Z]+", letters) and all(v in labels for v in letters):
        answer = tuple(sorted(options[index] for index in {labels.index(v) for v in letters}))
    elif normalized(raw) in options:
        answer = (normalized(raw),)
    else:
        return None
    stem = stem_text(row.stem)
    if not stem:
        return None
    # References such as 'A和B均正确' make the source's option ordering meaningful.
    references = re.search(r"(?<![A-Za-z])[A-Z](?![A-Za-z])|[A-Z]{1,6}(?:均|都|正确|错误|项)|以上|上述|前[两三四]项|第[一二三四1234]项|(?i:above|below)",
                           " ".join([row.parent_stem or "", stem, *(row.options or [])]))
    choice_key = (tuple(labels), tuple(options)) if references else tuple(sorted(options))
    return (normalized(row.qtype), normalized(row.parent_stem), stem, choice_key, answer)


async def mapping_for(session, uid, ids):
    """Return a request-local practice map, never write a global identity map."""
    mapping = await question_links.redirects(session)
    attempted = list((await session.scalars(select(Attempt.question_id).distinct().where(
        Attempt.user_id == uid, Attempt.picked != "",
    ))).all())
    roots = sorted({question_links.resolve(mapping, ident) for ident in [*ids, *attempted]})
    groups = defaultdict(list)
    for chunk in batches(roots):
        rows = (await session.execute(select(
            Question.id, Question.qtype, Question.parent_stem, Question.stem, Question.options,
            Question.option_labels, Question.answer,
        ).where(Question.id.in_(chunk)))).all()
        for row in rows:
            key = practice_key(row)
            if key is not None:
                groups[key].append(row.id)
    for members in groups.values():
        root = min(members)
        for ident in members:
            if ident != root:
                mapping[ident] = root
    return mapping
