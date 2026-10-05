from search import search_chunks

print("=== E-16 query ===")
results = search_chunks("What is the recommended action for an E-16 braking resistor overload?", n_results=5)
for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
    print(f"--- {meta['source_file']} ({meta.get('page_number')}) ---")
    print(doc[:150])

print("\n=== UC100 circuit board query ===")
results2 = search_chunks("What components are visible on the UC100's circuit board?", n_results=5)
for doc, meta in zip(results2['documents'][0], results2['metadatas'][0]):
    print(f"--- {meta['source_file']} ({meta.get('page_number')}) ---")
    print(doc[:150])