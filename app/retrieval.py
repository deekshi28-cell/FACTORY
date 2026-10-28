"""
retrieval.py

Everything related to STORING and FINDING chunks: the embedding model, the
ChromaDB connection, adding chunks, and searching for relevant chunks
(including the keyword-boost and sub-query decomposition logic).

This module knows nothing about the LLM or how answers are generated -
that split is deliberate, so ingestion (which only needs to embed and store
text) does not have to import anything related to answer generation.
"""

import os
import re
import unicodedata

import config

# --- Offline guard ---------------------------------------------------------
# The system must run fully offline. By default, the Hugging Face libraries are
# told NOT to contact the internet (no update checks, no downloads), so they use
# only the model already cached on this machine. This MUST be set before
# sentence_transformers is imported, because the libraries read it at import time.
# One-time setup on a new machine: set FACTORY_ALLOW_MODEL_DOWNLOAD=1 to let
# BGE-M3 download once; after that, leave it unset.
ALLOW_MODEL_DOWNLOAD = os.environ.get("FACTORY_ALLOW_MODEL_DOWNLOAD", "0") == "1"
if not ALLOW_MODEL_DOWNLOAD:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

from sentence_transformers import SentenceTransformer  # noqa: E402
import chromadb  # noqa: E402
from chromadb.config import Settings  # noqa: E402

CHROMA_DIR = config.CHROMA_DIR
N_RESULTS = config.N_RESULTS
MAX_KEYWORD_CHUNKS = config.MAX_KEYWORD_CHUNKS
_EMBED_MODEL_NAME = config.EMBED_MODEL_NAME

# --- Lazy-loaded model/DB handles ---------------------------------------
# Nothing below loads anything at import time. A caller (the app's startup
# code) must call init() once before using embed_text/add_chunk/search_chunks.
_embedder = None
_client = None
_collection = None


def init():
    """
    Loads the embedding model and connects to ChromaDB. Must be called once
    at application startup, BEFORE embed_text/add_chunk/search_chunks are
    used. Importing this module does NOT do this automatically - that was
    one of the TL's review points (importing a file shouldn't load models).
    Safe to call more than once; later calls are no-ops.
    """
    global _embedder, _client, _collection
    if _embedder is not None:
        return

    print("Loading embedding model (BGE-M3)... this may take a minute on first run.")
    try:
        _embedder = SentenceTransformer(_EMBED_MODEL_NAME)
    except Exception as e:
        if not ALLOW_MODEL_DOWNLOAD:
            raise RuntimeError(
                f"Embedding model '{_EMBED_MODEL_NAME}' could not be loaded from the local "
                f"cache while offline mode is on. On a machine WITH internet, run once with "
                f"FACTORY_ALLOW_MODEL_DOWNLOAD=1 to cache it, then copy the cache to this "
                f"machine. Original error: {e}"
            ) from e
        raise

    # anonymized_telemetry=False: ChromaDB otherwise sends anonymous usage
    # statistics to an external server, which an offline system must not do.
    _client = chromadb.PersistentClient(
        path=CHROMA_DIR,
        settings=Settings(anonymized_telemetry=False),
    )
    _collection = _client.get_or_create_collection(name="factory_docs")


def _require_init():
    if _embedder is None or _collection is None:
        init()


def get_collection():
    """Returns the live ChromaDB collection handle (after init())."""
    _require_init()
    return _collection


def embed_text(text):
    _require_init()
    return _embedder.encode(text).tolist()


def add_chunk(chunk_id, text, metadata):
    """Embeds and upserts a single chunk. Used by ingestion."""
    _require_init()
    embedding = embed_text(text)
    _collection.upsert(
        ids=[chunk_id],
        embeddings=[embedding],
        documents=[text],
        metadatas=[metadata]
    )


# --- Fault-code normalisation ---------------------------------------------
# Users type codes with a letter O instead of a zero ("E-O1") or in full-width
# characters ("Ｅ－０１") in Japanese input. The documents contain "E-01", so an
# exact keyword match would never find them. Only code-like tokens are touched;
# the rest of the question (including Japanese text) is left exactly as typed.
_CODE_RUN_RE = re.compile(r"[A-Za-z0-9\uFF21-\uFF3A\uFF41-\uFF5A\uFF10-\uFF19_\-\uFF0D\u2010\u2011\u2013]+")
_CODE_FIX_RE = re.compile(r"^([A-Za-z]{1,4}[-_])((?=[0-9Oo]*[0-9])[0-9Oo]+)$")


