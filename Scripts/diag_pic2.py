"""
diag_pictures2.py  -  for ids 67 and 69: what does the stored picture caption say, and
where does it rank for the question?

Retrieval only (no LLM). Run from D:\\FactoryKA\\Scripts:   python diag_pictures2.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import retrieval  # noqa: E402

CASES = [
    (67, "In Figure 1: Front View of XP-400 Automated X-Press at the front veiw Which component is used to release hydraulic pressure during an emergency?",
     "8.pdf", 9),
    (69, "What is shown on the cover of the Lincoln Industrial EM-U2 Owner's Manual?",
     "3.pdf", 2),
]

retrieval.init()
col = retrieval.get_collection()

for qid, question, f, page in CASES:
    print(f"\n=== id {qid}: {question[:80]}")
    got = col.get(
        where={"$and": [{"source_file": f}, {"page_number": page}, {"chunk_type": "picture_caption"}]},
        include=["documents", "metadatas"],
    )
    ids = got["ids"]
    print(f"  picture chunks stored for {f} page {page}: {len(ids)}")
    for cid, doc in zip(ids, got["documents"]):
        print(f"   - {cid}")
        print("     CAPTION: " + doc[:400].replace("\n", " "))

    emb = retrieval.embed_text(retrieval.normalize_query(question) if hasattr(retrieval, "normalize_query") else question)
    res = col.query(query_embeddings=[emb], n_results=80, include=["metadatas", "distances"])
    rid = res["ids"][0]
    dist = res["distances"][0]
    metas = res["metadatas"][0]
    for cid in ids:
        if cid in rid:
            r = rid.index(cid) + 1
            print(f"  rank of {cid}: {r} of 80  (distance {dist[r-1]:.3f})")
        else:
            print(f"  {cid}: NOT in the top 80")
    print("  top 6 for comparison (rank, distance, source, type):")
    for i in range(6):
        m = metas[i]
        print(f"    {i+1}. {dist[i]:.3f}  {retrieval.format_source(m)}  {m.get('chunk_type')}")