#!/usr/bin/env python3
"""Expand the bootstrap ATS registry from public source directories. Python 3.11+, stdlib only."""
import argparse,csv,json,os,re,time
from collections import OrderedDict,Counter
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

FIELDS=['entry_type','ats','company','board_token','token_type','hosted_board_url','api_jobs_url','api_jobs_content_url','api_method','source_status','source_checked_date','source_dataset','source_url','notes']
NOISE={'api','app','apps','career','careers','company','companies','developer','developers','docs','example','exampleco','examplecorp','example-corp','example-gmbh','foo','help','jobs','j','search','slug','support','test','testing','www','acme','acme-corp','beta','leverdemo','parseresume','patients','safety','applications','field','open-roles','robots.txt','https:'}
DIRS=[
 ('greenhouse','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/greenhouse_companies.json','Feashliaa/job-board-aggregator','flat'),
 ('ashby','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/ashby_companies.json','Feashliaa/job-board-aggregator','flat'),
 ('lever','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/lever_companies.json','Feashliaa/job-board-aggregator','flat'),
 ('workday','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/workday_companies.json','Feashliaa/job-board-aggregator','flat'),
 ('bamboohr','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/bamboohr_companies.json','Feashliaa/job-board-aggregator','flat'),
 ('icims','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/icims_companies.json','Feashliaa/job-board-aggregator','flat'),
 ('paylocity','https://raw.githubusercontent.com/Feashliaa/job-board-aggregator/main/data/paylocity_companies_clean.json','Feashliaa/job-board-aggregator','paylocity'),
 ('workable','https://raw.githubusercontent.com/Infrasity-Labs/developer-marketing-jobs/main/discovered_workable_companies.json','Infrasity-Labs/developer-marketing-jobs','companies_key'),
 ('smartrecruiters','https://raw.githubusercontent.com/Tindi12/Scout/main/packages/api/data/smartrecruiters_companies.json','Tindi12/Scout','flat'),
 ('recruitee','https://raw.githubusercontent.com/Tindi12/Scout/main/packages/api/data/recruitee_companies.json','Tindi12/Scout','flat'),
 ('teamtailor','https://raw.githubusercontent.com/Tindi12/Scout/main/packages/api/data/teamtailor_companies.json','Tindi12/Scout','flat'),
 ('multi','https://raw.githubusercontent.com/outscal/OpenJobs/main/data/companies_v2.json','outscal/OpenJobs','outscal'),
 ('multi','https://raw.githubusercontent.com/Thelastpoet/africa-ats-directory/main/companies/index.json','Thelastpoet/africa-ats-directory','africa'),
]
PATTERNS=[
 ('greenhouse',r'https?://(?:job-boards|boards)\.greenhouse\.io/([A-Za-z0-9._-]+)'),('ashby',r'https?://jobs\.ashbyhq\.com/([A-Za-z0-9._-]+)'),('lever',r'https?://jobs\.lever\.co/([A-Za-z0-9._-]+)'),('workable',r'https?://apply\.workable\.com/([A-Za-z0-9._-]+)'),('smartrecruiters',r'https?://jobs\.smartrecruiters\.com/([A-Za-z0-9._-]+)'),('recruitee',r'https?://([A-Za-z0-9._-]+)\.recruitee\.com'),('teamtailor',r'https?://([A-Za-z0-9._-]+)\.teamtailor\.com'),('breezy',r'https?://([A-Za-z0-9._-]+)\.breezy\.hr'),('personio',r'https?://([A-Za-z0-9._-]+)\.jobs\.personio\.(?:de|com)'),('bamboohr',r'https?://([A-Za-z0-9._-]+)\.bamboohr\.com'),('jobvite',r'https?://jobs\.jobvite\.com/([A-Za-z0-9._-]+)'),('rippling',r'https?://ats\.rippling\.com/(?:[A-Za-z]{2}(?:-[A-Za-z]{2})?/)?([A-Za-z0-9._-]+)/jobs'),('pinpoint',r'https?://([A-Za-z0-9._-]+)\.pinpointhq\.com'),('join',r'https?://(?:www\.)?join\.com/companies/([A-Za-z0-9._-]+)')]
PATTERNS=[(a,re.compile(p,re.I)) for a,p in PATTERNS]
WORKDAY=re.compile(r'https?://([A-Za-z0-9._-]+)\.(wd\d+)\.myworkdayjobs\.com/([^/?#]+)',re.I)

