"""
answer_formatter.py

Everything related to TURNING raw retrieved chunks + a raw LLM response
INTO the final answer dict: language detection, conflicting-value
detection, parsing the "USED SOURCES:" line, stripping leaked source
mentions, and building picture references/pointers. Knows nothing about
ChromaDB or Ollama directly - it only works with the docs/metas/raw text
it's given.
"""

import os
import re

import config
from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0


_KANA_RE = re.compile(r"[\u3040-\u30ff]")
_CJK_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


def detect_language(text):
    # hiragana/katakana only occur in Japanese, so one of them settles it (langdetect can
    # misjudge short mixed text such as "E-15\u3068\u306f\uff1f")
    if _KANA_RE.search(text or ""):
        return "Japanese"
    try:
        lang = detect(text)
        return "Japanese" if lang == "ja" else "English"
    except Exception:
        return "English"


def strip_source_mentions(text):
    return re.sub(r"\bSOURCE\s*\d+\b", "the source material", text, flags=re.IGNORECASE)


# --- "Which fault code?" clarification (no model call needed) ---------------

# a specific code such as E-12, E01, OH1, F-300 (letters + digits)
_CODE_TOKEN_RE = re.compile(r"[A-Za-z]{1,4}\s?-?\s?\d{1,4}")
# "the fault code" / "this error code" (singular, pointing at one unnamed code)
_UNNAMED_CODE_EN = re.compile(r"\b(?:the|this|that|my|a)\s+(?:fault|error|alarm)\s+code\b(?!s)", re.IGNORECASE)
# Japanese: "\u30d5\u30a9\u30eb\u30c8\u30b3\u30fc\u30c9\u306e..." (fault code's ...), same for error / alarm code or number
_UNNAMED_CODE_JA = re.compile(r"(?:\u30d5\u30a9\u30eb\u30c8|\u30a8\u30e9\u30fc|\u30a2\u30e9\u30fc\u30e0|\u8b66\u5831)(?:\u30b3\u30fc\u30c9|\u756a\u53f7)\u306e")


def needs_code_clarification(query):
    """
    True when the question is about 'the fault code' (one unnamed code) but gives no code
    at all - e.g. "What is the severity level of the fault code?". These questions cannot
    be answered, so we ask which code is meant instead of letting the model list examples.
    Questions about several codes ("Which fault codes are Critical?") are NOT matched.
    """
    if _CODE_TOKEN_RE.search(query):
        return False
    return bool(_UNNAMED_CODE_EN.search(query) or _UNNAMED_CODE_JA.search(query))


def build_code_clarification_answer(lang):
    if lang == "Japanese":
        return ("\u3069\u306e\u30d5\u30a9\u30eb\u30c8\u30b3\u30fc\u30c9\u306b\u3064\u3044\u3066\u304a\u5c0b\u306d\u3067\u3059\u304b\uff1f"
                "\u30b3\u30fc\u30c9\uff08\u4f8b\uff1aE-12\uff09\u3092\u6559\u3048\u3066\u3044\u305f\u3060\u3051\u308c\u3070\u3001"
                "\u610f\u5473\u30fb\u539f\u56e0\u30fb\u91cd\u5927\u5ea6\u30fb\u5bfe\u51e6\u65b9\u6cd5\u3092\u8abf\u3079\u307e\u3059\u3002"
                "\u3069\u306e\u30b3\u30fc\u30c9\u3067\u3059\u304b\uff1f")
    return ("The question doesn't say which fault code it means. "
            "Please give me the code (for example E-12) and I will look up its meaning, cause, severity and action. "
            "Which fault code do you mean?")


# --- Severity questions answered straight from the fault table ----------------
# The 7B model often gets "which codes are Critical?" / "what is the severity of E-12?" wrong
# (it drops or adds a code, or swaps a level). The answer is a fixed fact in the table, so it
# is read from the indexed table rows by code instead of being left to the model.

