import asyncio
from pathlib import Path
from jobradar.database import migrate, Job, sessions
from jobradar.models import RawJob
from jobradar.normalization import normalize
from jobradar.services import upsert_job
from sqlalchemy import select

def test_job_upsert_is_idempotent(tmp_path: Path):
    url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}"
    async def scenario():
        await migrate(url)
        raw=RawJob(provider="greenhouse",source_id="1",external_job_id="a",company_name="Acme",title="AI Engineer",apply_url="https://example.com/jobs/a",description_html="Python")
        assert await upsert_job(url,normalize(raw),1)
        assert not await upsert_job(url,normalize(raw),1)
        Session=sessions(url)
        async with Session() as db: assert len((await db.scalars(select(Job))).all())==1
    asyncio.run(scenario())
