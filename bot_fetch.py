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
from datetime import datetime, timezone
import sys
import time
import urllib.error
import urllib.request

from quizlib import (load_json, migrate_metadata, parse_bot_poll, save_json,
                     save_rows, to_row, validate_quiz, validate_row)

log = logging.getLogger("quiz")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

QUIZ_DIR = "quizzes"                     # one file per run: quizzes/batch_<UTC time>.json
MANIFEST = os.path.join(QUIZ_DIR, "index.json")  # list of batch file names (for the player)
MIGRATED = "batch_00000000_migrated.json"  # old per-quiz / merged files are gathered here once
LEGACY_FILE = "quizzes.json"
METADATA_FILE = "metadata.json"
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


def migrate_old(rows, ids):
    """Gather old per-quiz files (<id>.json) and the old merged quizzes.json into `rows`."""
    for name in sorted(os.listdir(QUIZ_DIR)):
        if name == "index.json" or name.startswith("batch_") or not name.endswith(".json"):
            continue
        path = os.path.join(QUIZ_DIR, name)
        row = load_json(path, None)
        if row and not validate_row(row):
            rows.append(row)
        ids.add(name[:-5])
        os.remove(path)
    for q in load_json(LEGACY_FILE, []):
        if "id" in q and not validate_quiz(q) and q["id"] not in ids:
            rows.append(to_row(q))
            ids.add(q["id"])


def all_rows(manifest):
    rows = []
    for name in manifest:
        rows += load_json(os.path.join(QUIZ_DIR, name), [])
    return rows


def stats_text(manifest, added_now):
    rows = all_rows(manifest)
    lines = [f"📊 Total quizzes: {len(rows)}", f"📦 Batches: {len(manifest)}",
             f"➕ Added this run: {added_now}"]
    if rows:
        lines.append("Latest:")
        lines += ["• " + r[0][:60] for r in rows[-3:][::-1]]
    return "\n".join(lines)


def main():
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        sys.exit("Set BOT_TOKEN.")
    allowed = {int(x) for x in os.environ.get("ALLOWED_USER_IDS", "").replace(" ", "").split(",")
               if x.lstrip("-").isdigit()}
    if not allowed:
        sys.exit("Set ALLOWED_USER_IDS (your Telegram user id; message @userinfobot to find it).")

    os.makedirs(QUIZ_DIR, exist_ok=True)
    meta = migrate_metadata(load_json(METADATA_FILE, {}))
    seen = set(meta["hashes"])
    manifest = [n for n in load_json(MANIFEST, []) if os.path.exists(os.path.join(QUIZ_DIR, n))]
    old_rows = []
    migrate_old(old_rows, seen)
    if old_rows:
        path = os.path.join(QUIZ_DIR, MIGRATED)
        save_rows(path, load_json(path, []) + old_rows)
        if MIGRATED not in manifest:
            manifest.insert(0, MIGRATED)
        log.info("Gathered %d old quizzes into %s", len(old_rows), MIGRATED)
    new_rows = []  # this run's quizzes -> ONE batch file
    offset = meta["update_offset"]
    stats = {}  # chat_id -> {"added": n, "dup": n, "skipped": {reason: n}}
    stats_requests = set()  # chats where an allowed user sent /stats
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
            if not msg:
                continue
            sender = (msg.get("from") or {}).get("id")
            text = (msg.get("text") or "").strip().lower()
            if text.split("@")[0] == "/stats" and sender in allowed:
                stats_requests.add(msg["chat"]["id"])
                continue
            if "poll" not in msg:
                continue
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
                new_rows.append(to_row(quiz))
                st["added"] += 1
                added_total += 1
                log.info("Saved: %s", quiz["question"][:80])
        if len(updates) < 100:
            break

    if new_rows:  # one run = one batch file
        name = f"batch_{datetime.now(timezone.utc):%Y%m%d_%H%M%S}.json"
        save_rows(os.path.join(QUIZ_DIR, name), new_rows)
        manifest.append(name)
        log.info("Wrote %s with %d quizzes", name, len(new_rows))
    meta["update_offset"] = offset  # confirms updates on the next getUpdates call
    meta["hashes"] = sorted(seen)
    save_json(MANIFEST, manifest)
    save_json(METADATA_FILE, meta)
    log.info("Done. %d new, %d batches.", added_total, len(manifest))

    # Replies (best effort): one summary per private chat, plus /stats answers
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
    for chat_id in stats_requests:
        try:
            call(token, "sendMessage", chat_id=chat_id, text=stats_text(manifest, added_total))
        except RuntimeError as e:
            log.warning("Stats reply failed: %s", e)


if __name__ == "__main__":
    main()
