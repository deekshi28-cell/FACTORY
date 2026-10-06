import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
"""
One-off script to re-ingest 9.pdf with OCR turned on, after the normal
(non-OCR) ingest run returned 0 chunks for it - likely because it's a
scanned/image-only PDF with no extractable text layer.
"""
import logging
import retrieval
from ingest import ingest_document

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("reingest9")

retrieval.init()

filepath = os.path.join(config.DOCUMENTS_DIR, "9.pdf")
try:
    n = ingest_document(filepath, use_ocr=True)
except Exception as e:
    logger.error("Failed to re-ingest '%s': %s", filepath, e, exc_info=True)
    n = 0

print(f"9.pdf (with OCR) -> {n} chunks added")

if n == 0:
    print(
        "Still 0 chunks even with OCR on. This means the problem isn't "
        "missing text (OCR should have caught that) - check ingest.log for "
        "an actual error, or open 9.pdf manually to confirm it isn't "
        "corrupted, password-protected, or blank."
    )