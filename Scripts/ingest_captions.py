import sys
import os
import json
import logging

# Allow imports from app/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))
sys.stdout.reconfigure(encoding="utf-8")

import config
import retrieval

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("ingest_captions")

CAPTIONS_PATH = os.path.join(config.BASE_DIR, "Results", "all_captions.json")

if not os.path.exists(CAPTIONS_PATH):
    logger.error("Captions file not found: %s", CAPTIONS_PATH)
    sys.exit(1)

with open(CAPTIONS_PATH, "r", encoding="utf-8") as f:
    captions = json.load(f)

retrieval.init()

count = 0
skipped = 0
failed = 0

for idx, item in enumerate(captions):
    try:
        if item.get("caption") == "CAPTION_FAILED":
            skipped += 1
            continue

        source_file = item["source_file"]
        image_path = item["image_path"]
        chunk_id = f"img_{source_file}_{image_path.split(chr(92))[-1]}"

        retrieval.add_chunk(
            chunk_id=chunk_id,
            text=item["caption"],
            metadata={
                "source_file": source_file,
                "page_number": item.get("page_number", 0),
                "chunk_type": "picture_caption",
                "image_path": image_path,
            },
        )
        count += 1
    except Exception as e:
        logger.error("Failed to process caption entry #%d: %s", idx, e, exc_info=True)
        failed += 1

logger.info(
    "Caption ingestion complete — added: %d | skipped (CAPTION_FAILED): %d | errors: %d",
    count, skipped, failed,
)