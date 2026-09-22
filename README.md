# JobRadar AI

JobRadar is a personal, evidence-based job search engine. It imports a durable registry of direct company ATS boards, polls provider APIs asynchronously, keeps a canonical job history, filters for India-compatible junior roles, chooses the most relevant resume, and renders one idempotent report of new live matches.

## Quick start

```powershell
uv sync --all-groups
Copy-Item .env.example .env
uv run jobradar doctor
uv run jobradar sources import-all
uv run jobradar resumes import
uv run jobradar run --dry-run --sample-sources 3
```

The preview is written to `reports/jobradar-preview.html`. Development defaults to no email. Set `NOTIFICATIONS_ENABLED=true`, `EMAIL_FROM`, and `EMAIL_TO` only after the preview is satisfactory.

## Architecture

`registry -> bounded Tavily discovery -> provider adapters -> normalize/dedupe -> eligibility -> deterministic score -> limited Cerebras evaluation -> final live check -> idempotent Resend report -> notification ledger`.

The database is SQLite by default for local development and supports PostgreSQL with `DATABASE_URL=postgresql+psycopg://...`. Tables are created repeatably by `jobradar doctor`; production deployments should execute the same migration step before a run.

## Providers

Live public adapters: Greenhouse, Ashby, Lever. The registry and common adapter interface include Workable, Workday, SmartRecruiters, Recruitee, Teamtailor, BambooHR, iCIMS, Paylocity, Personio, Jobvite, Breezy, Pinpoint, Rippling, JSON-LD, and sitemap sources. Unsupported providers are retained in the registry and fail safely rather than being discarded.

## Configuration and safety

Candidate data and role preferences live in `config/`. Secrets live only in `.env`, which is ignored by Git. The engine records jobs and notification rows with uniqueness constraints, source-health state, and a stable delivery idempotency key. It never treats an ambiguous remote location as India-eligible.

See [ARCHITECTURE.md](ARCHITECTURE.md), [OPERATIONS.md](OPERATIONS.md), [SECURITY.md](SECURITY.md), and [SETUP_REQUIRED.md](SETUP_REQUIRED.md).
