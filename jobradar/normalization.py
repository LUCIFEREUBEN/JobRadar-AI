from __future__ import annotations
import hashlib, re
from urllib.parse import urlsplit, urlunsplit
try:
    from selectolax.parser import HTMLParser
except ImportError:
    HTMLParser = None
from .models import RawJob, NormalizedJob, EligibilityStatus

def clean(value: str) -> str: return re.sub(r"\s+", " ", value or "").strip()
def slug(value: str) -> str: return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
def canonical_url(url: str) -> str:
    p=urlsplit(url); return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", ""))
def text_from_html(html: str) -> str:
    if HTMLParser:
        return clean(HTMLParser(html or "").text(separator=" "))
    return clean(re.sub(r"<[^>]+>", " ", html or ""))
def normalize(raw: RawJob) -> NormalizedJob:
    text=text_from_html(raw.description_html); url=canonical_url(raw.apply_url)
    identity="|".join([raw.provider.lower(), raw.external_job_id or "", slug(raw.company_name), slug(raw.title), url])
    key=hashlib.sha256(identity.encode()).hexdigest()
    return NormalizedJob(provider=raw.provider.lower(),source_id=raw.source_id,external_job_id=str(raw.external_job_id),company_name=clean(raw.company_name),title=clean(raw.title),normalized_title=slug(raw.title),apply_url=raw.apply_url,canonical_url=url,canonical_job_key=key,locations=raw.locations,description_text=text,content_hash=hashlib.sha256((text+raw.title).encode()).hexdigest(),requisition_id=raw.requisition_id,posted_at=raw.posted_at)
def eligibility(title: str, description: str, locations: list[str], preferences: dict) -> tuple[EligibilityStatus, list[str]]:
    corpus=slug(" ".join([title, description, *locations])); title_norm=slug(title); reasons=[]
    if any(term in title_norm for term in preferences.get("excluded_title_terms", [])): return EligibilityStatus.INELIGIBLE,["seniority excluded by preference"]
    if re.search(r"\b([4-9]|[1-9][0-9])\+? years?\b", corpus): return EligibilityStatus.INELIGIBLE,["experience requirement exceeds configured maximum"]
    if any(term in corpus for term in ["us citizens only","us residents only","must be authorized to work in the us","uk residents only","eu residents only"]): return EligibilityStatus.INELIGIBLE,["explicit geography restriction"]
    if any(term in corpus for term in preferences.get("excluded_terms", [])): return EligibilityStatus.INELIGIBLE,["employment type excluded"]
    if "remote" in corpus and "india" not in corpus and any(x in corpus for x in ["us remote","remote us","uk remote","eu remote"]): return EligibilityStatus.INELIGIBLE,["remote region excludes India"]
    if "india" in corpus or "worldwide" in corpus or "global remote" in corpus: return EligibilityStatus.ELIGIBLE,["India or worldwide eligibility evidenced"]
    if "remote" in corpus: return EligibilityStatus.NEEDS_VERIFICATION,["remote location lacks India confirmation"]
    return EligibilityStatus.LIKELY_ELIGIBLE,["no explicit location restriction found"]
