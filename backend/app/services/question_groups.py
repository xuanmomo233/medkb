"""Derive complete cases without a migration or loading the whole question bank.

Filters select seeds. Membership never depends on a child's progress, type or
answer: only the exact trimmed common stem and its bank/source namespace.
"""

from collections.abc import Iterable, Sequence
from os.path import commonprefix
import re

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Question

# All characters stripped by Python str.strip(); pass the same set to SQL so
# tabs/newlines and Unicode whitespace are treated consistently on both DBs.
TRIM_CHARS = " \t\n\r\v\f\x1c\x1d\x1e\x1f\x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000"
ID_BATCH = 400
GROUP_BATCH = 100


def batches(values: Sequence, size: int = ID_BATCH):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def parent_expression(session: AsyncSession):
    trim = func.btrim if session.get_bind().dialect.name == "postgresql" else func.trim
    return trim(func.coalesce(Question.parent_stem, ""), TRIM_CHARS)


def group_key(bank_group: str, bank: str, source_file: str, parent_stem: str | None):
    parent = (parent_stem or "").strip()
    return (bank_group, bank, source_file, parent) if parent else None


LEGACY_HEADER = re.compile(r"^[（(]\s*(\d+)\s*[~～〜\-—–至]\s*(\d+)\s*题共用题干[）)]")


async def legacy_case_parts(session: AsyncSession, seed_ids: Sequence[int]) -> dict[int, tuple[str, str, str]]:
    parts = {}
    scopes = set()
    for chunk in batches(seed_ids):
        rows = (await session.execute(
            select(Question.bank_group, Question.bank, Question.source_file, Question.stem)
            .where(Question.id.in_(chunk), parent_expression(session) == "",
                   func.substr(Question.stem, 1, 40).contains("共用题干"))
        )).all()
        for bg, bank, source, stem in rows:
            match = LEGACY_HEADER.match(stem)
            if match and 2 <= int(match[2]) - int(match[1]) + 1 <= 10:
                scopes.add((bg, bank, source, match[0], int(match[2]) - int(match[1]) + 1))
    for bg, bank, source, header, count in scopes:
        rows = (await session.execute(
            select(Question.id, Question.stem)
            .where(Question.bank_group == bg, Question.bank == bank, Question.source_file == source,
                   parent_expression(session) == "", Question.stem.startswith(header, autoescape=True))
            .order_by(Question.id)
        )).all()
        # Reused numbering or incomplete exports are ambiguous, not permission to merge.
        if len(rows) != count:
            continue
        shared = commonprefix([stem[len(header):] for _, stem in rows])
        boundaries = list(re.finditer(r"[。！？；\n]", shared))
        if not boundaries:
            continue
        boundary = boundaries[-1].end()
        parent = shared[:boundary].strip()
        children = [(qid, stem[len(header) + boundary:].strip()) for qid, stem in rows]
        if len(parent) < 10 or any(not child for _, child in children):
            continue
        parts.update((qid, (parent, child, header)) for qid, child in children)
    return parts


async def ordered_groups(session: AsyncSession, seed_ids: Iterable[int]) -> list[tuple[int, ...]]:
    """Complete seeds, in first requested group order, with ascending child IDs.

    ID and key lookups are batched for driver parameter limits, not truncated.
    Normal cases fetch identity columns only. Marked legacy stems are inspected
    in their exact bank/file scope. Missing IDs and ambiguous markers are ignored.
    """
    seeds = list(dict.fromkeys(seed_ids))
    identity = (Question.id, Question.bank_group, Question.bank, Question.source_file, Question.parent_stem)
    keys = {}
    for chunk in batches(seeds):
        for qid, bg, bank, source, parent in (await session.execute(select(*identity).where(Question.id.in_(chunk)))).all():
            keys[qid] = group_key(bg, bank, source, parent)
    requested_keys = list(dict.fromkeys(key for key in keys.values() if key is not None))
    members = {key: set() for key in requested_keys}
    scoped_key = tuple_(Question.bank_group, Question.bank, Question.source_file, parent_expression(session))
    for chunk in batches(requested_keys, GROUP_BATCH):
        rows = (await session.execute(select(*identity).where(scoped_key.in_(chunk)))).all()
        for qid, bg, bank, source, parent in rows:
            key = group_key(bg, bank, source, parent)
            # Python's exact equality also protects against a permissive DB collation.
            if key in members:
                members[key].add(qid)
    legacy = await legacy_case_parts(session, [qid for qid, key in keys.items() if key is None])
    legacy_members = {}
    # Scope each inferred case by its authoritative bank/file identity, not text alone.
    if legacy:
        identities = {}
        for chunk in batches(list(legacy)):
            for qid, bg, bank, source, _ in (await session.execute(select(*identity).where(Question.id.in_(chunk)))).all():
                identities[qid] = (bg, bank, source, legacy[qid][2], legacy[qid][0])
        grouped = {}
        for qid, key in identities.items():
            grouped.setdefault(key, []).append(qid)
        for ids in grouped.values():
            children = tuple(sorted(ids))
            legacy_members.update((qid, children) for qid in children)
    out = []
    seen = set()
    for qid in seeds:
        if qid not in keys:
            continue
        key = keys[qid]
        token = key if key is not None else legacy_members.get(qid, qid)
        if token in seen:
            continue
        seen.add(token)
        children = members[key] | {qid} if key is not None else legacy_members.get(qid, (qid,))
        out.append(tuple(sorted(children)))
    return out


def flatten_groups(groups: Iterable[Sequence[int]], limit: int | None = None) -> list[int]:
    """A child-count soft limit: finish the final case, never slice its IDs."""
    if limit is not None and limit <= 0:
        return []
    out = []
    for children in groups:
        out.extend(children)
        if limit is not None and len(out) >= limit:
            break
    return out


async def complete_question_ids(session: AsyncSession, seed_ids: Iterable[int], limit: int | None = None) -> list[int]:
    return flatten_groups(await ordered_groups(session, seed_ids), limit)
