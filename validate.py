"""Validate every batch file in quizzes/. Exit 1 on any problem (used in CI)."""
import os
import sys

from quizlib import load_json, validate_row

FOLDER = "quizzes"
bad = total = files = 0
for name in sorted(os.listdir(FOLDER)) if os.path.isdir(FOLDER) else []:
    if not name.endswith(".json") or name == "index.json":
        continue
    files += 1
    rows = load_json(os.path.join(FOLDER, name), None)
    if not isinstance(rows, list):
        bad += 1
        print(f"{name}: must be a JSON list")
        continue
    for i, row in enumerate(rows):
        total += 1
        problems = validate_row(row)
        if problems:
            bad += 1
            print(f"{name} #{i}: {'; '.join(problems)}")
print(f"{files} files, {total} quizzes checked, {bad} invalid")
sys.exit(1 if bad else 0)
