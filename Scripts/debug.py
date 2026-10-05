import time
from search import search_chunks, generate_answer

print("=" * 60)
print("Diagnostic Q&A - shows retrieved chunks, answer, AND timing")
print("Type 'exit' to quit.")
print("=" * 60)

while True:
    query = input("\nYour question: ").strip()
    if query.lower() in ("exit", "quit"):
        break
    if not query:
        continue

    print("\n--- RETRIEVED CHUNKS ---")
    results = search_chunks(query, n_results=5)
    for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
        print(f"[{meta['source_file']} - {meta.get('page_number')}]")
        print(f"  {doc[:150]}")
        print()

    print("--- FINAL ANSWER ---")
    start = time.time()
    result = generate_answer(query)
    elapsed = time.time() - start

    print(f"Answer: {result['answer']}")
    print(f"Sources used: {result['sources']}")
    print(f"\n⏱ Response time: {elapsed:.1f} seconds")