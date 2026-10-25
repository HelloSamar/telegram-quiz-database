import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import bot_fetch


def upd(uid, user, p, chat=1, cid=1):
    return {"update_id": uid, "message": {"message_id": uid, "date": 1767225600,
            "from": {"id": user}, "chat": {"id": chat}, "poll": p}}


QUIZ = {"type": "quiz", "question": "Q1?", "options": [{"text": "a"}, {"text": "b"}],
        "correct_option_id": 0}


@pytest.fixture
def run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("BOT_TOKEN", "123:SECRET")
    monkeypatch.setenv("ALLOWED_USER_IDS", "42")

    def go(updates):
        sent, offsets = [], []

        def fake(token, method, **p):
            assert token == "123:SECRET"
            if method == "getUpdates":
                offsets.append(p["offset"])
                return updates if len(offsets) == 1 else []
            sent.append(p)
        monkeypatch.setattr(bot_fetch, "call", fake)
        bot_fetch.main()
        return sent
    return go


def read(name):
    return json.load(open(name))


def test_saves_dedupes_and_ignores_strangers(run):
    sent = run([upd(10, 42, QUIZ), upd(11, 42, QUIZ), upd(12, 999, {**QUIZ, "question": "Other?"}),
                upd(13, 42, {**QUIZ, "correct_option_id": None, "question": "Hidden?"})])
    assert [q["question"] for q in read("quizzes.json")] == ["Q1?"]
    assert read("metadata.json")["update_offset"] == 14
    assert len(read("quizzes_compact.json")) == 1
    text = sent[0]["text"]
    assert "Added 1" in text and "Duplicates 1" in text and "Skipped 1" in text


def test_second_run_adds_nothing(run):
    run([upd(10, 42, QUIZ)])
    run([upd(11, 42, QUIZ)])
    assert len(read("quizzes.json")) == 1


def test_requires_allowed_ids(run, monkeypatch):
    monkeypatch.setenv("ALLOWED_USER_IDS", "")
    with pytest.raises(SystemExit):
        run([])
