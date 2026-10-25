"""Fetch quiz polls from a Telegram chat and store them in quizzes.json.

Each quiz is stored as: [question, [options...], correct_index, explanation]
"""
import asyncio
import json
import os
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]
SESSION = os.environ["TELEGRAM_SESSION"]
GROUP = os.environ.get("TELEGRAM_GROUP", "").strip()

QUIZZES_FILE = "quizzes.json"
METADATA_FILE = "metadata.json"
BATCH_LIMIT = 500  # max new messages inspected per run


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # atomic: never leaves a half-written file


def text_of(value):
    """Newer Telegram layers wrap text in TextWithEntities."""
    return getattr(value, "text", value) or ""


def parse_quiz(message):
    """Return (poll_id, quiz_list) or None if the message isn't a quiz."""
    media = message.poll  # MessageMediaPoll
    if media is None:
        return None
    poll = media.poll
    if not poll.quiz:
        return None

    results = media.results
    correct_index = None
    if results and results.results:
        for i, r in enumerate(results.results):
            if r.correct:
                correct_index = i
                break
    if correct_index is None:
        return None  # correct answer unknown (e.g. not visible); skip

    options = [text_of(a.text) for a in poll.answers]
    explanation = text_of(results.solution) if results and results.solution else ""
    return poll.id, [text_of(poll.question), options, correct_index, explanation]


async def main():
    if not GROUP:
        sys.exit("Set the TELEGRAM_GROUP environment variable (username or id).")
    group = int(GROUP) if GROUP.lstrip("-").isdigit() else GROUP

    quizzes = load_json(QUIZZES_FILE, [])
    metadata = load_json(METADATA_FILE, {"last_message_id": 0, "poll_ids": []})
    seen = set(metadata["poll_ids"])
    last_id = metadata.get("last_message_id", 0)

    added = 0
    async with TelegramClient(StringSession(SESSION), API_ID, API_HASH) as client:
        # Only messages newer than the last run, oldest first.
        async for message in client.iter_messages(
            group, min_id=last_id, reverse=True, limit=BATCH_LIMIT
        ):
            last_id = max(last_id, message.id)
            parsed = parse_quiz(message)
            if not parsed:
                continue
            poll_id, quiz = parsed
            if poll_id in seen:
                continue
            quizzes.append(quiz)
            seen.add(poll_id)
            metadata["poll_ids"].append(poll_id)
            added += 1
            print("Saved:", quiz[0])

    metadata["last_message_id"] = last_id
    save_json(QUIZZES_FILE, quizzes)
    save_json(METADATA_FILE, metadata)
    print(f"Done. {added} new quiz(zes), {len(quizzes)} total.")


if __name__ == "__main__":
    asyncio.run(main())
