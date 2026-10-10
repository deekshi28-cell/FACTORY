import json
import time
import os
import sys
import re
import requests
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
import search
import config

RESULTS_PATH = config.TEST_RESULTS_PATH
QUESTIONS_PATH = config.TEST_QUESTIONS_PATH
RETRY_DELAY_SECONDS = config.TEST_RETRY_DELAY_SECONDS

_NO_SOURCE_VALUES = {"", "n/a", "na", "none", "not applicable", "n/a", "none."}

# How semantically close the actual answer needs to be to the expected
# answer to count as correct. 1.0 = identical meaning, 0.0 = unrelated.
# Chosen conservatively - re-tune after a real run if it's too strict/loose,
# by looking at the printed similarity scores against answers you judge
# correct/incorrect yourself.
ANSWER_MATCH_THRESHOLD = 0.72
# Lower floor for the "all key tokens present" rescue (cross-lingual answers
# such as a Japanese reply to an English expected answer often land 0.60-0.72).
KEY_TOKEN_RESCUE_MIN_SIM = 0.60

# "Not Found" questions expect the model to decline/say it doesn't know.
# expected_answer for these is usually a short template ("Correctly states
# information is not available"), while the model's real answer is a full
# sentence explaining *why* it can't answer - different wording/length, so
# embedding similarity comes out low even when the decline itself is
# correct. As a fallback (OR'd with the embedding check) for this category
# only, also accept the answer if it contains clear decline/refusal
# language. This does NOT apply to other categories - there, embedding
# similarity to expected_answer remains the only check.
DECLINE_PHRASES = [
    "not present in",
    "isn't in the",
    "is not in the",
    "isn't present",
    "not in the provided",
    "not in the context",
    "don't have enough",
    "does not contain",
    "do not contain",
    "not contain any information",
    "not contain information",
    "does not provide",
    "do not provide",
    "not provide specific",
    "not include",
    "not specify",
    "not available",
    "not found in",
    "no information",
    "not mentioned",
    "not specified",
    "not explicitly stated",
    "not stated",
    "don't have enough information",
    "do not have enough information",
    "cannot find",
    "could not find",
    "no specific source",
    "i don't have",
    "unable to find",
    "unrelated",
    "is unclear",
    "unclear without",
    # Japanese refusals (the model may reply in Japanese to a Japanese question)
    "含まれていません",
    "情報がありません",
    "情報は見つかりません",
    "見つかりません",
    "記載されていません",
    "提供されていません",
    "分かりません",
    "わかりません",
    "存在しません",
    "判明していません",
    "不明です",
    "確認できません",
    "見当たりません",
]

# Edge-case questions whose correct behaviour is to ASK for the missing detail
# (e.g. "What is the severity level of the fault code?" with no code given).
# Applied only when expected_answer itself describes a clarification request.
CLARIFY_PHRASES = [
    "please specify",
    "could you specify",
    "can you specify",
    "please provide",
    "which fault code",
    "specify which",
    "specify the fault code",
    "which code",
    "need more information",
    "need to know which",
    "指定してください",
    "教えてください",
    "どのフォルトコード",
    "どのコード",
]

# Severity words are the classic single-word contradiction the embedding check
# cannot see (Critical vs Warning scores ~0.92 similar). Each canonical word
# maps to the spellings accepted in the actual answer (English + Japanese).
SEVERITY_WORDS = {
    "critical": ["critical", "重大", "クリティカル", "致命"],
    "warning": ["warning", "警告", "ワーニング"],
    "info": ["info", "information", "情報", "インフォ"],
}

# Cap on expected_answer length for plain-number checking. Long prose answers
# contain incidental numbers the model may legitimately rephrase; short factual
# answers ("0-10 V dc", "3 years") must reproduce them.
NUMBER_CHECK_MAX_LEN = 80
# Same idea for identifiers (fault codes / catalog numbers). Higher cap so a
# list such as "E-01, E-02, ... E-18." is still checked in full.
IDENTIFIER_CHECK_MAX_LEN = 160


