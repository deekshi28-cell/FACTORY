"""
search.py

The orchestrator: ties retrieval.py (finding chunks), llm_client.py (calling
the model), and answer_formatter.py (turning the raw output into a final
answer) together into one generate_answer() function.

This file does NOT load any models or connect to the database on import -
call init() once at application startup first (chat.py does this).

Kept as the single entry point that chat.py / run_tests.py / app.py import
from, so nothing downstream needs to change for this split.
"""

import time

import retrieval
import llm_client
import answer_formatter as fmt

# Re-exported for backward compatibility with existing callers
# (e.g. ingest.py currently does `from search import add_chunk`).
# NOTE: per the TL's review, ingestion will be pointed directly at
# retrieval.py instead, as a follow-up step - this re-export is a bridge
# so nothing breaks while that change is made separately.
add_chunk = retrieval.add_chunk
embed_text = retrieval.embed_text
search_chunks = retrieval.search_chunks
format_source = retrieval.format_source


def init():
    """
    Loads the embedding model, connects to ChromaDB, and warms up the LLM.
    Call this once at application startup (chat.py does this) before calling
    generate_answer(). Importing this module does not do this automatically.
    """
    retrieval.init()
    warm_s = llm_client.warm_up()
    return warm_s


def format_timings(t):
    """One-line timing summary, e.g. for printing after each answer."""
    return (
        f"{t['total_s']:.1f}s total | search {t['retrieval_s']:.1f}s | "
        f"LLM {t['llm_s']:.1f}s (model load {t['load_s']:.1f}s, "
        f"read {t['prompt_tokens']} tokens in {t['prompt_s']:.1f}s, "
        f"wrote {t['output_tokens']} tokens in {t['output_s']:.1f}s)"
    )


