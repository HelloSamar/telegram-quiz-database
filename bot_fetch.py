"""Collect quiz polls sent to a Telegram bot and store them in quizzes.json.

Env:
  BOT_TOKEN          token from @BotFather (required)
  ALLOWED_USER_IDS   comma-separated Telegram user ids allowed to add quizzes (required)

Telegram only reveals a quiz's correct answer to bots when the quiz is closed or was
sent to a private chat with the bot, so the workflow is: forward quizzes to the bot.
Standard library only; the token is never logged.
"""
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request

from quizlib import (load_json, migrate_metadata, parse_bot_poll, save_json,
                     to_compact, validate_quiz)

log = logging.getLogger("quiz")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

QUIZZES_FILE, COMPACT_FILE, METADATA_FILE = "quizzes.json", "quizzes_compact.json", "metadata.json"
MAX_PAGES = 20  # x100 updates per run
MAX_RETRIES = 3


def call(token, method, **params):
    """Bot API call with retry. Errors never include the URL (it holds the token)."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = json.dumps(params).encode()
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(url, body, {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            try:
                data = json.load(e)
            except Exception:
                data = {"ok": False, "error_code": e.code, "description": "HTTP error"}
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == MAX_RETRIES:
                raise RuntimeError(f"{method}: network error")
            time.sleep(2 ** attempt)
            continue
        if data.get("ok"):
            return data["result"]
        if data.get("error_code") == 429 and attempt < MAX_RETRIES:
            wait = data.get("parameters", {}).get("retry_after", 5)
            if wait <= 60:
                log.warning("Rate limited, sleeping %ss", wait)
                time.sleep(wait + 1)
                continue
        raise RuntimeError(f"{method} failed: {data.get('error_code')} {data.get('description')}")


def main():
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        sys.exit("Set BOT_TOKEN.")
    allowed = {int(x) for x in os.environ.get("ALLOWED_USER_IDS", "").replace(" ", "").split(",")
               if x.lstrip("-").isdigit()}
    if not allowed:
        sys.exit("Set ALLOWED_USER_IDS (your Telegram user id; message @userinfobot to find it).")

    quizzes = load_json(QUIZZES_FILE, [])
    meta = migrate_metadata(load_json(METADATA_FILE, {}))
    seen = set(meta["hashes"]) | {q["id"] for q in quizzes if "id" in q}
    offset = meta["update_offset"]
    stats = {}  # chat_id -> {"added": n, "dup": n, "skipped": {reason: n}}
    added_total = 0

    for _ in range(MAX_PAGES):
        updates = call(token, "getUpdates", offset=offset, limit=100, timeout=0,
                       allowed_updates=["message", "channel_post"])
        if not updates:
            break
        for u in updates:
            offset = max(offset, u["update_id"] + 1)
            msg = u.get("message") or u.get("channel_post")
            kind = next((k for k in ("poll", "text", "photo", "document") if msg and k in msg), "other")
            log.info("Update %s: from=%s chat=%s type=%s", u["update_id"],
                     (msg or {}).get("from", {}).get("id"), (msg or {}).get("chat", {}).get("id"), kind)
            if not msg or "poll" not in msg:
                continue
            sender = (msg.get("from") or {}).get("id")
            is_channel = "channel_post" in u
            if not is_channel and sender not in allowed:
                log.warning("Ignored poll from unauthorised user id %s", sender)
                continue
            chat = msg["chat"]
            st = stats.setdefault(chat["id"], {"added": 0, "dup": 0, "skipped": {}})
            source = chat.get("username") or str(chat["id"])
            quiz, reason = parse_bot_poll(msg["poll"], msg.get("message_id"), msg.get("date"), source)
            if quiz:
                problems = validate_quiz(quiz)
                if problems:
                    quiz, reason = None, "; ".join(problems)
            if not quiz:
                st["skipped"][reason] = st["skipped"].get(reason, 0) + 1
                log.warning("Skipped: %s", reason)
            elif quiz["id"] in seen:
                st["dup"] += 1
            else:
                seen.add(quiz["id"])
                quizzes.append(quiz)
                st["added"] += 1
                added_total += 1
                log.info("Saved: %s", quiz["question"][:80])
        if len(updates) < 100:
            break

    meta["update_offset"] = offset  # confirms updates on the next getUpdates call
    meta["hashes"] = sorted(seen)
    save_json(QUIZZES_FILE, quizzes)
    save_json(COMPACT_FILE, to_compact(quizzes))
    save_json(METADATA_FILE, meta)
    log.info("Done. %d new, %d total.", added_total, len(quizzes))

    # One summary reply per private chat (best effort)
    for chat_id, st in stats.items():
        if chat_id < 0 and chat_id not in allowed:
            continue
        lines = [f"✅ Added {st['added']}"]
        if st["dup"]:
            lines.append(f"♻️ Duplicates {st['dup']}")
        lines += [f"⚠️ Skipped {n}: {r}" for r, n in st["skipped"].items()]
        try:
            call(token, "sendMessage", chat_id=chat_id, text="\n".join(lines))
        except RuntimeError as e:
            log.warning("Reply failed: %s", e)


if __name__ == "__main__":
    main()