def check_source_match(expected_source, actual_sources):
    """
    Checks whether the system's actual sources correctly match what was expected.
    This checks CITATION correctness only - which document was cited - not
    whether the answer text itself is correct. See check_answer_match() for that.
    """
    if not expected_source:
        return any("no specific source" in s.lower() for s in actual_sources)

    expected_clean = str(expected_source).strip().lower().replace("\\\\", "/").replace("\\", "/")
    if expected_clean in _NO_SOURCE_VALUES:
        return any("no specific source" in s.lower() for s in actual_sources)

    expected_files = set(re.findall(r"[\w\-\.\s]+\.(?:pdf|docx|xlsx)", expected_clean))
    if not expected_files:
        tokens = re.split(r"[,/]", expected_clean)
        expected_files = {t.strip().split()[0] for t in tokens if t.strip()}

    actual_str = " ".join(actual_sources).lower()
    for ef in expected_files:
        if ef.strip().lower() in actual_str:
            return True
    return False


def check_answer_match(expected_answer, actual_answer, threshold=ANSWER_MATCH_THRESHOLD):
    """
    Checks whether the actual answer is semantically correct, by comparing
    it to expected_answer using the same BGE-M3 embedding model already used
    for retrieval - not just whether the right file got cited.

    Returns (is_match: bool, similarity: float). similarity is always
    returned (even on a fail) so it can be inspected/reviewed, not just a
    pass/fail flag with no way to see how close it was.
    """
    if not expected_answer or not actual_answer:
        return False, 0.0
    try:
        emb_expected = np.array(search.embed_text(expected_answer))

        def _sim(text):
            e = np.array(search.embed_text(text))
            return float(np.dot(emb_expected, e) / ((np.linalg.norm(emb_expected) * np.linalg.norm(e)) + 1e-8))

        similarity = _sim(actual_answer)
        # Detailed answers are longer than the short expected answer, which dilutes the
        # whole-answer embedding even when the answer is correct. For short expected
        # answers also compare against each 1-3 line window of the actual answer and keep
        # the best score. Key-token checks in score_answer still apply, so a window that
        # is merely similar-sounding but has a wrong code/number/severity still fails.
        if len(expected_answer) <= 250 and len(actual_answer) > len(expected_answer) * 1.5:
            lines = [l.strip() for l in re.split(r"[\n]+|(?<=[.!?。])\s+", actual_answer) if len(l.strip()) > 8]
            for w in (1, 2, 3):
                for i in range(0, max(1, len(lines) - w + 1)):
                    chunk = " ".join(lines[i:i + w])
                    if chunk and chunk != actual_answer:
                        similarity = max(similarity, _sim(chunk))
        return similarity >= threshold, round(similarity, 3)
    except Exception as e:
        print(f"  (warning: answer similarity check failed: {e})")
        return False, 0.0


def check_decline_phrase(actual_answer):
    """
    Fallback check used only for the "Not Found" category: does the actual
    answer contain clear decline/refusal language? Used to catch correct
    refusals that are worded very differently from the short expected_answer
    template, which the embedding check alone tends to under-score.
    """
    if not actual_answer:
        return False
    text = actual_answer.lower()
    return any(phrase in text for phrase in DECLINE_PHRASES)


def _norm(text):
    """Lowercase, unify dashes/whitespace, drop thousands separators."""
    t = str(text).lower()
    t = re.sub(r"[‐‑‒–—−ー]", "-", t)
    t = re.sub(r"(?<=\d),(?=\d{3}\b)", "", t)
    return re.sub(r"\s+", " ", t).strip()


def _code_in(code, text):
    """True if an ID such as 'e-12' / 'cle-201001' appears in text as a whole
    token. Tolerates 'E12', 'E 12' and 'E-12'."""
    m = re.match(r"([a-z]+)-?(\d+)$", code)
    if not m:
        return code in text
    pat = r"(?<![a-z0-9])" + m.group(1) + r"[-\s]?" + m.group(2) + r"(?!\d)"
    return re.search(pat, text) is not None


