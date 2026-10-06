import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
from readers import read_docx

result = read_docx(os.path.join(config.DOCUMENTS_DIR, "6.docx"))

table = result['tables'][31]
print(f"Table 31 - {len(table['rows'])} rows total\n")
for i, row in enumerate(table['rows']):
    print(f"Row {i}: {row}")