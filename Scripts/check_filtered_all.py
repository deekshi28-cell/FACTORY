import pymupdf
import os
import zipfile
import io
from PIL import Image

def count_filtered_pdf(filepath, min_size=250, max_size=1800):
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


def count_filtered_zip_based(filepath, min_size=150):
    """For .docx and .xlsx files (both are zip archives with a media/ folder)."""
    total_found = 0
    too_small = 0
    kept = 0

    try:
        with zipfile.ZipFile(filepath, 'r') as z:
            for name in z.namelist():
                if 'media/' in name and not name.endswith('/'):
                    total_found += 1
                    data = z.read(name)
                    try:
                        img = Image.open(io.BytesIO(data))
                        w, h = img.size
                        if w < min_size or h < min_size:
                            too_small += 1
                        else:
                            kept += 1
                    except Exception:
                        pass
    except Exception as e:
        print(f"Error reading {filepath}: {e}")

    return {"total_found": total_found, "too_small": too_small, "too_large": 0, "kept": kept}


if __name__ == "__main__":
    documents_folder = r"D:\FactoryKA\documents"
    all_files = os.listdir(documents_folder)

    grand_total = {"total_found": 0, "too_small": 0, "too_large": 0, "kept": 0}

    print("=== PDF FILES ===")
    for fname in all_files:
        if fname.lower().endswith(".pdf"):
            path = os.path.join(documents_folder, fname)
            stats = count_filtered_pdf(path)
            print(f"{fname}: found={stats['total_found']}, too_small={stats['too_small']}, too_large={stats['too_large']}, kept={stats['kept']}")
            for k in grand_total:
                grand_total[k] += stats[k]

    print("\n=== WORD FILES ===")
    for fname in all_files:
        if fname.lower().endswith(".docx"):
            path = os.path.join(documents_folder, fname)
            stats = count_filtered_zip_based(path)
            print(f"{fname}: found={stats['total_found']}, too_small={stats['too_small']}, kept={stats['kept']}")
            for k in grand_total:
                grand_total[k] += stats[k]

    print("\n=== EXCEL FILES ===")
    for fname in all_files:
        if fname.lower().endswith(".xlsx"):
            path = os.path.join(documents_folder, fname)
            stats = count_filtered_zip_based(path)
            print(f"{fname}: found={stats['total_found']}, too_small={stats['too_small']}, kept={stats['kept']}")
            for k in grand_total:
                grand_total[k] += stats[k]

    print("\n=== GRAND TOTAL (PDF + Word + Excel) ===")
    print(f"Total images found: {grand_total['total_found']}")
    print(f"Filtered (too small): {grand_total['too_small']}")
    print(f"Filtered (too large/full-page): {grand_total['too_large']}")
    print(f"Kept for captioning: {grand_total['kept']}")