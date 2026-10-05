import json

with open(r"D:\FactoryKA\all_captions.json", "r", encoding="utf-8") as f:
       completed = json.load(f)

failed = [r for r in completed if r['caption'] == "CAPTION_FAILED"]

print(f"Completed: {len(completed)}")
print(f"Pending: {648 - len(completed)}")
print(f"Failed: {len(failed)}")