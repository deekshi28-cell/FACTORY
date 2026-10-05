from readers import extract_images_from_docx, extract_images_from_xlsx

docx_images = extract_images_from_docx(r"D:\FactoryKA\documents\6.docx", r"D:\FactoryKA\extracted_images")
print(f"Images from 6.docx: {len(docx_images)}")
for img in docx_images[:3]:
    print(f"  {img}")

xlsx_images = extract_images_from_xlsx(r"D:\FactoryKA\documents\excel.xlsx", r"D:\FactoryKA\extracted_images")
print(f"\nImages from excel.xlsx: {len(xlsx_images)}")