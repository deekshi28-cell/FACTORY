"""
diag_pictures.py  -  why do ids 67 and 69 return no picture?

Retrieval only (no LLM, takes seconds). For each question it prints the chunks that
would be given to the model, marks picture chunks, and says whether the expected
picture chunk is among them.

Run from D:\\FactoryKA\\Scripts:   python diag_pictures.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import retrieval  # noqa: E402

CASES = [
    (67, "In Figure 1: Front View of XP-400 Automated X-Press at the front veiw Which component is used to release hydraulic pressure during an emergency?",
     ("8.pdf", 9)),
    (69, "What is shown on the cover of the Lincoln Industrial EM-U2 Owner's Manual?",
     ("3.pdf", 2)),
]

retrieval.init()
for qid, question, (want_file, want_page) in CASES:
    res = retrieval.search_chunks(question)
    metas = res["metadatas"][0]
    docs = res["documents"][0]
    print(f"\n=== id {qid}: {question[:90]}")
    found = False
    for i, (m, d) in enumerate(zip(metas, docs), start=1):
        is_pic = m.get("chunk_type") == "picture_caption"
        hit = is_pic and m.get("source_file") == want_file and m.get("page_number") == want_page
        found = found or hit
        flag = "  <== EXPECTED PICTURE" if hit else ""
        print(f"  SOURCE {i:2d}: {retrieval.format_source(m):28s} {m.get('chunk_type', ''):16s}{flag}")
    print(f"  -> expected picture chunk ({want_file} page {want_page}) in the context: {'YES' if found else 'NO'}")
    if found:
        print("     It reaches the model but the model did not cite it (prompt / citation issue).")
    else:
        print("     It never reaches the model (retrieval ranking issue).")