import json

with open(r"D:\FactoryKA\captions_7pdf.json", "r", encoding="utf-8") as f:
    results = json.load(f)

failed = [r for r in results if r['caption'] == "CAPTION_FAILED"]
succeeded = [r for r in results if r['caption'] != "CAPTION_FAILED"]

print(f"Total: {len(results)}")
print(f"Succeeded: {len(succeeded)}")
print(f"Failed: {len(failed)}")

if failed:
    print("\nFailed images:")
    for f_img in failed:
        print(f"  {f_img['image_path']}")

print("\n--- Sample captions ---")
for r in succeeded[:3]:
    print(f"\n{r['image_path']}")
    print(f"Caption: {r['caption']}")