def generate_answer(query, n_results=None):
    """
    Full RAG pipeline:
      1. retrieval.search_chunks()  - find relevant chunks
      2. answer_formatter           - check for conflicting values (ask to clarify)
      3. llm_client.call_llm()      - generate the answer
      4. answer_formatter           - parse USED SOURCES, strip leaks, attach pictures
    """
    t_start = time.perf_counter()
    # Fix letter-O / full-width typos in fault codes (E-O1 -> E-01) so both the search
    # and the LLM see the code exactly as it is written in the documents.
    query = retrieval.normalize_query(query)
    # "What is the severity of the fault code?" - no code given: ask which one, no model call.
    if fmt.needs_code_clarification(query):
        lang = fmt.detect_language(query)
        return {
            "answer": fmt.build_code_clarification_answer(lang),
            "sources": ["No specific source cited"],
            "detected_language": lang,
            "all_retrieved_sources": [],
            "images": [],
            "timings": {
                "retrieval_s": 0.0, "llm_s": 0.0,
                "total_s": time.perf_counter() - t_start,
                "load_s": 0, "prompt_tokens": 0, "prompt_s": 0,
                "output_tokens": 0, "output_s": 0,
            }
        }

    # "Which fault codes are Critical?" / "Severity of E-12?" - read straight from the fault
    # table rows instead of letting the model list them (it drops or swaps codes).
    sev_q = fmt.parse_severity_question(query)
    if sev_q:
        sdocs, smetas = retrieval.get_severity_chunks()
        built = fmt.build_severity_index(sdocs, [retrieval.format_source(m) for m in smetas])
        if built:
            lang = fmt.detect_language(query)
            hit = fmt.answer_severity(sev_q, built[0], built[1], lang)
            if hit:
                return {
                    "answer": hit[0],
                    "sources": hit[1] if hit[1] else ["No specific source cited"],
                    "detected_language": lang,
                    "all_retrieved_sources": hit[1],
                    "images": [],
                    "timings": {
                        "retrieval_s": time.perf_counter() - t_start, "llm_s": 0.0,
                        "total_s": time.perf_counter() - t_start,
                        "load_s": 0, "prompt_tokens": 0, "prompt_s": 0,
                        "output_tokens": 0, "output_s": 0,
                    }
                }

    results = retrieval.search_chunks(query, n_results=n_results)

    docs = results['documents'][0]
    metas = results['metadatas'][0]
    all_sources = [retrieval.format_source(m) for m in metas]

    detected_lang = fmt.detect_language(query)

    conflicting = fmt.detect_conflicting_values(query, docs)
    if conflicting:
        answer = fmt.build_conflicting_value_answer(conflicting, detected_lang)
        return {
            "answer": answer,
            "sources": all_sources[:3],
            "detected_language": detected_lang,
            "all_retrieved_sources": all_sources,
            "images": [],
            "timings": {
                "retrieval_s": time.perf_counter() - t_start,
                "llm_s": 0.0,
                "total_s": time.perf_counter() - t_start,
                "load_s": 0, "prompt_tokens": 0, "prompt_s": 0,
                "output_tokens": 0, "output_s": 0,
            }
        }

    labeled_context = []
    for i, doc in enumerate(docs):
        labeled_context.append(f"[SOURCE {i+1}: {all_sources[i]}]\n{doc}")
    context = "\n\n---\n\n".join(labeled_context)

    t_retrieved = time.perf_counter()

    prompt = llm_client.build_prompt(query, context, detected_lang)
    raw_answer, llm_stats = llm_client.call_llm(prompt)
    # The answer must be in the question's language. The 7B model sometimes answers a Japanese
    # question in English, slips Chinese into a Japanese answer, or puts Japanese into an English
    # one. When that happens, ask once more with a stricter instruction and keep the better answer.
    if fmt.language_problems(detected_lang, raw_answer):
        retry_answer, retry_stats = llm_client.call_llm(
            llm_client.build_prompt(query, context, detected_lang, strict=True))
        if fmt.language_problems(detected_lang, retry_answer) < fmt.language_problems(detected_lang, raw_answer):
            raw_answer = retry_answer
        for k, v in retry_stats.items():
            llm_stats[k] = llm_stats.get(k, 0) + v
    t_answered = time.perf_counter()

    used_ids, answer_clean = fmt.parse_used_sources(raw_answer)
    if detected_lang == "Japanese":
        if not fmt.looks_japanese(answer_clean) and fmt.is_decline(answer_clean):
            answer_clean = fmt.standard_decline("Japanese")      # declined in English: say it in Japanese
        elif fmt.has_chinese_text(answer_clean):
            answer_clean = fmt.cut_at_chinese(answer_clean)      # last resort: fix / drop the Chinese part

    if used_ids:
        used_sources = list(dict.fromkeys(
            [all_sources[i - 1] for i in used_ids if 0 < i <= len(all_sources)]
        ))
    else:
        used_sources = []

    # Picture question + the model cited text but no picture: also show the picture on the
    # same page as the text it used (not for "not found" answers).
    picture_sources, attached_images = fmt.collect_picture_data(
        used_ids, metas,
        same_page_fallback=retrieval._wants_picture(query) and not fmt.is_decline(answer_clean))

    if picture_sources:
        pointer_str = fmt.format_picture_pointers(picture_sources, detected_lang)
        if pointer_str:
            answer_clean = answer_clean + "\n\n" + pointer_str

    answer_clean = fmt.append_image_markdown(answer_clean, attached_images)

    return {
        "answer": answer_clean,
        "sources": used_sources if used_sources else ["No specific source cited"],
        "detected_language": detected_lang,
        "all_retrieved_sources": all_sources,
        "images": attached_images,
        "timings": {
            "retrieval_s": t_retrieved - t_start,
            "llm_s": t_answered - t_retrieved,
            "total_s": time.perf_counter() - t_start,
            **llm_stats,
        }
    }


if __name__ == "__main__":
    init()
    print(f"Total chunks in store: {retrieval.get_collection().count()}")

    query = "配送された荷物の検査手順は何ですか？"
    result = generate_answer(query)
    print(f"\nQuery: {query}")
    print(f"Answer: {result['answer']}")
    print(f"Sources: {result['sources']}")