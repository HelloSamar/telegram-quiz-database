"""Pure helpers (no network) so they can be unit-tested."""
import hashlib
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


def parse_quiz(message, source=""):
    """Return a quiz dict for a quiz-poll message, else None."""
    media = getattr(message, "poll", None)
    if media is None:
        return None
    poll = media.poll
    if not poll.quiz:
        return None
    results = media.results
    correct = None
    if results and results.results:
        for i, r in enumerate(results.results):
            if r.correct:
                correct = i
                break
    if correct is None:
        return None
    options = [text_of(a.text) for a in poll.answers]
    question = text_of(poll.question)
    return {
        "id": content_hash(question, options),
        "question": question,
        "options": options,
        "answer": correct,
        "explanation": text_of(results.solution) if results and results.solution else "",
        "source": source,
        "message_id": message.id,
        "date": message.date.isoformat() if getattr(message, "date", None) else None,
    }


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


def to_compact(quizzes):
    """Legacy format: [question, options, correct_index, explanation]."""
    return [[q["question"], q["options"], q["answer"], q.get("explanation", "")]
            for q in quizzes]


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


def migrate_metadata(meta, groups):
    """Old: {last_message_id:int, poll_ids:[...]}  ->  per-source ids + hashes."""
    meta = dict(meta or {})
    last = meta.get("last_message_id", {})
    if not isinstance(last, dict):  # legacy int
        last = {groups[0]: last} if groups and last else {}
    meta["last_message_id"] = last
    meta.setdefault("hashes", [])
    meta.pop("poll_ids", None)  # superseded by content hashes
    return meta