def clean(x): return str(x or '').strip().strip('/').lower()
def valid(x):
 x=clean(x); return bool(x) and x not in NOISE and len(x)<=240 and bool(re.fullmatch(r'[a-z0-9._|:-]+',x))
def urls(a,t):
 if a=='greenhouse': return f'https://job-boards.greenhouse.io/{t}',f'https://boards-api.greenhouse.io/v1/boards/{t}/jobs',f'https://boards-api.greenhouse.io/v1/boards/{t}/jobs?content=true','GET','slug'
 if a=='ashby': return f'https://jobs.ashbyhq.com/{t}',f'https://api.ashbyhq.com/posting-api/job-board/{t}',f'https://api.ashbyhq.com/posting-api/job-board/{t}?includeCompensation=true','GET','slug'
 if a=='lever': return f'https://jobs.lever.co/{t}',f'https://api.lever.co/v0/postings/{t}?mode=json','','GET','slug'
 if a=='workable': return f'https://apply.workable.com/{t}/',f'https://apply.workable.com/api/v1/widget/accounts/{t}?details=true','','GET','slug'
 if a=='smartrecruiters': return f'https://jobs.smartrecruiters.com/{t}',f'https://api.smartrecruiters.com/v1/companies/{t}/postings','','GET','company_slug'
 if a=='recruitee': return f'https://{t}.recruitee.com',f'https://{t}.recruitee.com/api/offers/','','GET','subdomain'
 if a=='teamtailor': return f'https://{t}.teamtailor.com/jobs',f'https://{t}.teamtailor.com/jobs.json','','GET','subdomain'
 if a=='breezy': return f'https://{t}.breezy.hr',f'https://{t}.breezy.hr/json?verbose=true','','GET','subdomain'
 if a=='personio': return f'https://{t}.jobs.personio.de',f'https://{t}.jobs.personio.de/xml?language=en','','GET','subdomain'
 if a=='bamboohr': return f'https://{t}.bamboohr.com/careers',f'https://{t}.bamboohr.com/careers/list','','GET','subdomain'
 if a=='icims': return f'https://careers-{t}.icims.com',f'https://careers-{t}.icims.com/sitemap.xml','','GET','subdomain_fragment'
 if a=='rippling': return f'https://ats.rippling.com/{t}/jobs',f'https://api.rippling.com/platform/api/ats/v1/board/{t}/jobs','','GET','board_slug'
 if a=='pinpoint': return f'https://{t}.pinpointhq.com',f'https://{t}.pinpointhq.com/postings.json','','GET','subdomain'
 if a=='jobvite': return f'https://jobs.jobvite.com/{t}','','','HTML','slug'
 if a=='join': return f'https://join.com/companies/{t}','','','HTML','slug'
 if a=='paylocity': return f'https://recruiting.paylocity.com/recruiting/jobs/All/{t}/','','','HTML','tenant_guid'
 if a=='workday':
  try:
   tenant,wd,site=t.split('|',2); h=f'{tenant}.{wd}.myworkdayjobs.com'; return f'https://{h}/{site}',f'https://{h}/wday/cxs/{tenant}/{site}/jobs','','POST','tenant|instance|site'
  except: return '','','','POST','tenant|instance|site'
 return '','','','','slug'

def fetch(url,retries=4):
 err=None
 for i in range(retries):
  try:
   req=Request(url,headers={'User-Agent':'JobRadar-SourceRegistry/1.0','Accept':'application/json,text/plain,*/*'})
   with urlopen(req,timeout=90) as r: return json.loads(r.read().decode('utf-8'))
  except (HTTPError,URLError,TimeoutError,ValueError) as e: err=e; time.sleep(min(2**i,8))
 raise RuntimeError(f'{url}: {err}')

