import datetime
import os
import sys
from types import SimpleNamespace as NS

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from quizlib import (content_hash, migrate_metadata, parse_quiz, to_compact,
                     validate_quiz)


def msg(quiz=True, correct=1, question="Capital of France?", opts=("Rome", "Paris"),
        solution="Paris is the capital."):
    poll = NS(quiz=quiz, question=NS(text=question),
              answers=[NS(text=NS(text=o)) for o in opts])
    results = NS(results=[NS(correct=(i == correct)) for i in range(len(opts))],
                 solution=solution)
    return NS(id=7, date=datetime.datetime(2026, 1, 1), poll=NS(poll=poll, results=results))


def test_parse_ok():
    q = parse_quiz(msg(), source="grp")
    assert q["answer"] == 1 and q["options"] == ["Rome", "Paris"]
    assert q["explanation"] == "Paris is the capital." and q["source"] == "grp"
    assert validate_quiz(q) == []


def test_plain_string_text():
    m = msg()
    m.poll.poll.question = "Plain?"
    assert parse_quiz(m)["question"] == "Plain?"


def test_non_quiz_and_no_poll_skipped():
    assert parse_quiz(msg(quiz=False)) is None
    assert parse_quiz(NS(poll=None)) is None


def test_unknown_answer_skipped():
    assert parse_quiz(msg(correct=-1)) is None


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
    q = parse_quiz(msg())
    assert to_compact([q]) == [["Capital of France?", ["Rome", "Paris"], 1,
                                "Paris is the capital."]]


def test_migrate_legacy_metadata():
    m = migrate_metadata({"last_message_id": 42, "poll_ids": [1]}, ["g"])
    assert m == {"last_message_id": {"g": 42}, "hashes": []}
    assert migrate_metadata({}, ["g"])["last_message_id"] == {}
