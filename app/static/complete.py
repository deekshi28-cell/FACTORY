import json

with open(r"D:\FactoryKA\automatic_test_results.json", "r", encoding="utf-8") as f:
    results = json.load(f)

print(f"Total results saved: {len(results)}")
print(f"Expected: 100")

if len(results) < 100:
    print(f"\nIncomplete run — missing {100 - len(results)} questions")
    completed_ids = set(r['id'] for r in results)
    print(f"Last completed ID: {max(completed_ids) if completed_ids else 'none'}")
else:
    print("\nAll 100 questions completed.")