"""
add_questions.py - add the 10 new Japanese questions (ids 122-131) to tests\\test_questions.json.

1. Put new_test_questions_japanese_122_131.json in the same folder as this script
   (D:\\FactoryKA\\Scripts).
2. Run from D:\\FactoryKA\\Scripts:   python add_questions.py
   (or give the file name:            python add_questions.py other_file.json)

Questions whose id is already in test_questions.json are skipped, so it is safe to run twice.
A backup is saved as test_questions.json.bak before anything is changed.
"""
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "app"))
import config  # noqa: E402

new_name = sys.argv[1] if len(sys.argv) > 1 else "new_test_questions_japanese_122_131.json"
new_path = new_name if os.path.isabs(new_name) else os.path.join(HERE, new_name)
if not os.path.exists(new_path):
    sys.exit(f"Cannot find {new_path}\nPut the file in {HERE} or pass its full path.")

with open(config.TEST_QUESTIONS_PATH, encoding="utf-8") as f:
    questions = json.load(f)
with open(new_path, encoding="utf-8") as f:
    new_questions = json.load(f)

have = {q["id"] for q in questions}
to_add = [q for q in new_questions if q["id"] not in have]
skipped = [q["id"] for q in new_questions if q["id"] in have]
if skipped:
    print(f"Skipped (id already in the file): {skipped}")
if not to_add:
    print("Nothing to add.")
    sys.exit(0)

shutil.copyfile(config.TEST_QUESTIONS_PATH, config.TEST_QUESTIONS_PATH + ".bak")
questions.extend(to_add)
with open(config.TEST_QUESTIONS_PATH, "w", encoding="utf-8") as f:
    json.dump(questions, f, ensure_ascii=False, indent=2)
print(f"Added {len(to_add)} questions (ids {[q['id'] for q in to_add]}).")
print(f"{config.TEST_QUESTIONS_PATH} now has {len(questions)} questions. Backup: {config.TEST_QUESTIONS_PATH}.bak")
