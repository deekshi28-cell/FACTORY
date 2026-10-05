from search import collection

all_data = collection.get()
target_docs = ["1.pdf", "2.pdf", "3.pdf", "4 .pdf", "13.pdf"]

for target_doc in target_docs:
    print(f"\n{'='*20} {target_doc} {'='*20}")
    count = 0
    shown = 0
    for i, meta in enumerate(all_data['metadatas']):
        if meta['source_file'] == target_doc and meta.get('chunk_type', 'text') != 'picture_caption':
            count += 1
            if count <= 5:
                continue
            print(f"--- Chunk (page {meta.get('page_number')}) ---")
            print(all_data['documents'][i][:250])
            print()
            shown += 1
            if shown >= 4:
                break