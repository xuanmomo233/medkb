"""Distinguish historical gaps from contradictory or new invalid reviews."""
from collections import Counter
from sqlalchemy import select
from app.models import ContentCitation, TextbookSource
from app.services.provenance import TARGET_MODELS

async def audit(session):
    rows=(await session.scalars(select(ContentCitation))).all()
    sources=set((await session.scalars(select(TextbookSource.key))).all())
    targets={kind:set((await session.scalars(select(model.id))).all()) for kind,model in TARGET_MODELS.items()}
    errors=[];legacy=[];counts=Counter()
    for row in rows:
        counts[row.status]+=1
        if row.source_key not in sources or row.target_id not in targets.get(row.target_type,set()):
            errors.append({'id':row.id,'reason':'orphan_reference'})
        reviewed=row.status in ('verified','disputed')
        missing=reviewed and (row.verified_by is None or row.verified_at is None)
        if missing:
            item={'id':row.id,'reason':'missing_review_attribution','target_type':row.target_type,'target_id':row.target_id}
            (legacy if row.verification_origin=='legacy_unattributed' else errors).append(item)
        if row.status=='unverified' and (row.verified_by is not None or row.verified_at is not None):
            errors.append({'id':row.id,'reason':'unreviewed_with_attribution'})
        if row.page_start is not None and (row.page_start<=0 or (row.page_end is not None and row.page_end<row.page_start)):
            errors.append({'id':row.id,'reason':'invalid_pages'})
    return {'citations':len(rows),'status_counts':dict(counts),'errors':errors,
        'legacy_unattributed':legacy,'valid':not errors}