_SEV_LEVEL_RE = re.compile(r"(?<![A-Za-z])(critical|warning|info)(?![A-Za-z])", re.IGNORECASE)
_SEV_WORD_RE = re.compile(r"severity|severe|\u91cd\u5927\u5ea6|\u91cd\u8981\u5ea6", re.IGNORECASE)      # 重大度 / 重要度
_LIST_WORD_RE = re.compile(r"(?<![A-Za-z])(which|list|all)(?![A-Za-z])|\u3069\u308c|\u4e00\u89a7|\u3059\u3079\u3066", re.IGNORECASE)  # どれ / 一覧 / すべて
_CODES_WORD_RE = re.compile(r"(?:fault|error|alarm)\s+codes?|\u30d5\u30a9\u30eb\u30c8\u30b3\u30fc\u30c9|\u30a8\u30e9\u30fc\u30b3\u30fc\u30c9", re.IGNORECASE)
_COMPARE_RE = re.compile(r"(?<![A-Za-z])(more|less|than|compare|versus|vs|difference)(?![A-Za-z])|\u3088\u308a|\u6bd4\u8f03", re.IGNORECASE)  # より / 比較
_SEV_CODE_RE = re.compile(r"(?<![A-Za-z0-9])([A-Za-z]{1,3})-(\d{1,3})(?![A-Za-z0-9])")
_SEV_ROW_RE = re.compile(r"^\s*([A-Za-z]{1,3}-\d{1,3})\s*\|.*\|\s*(Critical|Warning|Info)\s*$")


def _code_sort_key(code):
    prefix, num = code.split("-")
    return (prefix, int(num))


def parse_severity_question(query):
    """
    Returns ("list", "Critical") for "Which fault codes are classified as Critical?",
    ("single", "E-12") for "What is the severity level of fault code E-12?", else None.
    Comparisons ("Is E-17 more severe than E-12?") are not handled here.
    """
    codes = {f"{a.upper()}-{int(n):02d}" for a, n in _SEV_CODE_RE.findall(query)}
    level = _SEV_LEVEL_RE.search(query)
    if not codes:
        if level and _LIST_WORD_RE.search(query) and _CODES_WORD_RE.search(query):
            return ("list", level.group(1).capitalize())
        return None
    if len(codes) == 1 and _SEV_WORD_RE.search(query) and not _COMPARE_RE.search(query):
        return ("single", next(iter(codes)))
    return None


def build_severity_index(docs, source_labels):
    """
    Reads every 'E-12 | ... | Warning' table row out of the given chunk texts.
    Returns (index, sources): index = {code: level}, sources = {code: [source labels]}.
    Returns None when two tables disagree about a code, so the model/clarification flow handles it.
    """
    index, sources = {}, {}
    for doc, label in zip(docs, source_labels):
        for line in doc.splitlines():
            m = _SEV_ROW_RE.match(line)
            if not m:
                continue
            code, level = m.group(1).upper(), m.group(2)
            if index.setdefault(code, level) != level:
                return None
            if label not in sources.setdefault(code, []):
                sources[code].append(label)
    return (index, sources) if index else None


def answer_severity(parsed, index, sources, lang):
    """Builds (answer_text, source_labels) for a parsed severity question, or None if the table has no answer."""
    kind, arg = parsed
    if kind == "single":
        level = index.get(arg)
        if not level:
            return None
        if lang == "Japanese":
            text = f"\u30d5\u30a9\u30eb\u30c8\u30b3\u30fc\u30c9{arg}\u306e\u91cd\u5927\u5ea6\u30ec\u30d9\u30eb\u306f{level}\u3067\u3059\u3002"
        else:
            text = f"The severity level of fault code {arg} is {level}."
        return text, sources.get(arg, [])[:3]
    codes = sorted((c for c, lv in index.items() if lv == arg), key=_code_sort_key)
    if not codes:
        return None
    labels = []
    for c in codes:
        for lab in sources.get(c, []):
            if lab not in labels:
                labels.append(lab)
    if lang == "Japanese":
        joined = "\u3001".join(codes)
        text = f"\u91cd\u5927\u5ea6\u304c{arg}\u306b\u5206\u985e\u3055\u308c\u308b\u30d5\u30a9\u30eb\u30c8\u30b3\u30fc\u30c9\u306f\u6b21\u306e\u3068\u304a\u308a\u3067\u3059\uff1a{joined}\u3002"
    else:
        text = f"The fault codes classified as {arg} severity are {', '.join(codes)}."
    return text, labels[:3]


