from search import collection

all_data = collection.get()

for i, meta in enumerate(all_data['metadatas']):
    if meta['source_file'] == 'Factory_Maintenance_Equipment_Master_Manual_20_Pages.docx':
        print(f"--- {meta.get('page_number')} ---")
        print(all_data['documents'][i][:400])
        print()