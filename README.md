# telegram-quiz-database

Collects Telegram quiz polls from one or more chats into JSON, via GitHub Actions
(every 15 minutes). Optional GitHub Pages quiz player (`index.html`).

## Data
- `quizzes.json`: list of
  `{id, question, options, answer, explanation, source, message_id, date}`
  (`id` is a content hash, so the same quiz forwarded twice is stored once).
- `quizzes_compact.json`: legacy `[question, options, answer, explanation]` format.
- `metadata.json`: per-source last message id + seen hashes.

## Setup
1. Get `api_id` / `api_hash` from https://my.telegram.org.
2. Locally: `pip install -r requirements.txt && python generate_session.py`
   (use a dedicated Telegram account if possible).
3. Repo secrets: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION`.
4. Repo variable: `TELEGRAM_GROUP`, comma-separated usernames or numeric ids.
5. Run "Fetch Telegram Quiz" (tick **backfill** once to import full history).
6. Optional: Settings → Pages → deploy from `main` / root to get the quiz player and a
   public `quizzes.json` endpoint.

The account must be able to see correct answers (answered the quiz or admin);
otherwise that quiz is skipped.

## Reliability
Retries with backoff, FloodWait handling, expired-session detection, validation before
every commit, and an auto-opened issue if the workflow fails.

## Development
`pip install -r requirements.txt -r requirements-dev.txt && pytest && python validate.py`
