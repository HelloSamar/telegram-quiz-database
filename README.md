# telegram-quiz-database

Stores Telegram quiz polls as JSON **inside this repo**. A Telegram bot receives quizzes
you forward to it; a GitHub Action (every 15 min) saves them. Nothing runs on your computer.

## Data
- `quizzes/<id>.json`: one file per quiz, never merged. Each holds
  `[question, options, correct_index, explanation]` (`id` is a content hash, so duplicates are stored once)
- `quizzes/index.json`: list of the file names, in the order they were added (used by the player)
- `metadata.json`: update offset + seen hashes
- `index.html`: optional quiz player (enable Pages from `main` / root)

## Bot commands
- Send `/stats` to the bot: it replies with the total saved and the latest quizzes
  (answered on the next run, so within ~15 min or when you run the workflow manually).

## Setup (all from your phone)
1. In Telegram, open **@BotFather** → `/newbot` → copy the token.
2. Message **@userinfobot** to get your numeric user id.
3. Repo → Settings → Secrets and variables → Actions:
   - Secret `BOT_TOKEN` = the token
   - Variable `ALLOWED_USER_IDS` = your id (comma-separate to allow more people)
4. Open your bot in Telegram and press **Start**.
5. **Forward quizzes to the bot** (select many messages and forward at once).
   Within ~15 min they appear in `quizzes.json`, and the bot replies with a summary.
   Actions → "Fetch Telegram Quiz" → Run workflow does it immediately.

## Why forwarding?
Telegram hides a quiz's correct answer from bots unless the quiz is closed, was sent by
the bot, or was sent to a private chat with the bot. Quizzes the bot merely sees in a
group won't have an answer, so they are skipped. Forwarding privately avoids that.
Bots also can't read old chat history, which is why you forward rather than backfill.

Channels: add the bot as admin and it also receives new `channel_post` quizzes, but only
closed ones carry the answer.

## Safety
Only users in `ALLOWED_USER_IDS` can add quizzes, so strangers who find the bot can't
write to your repo. If a token leaks, regenerate it with `/revoke` in @BotFather.
The bot token is never logged.

## Development
`pip install -r requirements-dev.txt && pytest && python validate.py`
