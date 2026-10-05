from search import collection

all_data = collection.get()
target_docs = ["1.pdf", "2.pdf", "3.pdf", "4 .pdf", "13.pdf", "hoist.pdf", "i-line.pdf", "synchronous.pdf"]

for doc in target_docs:
    print(f"\n{'='*15} {doc} {'='*15}")
    shown = 0
    for i, meta in enumerate(all_data['metadatas']):
        if meta['source_file'] == doc and meta.get('chunk_type') == 'picture_caption':
            print(f"--- Caption (page {meta.get('page_number')}) ---")
            print(all_data['documents'][i][:200])
            print()
            shown += 1
            if shown >= 2:
                break
    if shown == 0:
        print("(no picture captions found for this document)")