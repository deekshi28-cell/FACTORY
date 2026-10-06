import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
import json

with open(config.TEST_QUESTIONS_PATH, "r", encoding="utf-8") as f:
       questions = json.load(f)

for q in questions[:10]:
       print(f"ID {q['id']}: expected_source = {repr(q.get('expected_source'))}")