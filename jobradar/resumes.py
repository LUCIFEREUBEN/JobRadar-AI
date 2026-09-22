from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import hashlib, re
from pypdf import PdfReader
from .models import ResumeProfile

KNOWN_SKILLS="python fastapi django flask sql postgresql mysql redis docker kubernetes aws azure gcp git react typescript javascript langchain langgraph rag llm openai agentic machine learning pytorch tensorflow pandas numpy airflow spark kafka dbt tableau power bi".split()
def category(path:Path)->str:
    s=path.stem.lower(); return next((x for x in ["ai_evaluation","fullstack_ai","ml_applied_ai","data_engg","dsci_data_analyst","backend","sde","master","ai"] if x.replace("_","") in s.replace("_","").replace(" ","")),"general")
def import_pdf(path:Path)->ResumeProfile:
    raw=path.read_bytes(); text="\n".join(page.extract_text() or "" for page in PdfReader(path).pages); low=text.lower()
    skills=sorted({skill for skill in KNOWN_SKILLS if re.search(rf"\b{re.escape(skill)}\b",low)})
    digest=hashlib.sha256(raw).hexdigest(); lines=[line.strip() for line in text.splitlines() if line.strip()]
    return ResumeProfile(resume_id=digest[:16],display_name=path.stem,category=category(path),target_roles=[],skills=skills,technologies=skills,domains=[],experience=lines[:20],projects=[],education=[],evidence_items=lines[:50],keywords=skills,source_file=str(path),file_sha256=digest,parsed_at=datetime.now(timezone.utc))
