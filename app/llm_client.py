"""
llm_client.py

Everything related to CALLING THE LLM: prompt construction, the Ollama
HTTP call itself, and the fixed prompt rules/instructions. Knows nothing
about ChromaDB or embeddings, and nothing about how to parse or format the
raw model output into a final answer - that lives in answer_formatter.py.
"""

import time
import logging
import requests as req_lib
import config

logger = logging.getLogger("llm_client")

# --- Settings -------------------------------------------------------------
# All settings now come from config.py (single source of truth, per the TL
# review) instead of being duplicated here.
OLLAMA_URL = config.OLLAMA_URL
LLM_MODEL = config.LLM_MODEL

# Speed settings (target: every answer in under 15 seconds)
# - keep_alive: keep the LLM loaded in memory between questions. Ollama's default
#   unloads it after 5 idle minutes, and reloading a 7B model costs 5-20 seconds.
# - num_ctx: must stay the same on every call, otherwise Ollama reloads the model.
# - num_predict: upper limit on answer length - generation time grows with every token.
# - num_thread: NOT set by default. os.cpu_count() counts logical (hyperthreaded)
#   cores, and forcing that many threads caused severe CPU oversubscription on this
#   machine - answers got ~8x SLOWER (292.9s avg instead of ~30-50s) plus crashes.
#   Ollama's own default thread selection handles this correctly. Only set
#   FACTORY_LLM_NUM_THREAD if you know your PHYSICAL core count and have re-measured.
LLM_KEEP_ALIVE = config.LLM_KEEP_ALIVE
LLM_NUM_CTX = config.LLM_NUM_CTX
LLM_MAX_TOKENS = config.LLM_MAX_TOKENS
LLM_NUM_THREAD = config.LLM_NUM_THREAD
LLM_TIMEOUT = config.LLM_TIMEOUT

# One HTTP connection reused for every Ollama call. Created at import time -
# this is just a Session object, it does not talk to the network or load
# anything, so it's fine to construct eagerly (unlike the embedding model /
# database connection in retrieval.py, which are loaded lazily via init()).
_http = req_lib.Session()


# Fixed instructions, identical for every question. They come FIRST in the prompt so
# Ollama can reuse its cached work for this prefix (prompt caching) instead of
# re-reading ~1500 tokens of rules on every question. Everything that changes per
# question (context, answer language, question) comes after it.
PROMPT_RULES = """Answer the question using ONLY the context below. Each piece of context is labeled with a SOURCE number.

CRITICAL RULE - NEVER VIOLATE THIS: Never write the word "SOURCE" or any source number (like "SOURCE 1", "SOURCE 3") anywhere in your answer text. Source numbers are ONLY allowed in the final USED SOURCES line, nowhere else.

IMPORTANT - ASK FOR CLARIFICATION when needed, in THREE situations. Do NOT guess a single value, do NOT average or blend numbers, and do NOT list every conflicting value as if that were an answer:

1. AMBIGUOUS TERM: a short term, code, or abbreviation could mean more than one different thing across the context. Name the possibilities and ask which is meant.

2. UNDERSPECIFIED QUESTION: the topic is clear, but the source has multiple values depending on a parameter the question didn't give (a quantity, size, model, category). This includes tables: if a table row's value depends on a column (e.g. pole count, enclosure type, voltage class) and the question does not state which value of that column applies, do NOT pick one row or one value - name the missing parameter and list the options that column contains.

3. MULTIPLE CONFLICTING PRODUCT TABLES: the context contains different tables or sections, belonging to different products, models, classes, or types, that each give a different value for what looks like the same question. Do not try to reconcile, average, or list all the conflicting numbers. Instead, briefly state that the answer depends on which product/type is meant, name 1-3 of the products/types you noticed (by their description, never by SOURCE number), and ask the user to specify. Keep this answer SHORT - a sentence or two plus the question, not a breakdown of every value found.

BEFORE USING CASE 3 - CHECK RELEVANCE FIRST: case 3 is for genuinely competing answers to the SAME question, not for "the context happens to contain some numbers." Before treating a set of values as "multiple conflicting values," check that each one is actually the same kind of quantity being asked about - the same unit and the same real-world meaning (e.g. a price in currency, not a weight in kg or a rating in volts that happens to appear near similar words). A dollar amount, a weight in kg, and a voltage rating are never "conflicting values for the same question," even if they all appear in results for the same query - they are answers to different questions, meaning none of them answers this one. If none of the retrieved context contains a value of the actual kind being asked about, this is NOT case 3 - it is a NOT-FOUND situation: say plainly that the answer isn't in the documents, and do not list any of the irrelevant numbers as if they were candidate answers.

IMPORTANT - EXACT FAULT CODE / PART NUMBER MATCHING: If the question asks about a specific fault code, error code, alarm code, or part number (e.g. E-16), verify whether that exact identifier appears in the provided context. If the exact code or part number does NOT appear anywhere in the context, do NOT answer using a different or nearby code (such as E-15, E-07, or OH) — state clearly that the specified code/number is not found in the documents and set USED SOURCES to none.

IMPORTANT - UNDERSPECIFIED GENERAL QUESTIONS ACROSS MULTIPLE MANUALS: If the question asks for a broad specification, warranty, shipping cost, or system layout (such as "warranty period", "shipping cost", or "block diagram layout") without naming the specific equipment or product model, and the retrieved context contains manuals for multiple different equipment/manufacturers, do NOT pick one product at random — state clearly that the specific equipment model must be specified.

IMPORTANT - ACCURACY: State only what the source text explicitly says. Do NOT add conclusions, guarantees, or interpretations that go beyond the literal wording of the source — this is especially critical for safety-related statements.

IMPORTANT - DO NOT BLEND COMPETING PROCEDURES: Different manuals can contain their own version of what looks like the same standard procedure (e.g. unpacking, receiving inspection, general maintenance) - these versions are for different equipment and can differ in real, specific ways even when they look similar. This applies even when the manuals are for completely unrelated equipment (e.g. a transformer manual and a press manual can both have a generic "receiving inspection" section) - similarity of topic across sources is not evidence they describe the same procedure. If more than one SOURCE describes what appears to be the same generic procedure, you MUST pick exactly ONE of them - the one whose content most completely and specifically answers the question - and answer using ONLY that source's steps, in full and in order. Cite exactly that one document. Do not add a step, term, or number from a second source into this answer, even if it seems to fit. The only exception is a question that is explicitly asking you to compare or combine distinct sources (e.g. several diagrams that each show a different component of the same panel) - in that case alone, citing multiple sources is correct.

Write your complete answer FIRST. Then, as the VERY LAST line of your response, write exactly which source(s) you used, in this exact format:
USED SOURCES: 1, 3

If the answer isn't in the context, write your explanation first (in the answer language given below), then end with:
USED SOURCES: none

Only list source numbers you actually relied on.

Context:
"""


