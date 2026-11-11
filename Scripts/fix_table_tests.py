"""
Corrects the expected answers of test ids 64 and 65 in tests\\test_questions.json after checking
them against the page image of 7.pdf page 20 (Controller Modifications price table; columns are
7-1/2, 15, 35 and 55 HP):
  id 64: modifications 2 ($400), 12A/12B/12C ($368), 17 and 18 ($440) all cost the same in all four
         columns - the old expected answer listed only modification 2.
  id 65: for 55 HP, modification 3 costs $912 and modification 25 (Negative Line Contactor) costs
         $604, so modification 3 is $308 more. The old expected answer used the 35 HP price ($776)
         and the Shunt Brake Relay price ($368), which is a different modification.
Makes a backup (test_questions.json.bak) before changing anything. Run from D:\\FactoryKA\\Scripts.
"""
import json
import os
import shutil

path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tests", "test_questions.json")
shutil.copyfile(path, path + ".bak")
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

NEW = {
    64: "Several modifications cost the same for all four HP ratings: modification 2 (Substitute Circuit Breakers "
        "for Main Line and Control Circuit Knife Switches) at $400; modifications 12A, 12B and 12C (Shunt Brake "
        "Relay) at $368; modification 17 (Arc Inhibitors) and modification 18 (Cabinet Space Heater) at $440.",
    65: "For a 55 HP motor, Modification 3 (Additional Acceleration Point) costs $912 and Modification 25 "
        "(Negative Line Contactor) costs $604, so Modification 3 is more expensive by $308.",
}
changed = 0
for q in data:
    if q["id"] in NEW:
        q["expected_answer"] = NEW[q["id"]]
        q["expected_source"] = "7.pdf (page 20)"
        changed += 1
with open(path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print("Updated {} questions (backup: {}.bak)".format(changed, os.path.basename(path)))
