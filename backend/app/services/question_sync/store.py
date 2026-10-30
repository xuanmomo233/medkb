from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.models import Question, SyncCursor, SyncDocument, SyncRevision, SyncRun
from .normalize import digest, normalize, snapshot


def utcnow():
    return datetime.now(timezone.utc)


async def insert_once(session, model, **values):
    insert = sqlite_insert if session.bind.dialect.name == "sqlite" else pg_insert
    await session.execute(insert(model).values(**values).on_conflict_do_nothing())


async def ingest(session, raw: dict, source_meta: dict) -> str:
    """Only stage data. Never change questions, cards or user learning records."""
    external_id = str(raw.get("id", ""))
    if not external_id.isdigit() or len(external_id) > 32:
        raise ValueError("上游 id 缺失或过长")
    await insert_once(session, SyncDocument, source="wcyk", external_id=external_id,
                      latest_version=0, latest_hash="", raw={}, validation_error="")
    doc = await session.scalar(select(SyncDocument).where(
        SyncDocument.source == "wcyk", SyncDocument.external_id == external_id,
    ).with_for_update().execution_options(populate_existing=True))
    doc.last_seen_at, doc.raw = utcnow(), raw
    try:
        data = normalize(raw, source_meta)
        doc.validation_error = ""
    except ValueError as error:
        data = {}
        doc.validation_error = str(error)
    # Unknown source fields may contain meaningful revisions; only known counters
    # are ignored for versioning, while the latest complete raw record is retained.
    raw_content = {key: value for key, value in raw.items() if key not in ("studCount", "rightCount")}
    fingerprint = digest({"data": data, "raw_content": raw_content, "source_meta": source_meta})
    if fingerprint == doc.latest_hash:
        return "unchanged"
    if doc.question_id is None:
        doc.question_id = await session.scalar(select(Question.id).where(Question.qid == external_id))
    result = "changed" if doc.latest_version or doc.question_id else "new"
    first_version = doc.latest_version == 0
    doc.latest_version += 1
    doc.latest_hash = fingerprint
    baseline = {}
    if first_version and doc.question_id and not doc.validation_error:
        existing = await session.get(Question, doc.question_id)
        clinical_fields = ("bank", "qtype", "stem", "options", "option_labels", "answer", "analysis", "parent_stem")
        if existing is not None and all(snapshot(existing)[field] == data[field] for field in clinical_fields):
            baseline = snapshot(existing)
            doc.published_version = doc.latest_version
            result = "unchanged"
    session.add(SyncRevision(document_id=doc.id, version=doc.latest_version, digest=fingerprint,
                             normalized=data, raw=raw, source_meta=source_meta, local_baseline=baseline))
    await session.flush()
    return "invalid" if doc.validation_error else result


async def acquire(session, scope: str, start: int):
    if start < 1:
        raise ValueError("扫描起点必须大于零")
    await insert_once(session, SyncCursor, source="wcyk", scope=scope, next_id=start)
    now, token = utcnow(), str(uuid4())
    changed = await session.execute(update(SyncCursor).where(
        SyncCursor.source == "wcyk", SyncCursor.scope == scope,
        or_(SyncCursor.lease_until.is_(None), SyncCursor.lease_until < now),
    ).values(lease_token=token, lease_until=now + timedelta(minutes=5)))
    if changed.rowcount != 1:
        await session.rollback()
        raise ValueError(f"同步范围 {scope} 正在运行")
    position = await session.scalar(select(SyncCursor.next_id).where(
        SyncCursor.source == "wcyk", SyncCursor.scope == scope))
    await session.commit()
    return token, position


async def advance(session, scope: str, token: str, position: int):
    now = utcnow()
    changed = await session.execute(update(SyncCursor).where(
        SyncCursor.source == "wcyk", SyncCursor.scope == scope,
        SyncCursor.lease_token == token, SyncCursor.lease_until > now,
    ).values(next_id=position, lease_until=now + timedelta(minutes=5)))
    if changed.rowcount != 1:
        raise ValueError("同步租约已失效，停止提交")


async def release(session, scope: str, token: str):
    await session.execute(update(SyncCursor).where(
        SyncCursor.source == "wcyk", SyncCursor.scope == scope, SyncCursor.lease_token == token,
    ).values(lease_token=None, lease_until=None))