# --- Answer language must match the question language -------------------------
# Japanese question -> Japanese answer (no English sentences, no Chinese);
# English question -> English answer (no Japanese / Chinese characters).

def looks_japanese(text):
    """True when the text contains real Japanese (at least two hiragana/katakana)."""
    return len(_KANA_RE.findall(text or "")) >= 2


def language_problems(lang, text):
    """0 when the answer is in the right language; larger numbers mean 'more wrong'."""
    if lang == "Japanese":
        return count_chinese_chars(text) + (0 if looks_japanese(text) else 50)
    return len(_CJK_RE.findall(text or ""))


def standard_decline(lang):
    """Fixed 'not found' sentence, used when the model declined in the wrong language."""
    if lang == "Japanese":
        return "\u5341\u5206\u306a\u60c5\u5831\u304c\u3042\u308a\u307e\u305b\u3093\u3002\u3053\u306e\u8cea\u554f\u306b\u8a72\u5f53\u3059\u308b\u5185\u5bb9\u306f\u3001\u6587\u66f8\u306e\u4e2d\u306b\u898b\u3064\u304b\u308a\u307e\u305b\u3093\u3002"
    return "I don't have enough information to answer this."


# --- Chinese text inside a Japanese answer ------------------------------------
# The 7B model sometimes slips into Chinese mid-answer ("推荐操作是检查..."). These are
# characters that exist ONLY in simplified Chinese (Japanese writes them differently),
# so finding one in a Japanese answer means it has switched language.
_CHINESE_ONLY = set("\u8fd9\u4eec\u4e3a\u8bf4\u68c0\u786e\u8350\u8bae\u9879\u5e94\u8be5\u5f00\u5173\u7535\u673a\u8fc7\u5b9e\u73b0\u65f6\u5bf9\u4e48\u4e2a\u8fd8\u8fdb\u52a8\u6837\u79cd\u6001\u4ea7\u7c7b\u522b\u51b3\u8bc1\u52a1\u95ee\u9898")


def count_chinese_chars(text):
    return sum(1 for ch in (text or "") if ch in _CHINESE_ONLY)


def has_chinese_text(text):
    return count_chinese_chars(text) >= 1


# Common Chinese words the model slips in, with their Japanese equivalents.
_CHINESE_TO_JAPANESE = {
    "\u63a8\u8350": "\u63a8\u5968",      # 推荐 -> 推奨
    "\u68c0\u67e5": "\u78ba\u8a8d",      # 检查 -> 確認
    "\u786e\u8ba4": "\u78ba\u8a8d",      # 确认 -> 確認
    "\u786e\u4fdd": "\u78ba\u4fdd",      # 确保 -> 確保
}


def cut_at_chinese(text):
    """
    Last resort for a Japanese answer that still contains Chinese: swap known Chinese words
    for their Japanese equivalents; if Chinese characters remain, drop the sentence that
    contains the first one (and what follows).
    """
    for zh, ja in _CHINESE_TO_JAPANESE.items():
        text = text.replace(zh, ja)
    for i, ch in enumerate(text):
        if ch in _CHINESE_ONLY:
            head = text[:i]
            cut = max(head.rfind("\u3002"), head.rfind("\n"))
            if cut >= 20:
                return head[:cut + 1].rstrip()
            return text
    return text


# --- Conflicting-value detection (for the "ask for clarification" flow) --

_QUANTITY_KEYWORDS = ["weight", "price", "cost", "dimension", "size", "rating", "capacity"]

_UNIT_PATTERN = re.compile(
    r'(\d+\.?\d*)\s*(lbs?|pounds?|kg|dollars?|\$|amps?|volts?|hp|inches?|mm)',
    re.IGNORECASE
)


