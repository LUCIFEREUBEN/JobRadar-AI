# Security

API tokens are environment secrets, never source files, logs, fixtures, or reports. `.env` is ignored. AI prompts include only shortlisted job text and resume evidence; they instruct the model not to invent qualifications. The crawler uses public endpoints only and does not bypass login, CAPTCHA, or access controls.
