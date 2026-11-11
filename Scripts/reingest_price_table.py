"""
Re-ingests ONE price-table page of a PDF as "one row per chunk", with the column
names written into every row, so the model never has to guess which number
belongs to which column.

Default target: 7.pdf page 20 (Controller Modifications, Form Y35), columns
7-1/2 HP | 15 HP | 35 HP | 55 HP.

What it adds to the database (the page's existing text chunk is NOT touched):
  * one chunk per table row:
      "Modification 3: Additional Acceleration Point. Price by Max. HP rating (single motor):
       7-1/2 HP = $676; 15 HP = $712; 35 HP = $776; 55 HP = $912."
  * one summary chunk with every row on one line, plus the list of rows whose price is the
    same for all columns (answers "which modification has the same price for all ratings?").

Run from D:\\FactoryKA\\Scripts (needs the venv, like your other re-ingest scripts):
    python reingest_price_table.py --dry-run     (shows the chunks, changes nothing)
    python reingest_price_table.py               (writes them to the database)
It is safe to run twice: chunk ids are fixed, so the second run just replaces the first.
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))

import pymupdf

COLUMNS = ["7-1/2 HP", "15 HP", "35 HP", "55 HP"]
TITLE = "Controller Modifications (Form Y35) price list"
UNIT_NOTE = "Price by Max. HP rating (single motor)"
ROW_TOL = 4.0                      # words whose vertical centres differ by less than this are one line
_PRICE_RE = re.compile(r"^\$?\s*\d[\d,]*\.?$")


def _price_value(token):
    digits = re.sub(r"[^\d]", "", token)
    return int(digits) if digits else None


LABEL_MAX_X = 90.0      # modification numbers sit left of this
PRICE_MIN_X = 390.0     # price columns start right of this (points on the page)
ROW_GAP = 5.0           # price tokens closer than this vertically belong to one row
COL_GAP = 15.0          # price tokens closer than this horizontally belong to one column
MAX_DIST = 11.0         # a description/label word further than this from every row is ignored


def _clean_label(raw, prev_label):
    """OCR turns 5B into 58, 12B into 128, 25 into '2 5 t'. Fix the common cases."""
    label = re.sub(r"[\s*\u2020]+", "", raw)
    label = re.sub(r"t$", "", label)                       # the dagger footnote mark is read as "t"
    label = re.sub(r"^S([AB])$", r"5\1", label)
    if prev_label and re.fullmatch(r"\d+8", label) and prev_label.endswith("A") \
            and prev_label[:-1] == label[:-1]:
        label = label[:-1] + "B"                           # 58 -> 5B, 128 -> 12B
    return label


def parse_rows(page, n_cols):
    """Reads the table by position: price words -> rows (by height) and columns (by x);
    other words -> the nearest row (label zone on the left, description zone in the middle)."""
    words = [(w[0], (w[1] + w[3]) / 2, w[4]) for w in page.get_text("words")]
    prices = [(x, y, _price_value(t)) for x, y, t in words
              if x >= PRICE_MIN_X and _PRICE_RE.match(t) and t != "$" and _price_value(t) is not None]
    if not prices:
        return []
    # columns: cluster by x
    xs = sorted(p[0] for p in prices)
    centers, group = [], [xs[0]]
    for x in xs[1:]:
        if x - group[-1] > COL_GAP:
            centers.append(sum(group) / len(group)); group = [x]
        else:
            group.append(x)
    centers.append(sum(group) / len(group))
    if len(centers) != n_cols:
        raise RuntimeError("Expected {} price columns but found {} - check COLUMNS.".format(n_cols, len(centers)))
    # rows: cluster by y
    prices.sort(key=lambda p: p[1])
    row_groups, group = [], [prices[0]]
    for p in prices[1:]:
        if p[1] - group[-1][1] > ROW_GAP:
            row_groups.append(group); group = [p]
        else:
            group.append(p)
    row_groups.append(group)
    rows = []
    for g in row_groups:
        cells = [None] * n_cols
        for x, y, v in g:
            ci = min(range(n_cols), key=lambda i: abs(centers[i] - x))
            cells[ci] = v
        if None in cells:
            continue                                       # incomplete row: leave it to the page text chunk
        rows.append({"y": sum(p[1] for p in g) / len(g), "prices": cells, "label_w": [], "desc_w": []})
    if not rows:
        return []
    for x, y, t in words:
        if x >= PRICE_MIN_X:
            continue
        dist = [abs(r["y"] - y) for r in rows]
        best = min(range(len(rows)), key=lambda i: (dist[i], i))   # tie -> the earlier row
        if dist[best] > MAX_DIST:
            continue
        (rows[best]["label_w"] if x < LABEL_MAX_X else rows[best]["desc_w"]).append((y, x, t))
    out, prev_label = [], None
    for r in rows:
        label = _clean_label("".join(t for _, _, t in sorted(r["label_w"])), prev_label)
        desc = " ".join(t for _, _, t in sorted(r["desc_w"], key=lambda w: (round(w[0] / 3), w[1])))
        if not desc and out:
            desc = out[-1]["description"]                  # 5B / 12B / 12C share the row above
        out.append({"label": label, "description": desc.strip(), "prices": r["prices"]})
        prev_label = label
    return out


def money(v):
    return "${:,}".format(v)


def build_chunks(source, page_no, rows):
    chunks = []
    for r in rows:
        prices = "; ".join("{} = {}".format(c, money(p)) for c, p in zip(COLUMNS, r["prices"]))
        text = "{} ({} page {}). Modification {}: {}. {}: {}.".format(
            TITLE, source, page_no, r["label"], r["description"], UNIT_NOTE, prices)
        chunks.append(("{}_p{}_row_{}".format(source, page_no, r["label"]), text))
    same = ["Modification {} ({}, {})".format(r["label"], r["description"], money(r["prices"][0]))
            for r in rows if len(set(r["prices"])) == 1]
    lines = ["Modification {}: {} - {}".format(
        r["label"], r["description"],
        ", ".join("{} {}".format(c, money(p)) for c, p in zip(COLUMNS, r["prices"]))) for r in rows]
    summary = ("{} ({} page {}) - all rows. {}. Columns: {}.\n{}\n"
               "Modifications that cost the same for all {} HP ratings: {}.").format(
        TITLE, source, page_no, UNIT_NOTE, ", ".join(COLUMNS), "\n".join(lines),
        len(COLUMNS), "; ".join(same) if same else "none")
    chunks.append(("{}_p{}_rows_summary".format(source, page_no), summary))
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="7.pdf")
    ap.add_argument("--page", type=int, default=20)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--path", default=None, help="full path to the PDF (default: documents folder)")
    args = ap.parse_args()

    path = args.path
    if not path:
        import config
        path = os.path.join(config.DOCUMENTS_DIR, args.file)
    doc = pymupdf.open(path)
    page = doc[args.page - 1]
    rows = parse_rows(page, len(COLUMNS))
    if not rows:
        print("No price rows found on that page - nothing written.")
        return
    chunks = build_chunks(args.file, args.page, rows)
    for cid, text in chunks:
        print("--", cid, "\n", text, "\n")
    print("{} rows found, {} chunks.".format(len(rows), len(chunks)))
    if args.dry_run:
        print("Dry run: nothing written.")
        return
    import retrieval
    retrieval.init()
    for cid, text in chunks:
        retrieval.add_chunk(chunk_id=cid, text=text,
                            metadata={"source_file": args.file, "page_number": args.page,
                                      "chunk_type": "table_row"})
    print("Written to the database.")


if __name__ == "__main__":
    main()
