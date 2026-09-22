# Operations

Run `uv run jobradar doctor` before production. Import sources and resumes once, then use `uv run jobradar run --dry-run` to inspect the report. Use a small `--sample-sources` first because a full seed registry can be large.

For scheduled execution, GitHub Actions runs every two hours and executes the dry-run-disabled command after database and secret configuration are complete. A source failure does not terminate an entire cycle; five consecutive failures mark a source `BROKEN`. Inspect source statistics with `uv run jobradar sources stats` and test a bounded sample with `uv run jobradar sources verify --sample 10`.

For PostgreSQL/Supabase set `DATABASE_URL` to an async SQLAlchemy-compatible URL. Back up the database; job and notification history must be retained to prevent repeats.
