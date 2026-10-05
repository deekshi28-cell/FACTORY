import openpyxl
import json

wb = openpyxl.load_workbook(r"D:\FactoryKA\Phase2_Test_Questions.xlsx")
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

with open(r"D:\FactoryKA\test_questions.json", "w", encoding="utf-8") as f:
    json.dump(questions, f, ensure_ascii=False, indent=2)

print(f"Exported {len(questions)} questions")