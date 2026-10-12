"""
measure_kpis.py  -  measures the KPIs that run_tests.py does not:

  A3   Search hit rate   : is a correct page/row in the top 5 search results?   (fast, ~2 min)
  A14  Picture shown     : is the picture next to the answer from a correct page? (slow: runs the LLM)
  A15  Picture pointer   : do picture answers point to the page ("See the picture on page X")
                           instead of guessing?                                 (slow: same run as A14)

Run from the project root, venv active, Ollama running:
    python Scripts\measure_kpis.py a3          # A3 only, no LLM
    python Scripts\measure_kpis.py pictures    # A14 + A15 (runs the picture questions through the LLM)
    python Scripts\measure_kpis.py all

Results are printed and saved to Results\kpi_measurements.json.
"""
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
import search  # noqa: E402
import retrieval  # noqa: E402

A3_TOP_N = 5
POINTER_RE = re.compile(r"See the pictures? on|See pictures in|画像もご確認ください", re.IGNORECASE)


def norm(s):
    return re.sub(r"\s+", " ", str(s).strip().lower())


def expected_sources(q):
    """'a.pdf (page 2), b.xlsx (Row 2-16)' -> ['a.pdf (page 2)', 'b.xlsx (row 2-16)']"""
    e = q.get("expected_source") or ""
    if norm(e) in ("", "n/a", "none"):
        return []
    return [norm(x) for x in re.findall(r"[^,()]+\([^)]*\)", e)]


def load_questions():
    with open(config.TEST_QUESTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)


def measure_a3(questions):
    hits = total = 0
    misses = []
    for q in questions:
        exp = expected_sources(q)
        if q.get("category") == "Not Found" or not exp:
            continue
        total += 1
        res = retrieval.search_chunks(q["question"], n_results=A3_TOP_N)
        got = [norm(retrieval.format_source(m)) for m in res["metadatas"][0][:A3_TOP_N]]
        if any(g in exp for g in got):
            hits += 1
        else:
            misses.append({"id": q["id"], "question": q["question"][:70], "expected": exp, "retrieved": got})
    rate = hits / total if total else 0
    print(f"\nA3  Search hit rate (correct page/row in top {A3_TOP_N}): {hits}/{total} = {rate:.1%}   target >= 80%")
    for m in misses:
        print(f"    miss id {m['id']}: expected {m['expected']}  got {m['retrieved']}")
    return {"hits": hits, "total": total, "rate": round(rate, 3), "misses": misses}


def measure_pictures(questions):
    shown = pointed = total = 0
    rows = []
    for q in questions:
        exp = expected_sources(q)
        if q.get("category") != "Picture" or not exp:
            continue
        total += 1
        t0 = time.time()
        r = search.generate_answer(q["question"])
        first = r.get("images", [])[:1]          # the web page shows only the first picture
        img_ok = any(norm(f"{i['source_file']} (page {i['page_number']})") in exp for i in first)
        ptr_ok = bool(POINTER_RE.search(r.get("answer", "")))
        shown += img_ok
        pointed += ptr_ok
        rows.append({"id": q["id"], "picture_correct": img_ok, "pointer": ptr_ok,
                     "picture": [f"{i['source_file']} (page {i['page_number']})" for i in first], "expected": exp})
        print(f"  id {q['id']:>3}  picture {'OK ' if img_ok else 'NO '} pointer {'OK ' if ptr_ok else 'NO '} ({time.time() - t0:.0f}s)  {q['question'][:50]}")
    print(f"\nA14 Correct picture shown : {shown}/{total} = {shown / total:.1%}   target >= 70%" if total else "no picture questions")
    print(f"A15 Page pointer given    : {pointed}/{total} = {pointed / total:.1%}   target >= 90%" if total else "")
    return {"a14_shown": shown, "a15_pointer": pointed, "total": total, "rows": rows}


def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else "all").lower()
    qs = load_questions()
    search.init()
    out = {"measured_at": time.strftime("%Y-%m-%d %H:%M:%S")}
    if mode in ("a3", "all"):
        out["A3"] = measure_a3(qs)
    if mode in ("pictures", "a14", "a15", "all"):
        out["A14_A15"] = measure_pictures(qs)
    os.makedirs(config.RESULTS_DIR, exist_ok=True)
    path = os.path.join(config.RESULTS_DIR, "kpi_measurements.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()