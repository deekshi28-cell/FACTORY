"""
Nichi-In Factory Knowledge Assistant — Web UI backend.

Run with:  python app.py
Then open: http://localhost:5000
"""

import os
import re
import json
import logging
import requests as req_lib
from flask import Flask, request, jsonify, send_from_directory, render_template

import search
import retrieval
import config

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(config.INGEST_LOG_PATH, encoding="utf-8"),
    ]
)
logger = logging.getLogger("app")

MAX_IMAGES_PER_ANSWER = 1

_MD_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(file:///[^)]+\)")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(force=True)
    question = (data.get("question") or "").strip()
    if not question:
        return jsonify({"error": "No question provided"}), 400

    try:
        result = search.generate_answer(question)
    except req_lib.exceptions.Timeout:
        logger.error("Ollama call timed out answering question: %s", question)
        return jsonify({
            "error": "The model took too long to respond and timed out. "
                     "Please try again — if it keeps happening, check that Ollama is running normally."
        }), 504
    except req_lib.exceptions.ConnectionError:
        logger.error("Could not connect to Ollama while answering question: %s", question)
        return jsonify({
            "error": "Could not reach the AI model service. Please make sure Ollama is running, then try again."
        }), 502
    except req_lib.exceptions.RequestException as e:
        logger.error("Model call failed answering question '%s': %s", question, e)
        return jsonify({"error": "The model call failed. Please try again."}), 502

    image_urls = []
    for img in result.get("images", [])[:MAX_IMAGES_PER_ANSWER]:
        path = img.get("path")
        if path:
            filename = os.path.basename(path)
            image_urls.append(f"/api/image/{filename}")

    answer_text = _MD_IMAGE_PATTERN.sub("", result["answer"]).strip()
    answer_text = re.sub(r"\n{3,}", "\n\n", answer_text).strip()

    return jsonify({
        "answer": answer_text,
        "sources": result["sources"],
        "detected_language": result.get("detected_language", "English"),
        "image_urls": image_urls,
    })


@app.route("/api/image/<path:filename>")
def get_image(filename):
    return send_from_directory(config.EXTRACTED_IMAGES_DIR, filename)


@app.route("/api/stats")
def stats():
    collection = retrieval.get_collection()
    all_data = collection.get()
    sources = set(meta["source_file"] for meta in all_data["metadatas"])

    accuracy = None
    total_questions = None
    if os.path.exists(config.TEST_RESULTS_PATH):
        with open(config.TEST_RESULTS_PATH, "r", encoding="utf-8") as f:
            results = json.load(f)
        total_questions = len(results)
        passed = sum(1 for r in results if r.get("answer_match"))
        if total_questions:
            accuracy = round(passed / total_questions * 100, 1)

    return jsonify({
        "total_chunks": len(all_data["ids"]),
        "total_documents": len(sources),
        "documents": sorted(sources),
        "measured_accuracy": accuracy,
        "total_test_questions": total_questions,
    })


if __name__ == "__main__":
    print("=" * 60)
    print("Nichi-In Factory Knowledge Assistant — Web UI")
    print("Loading models and connecting to the database...")
    warm_s = search.init()
    print(f"Ready. (startup took {warm_s:.1f}s)")
    print("Open http://localhost:5000 in your browser")
    print("=" * 60)
    app.run(host="127.0.0.1", port=5000, debug=False)