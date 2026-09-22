# Architecture

JobRadar stores source registry rows, canonical jobs, parsed resume profiles, and notification ledger rows in SQL. Unique source `(provider, board_token)`, canonical job key, resume file hash, and notification job ID constraints provide retry safety.

Each two-hour workflow discovers public ATS boards under a bounded Tavily budget, concurrently fetches active sources with bounded concurrency, then serializes SQLite writes to avoid lock contention. It normalizes content and URLs, rejects obvious seniority, geography, employment, and experience mismatches before scoring. Only likely candidates consume Cerebras capacity; a deterministic score remains usable if the AI provider fails. A final provider lookup is the pre-send live check boundary; closed/uncertain jobs are never notified.

Provider-specific HTTP APIs are preferred. New ATS URLs are detected with provider signatures and can be added to the registry with provenance. Static seed data stays an import artifact, never runtime authority.
