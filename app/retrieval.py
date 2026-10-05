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
from sentence_transformers import SentenceTransformer
import chromadb

import config

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
    _embedder = SentenceTransformer(_EMBED_MODEL_NAME)

    _client = chromadb.PersistentClient(path=CHROMA_DIR)
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
            hits = _collection.get(
                where_document={"$contains": token},
                limit=max_extra
            )
        except Exception as e:
            print(f"[retrieval] keyword-boost lookup failed for token '{token}': {e}")
            continue
        boundary_re = re.compile(r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])", re.IGNORECASE)
        for doc, meta in zip(hits.get("documents", []), hits.get("metadatas", [])):
            if boundary_re.search(doc):
                extra_docs.append(doc)
                extra_metas.append(meta)
    return extra_docs, extra_metas


# --- Main retrieval entry point ------------------------------------------

def search_chunks(query, n_results=None):
    """
    Returns the ChromaDB-style result dict: {'documents': [[...]], 'metadatas': [[...]]}.
    Includes sub-query decomposition for comparative questions ("compare X with Y")
    and keyword-boost chunks for exact fault-code / part-number matches.
    """
    _require_init()
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

    return results


def format_source(meta):
    """Turns a chunk's metadata into a human-readable source string, e.g. '7.pdf (page 6)'."""
    page_info = meta.get('page_number')
    source_file = meta.get('source_file')
    if isinstance(page_info, (int, float)):
        return f"{source_file} (page {page_info})"
    else:
        return f"{source_file} ({page_info})"
