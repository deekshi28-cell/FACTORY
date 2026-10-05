import os
from search import collection

documents_folder = r"D:\FactoryKA\documents"
all_files = set(os.listdir(documents_folder))

all_data = collection.get()
ingested_files = set(meta['source_file'] for meta in all_data['metadatas'])

missing = sorted(all_files - ingested_files)
print(f"Files in folder: {len(all_files)}")
print(f"Files ingested: {len(ingested_files)}")
print(f"\nNOT yet ingested ({len(missing)}):")
for f in missing:
    print(f"  - {f}")