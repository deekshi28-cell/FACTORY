import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
import os
from search import collection

documents_folder = config.DOCUMENTS_DIR
all_files = set(os.listdir(documents_folder))

all_data = collection.get()
ingested_files = set(meta['source_file'] for meta in all_data['metadatas'])

missing = sorted(all_files - ingested_files)
print(f"Files in folder: {len(all_files)}")
print(f"Files ingested: {len(ingested_files)}")
print(f"\nNOT yet ingested ({len(missing)}):")
for f in missing:
    print(f"  - {f}")