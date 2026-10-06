import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
import json

with open(config.TEST_RESULTS_PATH, "r", encoding="utf-8") as f:
    results = json.load(f)

matched = sum(1 for r in results if r["source_match"])
print(f"Total: {len(results)} | Passed: {matched} ({matched/len(results)*100:.1f}%)")

print("\n=== Still failing ===")
for r in results:
    if not r["source_match"]:
        print(f"[{r['id']}] {r['question'][:70]}")