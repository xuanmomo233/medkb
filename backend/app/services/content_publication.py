"""One atomic publication for chapter Markdown and its independent image index."""
import hashlib
import json
from sqlalchemy import delete, select, text
from app.models import Chapter, ChapterTextbookPage, ContentPublication, TextbookSource

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def text_sha(value):
    return hashlib.sha256(value.encode('utf-8')).hexdigest()

async def page_rows(session, ids):
    rows=(await session.execute(select(ChapterTextbookPage.chapter_id,ChapterTextbookPage.source_key,
        ChapterTextbookPage.page).where(ChapterTextbookPage.chapter_id.in_(ids))
        .order_by(ChapterTextbookPage.chapter_id,ChapterTextbookPage.source_key,ChapterTextbookPage.page))).all()
    result={i:[] for i in ids}
    for chapter,key,page in rows:result[chapter].append({'source_key':key,'page':page})
    return result

async def apply(session, manifest):
    if manifest.get('schema_version')!=1 or not isinstance(manifest.get('chapters'),list):
        raise ValueError('unsupported publication manifest')
    batch=manifest.get('id','')
    if not batch or len(batch)>64:raise ValueError('invalid publication id')
    items=manifest['chapters'];ids=[x['id'] for x in items]
    if not ids or len(ids)!=len(set(ids)):raise ValueError('empty/duplicate chapter ids')
    for item in items:
        if not isinstance(item.get('content_md'),str) or len(item['content_md'].encode())>2_000_000:
            raise ValueError('invalid chapter body')
        if text_sha(item['content_md'])!=item.get('after_sha256'):raise ValueError('target SHA mismatch')
        pages=item.get('textbook_pages',[])
        locations=[(p['source_key'],p['page']) for p in pages]
        if len(locations)!=len(set(locations)) or any(type(p)!=int or p<=0 for _,p in locations):
            raise ValueError('invalid/duplicate textbook pages')
        if locations!=sorted(locations):raise ValueError('textbook pages must be sorted by source and page')
    if session.bind.dialect.name=='postgresql':
        await session.execute(text('SELECT pg_advisory_xact_lock(736290,41032)'))
    manifest_sha=digest(manifest)
    prior=await session.get(ContentPublication,batch)
    if prior:
        if prior.manifest_sha256!=manifest_sha:raise ValueError('publication id reused with different data')
        return {**prior.receipt,'already_applied':True}
    chapters=(await session.scalars(select(Chapter).where(Chapter.id.in_(ids)).with_for_update())).all()
    found={c.id:c for c in chapters}
    if set(found)!=set(ids):raise ValueError('chapter missing')
    pages=await page_rows(session,ids)
    active=set((await session.scalars(select(TextbookSource.key).where(TextbookSource.active.is_(True)))).all())
    for item in items:
        if item.get('source_file') is not None and item['source_file']!=found[item['id']].source_file:
            raise ValueError('source_file mapping drift')
        if text_sha(found[item['id']].content_md or '')!=item['before_sha256']:
            raise ValueError(f"chapter #{item['id']} source drift")
        if digest(pages[item['id']])!=item['before_pages_sha256']:
            raise ValueError(f"chapter #{item['id']} page index drift")
        if any(p['source_key'] not in active for p in item['textbook_pages']):raise ValueError('inactive textbook source')
    receipt={'id':batch,'manifest_sha256':manifest_sha,'chapters':[]}
    for item in items:
        chapter=found[item['id']];chapter.content_md=item['content_md']
        await session.execute(delete(ChapterTextbookPage).where(ChapterTextbookPage.chapter_id==chapter.id))
        for p in item['textbook_pages']:
            session.add(ChapterTextbookPage(chapter_id=chapter.id,**p))
        receipt['chapters'].append({'id':chapter.id,'after_sha256':item['after_sha256'],
            'pages_sha256':digest(item['textbook_pages']),'source_file':chapter.source_file})
    session.add(ContentPublication(id=batch,manifest_sha256=manifest_sha,receipt=receipt))
    await session.flush()
    return receipt
