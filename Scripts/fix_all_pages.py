from search import collection
from ingest import ingest_xlsx, ingest_docx
import os

files_to_fix = [
    ("excel.xlsx", "xlsx"),
    ("Factory_Assistance_Data_100_Rows.xlsx", "xlsx"),
    ("VFD3000_Fault_Alarm_Codes.xlsx", "xlsx"),
    ("VFD_Fault_Alarm_Code_Table.xlsx", "xlsx"),
    ("6.docx", "docx"),
    ("Factory_Maintenance_Equipment_Master_Manual_20_Pages.docx", "docx"),
    ("Mock_Maintenance_SOP_VFD_Process_Pump.docx", "docx"),
]

all_data = collection.get()
filenames = [f[0] for f in files_to_fix]
ids_to_delete = [
    all_data['ids'][i] for i, meta in enumerate(all_data['metadatas'])
    if meta['source_file'] in filenames
]
print(f"Deleting {len(ids_to_delete)} old chunks...")
if ids_to_delete:
    collection.delete(ids=ids_to_delete)

documents_folder = r"D:\FactoryKA\documents"
for fname, ftype in files_to_fix:
    path = os.path.join(documents_folder, fname)
    if os.path.exists(path):
        if ftype == "xlsx":
            count = ingest_xlsx(path)
        else:
            count = ingest_docx(path)
        print(f"Re-ingested {fname}: {count} chunks")
    else:
        print(f"NOT FOUND: {fname}")