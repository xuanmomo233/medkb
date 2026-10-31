from sqlalchemy import select
from app.models import ChapterTextbookPage, TextbookSource

async def galleries(session, chapter_id: int) -> list[dict]:
    rows = (await session.execute(select(ChapterTextbookPage.source_key,TextbookSource.title,ChapterTextbookPage.page)
        .join(TextbookSource, TextbookSource.key==ChapterTextbookPage.source_key)
        .where(ChapterTextbookPage.chapter_id==chapter_id,TextbookSource.active.is_(True))
        .order_by(ChapterTextbookPage.source_key,ChapterTextbookPage.page))).all()
    result = {}
    for key,title,page in rows:
        result.setdefault(key, {'source_key':key,'title':title,'pages':[]})['pages'].append(page)
    return list(result.values())
