import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
from readers import extract_images_from_docx, extract_images_from_xlsx

docx_images = extract_images_from_docx(os.path.join(config.DOCUMENTS_DIR, "6.docx"), config.EXTRACTED_IMAGES_DIR)
print(f"Images from 6.docx: {len(docx_images)}")
for img in docx_images[:3]:
    print(f"  {img}")

xlsx_images = extract_images_from_xlsx(os.path.join(config.DOCUMENTS_DIR, "excel.xlsx"), config.EXTRACTED_IMAGES_DIR)
print(f"\nImages from excel.xlsx: {len(xlsx_images)}")