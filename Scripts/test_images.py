import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
from readers import extract_images_from_pdf

pdf_file = os.path.join(config.DOCUMENTS_DIR, "7.pdf") 
output_folder = config.EXTRACTED_IMAGES_DIR

images = extract_images_from_pdf(pdf_file, output_folder)
print(f"Total images extracted: {len(images)}")
for img in images[:10]:
    print(f"  Page {img['page_number']}: {img['image_path']}")