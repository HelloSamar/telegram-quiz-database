"""Pure helpers (no network) so they can be unit-tested."""
import hashlib
from datetime import datetime, timezone
import json
import os
import re

MIN_OPTIONS = 2
MAX_OPTIONS = 10


def text_of(value):
    """Newer Telegram layers wrap text in TextWithEntities."""
    return getattr(value, "text", value) or ""


def content_hash(question, options):
    """Stable hash so the same quiz forwarded twice is stored once."""
    norm = lambda s: re.sub(r"\s+", " ", s).strip().casefold()
    payload = json.dumps([norm(question), sorted(norm(o) for o in options)],
                         ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def parse_bot_poll(poll, message_id=None, date=None, source=""):
    """Parse a Bot API Poll dict. Returns (quiz_or_None, skip_reason_or_None)."""
    if poll.get("type") != "quiz":
        return None, "not a quiz"
    ids = poll.get("correct_option_ids")
    if ids is None and poll.get("correct_option_id") is not None:
        ids = [poll["correct_option_id"]]
    if not ids:
        return None, "correct answer hidden by Telegram (forward the quiz to the bot privately)"
    if len(ids) != 1:
        return None, "multiple correct answers not supported"
    options = [text_of(o.get("text") if isinstance(o, dict) else o)
               for o in poll.get("options", [])]
    question = text_of(poll.get("question"))
    return {
        "id": content_hash(question, options),
        "question": question,
        "options": options,
        "answer": ids[0],
        "explanation": poll.get("explanation") or "",
        "source": source,
        "message_id": message_id,
        "date": datetime.fromtimestamp(date, timezone.utc).isoformat() if date else None,
    }, None


def validate_quiz(q):
    """Return a list of problems (empty list = valid)."""
    problems = []
    for key in ("id", "question", "options", "answer"):
        if key not in q:
            problems.append(f"missing '{key}'")
    if problems:
        return problems
    if not str(q["question"]).strip():
        problems.append("empty question")
    opts = q["options"]
    if not isinstance(opts, list) or not (MIN_OPTIONS <= len(opts) <= MAX_OPTIONS):
        problems.append(f"options must be a list of {MIN_OPTIONS}-{MAX_OPTIONS}")
    else:
        if any(not str(o).strip() for o in opts):
            problems.append("empty option")
        if len({str(o).strip().casefold() for o in opts}) != len(opts):
            problems.append("duplicate options")
        if not isinstance(q["answer"], int) or not 0 <= q["answer"] < len(opts):
            problems.append("answer index out of range")
    return problems


def to_row(q):
    """Stored format: [question, options, correct_index, explanation]."""
    return [q["question"], q["options"], q["answer"], q.get("explanation", "")]


def to_compact(quizzes):
    return [to_row(q) for q in quizzes]


def validate_row(row):
    """Validate a stored [question, options, answer, explanation] row."""
    if not (isinstance(row, list) and len(row) == 4):
        return ["row must be [question, options, answer, explanation]"]
    question, options, answer, explanation = row
    if not (isinstance(question, str) and isinstance(explanation, str)):
        return ["question and explanation must be strings"]
    return validate_quiz({"id": "-", "question": question, "options": options,
                          "answer": answer})


def save_row(folder, quiz_id, row):
    """Write one quiz to its own file: <folder>/<id>.json (one line)."""
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"{quiz_id}.json")
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, path)
    return path


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
        f.write("\n")
    os.replace(tmp, path)  # atomic


def migrate_metadata(meta):
    """Normalise metadata; drops fields from the old Telethon version."""
    meta = meta if isinstance(meta, dict) else {}
    offset = meta.get("update_offset", 0)
    return {"update_offset": offset if isinstance(offset, int) else 0,
            "hashes": list(meta.get("hashes", []))}
