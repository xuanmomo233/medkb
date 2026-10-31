"""capture/prepare/apply/check chapter content through a single guarded manifest.

Capture once, prepare from the mapped local manuscripts, upload the manifest,
then apply on the server. Backups and receipts must be new paths.
"""
import argparse,asyncio,gzip,json
from pathlib import Path
from sqlalchemy import select,text
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.db import get_engine,dispose_engine
from app.models import Chapter
from app.services.content_publication import apply,digest,page_rows,text_sha

def write_new(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2).encode('utf-8')
    if str(path).endswith('.gz'):
        with gzip.open(path,'xb') as f:f.write(raw)
    else:
        with open(path,'xb') as f:f.write(raw)

def read(path):
    return json.loads(gzip.decompress(path.read_bytes()) if str(path).endswith('.gz') else path.read_bytes())

async def capture(session,ids=None):
    stmt=select(Chapter).order_by(Chapter.id)
    if ids is not None:stmt=stmt.where(Chapter.id.in_(ids))
    rows=(await session.scalars(stmt)).all();pages=await page_rows(session,[r.id for r in rows])
    return {'schema_version':1,'chapters':[{'id':r.id,'source_file':r.source_file,
        'content_md':r.content_md,'sha256':text_sha(r.content_md or ''),'textbook_pages':pages[r.id]} for r in rows]}

async def main(args):
    if args.command=='prepare':
        baseline=read(args.baseline);items=[];root=args.kb.resolve()
        page_map=read(args.page_map) if args.page_map else {}
        for row in baseline['chapters']:
            rel=row['source_file'].replace('\\','/').removeprefix('kb/')
            path=(root/rel).resolve()
            if not path.is_relative_to(root):raise ValueError('source_file escapes kb')
            body=path.read_text(encoding='utf-8-sig')
            pages=page_map.get(str(row['id']),row['textbook_pages'])
            pages=sorted(pages,key=lambda p:(p['source_key'],p['page']))
            if body==row['content_md'] and pages==row['textbook_pages']:continue
            items.append({'id':row['id'],'source_file':row['source_file'],
                'before_sha256':row['sha256'],'before_pages_sha256':digest(row['textbook_pages']),
                'after_sha256':text_sha(body),'content_md':body,'textbook_pages':pages})
        write_new(args.output,{'schema_version':1,'id':args.id,'chapters':items})
        print(json.dumps({'prepared_chapters':len(items),'output':str(args.output)}));return
    factory=async_sessionmaker(get_engine(),expire_on_commit=False)
    try:
        async with factory() as session:
            if args.command=='capture':
                if session.bind.dialect.name=='postgresql':await session.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
                write_new(args.output,await capture(session,args.chapter_id));await session.rollback();return
            manifest=read(args.manifest);ids=[x['id'] for x in manifest['chapters']]
            if args.command=='check':
                current=await capture(session,ids)
                expected={x['id']:x for x in manifest['chapters']}
                for row in current['chapters']:
                    target=expected[row['id']]
                    if row['sha256']!=target['after_sha256'] or digest(row['textbook_pages'])!=digest(target['textbook_pages']):raise ValueError('postread mismatch')
                if len(current['chapters'])!=len(ids):raise ValueError('postread missing chapter')
                print(json.dumps({'passed':True,'chapters':len(ids)}));return
            if args.backup is None:raise ValueError('apply requires --backup')
            from app.core.config import get_settings
            image_root=Path(get_settings().textbook_img_dir).resolve()
            for item in manifest['chapters']:
                for page in item['textbook_pages']:
                    image=(image_root/page['source_key']/f"page_{page['page']:04d}.webp").resolve()
                    if not image.is_relative_to(image_root) or not image.is_file():raise ValueError(f'missing textbook page: {image.name}')
            write_new(args.backup,await capture(session,ids))
            await session.rollback()
            receipt=await apply(session,manifest);await session.commit()
            write_new(args.output,receipt)
            # Separate session validates body and page index after the commit.
        async with factory() as verify:
            current=await capture(verify,ids);expected={x['id']:x for x in manifest['chapters']}
            if len(current['chapters'])!=len(ids):raise ValueError('postread missing chapter')
            for row in current['chapters']:
                target=expected[row['id']]
                if row['sha256']!=target['after_sha256'] or digest(row['textbook_pages'])!=digest(target['textbook_pages']):raise ValueError('postread mismatch')
        print(json.dumps({'committed':True,'verified_chapters':len(ids),'receipt':str(args.output)}))
    finally:await dispose_engine()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['capture','prepare','apply','check'])
    p.add_argument('--output',type=Path);p.add_argument('--backup',type=Path);p.add_argument('--manifest',type=Path)
    p.add_argument('--baseline',type=Path);p.add_argument('--kb',type=Path);p.add_argument('--id')
    p.add_argument('--page-map',type=Path,help='JSON mapping chapter ids to explicit textbook_pages arrays')
    p.add_argument('--chapter-id',type=int,action='append',help='limit capture to explicit chapter ids')
    asyncio.run(main(p.parse_args()))
