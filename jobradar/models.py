from __future__ import annotations
from datetime import datetime
from enum import StrEnum
from typing import Any
from pydantic import BaseModel, Field, HttpUrl

class EligibilityStatus(StrEnum): ELIGIBLE="ELIGIBLE"; LIKELY_ELIGIBLE="LIKELY_ELIGIBLE"; NEEDS_VERIFICATION="NEEDS_VERIFICATION"; INELIGIBLE="INELIGIBLE"
class LiveStatus(StrEnum): LIVE="LIVE"; CLOSED="CLOSED"; UNCERTAIN="UNCERTAIN"
class OpportunityType(StrEnum): OFFICIAL_JOB="OFFICIAL_JOB"; PUBLIC_HIRING_POST="PUBLIC_HIRING_POST"; PROACTIVE_OUTREACH_LEAD="PROACTIVE_OUTREACH_LEAD"

class RawJob(BaseModel):
    provider: str; source_id: str; external_job_id: str; company_name: str; title: str
    apply_url: str; locations: list[str] = Field(default_factory=list); description_html: str = ""
    posted_at: datetime | None = None; requisition_id: str | None = None; metadata: dict[str, Any] = Field(default_factory=dict)

class NormalizedJob(BaseModel):
    provider: str; source_id: str; external_job_id: str; company_name: str; title: str; normalized_title: str
    apply_url: str; canonical_url: str; canonical_job_key: str; locations: list[str] = Field(default_factory=list)
    description_text: str = ""; content_hash: str; requisition_id: str | None = None; posted_at: datetime | None = None
    opportunity_type: OpportunityType = OpportunityType.OFFICIAL_JOB

class ResumeProfile(BaseModel):
    resume_id: str; display_name: str; category: str; target_roles: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list); technologies: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list); experience: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list); education: list[str] = Field(default_factory=list)
    evidence_items: list[str] = Field(default_factory=list); keywords: list[str] = Field(default_factory=list)
    source_file: str; file_sha256: str; parsed_at: datetime

class AIAnalysis(BaseModel):
    score: int = Field(ge=0, le=100); best_resume_id: str | None = None
    strengths: list[str] = Field(default_factory=list); gaps: list[str] = Field(default_factory=list)
    deal_breakers: list[str] = Field(default_factory=list); explanation: str