def _fix_code_token(run):
    token = unicodedata.normalize("NFKC", run)
    token = token.replace("\u2010", "-").replace("\u2011", "-").replace("\u2013", "-")
    m = _CODE_FIX_RE.match(token)
    if m:
        token = m.group(1) + m.group(2).replace("O", "0").replace("o", "0")
    return token


def normalize_query(query):
    """Fixes letter-O / full-width typos inside fault codes and part numbers only."""
    return _CODE_RUN_RE.sub(lambda m: _fix_code_token(m.group(0)), query)


# --- Keyword-boost search (exact fault codes / part numbers) ------------

_CODE_CANDIDATE_RE = re.compile(
    r"\b[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+)+\b|\b[A-Za-z]{1,4}[-]?\d{1,6}\b|\b[A-Za-z]{2,5}\d+\b"
)

_STOP_WORDS = {
    "a", "an", "is", "it", "of", "on", "or", "to", "in", "at",
    "do", "be", "as", "if", "so", "no", "up", "my", "me", "we",
    "what", "how", "why", "when", "where", "who", "which", "the",
    "this", "that", "these", "those", "for", "with", "from", "and", "or"
}


def _extract_code_candidates(query):
    candidates = set()
    for m in _CODE_CANDIDATE_RE.finditer(query):
        token = m.group(0)
        if token.lower() in _STOP_WORDS:
            continue
        if len(token) >= 2:
            candidates.add(token)
    return candidates


def _keyword_boost_chunks(query, max_extra=MAX_KEYWORD_CHUNKS):
    _require_init()
    extra_docs, extra_metas = [], []
    for token in _extract_code_candidates(query):
        try:
            # fetch more than max_extra: some hits only contain the token inside a longer
            # string and are dropped by the boundary check below, which used to crowd out
            # the real match (e.g. the E-10 row of the fault table).
            hits = _collection.get(
                where_document={"$contains": token},
                limit=max(max_extra * 15, 30)
            )
        except Exception as e:
            print(f"[retrieval] keyword-boost lookup failed for token '{token}': {e}")
            continue
        boundary_re = re.compile(r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])", re.IGNORECASE)
        taken = 0
        for doc, meta in zip(hits.get("documents", []), hits.get("metadatas", [])):
            if taken >= max_extra:
                break
            if boundary_re.search(doc):
                extra_docs.append(doc)
                extra_metas.append(meta)
                taken += 1
    return extra_docs, extra_metas


def get_severity_chunks(limit=300):
    """Table chunks that contain a Critical / Warning / Info level (the fault code tables)."""
    _require_init()
    try:
        hit = _collection.get(
            where={"chunk_type": "table"},
            where_document={"$or": [{"$contains": "Critical"}, {"$contains": "Warning"}, {"$contains": "Info"}]},
            limit=limit,
        )
    except Exception as e:
        print(f"[retrieval] severity table lookup failed: {e}")
        return [], []
    return hit.get("documents", []), hit.get("metadatas", [])


# --- Picture-intent boost ----------------------------------------------------
# Questions such as "what is shown on the cover?" or "In Figure 1 ..." are about a picture,
# but a picture caption often ranks below the longer text chunks and never reaches the
# model (the diagram's caption was ranked 5th when only the top 4 are used). When the
# question is clearly about an image, also pass the model:
#   (a) the pictures on the same page as the best text chunks, and
#   (b) the picture captions closest to the question across all documents.
# Questions that do not mention a picture are not affected at all.
PICTURE_SAME_PAGE_CHUNKS = getattr(config, "PICTURE_SAME_PAGE_CHUNKS", 2)
PICTURE_POOL_CHUNKS = getattr(config, "PICTURE_POOL_CHUNKS", 2)

_PICTURE_INTENT_RE = re.compile(
    r"\b(?:image|images|picture|pictures|photo|photos|diagram|diagrams|figure|figures|fig|"
    r"schematic|illustration|drawing|cover)\b"
    r"|\u753b\u50cf|\u5199\u771f|\u56f3|\u8868\u7d19|\u30a4\u30e9\u30b9\u30c8",
    re.IGNORECASE,
)


def _wants_picture(query):
    return bool(_PICTURE_INTENT_RE.search(query))


