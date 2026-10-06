import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
from readers import read_docx
from chunker import chunk_table

# point this at the same Word file you tested earlier
word_file = os.path.join(config.DOCUMENTS_DIR, "6.docx")  # update to your actual filename

result = read_docx(word_file)
print(f"Total tables found: {len(result['tables'])}")

# pick the first table to inspect
first_table = result['tables'][0]
rows = first_table['rows']

print(f"\n--- Table 0 raw preview ---")
print(f"Total rows (including header): {len(rows)}")
print(f"Header row: {rows[0]}")
if len(rows) > 1:
    print(f"First data row: {rows[1]}")

# now chunk it
chunks = chunk_table(rows, max_rows_per_chunk=15)
print(f"\n--- After chunking ---")
print(f"Chunks created: {len(chunks)}")
for i, chunk in enumerate(chunks):
    print(f"  Chunk {i}: header={chunk['header']}, rows={len(chunk['rows'])}")

# preview actual content of chunk 0
print(f"\n--- Chunk 0 full content ---")
print(f"Header: {chunks[0]['header']}")
for r in chunks[0]['rows'][:3]:  # just first 3 rows to keep it readable
    print(f"  {r}")

print("\n=== Scanning first 10 tables for header sanity ===")
for i, table in enumerate(result['tables'][:10]):
    rows = table['rows']
    if rows:
        print(f"Table {i}: header={rows[0]}")