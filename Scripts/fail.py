import json

with open(r"D:\FactoryKA\automatic_test_results.json", "r", encoding="utf-8") as f:
    results = json.load(f)

print("=== Questions where source did NOT match ===")
for r in results:
    if not r.get("source_match"):
        print(f"[{r['id']}] {r['question'][:70]}")
        print(f"    Actual sources: {r['actual_sources']}")
        print()