import ast, pathlib

root = pathlib.Path(__file__).parent
mods = set()

for f in root.rglob("*.py"):
    if "venv" in f.parts or "__pycache__" in f.parts:
        continue
    try:
        tree = ast.parse(f.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                mods.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                mods.add(node.module.split(".")[0])

for m in sorted(mods):
    print(m)