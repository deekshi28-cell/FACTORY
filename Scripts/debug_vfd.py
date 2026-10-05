from search import search_chunks

query = "What does the diagram show for the timer relay contact configuration?"
results = search_chunks(query, n_results=5)

for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
    print(f"--- {meta['source_file']} (page {meta.get('page_number')}) ---")
    print(doc[:200])
    print()