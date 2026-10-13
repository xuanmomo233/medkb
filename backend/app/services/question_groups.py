"""Derive complete cases without a migration or loading the whole question bank.

Filters select seeds. Membership never depends on a child's progress, type or
answer: only the exact trimmed common stem and its bank/source namespace.
"""

from collections.abc import Iterable, Sequence

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


async def ordered_groups(session: AsyncSession, seed_ids: Iterable[int]) -> list[tuple[int, ...]]:
    """Complete seeds, in first requested group order, with ascending child IDs.

    ID and key lookups are batched for driver parameter limits, not truncated.
    Only identity columns are fetched; no stems/options/analysis ORM bank scan.
    Empty parents remain independent single questions. Missing IDs are ignored.
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
    out = []
    seen = set()
    for qid in seeds:
        if qid not in keys:
            continue
        key = keys[qid]
        token = key if key is not None else qid
        if token in seen:
            continue
        seen.add(token)
        children = members[key] | {qid} if key is not None else {qid}
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
