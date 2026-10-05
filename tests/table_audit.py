from readers import read_docx

def is_suspicious_header(header_row):
    """
    Flags a header row as suspicious if it looks like data or a merged/repeated title,
    rather than real column labels.
    """
    if not header_row:
        return True, "empty header"

    # check 1: repeated identical values (merged cell artifact)
    non_empty = [c for c in header_row if c]
    if non_empty and len(set(non_empty)) == 1 and len(non_empty) > 1:
        return True, "all cells identical (likely merged title row)"

    # check 2: header looks numeric (likely actual data, not labels)
    numeric_like = sum(1 for c in header_row if c and any(ch.isdigit() for ch in c))
    if numeric_like >= len(header_row) / 2:
        return True, "mostly numeric (likely data row, not header)"

    # check 3: too many empty cells
    empty_count = sum(1 for c in header_row if not c or not c.strip())
    if empty_count >= len(header_row) / 2:
        return True, "mostly empty cells"

    return False, "looks OK"


def audit_tables(filepath):
    result = read_docx(filepath)
    clean = []
    suspicious = []

    for idx, table in enumerate(result['tables']):
        rows = table['rows']
        if not rows:
            suspicious.append((idx, [], "no rows at all"))
            continue

        header = rows[0]
        flagged, reason = is_suspicious_header(header)
        if flagged:
            suspicious.append((idx, header, reason))
        else:
            clean.append((idx, header))

    return clean, suspicious


if __name__ == "__main__":
    word_file = r"D:\FactoryKA\documents\6.docx"  # update path
    clean, suspicious = audit_tables(word_file)

    print(f"Total tables: {len(clean) + len(suspicious)}")
    print(f"Clean: {len(clean)}")
    print(f"Suspicious: {len(suspicious)}")

    print("\n=== CLEAN TABLES (usable as-is) ===")
    for idx, header in clean:
        print(f"  Table {idx}: {header}")

    print("\n=== SUSPICIOUS TABLES (need review) ===")
    for idx, header, reason in suspicious:
        print(f"  Table {idx}: [{reason}] {header}")