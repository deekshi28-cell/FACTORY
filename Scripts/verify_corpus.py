from search import collection

all_data = collection.get()
sources = set()
for meta in all_data['metadatas']:
    sources.add(meta['source_file'])

print(f"Total chunks in knowledge base: {len(all_data['ids'])}")
print(f"Total unique documents ingested: {len(sources)}")
print("\nDocuments:")
for s in sorted(sources):
    print(f"  - {s}")