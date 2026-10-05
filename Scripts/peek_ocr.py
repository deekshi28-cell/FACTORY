from search import collection

all_data = collection.get()
target_docs = ["10.pdf", "15.pdf", "ACT.pdf", "seimens.pdf"]  # all confirmed scanned earlier

for doc in target_docs:
    print(f"\n{'='*15} {doc} {'='*15}")
    count = 0
    shown = 0
    for i, meta in enumerate(all_data['metadatas']):
        if meta['source_file'] == doc and meta.get('chunk_type', 'text') == 'text':
            count += 1
            if count <= 3:
                continue
            print(f"--- Chunk (page {meta.get('page_number')}) ---")
            print(all_data['documents'][i][:250])
            print()
            shown += 1
            if shown >= 2:
                break