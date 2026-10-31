import asyncio,json
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.core.db import get_engine,dispose_engine
from app.services.citation_audit import audit
async def main():
    try:
        async with async_sessionmaker(get_engine())() as s:result=await audit(s)
        print(json.dumps(result,ensure_ascii=False))
        if not result['valid']:raise SystemExit(1)
    finally:await dispose_engine()
if __name__=='__main__':asyncio.run(main())