def _language_instruction(detected_lang):
    if detected_lang == "Japanese":
        return (
            "You MUST answer entirely in natural, fluent Japanese. "
            "Do NOT use any English words (such as \"unpacking\"), Chinese characters, or mixed-language terms. "
            "Do NOT invent katakana transliterations for a term you are unsure of "
            "(e.g. do not write things like \"ネイルリーダー\" or \"フィスス\") — if you don't know "
            "the correct Japanese technical term, describe it in plain Japanese instead. "
            "Some correct terms for this domain: 開梱/荷ほどき (unpacking), 釘抜き (nail puller), ワイヤーカッター (wire cutter), "
            "てこ/バール (pry bar), ヒューズ (fuse), ヒューズ保持金具 (fuse holder bracket), "
            "配送伝票 (delivery receipt), リレー (relay), コンベア (conveyor). "
            "Never leave raw English words like \"unpacking\" in the text — use 開梱 (unpacking) or 荷ほどき instead. "
            "Before finishing, check that every step or key point present in the source context is "
            "represented in your Japanese answer — do not silently drop steps or substitute unrelated "
            "content. Every sentence must be grammatically complete; do not leave a clause unfinished."
        )
    return "You MUST answer entirely in English. Do NOT use any Japanese or Chinese characters."


def build_prompt(query, context, detected_lang):
    return f"""{PROMPT_RULES}{context}

ANSWER LANGUAGE: {_language_instruction(detected_lang)}

Question: {query}

Answer:"""


def call_llm(prompt, max_tokens=None):
    """
    Sends one prompt to Ollama and returns (answer_text, ollama_stats_dict).
    Raises requests.exceptions.RequestException (ConnectionError, Timeout, etc.)
    on failure - callers (e.g. run_tests.py) are responsible for deciding
    whether to retry. Failures are logged here first, with context, so they're
    never silently lost even if a caller has no logging of its own.
    """
    if max_tokens is None:
        max_tokens = LLM_MAX_TOKENS

    options = {
        "temperature": 0,
        "num_ctx": LLM_NUM_CTX,
        "num_predict": max_tokens,
    }
    if LLM_NUM_THREAD:
        options["num_thread"] = int(LLM_NUM_THREAD)

    try:
        response = _http.post(f"{OLLAMA_URL}/api/generate", json={
            "model": LLM_MODEL,
            "prompt": prompt,
            "stream": False,
            "keep_alive": LLM_KEEP_ALIVE,
            "options": options
        }, timeout=LLM_TIMEOUT)
        response.raise_for_status()
    except req_lib.exceptions.Timeout:
        logger.error("Ollama call timed out after %ds (model=%s, url=%s)", LLM_TIMEOUT, LLM_MODEL, OLLAMA_URL)
        raise
    except req_lib.exceptions.ConnectionError as e:
        logger.error("Could not connect to Ollama at %s: %s", OLLAMA_URL, e)
        raise
    except req_lib.exceptions.HTTPError as e:
        logger.error("Ollama returned an error status (model=%s): %s", LLM_MODEL, e)
        raise
    except req_lib.exceptions.RequestException as e:
        logger.error("Unexpected error calling Ollama (model=%s, url=%s): %s", LLM_MODEL, OLLAMA_URL, e)
        raise

    data = response.json()

    # Ollama reports its durations in nanoseconds
    ns = 1e9
    stats = {
        "load_s": data.get("load_duration", 0) / ns,
        "prompt_tokens": data.get("prompt_eval_count", 0),
        "prompt_s": data.get("prompt_eval_duration", 0) / ns,
        "output_tokens": data.get("eval_count", 0),
        "output_s": data.get("eval_duration", 0) / ns,
    }
    return data.get("response", ""), stats


def warm_up():
    """
    Loads the LLM into memory and pre-caches the fixed instruction prefix,
    so the user's FIRST question is as fast as the rest. Call once at
    application startup, after retrieval.init() (chat.py does this).
    """
    t0 = time.perf_counter()
    call_llm(build_prompt("warm up", "", "English"), max_tokens=1)
    return time.perf_counter() - t0