_KEYWORD_UNITS = {
    "price": {"$", "dollar", "dollars"}, "cost": {"$", "dollar", "dollars"},
    "weight": {"lb", "lbs", "pound", "pounds", "kg"},
    "rating": {"amp", "amps", "volt", "volts", "hp"}, "capacity": {"amp", "amps", "hp", "kg", "lb", "lbs"},
    "dimension": {"inch", "inches", "mm"}, "size": {"inch", "inches", "mm"},
}
_QUERY_QUANTITY = re.compile(r"\d+\.?\d*\s*(hp|kw|volts?|v|amps?|a|lbs?|kg|mm|inch(?:es)?|pole)\b", re.IGNORECASE)


def detect_conflicting_values(query, docs):
    """
    Code-level (non-LLM) check: does the query ask about a quantity, and do
    the retrieved chunks contain more than two different values, IN THE UNIT
    FAMILY THAT QUANTITY USES (price -> $, weight -> lb/kg, ...), for it?
    Only then force a clarification. Two guards avoid false triggers:
      - values in other units (a 640 $ price near a 200 amp rating) are ignored,
        so unrelated questions ("Tesla price") fall through to the normal
        not-found answer instead of a bogus "which product?" prompt;
      - if the question already states a quantity ("35 HP"), it is not
        underspecified, so the model answers instead of asking.
    """
    query_lower = query.lower()
    kws = [kw for kw in _QUANTITY_KEYWORDS if kw in query_lower]
    if not kws:
        return None
    if _QUERY_QUANTITY.search(query):
        return None

    wanted = set()
    for kw in kws:
        wanted |= _KEYWORD_UNITS.get(kw, set())

    values_with_units = set()
    for doc in docs:
        for value, unit in _UNIT_PATTERN.findall(doc):
            if not wanted or unit.lower().rstrip(".") in wanted:
                values_with_units.add(f"{value} {unit.lower()}")

    if len(values_with_units) > 2:
        return values_with_units
    return None


def build_conflicting_value_answer(conflicting, detected_lang):
    values_str = ", ".join(sorted(conflicting))
    if detected_lang == "Japanese":
        return (
            f"この質問に該当する複数の異なる値が見つかりました（{values_str}）。"
            f"おそらく複数の製品または種類にまたがる情報です。"
            f"どの製品、種類、または条件についてお知りになりたいか教えていただけますか？"
        )
    return (
        f"I found several different values for this ({values_str}) across what appear to be "
        f"different products, models, or categories in the source material. "
        f"Could you specify which product, type, or category you're asking about?"
    )


# --- Point-wise formatting safety net ---------------------------------------
_LIST_LINE = re.compile(r"^\s*(?:[-*\u2022\u30fb]\s+|\d+[\.)]\s+)")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9(\"'])|(?<=\u3002)\s*|\s+(?=Note:)")


_DECLINE_START = re.compile(
    r"^\s*[-*\u2022]?\s*(i don't have enough information|i do not have enough information|"
    r"the answer isn't in|the answer is not in|not found in the documents|"
    r"\u60c5\u5831\u304c\u4e0d\u8db3|\u5341\u5206\u306a\u60c5\u5831\u304c\u3042\u308a\u307e\u305b\u3093|\u8a72\u5f53\u3059\u308b\u60c5\u5831\u304c)",
    re.IGNORECASE)


# Answers shorter than this (or with fewer than 3 sentences/points) stay plain text.
LONG_ANSWER_CHARS = 180


