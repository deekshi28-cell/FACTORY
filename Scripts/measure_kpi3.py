import re
import json
from search import search_chunks

def extract_filenames(expected_source):
    """
    Pulls out just the plain filenames from a messy expected_source string,
    ignoring page/table/row annotations and handling both ',' and '/' separators.
    """
    if not expected_source:
        return []
    # split on both comma and slash
    parts = re.split(r'[,/]', expected_source)
    filenames = []
    for part in parts:
        part = part.strip()
        # strip off anything in parentheses, e.g. "(Table 31)" or "(page 20)"
        part = re.sub(r'\(.*?\)', '', part).strip()
        if part:
            filenames.append(part.lower())
    return filenames


with open(r"D:\FactoryKA\test_questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)

hits = 0
total_checked = 0
misses = []

for q in questions:
    expected = q.get("expected_source")
    if not expected or str(expected).strip().lower() in ("", "n/a", "na", "none"):
        continue

    expected_files = extract_filenames(expected)
    if not expected_files:
        continue

    total_checked += 1

    results = search_chunks(q["question"], n_results=5)
    retrieved_files = [meta['source_file'].lower() for meta in results['metadatas'][0]]

    if any(any(ef in rf for rf in retrieved_files) for ef in expected_files):
        hits += 1
    else:
        misses.append((q['id'], q['question'][:60]))

print(f"Total questions checked: {total_checked}")
print(f"Hits: {hits}")
print(f"Search hit rate: {hits/total_checked*100:.1f}%")

print("\n=== Misses ===")
for qid, qtext in misses:
    print(f"[{qid}] {qtext}")