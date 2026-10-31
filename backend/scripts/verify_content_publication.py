"""Verify current records and report preserved historical attribution gaps."""
import asyncio,json
from sqlalchemy import func,select
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.db import get_engine,dispose_engine
from app.models import ChapterTextbookPage,TextbookSource,CitationMetadataHistory
from app.services.citation_audit import audit
from app.services.provenance import DEFAULT_TEXTBOOKS
async def main():
    try:
        async with async_sessionmaker(get_engine())() as session:
            result=await audit(session)
            sources=set((await session.scalars(select(TextbookSource.key))).all())
            missing=sorted({s['key'] for s in DEFAULT_TEXTBOOKS}-sources)
            if missing:result['errors'].append({'reason':'missing_textbooks','keys':missing})
            result['chapter_page_rows']=await session.scalar(select(func.count()).select_from(ChapterTextbookPage))
            result['archived_metadata_rows']=await session.scalar(select(func.count()).select_from(CitationMetadataHistory))
            result['valid']=not result['errors']
            result['legacy_unattributed_count']=len(result.pop('legacy_unattributed'))
            print(json.dumps(result,ensure_ascii=False))
            if not result['valid']:raise SystemExit(1)
    finally:await dispose_engine()
if __name__=='__main__':asyncio.run(main())
