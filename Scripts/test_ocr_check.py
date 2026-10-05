from readers import read_pdf_with_ocr

result = read_pdf_with_ocr(r"D:\FactoryKA\documents\1.pdf")
ocr_pages = sum(1 for p in result if p["used_ocr"])
print(f"Pages that needed OCR: {ocr_pages} / {len(result)}")
print(f"Sample text: {result[0]['text'][:300]}")