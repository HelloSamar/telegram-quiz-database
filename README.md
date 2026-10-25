# telegram-quiz-database

Automatically collects Telegram quiz polls from a chat/channel into `quizzes.json`
(via GitHub Actions every 15 minutes).

Format: `[question, [options], correct_index, explanation]`

## Setup
1. Get `api_id` / `api_hash` from https://my.telegram.org.
2. Generate a session **locally**: `python generate_session.py`.
3. Repo → Settings → Secrets: `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`, `TELEGRAM_SESSION`.
4. Repo → Settings → Variables: `TELEGRAM_GROUP` (username or numeric id).
5. Run the "Fetch Telegram Quiz" workflow.

Note: the account must be able to see the quiz's correct answer (e.g. have answered it
or be an admin); otherwise the quiz is skipped.