def _picture_boost_chunks(query, docs, metas):
    """Returns (extra_docs, extra_metas) picture-caption chunks to add for a picture question."""
    extra_docs, extra_metas = [], []

    def _add(doc, meta):
        if doc in docs or doc in extra_docs:
            return False
        extra_docs.append(doc)
        extra_metas.append(meta)
        return True

    # (a) pictures on the same page as the best text chunks
    added = 0
    seen_pages = set()
    for meta in metas[:3]:
        if added >= PICTURE_SAME_PAGE_CHUNKS:
            break
        if meta.get("chunk_type") == "picture_caption":
            continue
        key = (meta.get("source_file"), meta.get("page_number"))
        if key[0] is None or key in seen_pages:
            continue
        seen_pages.add(key)
        try:
            hit = _collection.get(
                where={"$and": [{"source_file": key[0]}, {"page_number": key[1]},
                                {"chunk_type": "picture_caption"}]},
                limit=PICTURE_SAME_PAGE_CHUNKS,
            )
        except Exception as e:
            print(f"[retrieval] same-page picture lookup failed for {key}: {e}")
            continue
        for d, m in zip(hit.get("documents", []), hit.get("metadatas", [])):
            if added < PICTURE_SAME_PAGE_CHUNKS and _add(d, m):
                added += 1

    # (b) the picture captions closest to the question
    added = 0
    try:
        pool = _collection.query(
            query_embeddings=[embed_text(query)],
            n_results=PICTURE_POOL_CHUNKS + 4,
            where={"chunk_type": "picture_caption"},
        )
        for d, m in zip(pool["documents"][0], pool["metadatas"][0]):
            if added >= PICTURE_POOL_CHUNKS:
                break
            if _add(d, m):
                added += 1
    except Exception as e:
        print(f"[retrieval] picture-pool lookup failed: {e}")

    return extra_docs, extra_metas


# --- Main retrieval entry point ------------------------------------------

def search_chunks(query, n_results=None):
    """
    Returns the ChromaDB-style result dict: {'documents': [[...]], 'metadatas': [[...]]}.
    Includes sub-query decomposition for comparative questions ("compare X with Y")
    and keyword-boost chunks for exact fault-code / part-number matches.
    """
    _require_init()
    query = normalize_query(query)
    if n_results is None:
        n_results = N_RESULTS

    # Sub-query decomposition for comparative queries (e.g., "compare X with Y")
    sub_queries = []
    comp_split = re.split(r"\b(?:compare|versus|vs|difference between)\b", query, flags=re.IGNORECASE)
    if len(comp_split) > 1:
        for part in comp_split:
            sub = part.strip()
            if len(sub) > 5:
                sub_queries.append(sub)
    if " with " in query.lower() and not sub_queries:
        with_split = query.lower().split(" with ")
        if len(with_split) == 2 and len(with_split[0]) > 10 and len(with_split[1]) > 10:
            sub_queries = [with_split[0].strip(), with_split[1].strip()]

    if sub_queries:
        docs, metas = [], []
        for sq in sub_queries:
            sq_emb = embed_text(sq)
            sq_res = _collection.query(query_embeddings=[sq_emb], n_results=max(3, n_results // len(sub_queries)))
            for d, m in zip(sq_res['documents'][0], sq_res['metadatas'][0]):
                if d not in docs:
                    docs.append(d)
                    metas.append(m)
        results = {'documents': [docs[:n_results * 2]], 'metadatas': [metas[:n_results * 2]]}
    else:
        query_embedding = embed_text(query)
        results = _collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )

    extra_docs, extra_metas = _keyword_boost_chunks(query)
    if extra_docs:
        docs = results['documents'][0]
        metas = results['metadatas'][0]
        added = 0
        for doc, meta in zip(extra_docs, extra_metas):
            if added >= MAX_KEYWORD_CHUNKS:
                break
            if doc not in docs:
                docs.append(doc)
                metas.append(meta)
                added += 1
        results['documents'][0] = docs
        results['metadatas'][0] = metas

    if _wants_picture(query):
        pic_docs, pic_metas = _picture_boost_chunks(query, results['documents'][0], results['metadatas'][0])
        if pic_docs:
            results['documents'][0] = results['documents'][0] + pic_docs
            results['metadatas'][0] = results['metadatas'][0] + pic_metas

    return results


def format_source(meta):
    """Turns a chunk's metadata into a human-readable source string, e.g. '7.pdf (page 6)'."""
    page_info = meta.get('page_number')
    source_file = meta.get('source_file')
    if isinstance(page_info, (int, float)):
        return f"{source_file} (page {page_info})"
    else:
        return f"{source_file} ({page_info})"