def format_as_points(text):
    """
    Layout safety net, so the look of an answer never depends on the 7B model:
      - "not found" answers and clarification questions stay plain sentences;
      - SHORT answers (under ~180 characters, or fewer than 3 sentences) are plain text;
        a tiny list of 1-2 bullet lines is folded back into plain sentences;
      - LONG answers (3+ sentences and ~180+ characters) that came back as one paragraph
        are split: first sentence as the lead line, the rest as '- ' points;
      - lists the model already wrote (3+ points, numbered steps, 'Note:' lines) are kept.
    """
    if text:
        # drop empty bullet lines such as a lone "-" the model sometimes leaves behind
        text = "\n".join(l for l in text.splitlines() if l.strip() not in ("-", "*", "\u2022", "\u30fb")).strip()
    if not text:
        return text
    if _DECLINE_START.match(text):
        # a "not found" answer is plain sentences, not a list - undo any bullets
        return " ".join(re.sub(r"^\s*[-*\u2022]\s*", "", l).strip() for l in text.splitlines() if l.strip())
    if text.strip().endswith(("?", "\uff1f")):          # clarification question
        return text

    lines = [l for l in text.splitlines() if l.strip()]
    has_list = any(_LIST_LINE.match(l) for l in lines)

    if has_list:
        has_steps = any(re.match(r"^\s*\d+[\.)]\s+", l) for l in lines)
        has_note = any(l.strip().startswith("Note:") for l in lines)
        if not has_steps and not has_note and len(lines) <= 2 and len(text) < LONG_ANSWER_CHARS:
            # tiny "list" -> plain sentences
            return " ".join(re.sub(r"^\s*[-*\u2022\u30fb]\s*", "", l).strip() for l in lines)
        return text

    # no list lines: plain paragraph(s)
    sentences = []
    for para in lines:
        sentences.extend(x.strip() for x in _SENT_SPLIT.split(para) if x and x.strip())
    if len(sentences) < 3 or len(text) < LONG_ANSWER_CHARS:
        return text                                       # short answer stays plain
    out = [sentences[0]]                                  # lead line
    out.extend("- " + x for x in sentences[1:])
    return "\n".join(out)


# --- Parsing the raw LLM response -----------------------------------------

def parse_used_sources(raw_answer):
    """
    Finds the (last) "USED SOURCES: ..." line in the raw model output,
    returns (used_ids, answer_text_with_that_line_removed).
    """
    used_ids = []
    matches = list(re.finditer(r"USED SOURCES:\s*([^\n]+)", raw_answer, re.IGNORECASE))
    if matches:
        last_match = matches[-1]
        ids_text = last_match.group(1)
        if "none" not in ids_text.lower():
            used_ids = [int(x.strip()) for x in re.findall(r"\d+", ids_text)]
        answer_clean = re.sub(r"USED SOURCES:\s*[^\n]+", "", raw_answer, flags=re.IGNORECASE).strip()
    else:
        answer_clean = raw_answer.strip()

    if not answer_clean:
        answer_clean = "I don't have enough information to answer this."

    return used_ids, format_as_points(strip_source_mentions(answer_clean))


# --- Picture references / pointers -----------------------------------------

def format_picture_pointers(picture_sources, lang):
    if not picture_sources:
        return ""

    file_pages = {}
    for source_file, page_num in picture_sources:
        page_str = str(page_num)
        if source_file not in file_pages:
            file_pages[source_file] = []
        if page_str not in file_pages[source_file]:
            file_pages[source_file].append(page_str)

    if lang == "Japanese":
        items = []
        for src, pages in file_pages.items():
            pgs_str = ", ".join(pages)
            items.append(f"{src} ({pgs_str}ページ)")
        if len(file_pages) == 1:
            src, pages = next(iter(file_pages.items()))
            pgs_str = ", ".join(pages)
            return f"{src}の{pgs_str}ページの画像もご確認ください。"
        else:
            return f"{'、'.join(items)}の画像もご確認ください。"
    else:
        items = []
        for src, pages in file_pages.items():
            pg_label = "page" if len(pages) == 1 else "pages"
            pgs_str = ", ".join(pages)
            items.append(f"{src} ({pg_label} {pgs_str})")

        if len(file_pages) == 1:
            src, pages = next(iter(file_pages.items()))
            pg_label = "page" if len(pages) == 1 else "pages"
            pgs_str = ", ".join(pages)
            return f"See the pictures on {pg_label} {pgs_str} of {src}." if len(pages) > 1 else f"See the picture on page {pgs_str} of {src}."
        else:
            files_formatted = ", ".join(items[:-1]) + f" and {items[-1]}" if len(items) > 1 else items[0]
            return f"See pictures in {files_formatted}."


