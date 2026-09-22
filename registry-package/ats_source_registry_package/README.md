# JobRadar ATS Source Registry

Generated 2026-09-22.

This package combines the uploaded Greenhouse and Ashby board-token files with additional public ATS tenant discoveries, and includes an internet-connected builder that expands the registry from larger public corpora.

## Main files

- `ats_source_registry_bootstrap.csv` — 10k+ immediately usable, deduplicated board/tenant seeds plus directory rows.
- `<ats>_source_registry.csv` — per-provider bootstrap subsets.
- `provider_directories.csv` — upstream data feeds for the large expansion pass.
- `build_full_registry.py` — downloads/merges the upstream directories and outputs `ats_source_registry_full.csv` plus per-provider CSVs.
- `registry_summary.json` — bootstrap counts.
- `refresh_registry.yml` — GitHub Actions example to refresh the full registry daily.

## Expand to the much larger registry

Run from this folder on any internet-connected Python 3.11+ environment:

```bash
python build_full_registry.py \
  --bootstrap ats_source_registry_bootstrap.csv \
  --output ats_source_registry_full.csv \
  --per-provider-dir provider_csvs \
  --report full_registry_summary.json
```

The builder uses only Python's standard library.

## Providers covered

Bootstrap board rows currently cover Greenhouse, Ashby, Lever, Workable, SmartRecruiters, Recruitee, Teamtailor, Breezy, Personio, Rippling, Pinpoint and Jobvite. Directory expansion additionally includes Workday, BambooHR, iCIMS, Paylocity and Join.com discoveries.

## Upstream discovery sources

- https://github.com/Feashliaa/job-board-aggregator
- https://github.com/Infrasity-Labs/developer-marketing-jobs
- https://github.com/Tindi12/Scout
- https://github.com/outscal/OpenJobs
- https://github.com/Thelastpoet/africa-ats-directory

## Important design note

No static file can truly contain every ATS tenant forever. Companies create, rename, migrate and close boards continuously, and some ATS instances are private or not publicly indexed. Treat this registry as a discovery layer. Your runtime crawler should verify each board endpoint before fetching jobs, track health/failures, and add newly discovered ATS URLs back into the registry.

Recommended runtime fields in your database: `first_seen_at`, `last_success_at`, `last_failure_at`, `consecutive_failures`, `is_live`, and `disabled_at`.

## License note

The Feashliaa repository states its curated company datasets are CC BY-NC 4.0, while its code is MIT. Review upstream licenses before redistributing or commercially monetizing the registry. Other source repositories have their own licenses and should also be reviewed.