def _word_in(canon, text):
    return any(v in text for v in SEVERITY_WORDS[canon])


def missing_key_tokens(expected, actual):
    """
    Returns the list of 'must-have' tokens from expected_answer that are
    absent from the actual answer. An answer can be semantically close
    (high embedding similarity) yet differ in one decisive word or code;
    each token below is something a correct answer must reproduce:
      - identifiers: fault codes (E-12) and catalog numbers (CLE-201001)
      - severity words: Critical / Warning / Info
      - plain numbers, but only for short expected answers
    """
    exp, act = _norm(expected), _norm(actual)
    missing = []

    codes = re.findall(r"(?<![a-z0-9])[a-z]{1,5}-\d{2,}(?!\d)", exp)
    if len(exp) > IDENTIFIER_CHECK_MAX_LEN:
        codes = []  # long prose answers: the model may legitimately omit/rephrase IDs
    for c in dict.fromkeys(codes):
        if not _code_in(c, act):
            missing.append(c.upper())

    # Severity words: match on word boundaries in the expected text so that
    # e.g. "information" in prose is not mistaken for the severity level "Info".
    for canon in SEVERITY_WORDS:
        if canon == "info":
            wanted = re.search(r"\binfo\b", exp) is not None
        else:
            wanted = re.search(r"\b" + canon + r"\b", exp) is not None
        if wanted and not _word_in(canon, act):
            missing.append(canon.capitalize())

    if len(exp) <= NUMBER_CHECK_MAX_LEN:
        code_digits = {d for c in codes for d in re.findall(r"\d+", c)}
        for n in dict.fromkeys(re.findall(r"\d+(?:\.\d+)?", exp)):
            if n in code_digits:
                continue
            if not re.search(r"(?<![\d.])" + re.escape(n) + r"(?!\d)", act):
                missing.append(n)
    return missing


def expects_clarification(expected):
    e = (expected or "").lower()
    return ("specify" in e or "clarif" in e) and ("ask" in e or "request" in e)


def check_clarification(actual_answer):
    if not actual_answer:
        return False
    text = actual_answer.lower()
    return any(p in text for p in CLARIFY_PHRASES)


def score_answer(q, actual_answer):
    """
    Single entry point for answer scoring. Returns
    (is_match, similarity, method, missing_tokens, decline_phrase_match).

    Order of checks:
      1. Clarification edge cases: expected = 'ask the user to specify...' ->
         pass only if the model actually asks.
      2. Containment: the expected answer appears verbatim -> pass (fixes
         short expected values like 'CLE-201001' that embed poorly).
      3. Embedding similarity >= threshold AND no key token missing. A
         high-similarity answer with a wrong severity word / fault code /
         number FAILS (method 'key_token_mismatch').
      4. 'Not Found' only: decline-phrase fallback.
    """
    expected = q.get("expected_answer")
    sim = 0.0

    if expects_clarification(expected):
        ok = check_clarification(actual_answer)
        return ok, sim, "clarification" if ok else "no_clarification", [], False

    if expected and actual_answer and _norm(expected).rstrip(". ") in _norm(actual_answer):
        return True, 1.0, "contains", [], False

    emb_ok, sim = check_answer_match(expected, actual_answer)

    if q.get("category") == "Not Found":
        if emb_ok:
            return True, sim, "embedding", [], False
        if check_decline_phrase(actual_answer):
            return True, sim, "decline_phrase", [], True
        return False, sim, "embedding", [], False

    missing = missing_key_tokens(expected, actual_answer) if actual_answer else []
    if emb_ok and missing:
        return False, sim, "key_token_mismatch", missing, False
    if emb_ok:
        return True, sim, "embedding", [], False

    # Embedding below threshold: a cross-lingual or short answer may still be
    # right. Rescue only when there ARE key tokens and every one is present.
    if actual_answer and expected and not missing and _has_key_tokens(expected) and sim >= KEY_TOKEN_RESCUE_MIN_SIM:
        return True, sim, "key_tokens_rescue", [], False
    return False, sim, "embedding", missing, False


