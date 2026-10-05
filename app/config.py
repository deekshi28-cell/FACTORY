"""
config.py

Single source of truth for file paths, model names, and settings used
across the project. Nothing here loads any model or connects to anything -
it's just constants, so importing this file is always safe and instant.

Every value can still be overridden with an environment variable (same
FACTORY_* names as before), for anyone running this on a different machine
or drive letter - but the default now only needs to be written ONCE, here,
instead of being repeated as r"D:\FactoryKA\..." in every file.
"""

import os

# --- Base project folder ---------------------------------------------------
# Change this ONE line (or set the FACTORY_BASE_DIR environment variable) to
# move the whole project to a different drive/folder - nothing else needs editing.
BASE_DIR = os.environ.get("FACTORY_BASE_DIR", r"D:\FactoryKA")

# --- Derived paths -----------------------------------------------------------
DOCUMENTS_DIR = os.environ.get("FACTORY_DOCUMENTS_DIR", os.path.join(BASE_DIR, "documents"))

_default_chroma_dir = os.path.join(BASE_DIR, "Results", "chroma_db")
if not os.path.exists(_default_chroma_dir):
    _default_chroma_dir = os.path.join(BASE_DIR, "chroma_db")
CHROMA_DIR = os.environ.get("FACTORY_CHROMA_DIR", _default_chroma_dir)

_default_img_dir = os.path.join(BASE_DIR, "tests", "extracted_images")
if not os.path.exists(_default_img_dir):
    _default_img_dir = os.path.join(BASE_DIR, "extracted_images")
EXTRACTED_IMAGES_DIR = os.environ.get("FACTORY_EXTRACTED_IMAGES_DIR", _default_img_dir)

_default_test_q = os.path.join(BASE_DIR, "tests", "test_questions.json")
if not os.path.exists(_default_test_q):
    _default_test_q = os.path.join(BASE_DIR, "test_questions.json")
TEST_QUESTIONS_PATH = os.environ.get("FACTORY_TEST_QUESTIONS_PATH", _default_test_q)

_default_test_res = os.path.join(BASE_DIR, "Results", "automatic_test_results.json")
if not os.path.exists(_default_test_res):
    _default_test_res = os.path.join(BASE_DIR, "automatic_test_results.json")
TEST_RESULTS_PATH = os.environ.get("FACTORY_TEST_RESULTS_PATH", _default_test_res)

_default_ingest_log = os.path.join(BASE_DIR, "Results", "ingest.log")
if not os.path.exists(_default_ingest_log):
    _default_ingest_log = os.path.join(BASE_DIR, "ingest.log")
INGEST_LOG_PATH = os.environ.get("FACTORY_INGEST_LOG_PATH", _default_ingest_log)

# --- Models --------------------------------------------------------------
EMBED_MODEL_NAME = os.environ.get("FACTORY_EMBED_MODEL", "BAAI/bge-m3")
LLM_MODEL = os.environ.get("FACTORY_LLM_MODEL", "qwen2.5:7b-instruct-q4_K_M")
OLLAMA_URL = os.environ.get("FACTORY_OLLAMA_URL", "http://localhost:11434")

# --- Retrieval settings ----------------------------------------------------
N_RESULTS = int(os.environ.get("FACTORY_N_RESULTS", "4"))
# at most this many extra chunks from the exact-code keyword search, so the prompt can't grow unbounded
MAX_KEYWORD_CHUNKS = int(os.environ.get("FACTORY_MAX_KEYWORD_CHUNKS", "2"))

# --- LLM / speed settings (target: every answer in under 15 seconds) -----
# - keep_alive: keep the LLM loaded in memory between questions. Ollama's default
#   unloads it after 5 idle minutes, and reloading a 7B model costs 5-20 seconds.
# - num_ctx: must stay the same on every call, otherwise Ollama reloads the model.
# - num_predict: upper limit on answer length - generation time grows with every token.
# - num_thread: NOT set by default. os.cpu_count() counts logical (hyperthreaded)
#   cores, and forcing that many threads caused severe CPU oversubscription on this
#   machine - answers got ~8x SLOWER (292.9s avg instead of ~30-50s) plus crashes.
#   Ollama's own default thread selection handles this correctly. Only set
#   FACTORY_LLM_NUM_THREAD if you know your PHYSICAL core count and have re-measured.
LLM_KEEP_ALIVE = os.environ.get("FACTORY_LLM_KEEP_ALIVE", "60m")
LLM_NUM_CTX = int(os.environ.get("FACTORY_LLM_NUM_CTX", "8192"))
LLM_MAX_TOKENS = int(os.environ.get("FACTORY_LLM_MAX_TOKENS", "300"))
LLM_NUM_THREAD = os.environ.get("FACTORY_LLM_NUM_THREAD")  # unset by default - let Ollama choose
LLM_TIMEOUT = int(os.environ.get("FACTORY_LLM_TIMEOUT", "120"))

TARGET_SECONDS = 15  # KPI #9 target

# Retries: how long run_tests.py waits before retrying a question after a
# dropped Ollama connection.
TEST_RETRY_DELAY_SECONDS = int(os.environ.get("FACTORY_TEST_RETRY_DELAY_SECONDS", "5"))