def all_urls(c):
 if not isinstance(c,dict): return []
 out=[]
 for k in ('ats_links','list_urls'):
  if isinstance(c.get(k),list): out.extend(c[k])
 for k in ('ats_url','careers_url','listUrl','api','website','jobs_url','board_url'):
  if isinstance(c.get(k),str): out.append(c[k])
 return [u for u in out if isinstance(u,str) and u.startswith(('http://','https://'))]

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--bootstrap',default='ats_source_registry_bootstrap.csv'); ap.add_argument('--output',default='ats_source_registry_full.csv'); ap.add_argument('--per-provider-dir',default='provider_csvs'); ap.add_argument('--report',default='full_registry_summary.json'); ap.add_argument('--skip-outscal',action='store_true'); a=ap.parse_args()
 rows=OrderedDict(); today=datetime.now(timezone.utc).date().isoformat(); failed=[]
 def put(ats,tok,company=None,ds='',src='',status='upstream_directory_seed',note=''):
  tok=clean(tok)
  if not valid(tok): return
  h,api,cap,meth,typ=urls(ats,tok); r={k:'' for k in FIELDS}; r.update(entry_type='board',ats=ats,company=company or tok,board_token=tok,token_type=typ,hosted_board_url=h,api_jobs_url=api,api_jobs_content_url=cap,api_method=meth,source_status=status,source_checked_date=today,source_dataset=ds,source_url=src,notes=note or ('Company label is board-token-derived; resolve canonical name from live board metadata.' if not company else ''))
  old=rows.get((ats,tok));
  if old is None or (old.get('company')==old.get('board_token') and company): rows[(ats,tok)]=r
 if os.path.exists(a.bootstrap):
  with open(a.bootstrap,newline='',encoding='utf-8-sig') as f:
   for r in csv.DictReader(f):
    if r.get('entry_type')=='board' and r.get('ats') and r.get('board_token'): rows[(r['ats'],clean(r['board_token']))]={k:r.get(k,'') for k in FIELDS}
 for ats,src,ds,parser in DIRS:
  if ds=='outscal/OpenJobs' and a.skip_outscal: continue
  print('fetch',ds,ats,file=sys.stderr if False else __import__('sys').stderr)
  try: obj=fetch(src)
  except Exception as e: failed.append({'dataset':ds,'url':src,'error':str(e)}); continue
  try:
   if parser=='flat':
    for t in obj if isinstance(obj,list) else []: put(ats,t,ds=ds,src=src)
   elif parser=='companies_key':
    for t in obj.get('companies',[]) if isinstance(obj,dict) else []: put(ats,t,ds=ds,src=src)
   elif parser=='paylocity':
    for x in obj if isinstance(obj,list) else []:
     if isinstance(x,dict): put('paylocity',x.get('guid'),x.get('name'),ds,src)
   elif parser=='africa':
    entries=obj if isinstance(obj,list) else (obj.get('companies',[]) if isinstance(obj,dict) else [])
    for c in entries:
     if not isinstance(c,dict): continue
     cat=(c.get('ats') or '').lower(); pm=c.get('platform_metadata') or {}; tok=pm.get('board_token') or pm.get('org_slug') or pm.get('account_slug')
     if cat and tok: put(cat,tok,c.get('company'),ds,src,'curated_africa_seed',f"source status={c.get('status','')}; country={c.get('country','')}")
   elif parser=='outscal':
    comps=obj if isinstance(obj,list) else (obj.get('companies',[]) if isinstance(obj,dict) else [])
    for c in comps:
     name=c.get('name') if isinstance(c,dict) else None
     for u in all_urls(c):
      for pat_ats,rx in PATTERNS:
       m=rx.search(u)
       if m: put(pat_ats,m.group(1),name,ds,src,'upstream_multi_ats_seed')
      m=WORKDAY.search(u)
      if m and m.group(3).lower() not in {'en-us','en-gb','fr-fr','de-de'}: put('workday',f'{m.group(1)}|{m.group(2)}|{m.group(3)}',name,ds,src,'upstream_multi_ats_seed')
  except Exception as e: failed.append({'dataset':ds,'url':src,'error':'parse: '+str(e)})
 data=sorted(rows.values(),key=lambda r:(r['ats'],r['board_token']));
 with open(a.output,'w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows(data)
 os.makedirs(a.per_provider_dir,exist_ok=True)
 for ats in sorted({r['ats'] for r in data}):
  with open(os.path.join(a.per_provider_dir,f'{ats}_source_registry.csv'),'w',newline='',encoding='utf-8') as f: w=csv.DictWriter(f,fieldnames=FIELDS); w.writeheader(); w.writerows([r for r in data if r['ats']==ats])
 c=Counter(r['ats'] for r in data); report={'generated_at':datetime.now(timezone.utc).isoformat(),'total_unique_board_tokens':len(data),'by_ats':dict(sorted(c.items())),'failed_datasets':failed,'warning':'Directory membership is discovery, not liveness. Live-check provider endpoints at crawl time.'}
 with open(a.report,'w',encoding='utf-8') as f: json.dump(report,f,indent=2)
 print(json.dumps(report,indent=2))
if __name__=='__main__': main()
