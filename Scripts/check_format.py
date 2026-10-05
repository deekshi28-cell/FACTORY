import json

with open(r"D:\FactoryKA\test_questions.json", "r", encoding="utf-8") as f:
       questions = json.load(f)

for q in questions[:10]:
       print(f"ID {q['id']}: expected_source = {repr(q.get('expected_source'))}")