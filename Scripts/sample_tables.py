from readers import read_docx, read_xlsx
import random

# Pull tables from your Word document (72 tables) and pick a sample
result = read_docx(r"D:\FactoryKA\documents\6.docx")
all_tables = result['tables']

random.seed(42)  # reproducible sample
sample_indices = random.sample(range(len(all_tables)), min(30, len(all_tables)))

for idx in sorted(sample_indices):
    print(f"\n=== Table {idx} ===")
    for row in all_tables[idx]['rows'][:4]:  # show header + a few rows
        print(row)