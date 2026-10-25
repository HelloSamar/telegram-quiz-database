import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from quizlib import (content_hash, migrate_metadata, parse_bot_poll, to_compact,
                     validate_quiz, validate_row)


def poll(**kw):
    p = {"type": "quiz", "question": "Capital of France?",
         "options": [{"text": "Rome"}, {"text": "Paris"}],
         "correct_option_id": 1, "explanation": "Paris."}
    p.update(kw)
    return p


def test_parse_ok():
    q, why = parse_bot_poll(poll(), 7, 1767225600, "me")
    assert why is None and q["answer"] == 1 and q["options"] == ["Rome", "Paris"]
    assert q["date"].startswith("2026-01-01") and q["source"] == "me"
    assert validate_quiz(q) == []


def test_new_api_ids_list():
    q, _ = parse_bot_poll(poll(correct_option_id=None, correct_option_ids=[0]))
    assert q["answer"] == 0


def test_skips():
    assert parse_bot_poll(poll(type="regular"))[0] is None
    q, why = parse_bot_poll(poll(correct_option_id=None))
    assert q is None and "hidden" in why
    assert parse_bot_poll(poll(correct_option_ids=[0, 1]))[0] is None


def test_hash_ignores_case_whitespace_option_order():
    a = content_hash("What  is X?", ["A", "B"])
    assert a == content_hash("what is x?", ["b", "a"])
    assert a != content_hash("what is y?", ["a", "b"])


def test_validation():
    base = {"id": "x", "question": "q", "options": ["a", "b"], "answer": 0}
    assert validate_quiz(base) == []
    assert validate_quiz({**base, "answer": 5})
    assert validate_quiz({**base, "options": ["a"]})
    assert validate_quiz({**base, "options": ["a", "a"]})
    assert validate_quiz({**base, "question": " "})
    assert validate_quiz({"id": "x"})


def test_compact():
    q, _ = parse_bot_poll(poll())
    assert to_compact([q]) == [["Capital of France?", ["Rome", "Paris"], 1, "Paris."]]


def test_migrate_metadata():
    assert migrate_metadata({"last_message_id": {"g": 4}, "hashes": ["a"]}) == \
        {"update_offset": 0, "hashes": ["a"]}
    assert migrate_metadata(None) == {"update_offset": 0, "hashes": []}


def test_validate_row():
    assert validate_row(["q", ["a", "b"], 1, "e"]) == []
    assert validate_row(["q", ["a", "b"], 5, "e"])
    assert validate_row(["q", ["a", "b"]])
    assert validate_row(None)
