import os
import requests as req_lib
import search

print("=" * 60)
print("Factory Knowledge Assistant — Phase 1/2 Q&A")
print("Loading models and connecting to the database...")
warm_s = search.init()
print(f"Ready. (startup took {warm_s:.1f}s)")
print("Type your question and press Enter.")
print("Type 'exit' or 'quit' to stop.")
print("=" * 60)

while True:
    query = input("\nYour question: ").strip()

    if query.lower() in ("exit", "quit"):
        print("Goodbye!")
        break

    if not query:
        continue

    print("Searching and generating answer...")
    try:
        result = search.generate_answer(query)
    except req_lib.exceptions.Timeout:
        print("\nThe model took too long to respond and timed out. "
              "This can happen if Ollama is under heavy load or the model needs to reload. "
              "Try asking again — if it keeps happening, check that Ollama is running normally.")
        continue
    except req_lib.exceptions.ConnectionError:
        print("\nCould not reach Ollama. Make sure 'ollama serve' is running, then try again.")
        continue
    except req_lib.exceptions.RequestException as e:
        print(f"\nThe model call failed: {e}")
        continue

    print(f"\nAnswer: {result['answer']}")
    print(f"Sources: {', '.join(result['sources'])}")
    print(f"({search.format_timings(result['timings'])})")

    # "Show the picture next to the answer" - since a terminal can't
    # display images inline, open the actual supporting image file(s)
    # in the default viewer so they appear alongside this text answer.
    for img in result.get("images", []):
        img_path = img["path"]
        if os.path.exists(img_path):
            try:
                os.startfile(img_path)  # Windows: opens in default image viewer
            except Exception as e:
                print(f"(Could not open image {img_path}: {e})")
        else:
            print(f"(Referenced image file not found: {img_path})")