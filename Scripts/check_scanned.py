"""
Scans every PDF in the documents folder, page by page, and flags any page
with little or no extractable text - a strong sign it's a scanned/image
page that needs OCR to be usable (like 9.pdf turned out to be).

This catches BOTH:
  - a fully scanned file (every page flagged)
  - a mostly-text file with just a few scanned diagram/photo pages mixed in
    (which the earlier all-or-nothing "0 chunks" check would have missed)

Does not modify the database - read-only, just prints a report.
"""
import os
import fitz  # PyMuPDF

DOCUMENTS_FOLDER = r"D:\FactoryKA\documents"

# A page with fewer than this many extracted characters is flagged as
# likely scanned/image-only. Adjust if you get too many/few false positives -
# a real text page in these manuals is usually several hundred+ characters.
MIN_CHARS_PER_PAGE = 20


def check_pdf(filepath):
    """Returns a list of (page_number, char_count) for flagged pages."""
    flagged = []
    try:
        doc = fitz.open(filepath)
    except Exception as e:
        print(f"  COULD NOT OPEN: {e}")
        return flagged

    for page_num in range(len(doc)):
        try:
            page = doc[page_num]
            text = page.get_text().strip()
        except Exception as e:
            print(f"  page {page_num + 1}: could not read ({e}), treating as flagged")
            flagged.append((page_num + 1, 0))
            continue
        if len(text) < MIN_CHARS_PER_PAGE:
            flagged.append((page_num + 1, len(text)))

    doc.close()
    return flagged


if __name__ == "__main__":
    files_to_check = [
        "11.pdf", "12.pdf", "13.pdf", "14.pdf", "17.pdf",
        "5.pdf", "7.pdf", "8.pdf", "reduced vol.pdf"
        # 9.pdf skipped - already confirmed scanned and re-ingested with OCR
    ]

    print(f"Checking pages with fewer than {MIN_CHARS_PER_PAGE} extracted characters...\n")

    any_flagged = False
    for fname in files_to_check:
        filepath = os.path.join(DOCUMENTS_FOLDER, fname)
        if not os.path.exists(filepath):
            print(f"{fname}: NOT FOUND, skipping")
            continue

        flagged = check_pdf(filepath)
        if flagged:
            any_flagged = True
            print(f"{fname}: {len(flagged)} page(s) look scanned/empty:")
            for page_num, char_count in flagged:
                print(f"    page {page_num} ({char_count} chars extracted)")
        else:
            print(f"{fname}: OK - all pages have extractable text")

    print()
    if any_flagged:
        print("Files/pages flagged above may need OCR re-ingestion for those specific pages.")
    else:
        print("No scanned/image-only pages detected in the other 9 files.")