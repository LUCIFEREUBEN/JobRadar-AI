from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlparse
import re, json, httpx
from .models import RawJob, LiveStatus

@dataclass
class SourceRef:
    id: str; provider: str; company_name: str; board_token: str; base_url: str

class JobSourceAdapter(ABC):
    provider: str
    @abstractmethod
    async def fetch_jobs(self, source: SourceRef) -> list[RawJob]: ...
    async def fetch_job(self, source: SourceRef, external_job_id: str) -> RawJob | None: ...
    async def verify_source(self, source: SourceRef) -> bool: return bool(await self.fetch_jobs(source))
    async def verify_job(self, source: SourceRef, external_job_id: str) -> LiveStatus: return LiveStatus.LIVE if await self.fetch_job(source, external_job_id) else LiveStatus.CLOSED

class Greenhouse(JobSourceAdapter):
    provider="greenhouse"
    async def fetch_jobs(self,s:SourceRef)->list[RawJob]:
        async with httpx.AsyncClient(timeout=20) as c: data=(await c.get(f"https://boards-api.greenhouse.io/v1/boards/{s.board_token}/jobs?content=true")).json()
        return [RawJob(provider=self.provider,source_id=s.id,external_job_id=str(j["id"]),company_name=s.company_name,title=j["title"],apply_url=j["absolute_url"],locations=[j.get("location",{}).get("name","")],description_html=j.get("content","") or "",requisition_id=j.get("requisition_id")) for j in data.get("jobs",[])]
    async def fetch_job(self,s:SourceRef,jid:str)->RawJob|None: return next((j for j in await self.fetch_jobs(s) if j.external_job_id==str(jid)),None)
class Lever(JobSourceAdapter):
    provider="lever"
    async def fetch_jobs(self,s:SourceRef)->list[RawJob]:
        async with httpx.AsyncClient(timeout=20) as c: data=(await c.get(f"https://api.lever.co/v0/postings/{s.board_token}?mode=json")).json()
        return [RawJob(provider=self.provider,source_id=s.id,external_job_id=j["id"],company_name=s.company_name,title=j["text"],apply_url=j["hostedUrl"],locations=[j.get("categories",{}).get("location","")],description_html=j.get("descriptionPlain","") or "") for j in data]
    async def fetch_job(self,s:SourceRef,jid:str)->RawJob|None: return next((j for j in await self.fetch_jobs(s) if j.external_job_id==jid),None)
class Ashby(JobSourceAdapter):
    provider="ashby"
    async def fetch_jobs(self,s:SourceRef)->list[RawJob]:
        async with httpx.AsyncClient(timeout=20) as c: data=(await c.get(f"https://api.ashbyhq.com/posting-api/job-board/{s.board_token}")).json()
        return [RawJob(provider=self.provider,source_id=s.id,external_job_id=j["id"],company_name=s.company_name,title=j["title"],apply_url=j["jobUrl"],locations=[j.get("location","")],description_html=j.get("descriptionHtml","") or "") for j in data.get("jobs",[])]
    async def fetch_job(self,s:SourceRef,jid:str)->RawJob|None: return next((j for j in await self.fetch_jobs(s) if j.external_job_id==jid),None)
class GenericAdapter(JobSourceAdapter):
    def __init__(self, provider:str): self.provider=provider
    async def fetch_jobs(self,s:SourceRef)->list[RawJob]:
        """Read public JSON APIs or JSON-LD without provider-specific browser automation."""
        if not s.base_url:return []
        async with httpx.AsyncClient(timeout=20,follow_redirects=True,headers={"User-Agent":"JobRadarAI/0.1 (+public job monitoring)"}) as c:
            response=await c.get(s.base_url); response.raise_for_status()
        content_type=response.headers.get("content-type","")
        payload=response.json() if "json" in content_type else None
        records=[]
        def walk(value):
            if isinstance(value,dict):
                if str(value.get("@type","")).lower() in {"jobposting","job posting"}: records.append(value)
                for child in value.values(): walk(child)
            elif isinstance(value,list):
                for child in value:walk(child)
        if payload is not None: walk(payload)
        else:
            for block in re.findall(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',response.text,re.I|re.S):
                try:walk(json.loads(block))
                except json.JSONDecodeError:continue
        jobs=[]
        for index,item in enumerate(records):
            title=item.get("title") or item.get("name")
            if not title:continue
            ident=str(item.get("identifier",{}).get("value") if isinstance(item.get("identifier"),dict) else item.get("identifier") or index)
            org=item.get("hiringOrganization",{}); company=org.get("name") if isinstance(org,dict) else s.company_name
            loc=item.get("jobLocation",{}); location=loc.get("address",{}).get("addressLocality","") if isinstance(loc,dict) else ""
            jobs.append(RawJob(provider=self.provider,source_id=s.id,external_job_id=ident,company_name=company or s.company_name,title=title,apply_url=item.get("url") or s.base_url,locations=[location] if location else [],description_html=item.get("description","") or "",requisition_id=ident))
        return jobs
    async def fetch_job(self,s:SourceRef,jid:str)->RawJob|None:return next((j for j in await self.fetch_jobs(s) if j.external_job_id==jid),None)

ADAPTERS={"greenhouse":Greenhouse(),"lever":Lever(),"ashby":Ashby()}
for _provider in "workable workday smartrecruiters recruitee teamtailor bamboohr icims paylocity personio jobvite breezy pinpoint rippling jsonld sitemap".split(): ADAPTERS[_provider]=GenericAdapter(_provider)

PATTERNS={
 "greenhouse":r"(?:job-boards|boards)\.greenhouse\.io/([^/?#]+)", "ashby":r"jobs\.ashbyhq\.com/([^/?#]+)", "lever":r"jobs\.lever\.co/([^/?#]+)", "workable":r"apply\.workable\.com/([^/?#]+)", "smartrecruiters":r"jobs\.smartrecruiters\.com/([^/?#]+)", "recruitee":r"([^./]+)\.recruitee\.com", "teamtailor":r"([^./]+)\.teamtailor\.com", "bamboohr":r"([^./]+)\.bamboohr\.com", "personio":r"([^./]+)\.jobs\.personio", "pinpoint":r"([^./]+)\.pinpointhq\.com"}
def discover_source(url:str)->tuple[str,str]|None:
    for provider,pattern in PATTERNS.items():
        found=re.search(pattern,url,re.I)
        if found:return provider,found.group(1)
    return None
