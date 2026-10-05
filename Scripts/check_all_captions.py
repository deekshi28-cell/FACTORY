import json
with open(r"D:\FactoryKA\all_captions.json", "r", encoding="utf-8") as f:
    results = json.load(f)

failed = [r for r in results if r['caption'] == "CAPTION_FAILED"]
by_source = {}
for r in results:
    by_source[r['source_file']] = by_source.get(r['source_file'], 0) + 1

print(f"Total images captioned: {len(results)}")
print(f"Failed: {len(failed)}")
print("\nBreakdown by source file:")
for src, count in sorted(by_source.items()):
    print(f"  {src}: {count}")