def _has_key_tokens(expected):
    exp = _norm(expected)
    if re.search(r"(?<![a-z0-9])[a-z]{1,5}-\d{2,}(?!\d)", exp):
        return True
    if any(re.search(r"\b" + w + r"\b", exp) for w in SEVERITY_WORDS):
        return True
    return len(exp) <= NUMBER_CHECK_MAX_LEN and re.search(r"\d", exp) is not None


def _save(results):
    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)


def _ask_with_retry(question_text):
    for attempt in (1, 2):
        t0 = time.time()
        try:
            result = search.generate_answer(question_text)
            return result, None, time.time() - t0
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            elapsed = time.time() - t0
            if attempt == 1:
                print(f"  (connection error after {elapsed:.1f}s: {e}. "
                      f"Waiting {RETRY_DELAY_SECONDS}s, then retrying once...)")
                time.sleep(RETRY_DELAY_SECONDS)
                continue
            return None, str(e), elapsed
    return None, "unknown error", 0.0


def run_automatic_tests():
    print("Loading models and connecting to the database...")
    warm_s = search.init()
    print(f"Ready. (startup took {warm_s:.1f}s)\n")

    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        questions = json.load(f)

    results = []
    passed = 0
    errored = 0

    for q in questions:
        print(f"[{q['id']}] {q['question'][:60]}")

        result, error, elapsed = _ask_with_retry(q["question"])

        if error is not None:
            print(f"  FAILED after retry ({elapsed:.1f}s): {error}\n")
            errored += 1
            results.append({
                "id": q["id"],
                "category": q.get("category"),
                "question": q["question"],
                "expected_source": q.get("expected_source"),
                "expected_answer": q.get("expected_answer"),
                "actual_answer": None,
                "actual_sources": [],
                "source_match": False,
                "answer_match": False,
                "answer_similarity": 0.0,
                "decline_phrase_match": False,
                "match_method": "error",
                "missing_tokens": [],
                "error": error,
                "elapsed_seconds": round(elapsed, 1),
            })
            _save(results)
            continue

        source_match = check_source_match(q.get("expected_source"), result["sources"])
        (answer_match, answer_similarity, match_method,
         missing_tokens, decline_phrase_match) = score_answer(q, result["answer"])

        print(f"  ({elapsed:.1f}s) Actual: {result['answer'][:150]}")
        print(f"  Sources: {result['sources']}")
        print(f"  Source match: {source_match} | Answer match: {answer_match} "
              f"(similarity: {answer_similarity}, method: {match_method}"
              f"{', missing: ' + ', '.join(missing_tokens) if missing_tokens else ''})\n")

        # The real pass/fail now requires the ANSWER to be correct, not just
        # the right file being cited. source_match is still recorded for
        # diagnostics (e.g. right answer but wrong/missing citation).
        if answer_match:
            passed += 1

        results.append({
            "id": q["id"],
            "category": q.get("category"),
            "question": q["question"],
            "expected_source": q.get("expected_source"),
            "expected_answer": q.get("expected_answer"),
            "actual_answer": result["answer"],
            "actual_sources": result["sources"],
            "source_match": source_match,
            "answer_match": answer_match,
            "answer_similarity": answer_similarity,
            "decline_phrase_match": decline_phrase_match,
            "match_method": match_method,
            "missing_tokens": missing_tokens,
            "error": None,
            "elapsed_seconds": round(elapsed, 1),
        })

        _save(results)

    total = len(questions)
    answered = total - errored
    avg_time = (sum(r["elapsed_seconds"] for r in results if r["error"] is None) / answered) if answered else 0

    print(f"\n{'='*50}")
    print(f"TOTAL: {total} | PASSED (answer correctness): {passed} ({passed/total*100:.1f}%) | ERRORED: {errored}")
    print(f"AVERAGE TIME (answered questions only): {avg_time:.1f}s")

    _save(results)
    return results


if __name__ == "__main__":
    run_automatic_tests()