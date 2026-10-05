from search import collection, generate_answer

def verify_against_source(question, source_file, pages=None):
  
    print("=" * 70)
    print(f"QUESTION: {question}")
    print("=" * 70)

    result = generate_answer(question)
    print(f"\nSYSTEM'S ANSWER:\n{result['answer']}")
    print(f"\nSources cited: {result['sources']}")

    print(f"\n{'-'*70}")
    print(f"RAW SOURCE TEXT from {source_file}" + (f" (pages {pages})" if pages else "") + ":")
    print(f"{'-'*70}")

    all_data = collection.get()
    for i, meta in enumerate(all_data['metadatas']):
        if meta['source_file'] == source_file:
            if pages is None or meta.get('page_number') in pages:
                print(f"\n[Page/Location: {meta.get('page_number')}]")
                print(all_data['documents'][i])

    print("\n" + "=" * 70)
    print("MANUAL CHECK: Does the system's answer accurately reflect the raw text above?")
    print("=" * 70)


if __name__ == "__main__":
    # Test 13 - safety claim
    verify_against_source(
        "What makes the I-LINE Power Panelboard design safe according to the manual?",
        "i-line.pdf",
        pages=[5, 7]
    )