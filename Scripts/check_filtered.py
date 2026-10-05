import pymupdf
import os

def count_filtered_images(filepath, min_size=250, max_size=1800):
    doc = pymupdf.open(filepath)
    total_found = 0
    too_small = 0
    too_large = 0
    kept = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        image_list = page.get_images(full=True)
        for img in image_list:
            total_found += 1
            xref = img[0]
            base_image = doc.extract_image(xref)
            width = base_image["width"]
            height = base_image["height"]

            if width < min_size or height < min_size:
                too_small += 1
            elif width > max_size or height > max_size:
                too_large += 1
            else:
                kept += 1

    doc.close()
    return {"total_found": total_found, "too_small": too_small, "too_large": too_large, "kept": kept}


if __name__ == "__main__":
    documents_folder = r"D:\FactoryKA\documents"
    pdf_files = [f for f in os.listdir(documents_folder) if f.lower().endswith(".pdf")]

    grand_total = {"total_found": 0, "too_small": 0, "too_large": 0, "kept": 0}

    for pdf_file in pdf_files:
        path = os.path.join(documents_folder, pdf_file)
        stats = count_filtered_images(path)
        print(f"{pdf_file}: found={stats['total_found']}, too_small={stats['too_small']}, too_large={stats['too_large']}, kept={stats['kept']}")
        for k in grand_total:
            grand_total[k] += stats[k]

    print("\n=== TOTALS ACROSS ALL PDFs ===")
    print(f"Total images found: {grand_total['total_found']}")
    print(f"Filtered (too small): {grand_total['too_small']}")
    print(f"Filtered (too large/full-page): {grand_total['too_large']}")
    print(f"Kept for captioning: {grand_total['kept']}")