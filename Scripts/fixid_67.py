"""
fix_id67.py - add "8.pdf (page 9)" to the expected source of id 67 in tests\\test_questions.json.

Safe to run more than once. Makes a backup (test_questions.json.bak) first and changes
nothing else in the file.

Run from D:\\FactoryKA\\Scripts:   python fix_id67.py
"""
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402

PATH = config.TEST_QUESTIONS_PATH
NEW = "8.pdf (page 9)"

with open(PATH, encoding="utf-8") as f:
    raw = f.read()
data = json.loads(raw)

for q in data:
    if q["id"] == 67:
        src = q["expected_source"]
        if NEW in src:
            print(f"id 67 already lists {NEW}:\n  {src}\nNothing to do.")
            sys.exit(0)
        # split "a.pdf (page 8), a.pdf (page 23)" into its entries, add the new one, keep page order
        parts = [x.strip() for x in re.findall(r"[^,()]+\([^)]*\)", src)]
        parts.append(NEW)
        parts.sort(key=lambda s: int(re.search(r"page (\d+)", s).group(1)))
        q["expected_source"] = ", ".join(parts)
        print(f"id 67 expected_source:\n  before: {src}\n  after : {q['expected_source']}")
        break
else:
    sys.exit("id 67 not found in " + PATH)

shutil.copyfile(PATH, PATH + ".bak")
indent = 2
with open(PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=indent)
print(f"Saved {PATH}  (backup: {PATH}.bak)")