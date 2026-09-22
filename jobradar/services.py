from __future__ import annotations
from datetime import datetime, timezone
import asyncio, csv, json
from pathlib import Path
import httpx
from sqlalchemy import select, func
from .config import ROOT, yaml_config
from .database import Source, Job, Resume, Notification, sessions
from .models import AIAnalysis, NormalizedJob, ResumeProfile, LiveStatus
from .normalization import normalize, eligibility
from .resumes import import_pdf
from .sources import SourceRef, ADAPTERS, discover_source

async def import_sources(url:str, directory:Path|None=None)->int:
    directory=directory or ROOT/"registry-package"/"ats_source_registry_package"; Session=sessions(url); count=0
    async with Session() as db:
        for file in directory.glob("*_source_registry*.csv"):
            with file.open(encoding="utf-8-sig",newline="") as f:
                for row in csv.DictReader(f):
                    provider=(row.get("ats") or "").lower().strip(); token=(row.get("board_token") or "").strip()
                    if not provider or not token: continue
                    exists=await db.scalar(select(Source.id).where(Source.provider==provider,Source.board_token==token))
                    if not exists:
                        db.add(Source(provider=provider,company_name=(row.get("company") or token)[:255],board_token=token,base_url=row.get("api_jobs_url") or row.get("hosted_board_url") or "",careers_url=row.get("hosted_board_url"),source_origin=row.get("source_dataset") or file.name)); count+=1
        await db.commit()
    return count

async def import_resumes(url:str)->int:
    cfg=yaml_config("candidate.yaml"); paths=Path(cfg["resume_dir"]).glob(cfg.get("resume_glob","*.pdf")); Session=sessions(url); count=0
    async with Session() as db:
        for path in paths:
            profile=import_pdf(path); exists=await db.scalar(select(Resume.id).where(Resume.file_sha256==profile.file_sha256))
            if not exists: db.add(Resume(resume_id=profile.resume_id,category=profile.category,source_file=profile.source_file,file_sha256=profile.file_sha256,payload=profile.model_dump_json())); count+=1
        await db.commit()
    return count

async def upsert_job(url:str, job:NormalizedJob)->bool:
    Session=sessions(url)
    async with Session() as db:
        old=await db.scalar(select(Job).where(Job.canonical_job_key==job.canonical_job_key))
        if old: old.content_hash=job.content_hash; return False
        db.add(Job(canonical_job_key=job.canonical_job_key,provider=job.provider,external_job_id=job.external_job_id,company_name=job.company_name,title=job.title,canonical_url=job.canonical_url,apply_url=job.apply_url,description_text=job.description_text,content_hash=job.content_hash,locations=json.dumps(job.locations))); await db.commit(); return True

def deterministic_score(job:Job, resumes:list[ResumeProfile])->tuple[int,ResumeProfile|None]:
    words=set((job.title+" "+job.description_text).lower().split()); best=None; score=0
    for r in resumes:
        current=len(words & set(r.skills))*8 + sum(4 for role in r.target_roles if role.lower() in job.title.lower())
        if current>score: score,best=current,r
    return min(100,score),best

async def ai_score(settings, job:Job, resumes:list[ResumeProfile], score:int, best:ResumeProfile|None)->AIAnalysis:
    fallback=AIAnalysis(score=score,best_resume_id=best.resume_id if best else None,strengths=(best.skills[:5] if best else []),gaps=[],deal_breakers=[],explanation="Deterministic evidence-based ranking; AI analysis unavailable or not required.")
    if not settings.cerebras_api_key:return fallback
    prompt={"job":{"title":job.title,"description":job.description_text[:6000]},"resumes":[r.model_dump(include={"resume_id","skills","evidence_items"}) for r in resumes],"instruction":"Return JSON only: score 0-100, best_resume_id, strengths, gaps, deal_breakers, explanation. Never invent evidence."}
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            response=await c.post("https://api.cerebras.ai/v1/chat/completions",headers={"Authorization":f"Bearer {settings.cerebras_api_key}"},json={"model":"llama3.1-8b","messages":[{"role":"user","content":json.dumps(prompt)}],"response_format":{"type":"json_object"},"temperature":0})
            response.raise_for_status(); return AIAnalysis.model_validate_json(response.json()["choices"][0]["message"]["content"])
    except Exception:return fallback

async def crawl(url:str, limit:int=0)->dict:
    Session=sessions(url); stats={"sources_checked":0,"jobs_fetched":0,"new_jobs":0,"failures":0}
    async with Session() as db: sources=(await db.scalars(select(Source).where(Source.status.in_(["ACTIVE","WATCHLIST","EMPTY"])).limit(limit or 10_000))).all()
    sem=asyncio.Semaphore(12)
    async def one(s:Source):
        stats["sources_checked"]+=1; adapter=ADAPTERS.get(s.provider)
        if not adapter:return
        try:
            async with sem: raw=await adapter.fetch_jobs(SourceRef(str(s.id),s.provider,s.company_name,s.board_token,s.base_url))
            stats["jobs_fetched"]+=len(raw)
            for r in raw:
                if await upsert_job(url,normalize(r)):stats["new_jobs"]+=1
        except Exception: stats["failures"]+=1
    await asyncio.gather(*(one(s) for s in sources)); return stats

async def candidates(url:str, min_score:int=65)->list[tuple[Job,AIAnalysis]]:
    prefs=yaml_config("preferences.yaml"); Session=sessions(url)
    async with Session() as db:
        jobs=(await db.scalars(select(Job).where(Job.notified==False))).all(); records=(await db.scalars(select(Resume))).all(); resumes=[ResumeProfile.model_validate_json(r.payload) for r in records]
        results=[]
        for j in jobs:
            state,_=eligibility(j.title,j.description_text,json.loads(j.locations),prefs)
            if state.value=="INELIGIBLE":continue
            score,best=deterministic_score(j,resumes)
            if score>=min_score: results.append((j,await ai_score(__import__("jobradar.config",fromlist=["settings"]).settings(),j,resumes,score,best)))
        return sorted(results,key=lambda x:x[1].score,reverse=True)

async def send_report(settings, jobs:list[tuple[Job,AIAnalysis]], dry_run:bool=True)->str:
    from jinja2 import Template
    report=Template("<h1>JobRadar: new live matches</h1>{% for job, a in jobs %}<article><h2>{{a.score}} - {{job.title}} at {{job.company_name}}</h2><p>{{a.explanation}}</p><a href='{{job.apply_url}}'>Apply</a></article>{% endfor %}").render(jobs=jobs)
    out=ROOT/"reports";out.mkdir(exist_ok=True); path=out/"jobradar-preview.html";path.write_text(report,encoding="utf-8")
    if dry_run or not settings.notifications_enabled:return str(path)
    if not (settings.resend_api_key and settings.email_from and settings.email_to):raise RuntimeError("Resend/email configuration incomplete")
    async with httpx.AsyncClient(timeout=20) as c:
        r=await c.post("https://api.resend.com/emails",headers={"Authorization":f"Bearer {settings.resend_api_key}"},json={"from":settings.email_from,"to":[settings.email_to],"subject":"JobRadar: new live matches","html":report});r.raise_for_status()
    Session=sessions(settings.database_url)
    async with Session() as db:
        for job,_ in jobs:
            if not await db.scalar(select(Notification.id).where(Notification.job_id==job.id)): db.add(Notification(job_id=job.id,status="SENT",sent_at=datetime.now(timezone.utc))); job.notified=True
        await db.commit()
    return str(path)
