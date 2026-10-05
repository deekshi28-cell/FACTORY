import json

with open(r"D:\FactoryKA\automatic_test_results.json", "r", encoding="utf-8") as f:
    results = json.load(f)

not_found_results = [r for r in results if r.get("category") == "Not Found"]

correct_refusals = sum(1 for r in not_found_results if "no specific source" in str(r["actual_sources"]).lower())

print(f"Total 'Not Found' questions: {len(not_found_results)}")
print(f"Correct refusals: {correct_refusals}")
print(f"Rate: {correct_refusals/len(not_found_results)*100:.1f}%")

print("\n=== Incorrect (system found a source when it shouldn't have) ===")
for r in not_found_results:
    if "no specific source" not in str(r["actual_sources"]).lower():
        print(f"[{r['id']}] {r['question'][:70]}")
        print(f"    Sources: {r['actual_sources']}")