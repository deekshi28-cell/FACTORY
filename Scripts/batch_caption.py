import os
import sys
# This file lives in Scripts\, but readers.py lives in app\ - add that folder
# to the import path so `from readers import ...` below can find it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import json
from readers import extract_images_from_pdf, extract_images_from_docx, extract_images_from_xlsx
from test_caption import caption_image  # sibling file in Scripts\, no bootstrap needed for this one
import config
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.INGEST_LOG_PATH, encoding="utf-8"),
    ]
)
logger = logging.getLogger("batch_caption")

documents_folder = config.DOCUMENTS_DIR
output_folder = config.EXTRACTED_IMAGES_DIR
results_file = os.path.join(config.RESULTS_DIR, "all_captions.json")

if os.path.exists(results_file):
    with open(results_file, "r", encoding="utf-8") as f:
        all_results = json.load(f)
    already_done = set(r["image_path"] for r in all_results)
else:
    all_results = []
    already_done = set()

doc_files = os.listdir(documents_folder)
all_extracted_images = []

for file_name in doc_files:
    file_path = os.path.join(documents_folder, file_name)
    ext = os.path.splitext(file_name)[1].lower()

    if ext == ".pdf":
        print(f"Extracting images from PDF: {file_name}...")
        imgs = extract_images_from_pdf(file_path, output_folder, min_size=150, max_size=1800)
        all_extracted_images.extend(imgs)
    elif ext == ".docx":
        print(f"Extracting images from DOCX: {file_name}...")
        imgs = extract_images_from_docx(file_path, output_folder, min_size=150)
        all_extracted_images.extend(imgs)
    elif ext == ".xlsx":
        print(f"Extracting images from XLSX: {file_name}...")
        imgs = extract_images_from_xlsx(file_path, output_folder, min_size=150)
        all_extracted_images.extend(imgs)

print(f"\nTotal images extracted across all files: {len(all_extracted_images)}")

for i, img in enumerate(all_extracted_images):
    if img["image_path"] in already_done:
        continue

    if not os.path.exists(img["image_path"]):
        continue

    print(f"  [{i+1}/{len(all_extracted_images)}] Captioning {os.path.basename(img['image_path'])}...")
    caption = caption_image(img['image_path'])
    img['caption'] = caption if caption else "CAPTION_FAILED"
    all_results.append(img)
    already_done.add(img["image_path"])

    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

print(f"\nDone. Total images captioned in all_captions.json: {len(all_results)}")