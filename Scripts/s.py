import pymupdf
import os
import zipfile
import io
from PIL import Image

MIN_SIZE = 250  
MAX_SIZE = 1800

def count_pdf(filepath):
    doc = pymupdf.open(filepath)
    found = small = large = kept = 0
    for page_num in range(len(doc)):
        for img in doc[page_num].get_images(full=True):
            found += 1
            base_image = doc.extract_image(img[0])
            w, h = base_image["width"], base_image["height"]
            if w < MIN_SIZE or h < MIN_SIZE:
                small += 1
            elif w > MAX_SIZE or h > MAX_SIZE:
                large += 1
            else:
                kept += 1
    doc.close()
    return found, small, large, kept

def count_zip_based(filepath):
    found = small = kept = 0
    with zipfile.ZipFile(filepath, 'r') as z:
        for name in z.namelist():
            if 'media/' in name and not name.endswith('/'):
                found += 1
                data = z.read(name)
                try:
                    img = Image.open(io.BytesIO(data))
                    w, h = img.size
                    if w < MIN_SIZE or h < MIN_SIZE:
                        small += 1
                    else:
                        kept += 1
                except Exception:
                    pass
    return found, small, 0, kept

documents_folder = r"D:\FactoryKA\documents"
totals = {"found": 0, "small": 0, "large": 0, "kept": 0}

for fname in os.listdir(documents_folder):
    path = os.path.join(documents_folder, fname)
    if fname.lower().endswith(".pdf"):
        f, s, l, k = count_pdf(path)
    elif fname.lower().endswith((".docx", ".xlsx")):
        f, s, l, k = count_zip_based(path)
    else:
        continue
    totals["found"] += f
    totals["small"] += s
    totals["large"] += l
    totals["kept"] += k

print(f"Total found: {totals['found']}")
print(f"Filtered (too small): {totals['small']}")
print(f"Filtered (too large): {totals['large']}")
print(f"Total filtered: {totals['small'] + totals['large']}")
print(f"Kept: {totals['kept']}")
print(f"Check: found = filtered + kept? {totals['found']} = {totals['small']+totals['large']+totals['kept']}")