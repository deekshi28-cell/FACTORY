import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
import json

with open(config.TEST_RESULTS_PATH, "r", encoding="utf-8") as f:
    results = json.load(f)

print("=== Questions where source did NOT match ===")
for r in results:
    if not r.get("source_match"):
        print(f"[{r['id']}] {r['question'][:70]}")
        print(f"    Actual sources: {r['actual_sources']}")
        print()