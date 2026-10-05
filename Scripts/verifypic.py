from search import collection

all_data = collection.get()

print("=== STEP 1: Picture caption content ===")
for i, meta in enumerate(all_data['metadatas']):
    if meta.get('chunk_type') == 'picture_caption' and meta['source_file'] == '2.pdf':
        print(f"--- Caption (page {meta.get('page_number')}) ---")
        print(all_data['documents'][i])
        print()

print("=== STEP 2: Checking regular text chunks for the same fact ===")
found_in_text = False
for i, meta in enumerate(all_data['metadatas']):
    if meta['source_file'] == '2.pdf' and meta.get('chunk_type') != 'picture_caption':
        if '1900' in all_data['documents'][i] or '185' in all_data['documents'][i]:
            print(f"FOUND in regular text: {all_data['documents'][i][:200]}")
            found_in_text = True

if not found_in_text:
    print("Confirmed: '1900 watts' / '185mm' does NOT appear in regular text chunks — only in the picture caption.")