import os
import sys
import logging
import traceback
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

from ingest import ingest_pdf, ingest_docx, ingest_xlsx
import retrieval
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.INGEST_LOG_PATH, encoding="utf-8"),
    ]
)
logger = logging.getLogger("add_documents")

retrieval.init()

_D = config.DOCUMENTS_DIR

new_files = [
    {"path": os.path.join(_D, "1.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "10.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "15.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "2.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "3.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "4 .pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "8198.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "ACT.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "Circuit breaker.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "ci.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "drum.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "e.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "h.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "seimens.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "typeki.odf.pdf"), "type": "pdf", "use_ocr": True},
    {"path": os.path.join(_D, "6.pdf"), "type": "pdf", "use_ocr": False},
    {"path": os.path.join(_D, "c.pdf"), "type": "pdf", "use_ocr": False},
    {"path": os.path.join(_D, "dgr.pdf"), "type": "pdf", "use_ocr": False},
    {"path": os.path.join(_D, "hoist.pdf"), "type": "pdf", "use_ocr": False},
    {"path": os.path.join(_D, "i-line.pdf"), "type": "pdf", "use_ocr": False},
    {"path": os.path.join(_D, "synchronous.pdf"), "type": "pdf", "use_ocr": False},
]

files_with_errors = []
total_added = 0

for f in new_files:
    if not os.path.exists(f["path"]):
        logger.error("NOT FOUND, skipping: %s", f["path"])
        files_with_errors.append(f["path"])
        continue

    logger.info("Ingesting %s...", os.path.basename(f["path"]))
    try:
        if f["type"] == "pdf":
            count = ingest_pdf(f["path"], use_ocr=f.get("use_ocr", False))
        elif f["type"] == "docx":
            count = ingest_docx(f["path"])
        elif f["type"] == "xlsx":
            count = ingest_xlsx(f["path"])
        else:
            logger.error("Unknown type '%s' for %s", f["type"], f["path"])
            files_with_errors.append(f["path"])
            continue
    except Exception as e:
        logger.error("Unexpected failure ingesting '%s': %s\n%s", f["path"], e, traceback.format_exc())
        files_with_errors.append(f["path"])
        continue

    logger.info("  -> %d chunks added", count)
    if count == 0:
        files_with_errors.append(f["path"])
    total_added += count

logger.info("Total chunks added: %d", total_added)
if files_with_errors:
    logger.warning("Files with errors or zero chunks: %s", ", ".join(files_with_errors))
else:
    logger.info("All files ingested with no errors.")