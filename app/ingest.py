import os
import logging
import traceback

from readers import read_pdf, read_pdf_with_ocr, read_docx, read_xlsx
from chunker import chunk_text, chunk_table
import retrieval
import config

# --- Logging ---------------------------------------------------------------
# Per TL review: failed document/chunk processing must be VISIBLE, not
# silently swallowed. This logs to both the console and a file, so a failed
# run leaves a record you can check afterward, not just whatever scrolled
# past in the terminal.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.INGEST_LOG_PATH, encoding="utf-8"),
    ]
)
logger = logging.getLogger("ingest")


def _add_chunk_safe(chunk_id, text, metadata):
    """
    Wraps retrieval.add_chunk() with real error logging instead of a bare
    `except Exception: pass`. Returns True on success, False on failure -
    callers use this to keep an accurate count of what actually got ingested.
    """
    try:
        retrieval.add_chunk(chunk_id=chunk_id, text=text, metadata=metadata)
        return True
    except Exception as e:
        logger.error(
            "Failed to add chunk '%s' (source=%s, page=%s): %s\n%s",
            chunk_id, metadata.get("source_file"), metadata.get("page_number"),
            e, traceback.format_exc()
        )
        return False


def ingest_pdf(filepath, use_ocr=False):
    reader_fn = read_pdf_with_ocr if use_ocr else read_pdf
    try:
        pages = reader_fn(filepath)
    except Exception as e:
        logger.error("Failed to read PDF '%s': %s\n%s", filepath, e, traceback.format_exc())
        return 0

    count = 0
    failed = 0
    for page in pages:
        chunks = chunk_text(page["text"])
        for i, chunk_content in enumerate(chunks):
            chunk_id = f"{page['source_file']}_p{page['page_number']}_c{i}"
            ok = _add_chunk_safe(
                chunk_id=chunk_id,
                text=chunk_content,
                metadata={
                    "source_file": page["source_file"],
                    "page_number": page["page_number"],
                    "chunk_type": "text"
                }
            )
            if ok:
                count += 1
            else:
                failed += 1

    if failed:
        logger.warning("%s: %d chunk(s) failed to ingest out of %d", filepath, failed, count + failed)
    return count


def ingest_docx(filepath):
    try:
        result = read_docx(filepath)
    except Exception as e:
        logger.error("Failed to read DOCX '%s': %s\n%s", filepath, e, traceback.format_exc())
        return 0

    source = result["source_file"]
    count = 0
    failed = 0

    full_text = "\n\n".join(result["paragraphs"])
    chunks = chunk_text(full_text)
    for i, chunk_content in enumerate(chunks):
        chunk_id = f"{source}_para_c{i}"
        ok = _add_chunk_safe(
            chunk_id=chunk_id,
            text=chunk_content,
            metadata={"source_file": source, "page_number": f"Section {i+1}", "chunk_type": "text"}
        )
        if ok:
            count += 1
        else:
            failed += 1

    for t_idx, table in enumerate(result["tables"]):
        rows = table["rows"]
        if not rows:
            continue
        table_chunks = chunk_table(rows, max_rows_per_chunk=15)
        for c_idx, tc in enumerate(table_chunks):
            header_str = " | ".join(str(h) for h in tc["header"])
            rows_str = "\n".join(" | ".join(str(cell) for cell in row) for row in tc["rows"])
            table_text = f"Table columns: {header_str}\n{rows_str}"

            page_label = f"Table {t_idx + 1}" if len(table_chunks) == 1 else f"Table {t_idx + 1}, part {c_idx + 1}"

            chunk_id = f"{source}_table{t_idx}_c{c_idx}"
            ok = _add_chunk_safe(
                chunk_id=chunk_id,
                text=table_text,
                metadata={"source_file": source, "page_number": page_label, "chunk_type": "table", "table_index": t_idx}
            )
            if ok:
                count += 1
            else:
                failed += 1

    if failed:
        logger.warning("%s: %d chunk(s) failed to ingest out of %d", filepath, failed, count + failed)
    return count


def ingest_xlsx(filepath):
    try:
        result = read_xlsx(filepath)
    except Exception as e:
        logger.error("Failed to read XLSX '%s': %s\n%s", filepath, e, traceback.format_exc())
        return 0

    source = result["source_file"]
    count = 0
    failed = 0

    for sheet in result["sheets"]:
        rows = sheet["rows"]
        if not rows:
            continue
        table_chunks = chunk_table(rows, max_rows_per_chunk=15)
        row_tracker = 2
        for c_idx, tc in enumerate(table_chunks):
            header_str = " | ".join(str(h) for h in tc["header"])
            rows_str = "\n".join(" | ".join(str(cell) for cell in row) for row in tc["rows"])
            table_text = f"Sheet: {sheet['sheet_name']}\nColumns: {header_str}\n{rows_str}"

            start_row = row_tracker
            end_row = row_tracker + len(tc["rows"]) - 1
            row_tracker = end_row + 1

            chunk_id = f"{source}_{sheet['sheet_name']}_c{c_idx}"
            ok = _add_chunk_safe(
                chunk_id=chunk_id,
                text=table_text,
                metadata={"source_file": source, "page_number": f"Row {start_row}-{end_row}", "chunk_type": "table"}
            )
            if ok:
                count += 1
            else:
                failed += 1

    if failed:
        logger.warning("%s: %d chunk(s) failed to ingest out of %d", filepath, failed, count + failed)
    return count


def ingest_document(filepath, use_ocr=False):
    """Routes to the right ingester based on file extension."""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return ingest_pdf(filepath, use_ocr=use_ocr)
    elif ext == ".docx":
        return ingest_docx(filepath)
    elif ext == ".xlsx":
        return ingest_xlsx(filepath)
    else:
        logger.warning("Skipped (unsupported type): %s", filepath)
        return 0


if __name__ == "__main__":
    # Ingestion only needs the embedding model + database - NOT the LLM.
    # This is the point of the split: ingest.py no longer imports search.py
    # or generate_answer at all, so running this never loads Ollama-related
    # code.
    retrieval.init()

    documents_folder = r"D:\FactoryKA\documents"

    files_to_ingest = [
        "11.pdf", "12.pdf", "13.pdf", "14.pdf", "17.pdf",
        "5.pdf", "7.pdf", "8.pdf", "9.pdf", "reduced vol.pdf"
    ]

    total = 0
    files_with_errors = []

    for fname in files_to_ingest:
        filepath = os.path.join(documents_folder, fname)
        if not os.path.exists(filepath):
            logger.error("Not found, skipping: %s", fname)
            files_with_errors.append(fname)
            continue

        logger.info("Ingesting %s...", fname)
        try:
            n = ingest_document(filepath)
        except Exception as e:
            # Catch-all so one bad file can't kill the whole ingestion run.
            logger.error("Unexpected failure ingesting '%s': %s\n%s", fname, e, traceback.format_exc())
            files_with_errors.append(fname)
            continue

        logger.info("  -> %d chunks added", n)
        if n == 0:
            files_with_errors.append(fname)
        total += n

    logger.info("Total chunks ingested: %d", total)
    if files_with_errors:
        logger.warning("Files with errors or zero chunks ingested: %s", ", ".join(files_with_errors))
    else:
        logger.info("All files ingested with no errors.")