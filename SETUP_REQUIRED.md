# Required manual setup

1. Create a Supabase/PostgreSQL project and set `DATABASE_URL` for durable cloud operation (SQLite is suitable for local testing).
2. Configure a verified Resend sender and recipient email address in `.env` or GitHub Actions secrets.
3. Add `DATABASE_URL`, `CEREBRAS_API_KEY`, `RESEND_API_KEY`, `TAVILY_API_KEY`, `EMAIL_FROM`, and `EMAIL_TO` to GitHub repository secrets.
4. Enable notifications only after a dry-run preview passes review.
