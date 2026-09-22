from __future__ import annotations
import asyncio
from pathlib import Path
import typer
from sqlalchemy import select, func
from .config import settings
from .database import migrate, Source, Resume, sessions
from .services import import_sources, import_resumes, crawl, candidates, send_report
app=typer.Typer(help="JobRadar AI")
sources_app=typer.Typer(); resumes_app=typer.Typer(); app.add_typer(sources_app,name="sources"); app.add_typer(resumes_app,name="resumes")
def async_run(coro): return asyncio.run(coro)
@app.command()
def doctor():
    s=settings(); async_run(migrate(s.database_url)); Session=sessions(s.database_url)
    async def check():
        async with Session() as db:return await db.scalar(select(func.count(Source.id))),await db.scalar(select(func.count(Resume.id)))
    source_count,resume_count=async_run(check())
    typer.echo(f"PASS database/migrations\n{'PASS' if s.cerebras_api_key else 'WARN'} Cerebras configured\n{'PASS' if s.resend_api_key else 'WARN'} Resend configured\n{'PASS' if s.tavily_api_key else 'WARN'} Tavily configured\n{'PASS' if resume_count else 'WARN'} resumes: {resume_count}\nPASS sources: {source_count}")
@sources_app.command("import-all")
def sources_import():
    s=settings();async_run(migrate(s.database_url));typer.echo(f"Imported {async_run(import_sources(s.database_url))} new source records")
@sources_app.command()
def stats():
    s=settings(); Session=sessions(s.database_url)
    async def q():
        async with Session() as db:return (await db.execute(select(Source.provider,func.count(Source.id)).group_by(Source.provider))).all()
    for p,n in async_run(q()):typer.echo(f"{p}: {n}")
@sources_app.command()
def verify(sample:int=10):
    s=settings(); typer.echo(async_run(crawl(s.database_url,sample)))
@sources_app.command()
def discover(url:str):
    from .sources import discover_source
    typer.echo(discover_source(url) or "No supported ATS signature found")
@resumes_app.command("import")
def resumes_import():
    s=settings();async_run(migrate(s.database_url));typer.echo(f"Imported {async_run(import_resumes(s.database_url))} new resume profiles")
@app.command()
def report():
    s=settings(); jobs=async_run(candidates(s.database_url));typer.echo(async_run(send_report(s,jobs,True)))
@app.command("run")
def run_job(dry_run:bool=typer.Option(False,"--dry-run"), sample_sources:int=0):
    s=settings();async_run(migrate(s.database_url)); crawl_stats=async_run(crawl(s.database_url,sample_sources)); jobs=async_run(candidates(s.database_url)); path=async_run(send_report(s,jobs,dry_run=dry_run));typer.echo({**crawl_stats,"report_candidates":len(jobs),"preview":path})
if __name__=="__main__":app()
