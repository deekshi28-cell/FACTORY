from readers import read_docx

result = read_docx(r"D:\FactoryKA\documents\6.docx")

table = result['tables'][31]
print(f"Table 31 - {len(table['rows'])} rows total\n")
for i, row in enumerate(table['rows']):
    print(f"Row {i}: {row}")