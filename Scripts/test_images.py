from readers import extract_images_from_pdf

pdf_file = r"D:\FactoryKA\documents\7.pdf" 
output_folder = r"D:\FactoryKA\extracted_images"

images = extract_images_from_pdf(pdf_file, output_folder)
print(f"Total images extracted: {len(images)}")
for img in images[:10]:
    print(f"  Page {img['page_number']}: {img['image_path']}")