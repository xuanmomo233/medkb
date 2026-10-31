import pytest
from sqlalchemy import select,delete
from app.models import Chapter,ChapterTextbookPage,TextbookSource,ContentCitation
from app.services.content_publication import apply,digest,text_sha
from app.services.textbook_pages import galleries
from app.core.render import chapter_md,md

@pytest.mark.asyncio
async def test_page_index_survives_citation_removal_and_manifest_is_guarded(session):
    session.add(TextbookSource(key='book',title='Book',subject='test',publisher='',edition='',active=True))
    session.add(Chapter(id=1,kind='note',subject='test',title='a',content_md='before',source_file='a.md',pages=[12]))
    await session.flush()
    session.add(ChapterTextbookPage(chapter_id=1,source_key='book',page=7))
    session.add(ContentCitation(target_type='chapter',target_id=1,source_key='book',status='unverified',page_start=7))
    await session.commit()
    assert (await galleries(session,1))[0]['pages']==[7]
    await session.execute(delete(ContentCitation).where(ContentCitation.target_type=='chapter'))
    await session.commit()
    assert (await galleries(session,1))[0]['pages']==[7]
    manifest={'schema_version':1,'id':'batch','chapters':[{'id':1,'before_sha256':text_sha('before'),
        'before_pages_sha256':digest([{'source_key':'book','page':7}]),'content_md':'after',
        'after_sha256':text_sha('after'),'textbook_pages':[{'source_key':'book','page':8}]}]}
    receipt=await apply(session,manifest);await session.commit()
    assert (await galleries(session,1))[0]['pages']==[8]
    assert (await session.get(Chapter,1)).pages==[12]
    assert (await apply(session,manifest))['already_applied']
    with pytest.raises(ValueError,match='reused'):
        await apply(session,{**manifest,'chapters':[{**manifest['chapters'][0],'content_md':'other','after_sha256':text_sha('other')}]})
    with pytest.raises(ValueError,match='source drift'):
        await apply(session,{**manifest,'id':'other'})
    rollback={'schema_version':1,'id':'rollback','chapters':[{'id':1,'before_sha256':text_sha('after'),
        'before_pages_sha256':digest([{'source_key':'book','page':8}]),'content_md':'before',
        'after_sha256':text_sha('before'),'textbook_pages':[{'source_key':'book','page':7}]}]}
    await apply(session,rollback);await session.commit()
    assert (await session.get(Chapter,1)).content_md=='before'
    assert (await galleries(session,1))[0]['pages']==[7]

def test_chapter_orphan_list_after_table_but_not_fenced_code():
    source='| A | B |\n|---|---|\n|1|2|\n\n    - snRNA\n    - snoRNA\n'
    assert '<pre>' in md(source)
    assert '<pre>' not in chapter_md(source)
    assert '<li>snRNA' in chapter_md(source)
    assert '<pre>' in chapter_md('```\n    - code\n    - example\n```')

@pytest.mark.asyncio
async def test_audit_keeps_legacy_gaps_visible_but_rejects_new_missing_attribution(session):
    from app.services.citation_audit import audit
    session.add(TextbookSource(key='book',title='Book',subject='test',publisher='',edition='',active=True))
    session.add(Chapter(id=1,kind='note',subject='test',title='a',content_md='x',source_file='a.md',pages=[]))
    await session.flush()
    session.add(ContentCitation(target_type='chapter',target_id=1,source_key='book',status='verified',verification_origin='legacy_unattributed'))
    await session.flush()
    result=await audit(session)
    assert result['valid'] and len(result['legacy_unattributed'])==1
    session.add(ContentCitation(target_type='chapter',target_id=1,source_key='book',chapter='new',status='verified',verification_origin='native'))
    await session.flush()
    result=await audit(session)
    assert not result['valid'] and len(result['errors'])==1
