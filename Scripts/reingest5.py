"""
Re-ingests ONLY the 4 flagged pages of 5.pdf (2, 205, 206, 207) using OCR,
without touching the other ~200 pages that already have good extracted text.

NOTE: this reuses your existing read_pdf_with_ocr(), which OCRs the WHOLE
document - there's no cheaper option available without changing readers.py
to accept a page range. That means this will be slow for a 200+ page file
(OCR is much slower than normal text extraction, page by page). Only the
4 target pages actually get written to the database; the OCR results for
every other page are computed but simply discarded.
"""
import time
import logging
import retrieval
import config
from readers import read_pdf_with_ocr
from chunker import chunk_text

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.INGEST_LOG_PATH, encoding="utf-8"),
    ]
)
logger = logging.getLogger("reingest5")

retrieval.init()

TARGET_PAGES = {2, 205, 206, 207}
filepath = r"D:\FactoryKA\documents\5.pdf"

print("Running OCR across all of 5.pdf (this may take a while for a large file)...")
t0 = time.time()
try:
    pages = read_pdf_with_ocr(filepath)
except Exception as e:
    logger.error("Failed to OCR '%s': %s", filepath, e, exc_info=True)
    raise SystemExit(1)
print(f"OCR pass finished in {time.time() - t0:.1f}s")

added = 0
failed = 0
for page in pages:
    if page["page_number"] not in TARGET_PAGES:
        continue

    chunks = chunk_text(page["text"])
    if not chunks:
        logger.warning("page %d: OCR still found no usable text", page["page_number"])
        continue

    for i, chunk_content in enumerate(chunks):
        chunk_id = f"{page['source_file']}_p{page['page_number']}_c{i}"
        try:
            retrieval.add_chunk(
                chunk_id=chunk_id,
                text=chunk_content,
                metadata={
                    "source_file": page["source_file"],
                    "page_number": page["page_number"],
                    "chunk_type": "text"
                }
            )
            added += 1
        except Exception as e:
            logger.error("Failed to add chunk '%s': %s", chunk_id, e, exc_info=True)
            failed += 1
    print(f"  page {page['page_number']}: {len(chunks)} chunk(s) processed via OCR")

print(f"\nTotal chunks added: {added}")
if failed:
    logger.warning("%d chunk(s) failed to add", failed)