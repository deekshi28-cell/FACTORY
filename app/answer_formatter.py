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
from langdetect import detect, DetectorFactory

DetectorFactory.seed = 0


def detect_language(text):
    try:
        lang = detect(text)
        return "Japanese" if lang == "ja" else "English"
    except Exception:
        return "English"


def strip_source_mentions(text):
    return re.sub(r"\bSOURCE\s*\d+\b", "the source material", text, flags=re.IGNORECASE)


# --- Conflicting-value detection (for the "ask for clarification" flow) --

_QUANTITY_KEYWORDS = ["weight", "price", "cost", "dimension", "size", "rating", "capacity"]

_UNIT_PATTERN = re.compile(
    r'(\d+\.?\d*)\s*(lbs?|pounds?|kg|dollars?|\$|amps?|volts?|hp|inches?|mm)',
    re.IGNORECASE
)


def detect_conflicting_values(query, docs):
    """
    Code-level (non-LLM) check: does the query ask about a quantity, and do
    the retrieved chunks contain more than two different values with units
    for that kind of quantity? If so, we force a clarification response
    rather than relying on the LLM to notice on its own.
    """
    query_lower = query.lower()
    if not any(kw in query_lower for kw in _QUANTITY_KEYWORDS):
        return None

    values_with_units = set()
    for doc in docs:
        matches = _UNIT_PATTERN.findall(doc)
        for value, unit in matches:
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

    return used_ids, strip_source_mentions(answer_clean)


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


def collect_picture_data(used_ids, metas):
    """
    Given the source ids the LLM said it used and the full metadata list,
    returns (picture_sources, attached_images):
      - picture_sources: list of (source_file, page_number) tuples, for the
        "see the picture on page X" pointer text.
      - attached_images: list of {"path", "source_file", "page_number"} dicts
        for images that actually exist on disk.
    """
    picture_sources = []
    attached_images = []
    seen_pointer_keys = set()

    for i in used_ids:
        if not (0 < i <= len(metas)):
            continue
        meta = metas[i - 1]
        if meta.get("chunk_type") != "picture_caption":
            continue

        key = (meta.get("source_file"), meta.get("page_number"))
        if key not in seen_pointer_keys:
            seen_pointer_keys.add(key)
            picture_sources.append(key)

        img_path = meta.get("image_path")
        if img_path and os.path.exists(img_path):
            if not any(img["path"] == img_path for img in attached_images):
                attached_images.append({
                    "path": img_path,
                    "source_file": meta.get("source_file"),
                    "page_number": meta.get("page_number")
                })

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
