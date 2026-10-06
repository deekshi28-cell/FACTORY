import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app"))
import config  # noqa: E402
import openpyxl
import json

wb = openpyxl.load_workbook(os.path.join(config.TESTS_DIR, "Phase2_Test_Questions.xlsx"))
ws = wb["Test Questions"]

questions = []
for row in ws.iter_rows(min_row=2, values_only=True):
    no, category, question, expected_answer, source_doc, page_no, status, notes = row
    if question:
        questions.append({
            "id": no,
            "category": category,
            "question": question,
            "expected_answer": expected_answer,
            "expected_source": source_doc
        })

with open(config.TEST_QUESTIONS_PATH, "w", encoding="utf-8") as f:
    json.dump(questions, f, ensure_ascii=False, indent=2)

print(f"Exported {len(questions)} questions")