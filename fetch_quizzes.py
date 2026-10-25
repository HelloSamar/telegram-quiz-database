"""Fetch quiz polls from Telegram chats into quizzes.json.

Env: TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_SESSION,
     TELEGRAM_GROUP  (comma-separated usernames / numeric ids)
     BACKFILL=true   (ignore last_message_id, scan full history)
"""
import asyncio
import logging
import os
import sys

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession

from quizlib import (load_json, migrate_metadata, parse_quiz, save_json,
                     to_compact, validate_quiz)

log = logging.getLogger("quiz")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

QUIZZES_FILE = "quizzes.json"
COMPACT_FILE = "quizzes_compact.json"
METADATA_FILE = "metadata.json"
BATCH_LIMIT = 500
MAX_RETRIES = 3
MAX_FLOOD_WAIT = 120  # seconds we are willing to sleep


async def with_retry(factory):
    """Run an async operation with backoff; honour short FloodWaits."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await factory()
        except FloodWaitError as e:
            if e.seconds > MAX_FLOOD_WAIT or attempt == MAX_RETRIES:
                raise
            log.warning("FloodWait %ss, sleeping", e.seconds)
            await asyncio.sleep(e.seconds + 1)
        except (ConnectionError, TimeoutError, OSError) as e:
            if attempt == MAX_RETRIES:
                raise
            delay = 2 ** attempt
            log.warning("Network error (%s), retry in %ss", e, delay)
            await asyncio.sleep(delay)


async def fetch_group(client, group, last_id, seen):
    entity = int(group) if group.lstrip("-").isdigit() else group
    new, newest = [], last_id

    async def run():
        nonlocal newest
        new.clear()
        newest = last_id
        async for m in client.iter_messages(entity, min_id=last_id,
                                            reverse=True, limit=BATCH_LIMIT):
            newest = max(newest, m.id)
            quiz = parse_quiz(m, source=group)
            if not quiz:
                continue
            problems = validate_quiz(quiz)
            if problems:
                log.warning("Skip msg %s in %s: %s", m.id, group, "; ".join(problems))
                continue
            if quiz["id"] in seen:
                continue
            seen.add(quiz["id"])
            new.append(quiz)
            log.info("Saved: %s", quiz["question"][:80])

    await with_retry(run)
    return new, newest


async def main():
    groups = [g.strip() for g in os.environ.get("TELEGRAM_GROUP", "").split(",") if g.strip()]
    if not groups:
        sys.exit("Set TELEGRAM_GROUP (comma-separated usernames or ids).")
    backfill = os.environ.get("BACKFILL", "").lower() == "true"

    quizzes = load_json(QUIZZES_FILE, [])
    meta = migrate_metadata(load_json(METADATA_FILE, {}), groups)
    seen = set(meta["hashes"]) | {q["id"] for q in quizzes if "id" in q}

    total_new = 0
    async with TelegramClient(
        StringSession(os.environ["TELEGRAM_SESSION"]),
        int(os.environ["TELEGRAM_API_ID"]),
        os.environ["TELEGRAM_API_HASH"],
    ) as client:
        if not await client.is_user_authorized():
            sys.exit("Session is invalid or expired. Regenerate TELEGRAM_SESSION.")
        for group in groups:
            last_id = 0 if backfill else meta["last_message_id"].get(group, 0)
            new, newest = await fetch_group(client, group, last_id, seen)
            quizzes.extend(new)
            meta["last_message_id"][group] = max(newest, meta["last_message_id"].get(group, 0))
            total_new += len(new)
            log.info("%s: %d new", group, len(new))

    meta["hashes"] = sorted(seen)
    save_json(QUIZZES_FILE, quizzes)
    save_json(COMPACT_FILE, to_compact(quizzes))
    save_json(METADATA_FILE, meta)
    log.info("Done. %d new, %d total.", total_new, len(quizzes))


if __name__ == "__main__":
    asyncio.run(main())
