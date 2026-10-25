"""Validate every quiz file in quizzes/. Exit 1 on any problem (used in CI)."""
import os
import sys

from quizlib import load_json, validate_row

FOLDER = "quizzes"
bad = total = 0
for name in sorted(os.listdir(FOLDER)) if os.path.isdir(FOLDER) else []:
    if not name.endswith(".json") or name == "index.json":
        continue
    total += 1
    problems = validate_row(load_json(os.path.join(FOLDER, name), None))
    if problems:
        bad += 1
        print(f"{name}: {'; '.join(problems)}")
print(f"{total} quiz files checked, {bad} invalid")
sys.exit(1 if bad else 0)
