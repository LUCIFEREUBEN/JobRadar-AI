from jobradar.models import RawJob
from jobradar.normalization import normalize, eligibility
from jobradar.sources import discover_source

PREFS={"excluded_title_terms":["senior","staff","principal","lead","director","manager"],"excluded_terms":["unpaid"]}
def test_cross_source_canonical_identity_is_stable_for_same_official_url():
    a=RawJob(provider="greenhouse",source_id="a",external_job_id="1",company_name="Acme, Inc.",title="Junior AI Engineer",apply_url="https://jobs.acme.com/a?ref=x",description_html="Python FastAPI")
    b=RawJob(provider="greenhouse",source_id="b",external_job_id="1",company_name="Acme",title="Junior AI Engineer",apply_url="https://jobs.acme.com/a",description_html="Python FastAPI")
    assert normalize(a).canonical_url==normalize(b).canonical_url
def test_senior_is_rejected(): assert eligibility("Staff AI Engineer","",[],PREFS)[0].value=="INELIGIBLE"
def test_us_only_remote_is_rejected(): assert eligibility("AI Engineer","Remote - US residents only",["Remote"],PREFS)[0].value=="INELIGIBLE"
def test_worldwide_india_is_eligible(): assert eligibility("AI Engineer","Remote worldwide. India eligible",["Remote"],PREFS)[0].value=="ELIGIBLE"
def test_discovery_detects_ats(): assert discover_source("https://jobs.ashbyhq.com/acme/123")==("ashby","acme")
