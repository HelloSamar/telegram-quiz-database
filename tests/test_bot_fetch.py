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


def files():
    return sorted(f for f in os.listdir("quizzes") if f != "index.json")


def test_saves_dedupes_and_ignores_strangers(run):
    sent = run([upd(10, 42, QUIZ), upd(11, 42, QUIZ), upd(12, 999, {**QUIZ, "question": "Other?"}),
                upd(13, 42, {**QUIZ, "correct_option_id": None, "question": "Hidden?"})])
    assert len(files()) == 1
    assert read("quizzes/" + files()[0]) == ["Q1?", ["a", "b"], 0, ""]
    assert read("quizzes/index.json") == files()
    assert read("metadata.json")["update_offset"] == 14
    text = sent[0]["text"]
    assert "Added 1" in text and "Duplicates 1" in text and "Skipped 1" in text


def test_second_run_adds_nothing(run):
    run([upd(10, 42, QUIZ)])
    run([upd(11, 42, QUIZ)])
    assert len(files()) == 1


def test_requires_allowed_ids(run, monkeypatch):
    monkeypatch.setenv("ALLOWED_USER_IDS", "")
    with pytest.raises(SystemExit):
        run([])


def test_each_quiz_in_own_file(run):
    run([upd(10, 42, QUIZ), upd(11, 42, {**QUIZ, "question": "Q2?"})])
    assert len(files()) == 2
    assert len(read("quizzes/index.json")) == 2


def stats_msg(uid, user):
    return {"update_id": uid, "message": {"message_id": uid, "date": 1767225600,
            "from": {"id": user}, "chat": {"id": user}, "text": "/stats"}}


def test_stats_command(run):
    sent = run([upd(10, 42, QUIZ), stats_msg(11, 42)])
    assert any("Total quizzes: 1" in m["text"] for m in sent)


def test_stats_ignored_for_strangers(run):
    assert run([stats_msg(10, 999)]) == []


def test_legacy_file_migrated(run, tmp_path):
    json.dump([{"id": "abc", "question": "Old?", "options": ["a", "b"], "answer": 1,
                "explanation": "e"}], open("quizzes.json", "w"))
    run([])
    assert read("quizzes/abc.json") == ["Old?", ["a", "b"], 1, "e"]
