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


def rows():
    out = []
    for f in files():
        out += read("quizzes/" + f)
    return out


def test_saves_dedupes_and_ignores_strangers(run):
    sent = run([upd(10, 42, QUIZ), upd(11, 42, QUIZ), upd(12, 999, {**QUIZ, "question": "Other?"}),
                upd(13, 42, {**QUIZ, "correct_option_id": None, "question": "Hidden?"})])
    assert rows() == [["Q1?", ["a", "b"], 0, ""]]
    assert read("quizzes/index.json") == files()
    assert read("metadata.json")["update_offset"] == 14
    text = sent[0]["text"]
    assert "Added 1" in text and "Duplicates 1" in text and "Skipped 1" in text


def test_one_run_one_batch_file(run):
    run([upd(10, 42, QUIZ), upd(11, 42, {**QUIZ, "question": "Q2?"}),
         upd(12, 42, {**QUIZ, "question": "Q3?"})])
    assert len(files()) == 1 and files()[0].startswith("batch_")
    assert [r[0] for r in read("quizzes/" + files()[0])] == ["Q1?", "Q2?", "Q3?"]


def test_empty_run_creates_no_file(run):
    run([])
    assert files() == []


def test_second_run_adds_nothing(run):
    run([upd(10, 42, QUIZ)])
    run([upd(11, 42, QUIZ)])
    assert len(rows()) == 1 and len(files()) == 1


def test_requires_allowed_ids(run, monkeypatch):
    monkeypatch.setenv("ALLOWED_USER_IDS", "")
    with pytest.raises(SystemExit):
        run([])


def stats_msg(uid, user):
    return {"update_id": uid, "message": {"message_id": uid, "date": 1767225600,
            "from": {"id": user}, "chat": {"id": user}, "text": "/stats"}}


def test_stats_command(run):
    sent = run([upd(10, 42, QUIZ), stats_msg(11, 42)])
    assert any("Total quizzes: 1" in m["text"] for m in sent)


def test_stats_ignored_for_strangers(run):
    assert run([stats_msg(10, 999)]) == []


def test_old_per_quiz_files_gathered_into_one(run):
    os.makedirs("quizzes")
    json.dump(["Old1?", ["a", "b"], 1, "e"], open("quizzes/aaa.json", "w"))
    json.dump(["Old2?", ["a", "b"], 0, ""], open("quizzes/bbb.json", "w"))
    run([upd(10, 42, QUIZ)])
    assert sorted(files()) == sorted(["batch_00000000_migrated.json", files()[-1]])
    assert [r[0] for r in read("quizzes/batch_00000000_migrated.json")] == ["Old1?", "Old2?"]
    assert not os.path.exists("quizzes/aaa.json")
    assert len(rows()) == 3
