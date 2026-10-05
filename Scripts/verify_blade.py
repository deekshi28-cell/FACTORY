from search import collection

all_data = collection.get()

search_term = "ST-72-4X"  

print("=== Checking picture captions ===")
for i, meta in enumerate(all_data['metadatas']):
       if meta['source_file'] == '2.pdf' and meta.get('chunk_type') == 'picture_caption':
           if search_term in all_data['documents'][i]:
               print(f"FOUND in caption (page {meta.get('page_number')}): {all_data['documents'][i][:200]}")

print("\n=== Checking regular text ===")
found = False
for i, meta in enumerate(all_data['metadatas']):
       if meta['source_file'] == '2.pdf' and meta.get('chunk_type') != 'picture_caption':
           if search_term in all_data['documents'][i]:
               print(f"FOUND in text: {all_data['documents'][i][:200]}")
               found = True

if not found:
       print(f"Confirmed: '{search_term}' does NOT appear in regular text — only in the picture caption.")