async def scan(session, upstream, *, scope="frontier", start=1, count=500):
    """Resume after every confirmed result. Unknown failures keep the failed ID."""
    from .upstream import ExcludedQuestion, MissingQuestion

    if not 1 <= count <= 10000:
        raise ValueError("单批扫描数量应为 1–10000")
    token, position = await acquire(session, scope, start)
    counts = dict(scanned=0, missing=0, excluded=0, invalid=0, new=0, changed=0, unchanged=0)
    run = SyncRun(source="wcyk", scope=scope, counts=counts)
    session.add(run)
    await session.commit()
    run_id = run.id
    try:
        for external_id in range(position, position + count):
            try:
                records = await upstream.question(external_id)
                for raw, meta in records:
                    result = await ingest(session, raw, meta)
                    counts[result] += 1
            except MissingQuestion:
                counts["missing"] += 1
            except ExcludedQuestion:
                counts["excluded"] += 1
            # Ingestion and cursor advance are one transaction, including empty results.
            await advance(session, scope, token, external_id + 1)
            counts["scanned"] += 1
            await session.execute(update(SyncRun).where(SyncRun.id == run_id).values(counts=counts))
            await session.commit()
        await session.execute(update(SyncRun).where(SyncRun.id == run_id).values(status="completed", finished_at=utcnow()))
        await session.commit()
        return {"run_id": run_id, **counts, "next_id": position + count}
    except Exception as error:
        await session.rollback()
        # Log error type, never upstream URLs/tokens or DB connection strings.
        await session.execute(update(SyncRun).where(SyncRun.id == run_id).values(
            status="failed", error=type(error).__name__, finished_at=utcnow()))
        await session.commit()
        raise
    finally:
        await release(session, scope, token)
        await session.commit()


async def catalog(session, upstream):
    """Full chapter enumeration discovers lower IDs and updates to existing IDs."""
    token, _ = await acquire(session, "catalog", 1)
    run = SyncRun(source="wcyk", scope="catalog")
    session.add(run)
    await session.commit()
    run_id = run.id
    try:
        result = await _catalog_chapters(session, upstream, run_id, token)
        await session.execute(update(SyncRun).where(SyncRun.id == run_id).values(
            status="completed", counts=result, finished_at=utcnow()))
        await session.commit()
        return result
    except Exception as error:
        await session.rollback()
        await session.execute(update(SyncRun).where(SyncRun.id == run_id).values(
            status="failed", error=type(error).__name__, finished_at=utcnow()))
        await session.commit()
        raise
    finally:
        await release(session, "catalog", token)
        await session.commit()


async def _catalog_chapters(session, upstream, catalog_run_id, catalog_token):
    result = {"chapters": 0, "pages": 0, "new": 0, "changed": 0, "unchanged": 0, "invalid": 0}
    async for bank, chapter in upstream.chapters():
        scope = f"catalog:{bank['id']}:{chapter['id']}"
        token, page = await acquire(session, scope, 1)
        run = SyncRun(source="wcyk", scope=scope)
        session.add(run)
        await session.commit()
        run_id, pages, previous = run.id, 0, None
        try:
            while True:
                records, more = await upstream.chapter_page(bank, chapter, page)
                fingerprint = digest([raw["id"] for raw, _ in records])
                if more and (not records or fingerprint == previous):
                    raise ValueError("上游分页重复或无法确认结束")
                for raw, meta in records:
                    result[await ingest(session, raw, meta)] += 1
                await advance(session, scope, token, page + 1 if more else 1)
                await advance(session, "catalog", catalog_token, 1)
                pages += 1
                result["pages"] += 1
                await session.execute(update(SyncRun).where(SyncRun.id == run_id).values(counts={"pages": pages}))
                await session.execute(update(SyncRun).where(SyncRun.id == catalog_run_id).values(counts=dict(result)))
                await session.commit()
                if not more:
                    break
                page += 1
                previous = fingerprint
                if pages >= 10000:
                    raise ValueError("章节分页超过运行上限，需人工检查")
            result["chapters"] += 1
            await session.execute(update(SyncRun).where(SyncRun.id == run_id).values(status="completed", finished_at=utcnow()))
            await session.commit()
        except Exception as error:
            await session.rollback()
            await session.execute(update(SyncRun).where(SyncRun.id == run_id).values(
                status="failed", error=type(error).__name__, finished_at=utcnow()))
            await session.commit()
            raise
        finally:
            await release(session, scope, token)
            await session.commit()
    return result
