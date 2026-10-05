# Factory Knowledge Assistant (FactoryKA)

A fully local, offline RAG (retrieval-augmented generation) assistant for Nichi-In equipment manuals and factory documentation. It answers natural-language questions (English and Japanese) by retrieving relevant chunks from ingested PDF/DOCX/XLSX documents and generating answers with a locally-hosted LLM — no internet connection or external API calls required at query time.

## How it works

1. **Ingestion** — Documents (PDF, DOCX, XLSX) are read, OCR'd where needed (scanned pages), chunked, embedded with a local BGE-M3 embedding model, and stored in a local ChromaDB vector database. Embedded images are captioned and indexed alongside the text.
2. **Retrieval** — A user question is embedded with the same model and matched against the stored chunks (semantic search) plus keyword matching.
3. **Generation** — The retrieved context is passed to a local LLM served by [Ollama](https://ollama.com) (`qwen2.5:7b-instruct-q4_K_M` by default), which generates the final answer.
4. **Delivery** — Answers are available through a CLI chat (`app/chat.py`) or a Flask-based web UI (`app/app.py`).

## Prerequisites

Before installing the Python dependencies, two things must be installed separately — they are **not** pip packages:

- **[Ollama](https://ollama.com)**, running locally, with the model pulled:
  ```
  ollama pull qwen2.5:7b-instruct-q4_K_M
  ollama serve
  ```
  (Ollama must be running — `ollama serve` — whenever `chat.py` or `app.py` is used.)
- **Tesseract OCR**, installed and available on your system `PATH`. `pytesseract` is only a Python wrapper around the Tesseract engine — it does nothing without the engine itself installed. On Windows, install it from the [Tesseract installer](https://github.com/UB-Mannheim/tesseract/wiki) and confirm `tesseract --version` works from a new terminal.

Python 3.10 or later is recommended.

## Setup

```
cd D:\FactoryKA
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Confirm `(venv)` appears at the start of your prompt before running anything below — several bugs in this project traced back to running scripts outside the venv (missing `chromadb`, etc.).

## Configuration

All tunable settings live in `app/config.py` and can be overridden with environment variables (all optional — sensible defaults are built in):

| Variable | Purpose | Default |
|---|---|---|
| `FACTORY_OLLAMA_URL` | Ollama API endpoint | `http://localhost:11434` |
| `FACTORY_LLM_MODEL` | Model name served by Ollama | `qwen2.5:7b-instruct-q4_K_M` |
| `FACTORY_LLM_KEEP_ALIVE` | How long Ollama keeps the model loaded | `60m` |
| `FACTORY_LLM_NUM_CTX` | Context window size (tokens) | `8192` |
| `FACTORY_LLM_MAX_TOKENS` | Max tokens in a generated answer | `300` |
| `FACTORY_LLM_NUM_THREAD` | CPU threads Ollama uses (avoid oversubscription — see Known Issues) | unset (Ollama default) |
| `FACTORY_LLM_TIMEOUT` | Seconds before a model call times out | `120` |

Document, database, and log paths (`DOCUMENTS_DIR`, `CHROMA_DIR`, `EXTRACTED_IMAGES_DIR`, `INGEST_LOG_PATH`, `TEST_QUESTIONS_PATH`, `TEST_RESULTS_PATH`) are also set in `config.py`.

## Ingesting documents

1. Place source files (`.pdf`, `.docx`, `.xlsx`) into the documents folder (`config.DOCUMENTS_DIR`, currently `documents/` at the project root).
2. Run the ingestion script:
   ```
   python Scripts\add_documents.py
   ```
   This reads each file, OCRs scanned pages where needed, chunks and embeds the content, and writes it into the local ChromaDB store. Errors on individual files are logged (see `config.INGEST_LOG_PATH`) rather than stopping the whole batch.
3. To re-process a specific already-ingested file or recover from a partial ingest, see `Scripts\reingest5.py` / `Scripts\reingest9.py`. `Scripts\check_scanned.py` can be run first to flag which PDF pages look like scans (low extractable text) and will need OCR. Image captions are generated and ingested via `Scripts\batch_caption.py` and `Scripts\ingest_captions.py`.

## Running the assistant

**CLI:**
```
python app\chat.py
```
> Note: a `chat.py` also currently exists at the project root (`D:\FactoryKA\chat.py`). Confirm which one is the active/current version — if the root copy is an older leftover, remove it to avoid confusion about which file is actually being edited and run.

**Web UI:**
```
python app\app.py
```
Then open the app in your browser at the port configured in `app.py` (Flask defaults to `http://localhost:5000` unless changed). The web UI shows cited sources, extracted images, and a running accuracy stat pulled from the latest test run.

Both interfaces require `ollama serve` to be running in the background.

## Running the test suite

```
python tests\run_tests.py
```

This runs every question in `tests\test_questions.json` against the live system and scores each answer two ways:
- **Source match** — did it cite the expected document (diagnostic signal only).
- **Answer match** — is the actual answer semantically correct, via embedding similarity against `expected_answer` (plus a decline-phrase fallback for "Not Found" category questions). This is the primary pass/fail metric.

Results and other generated output (captions, logs, extracted images) are written under `Results/`, including `Results/automatic_test_results.json` (per-question detail, including similarity scores) and `Results/ingest.log`. The web UI's reported accuracy (`/api/stats`) is pulled from the results file.

## Project structure

```
FactoryKA/
├── app/
│   ├── app.py               # Flask web UI + API (/api/ask, /api/image, /api/stats)
│   ├── chat.py               # CLI chat interface
│   ├── search.py             # Query-time retrieval + answer generation
│   ├── retrieval.py          # ChromaDB access (add/query chunks)
│   ├── llm_client.py         # HTTP client for the Ollama model
│   ├── readers.py            # PDF/DOCX/XLSX text extraction + OCR
│   ├── chunker.py            # Splits extracted text into chunks for embedding
│   ├── ingest.py             # Ingestion pipeline (single document)
│   ├── answer_formatter.py   # Formats model output for display
│   ├── config.py             # Central configuration (see table above)
│   ├── static/               # Web UI frontend assets (script.js, etc.)
│   └── templates/            # Flask HTML templates
├── Scripts/                  # Ingestion, OCR, captioning, KPI/benchmark, and
│   │                         # verification utilities (44 scripts). Key ones:
│   ├── add_documents.py      # Bulk ingest all documents in DOCUMENTS_DIR
│   ├── batch_caption.py      # Generates captions for extracted images
│   ├── ingest_captions.py    # Ingests image captions into the index
│   ├── reingest5.py          # Re-ingest with OCR recovery
│   ├── reingest9.py          # Re-ingest a single document
│   ├── check_scanned.py      # Flags PDF pages likely needing OCR
│   ├── benchmark_latency.py, measure_kpi3.py, measure_kpi7.py
│   │                         # KPI / latency benchmarking
│   └── check_*.py, verify*.py, peek_*.py, test_*.py
│                             # Diagnostic/verification scripts accumulated
│                             # during development — candidates for a cleanup
│                             # pass (see note below)
├── tests/
│   ├── run_tests.py          # Automated test runner + scoring
│   ├── test_questions.json   # Test question bank (with expected answers/sources)
│   ├── export_questions.py
│   ├── Phase2_Test_Questions.xlsx
│   ├── table_audit.py        # Also exists in Scripts/ — check for duplication
│   └── test_real_table.py
├── Results/                   # Generated output (not hand-edited)
│   ├── chroma_db/             # ChromaDB vector store
│   ├── extracted_images/      # Images pulled from ingested documents
│   ├── automatic_test_results.json
│   ├── all_captions.json
│   ├── ingest.log
│   └── ...
├── chroma_db/, documents/     # Also present at project root — confirm
│                               # whether these are the live paths config.py
│                               # points to, or stale copies from before the
│                               # Results/ reorganization
├── venv/
├── requirements.txt
├── Document_Tracker.xlsx
├── Factory_Knowledge_Assistant 1.docx
├── scan_reports.py
└── README.md
```

> **Two things worth resolving before this structure is considered final:** (1) `chat.py` exists both at the project root and in `app/` — pick one and remove the other. (2) `chroma_db/` and `documents/` exist both at the project root and inside `Results/` — `config.py`'s `CHROMA_DIR`/`DOCUMENTS_DIR`/`EXTRACTED_IMAGES_DIR` settings determine which copies are actually live; the others are likely stale and safe to delete once confirmed, freeing disk space and removing a source of confusion for anyone new to the repo (including a TL reviewing it).

## Known limitations

- A small number of scanned pages (e.g. `5.pdf` pages 2, 205–207) remain unreadable even with OCR and return no chunks.
- Answer-correctness scoring is based on embedding similarity, which is an approximation, not a perfect judge — it can occasionally miss a subtly wrong answer or under-score a correct-but-differently-worded one. Spot-check results near the similarity threshold (`ANSWER_MATCH_THRESHOLD` in `run_tests.py`) periodically.
- `Scripts/` has accumulated a number of one-off diagnostic scripts from development (`debug.py`, `debug_vfd.py`, `vfd.py`, `s.py`, `fail.py`, `checkf.py`, `inspect31.py`, `verify22.py`, and similar). They aren't part of the documented workflow above and are worth a cleanup pass — either removing them or moving them to a clearly-labeled `Scripts/scratch/` subfolder — before a TL reviews the repo structure.
- All processing is local/offline by design — no document content or questions are sent to any external service.