def resolve_image_path(stored_path):
    """
    The image path saved in ChromaDB at ingestion time is an old absolute path
    (e.g. D:\\FactoryKA\\extracted_images\\x.png). After the folders were
    reorganised / paths moved into config, that exact path no longer exists, so
    pictures silently stopped showing. Only the FILE NAME is reliable, so look
    for it in the folders listed in config.IMAGE_DIRS.
    Returns a path that exists on disk, or None.
    """
    if not stored_path:
        return None
    if os.path.exists(stored_path):
        return stored_path
    name = os.path.basename(stored_path.replace("\\", "/"))
    for folder in config.IMAGE_DIRS:
        candidate = os.path.join(folder, name)
        if os.path.exists(candidate):
            return candidate
    return None


# Phrases that mean "the answer is not in the documents" - no picture is added to such answers.
_DECLINE_ANYWHERE = (
    "don't have enough information", "do not have enough information",
    "not found in the documents", "isn't in the", "is not in the",
    "\u898b\u3064\u3051",            # 見つけ(られません / ることができません)
    "\u898b\u3064\u304b",            # 見つか(りません)
    "\u898b\u5f53\u305f\u308a",      # 見当たり(ません)
    "\u60c5\u5831\u304c\u4e0d\u8db3",  # 情報が不足
    "\u78ba\u8a8d\u3067\u304d\u307e\u305b\u3093",  # 確認できません
)

MAX_FALLBACK_PICTURES = 2


def is_decline(text):
    """True when the answer says the information is not in the documents."""
    low = (text or "").lower()
    return any(p in low for p in _DECLINE_ANYWHERE)


def collect_picture_data(used_ids, metas, same_page_fallback=False):
    """
    Given the source ids the LLM said it used and the full metadata list,
    returns (picture_sources, attached_images):
      - picture_sources: list of (source_file, page_number) tuples, for the
        "see the picture on page X" pointer text.
      - attached_images: list of {"path", "source_file", "page_number"} dicts
        for images that actually exist on disk.

    same_page_fallback: for a picture question, when the model cited TEXT chunks but no
    picture chunk, also attach the picture(s) that sit on the same page as a cited text
    chunk (the picture is then from a page the model already relied on).
    """
    picture_sources = []
    attached_images = []
    seen_pointer_keys = set()

    def _add_picture(meta):
        key = (meta.get("source_file"), meta.get("page_number"))
        if key not in seen_pointer_keys:
            seen_pointer_keys.add(key)
            picture_sources.append(key)

        img_path = resolve_image_path(meta.get("image_path"))
        if img_path:
            if not any(img["path"] == img_path for img in attached_images):
                attached_images.append({
                    "path": img_path,
                    "source_file": meta.get("source_file"),
                    "page_number": meta.get("page_number")
                })

    for i in used_ids:
        if not (0 < i <= len(metas)):
            continue
        meta = metas[i - 1]
        if meta.get("chunk_type") != "picture_caption":
            continue
        _add_picture(meta)

    if same_page_fallback and not picture_sources:
        cited_pages = []
        for i in used_ids:
            if 0 < i <= len(metas):
                key = (metas[i - 1].get("source_file"), metas[i - 1].get("page_number"))
                if key not in cited_pages:
                    cited_pages.append(key)
        added = 0
        for key in cited_pages:
            for meta in metas:
                if added >= MAX_FALLBACK_PICTURES:
                    break
                if (meta.get("chunk_type") == "picture_caption"
                        and (meta.get("source_file"), meta.get("page_number")) == key):
                    _add_picture(meta)
                    added += 1

    return picture_sources, attached_images


def append_image_markdown(answer_text, attached_images):
    """Appends '![...](file:///...)' markdown for each attached image."""
    if not attached_images:
        return answer_text
    md_images = []
    for img in attached_images:
        norm_path = img["path"].replace("\\", "/")
        md_images.append(f"![Figure from {img['source_file']} page {img['page_number']}](file:///{norm_path})")
    return answer_text + "\n\n" + "\n".join(md_images)