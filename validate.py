"""Validate quizzes.json. Exit 1 on any problem (used in CI)."""
import sys

from quizlib import load_json, validate_quiz

quizzes = load_json("quizzes.json", None)
if not isinstance(quizzes, list):
    sys.exit("quizzes.json must be a JSON list")
bad, ids = 0, set()
for i, q in enumerate(quizzes):
    problems = validate_quiz(q)
    if q.get("id") in ids:
        problems.append("duplicate id")
    ids.add(q.get("id"))
    if problems:
        bad += 1
        print(f"#{i}: {'; '.join(problems)}")
print(f"{len(quizzes)} quizzes checked, {bad} invalid")
sys.exit(1 if bad else 0)
