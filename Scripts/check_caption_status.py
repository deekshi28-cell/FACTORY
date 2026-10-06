import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
import json

with open(os.path.join(config.RESULTS_DIR, "all_captions.json"), "r", encoding="utf-8") as f:
       completed = json.load(f)

failed = [r for r in completed if r['caption'] == "CAPTION_FAILED"]

print(f"Completed: {len(completed)}")
print(f"Pending: {648 - len(completed)}")
print(f"Failed: {len(failed)}")