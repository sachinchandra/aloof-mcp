"""Regenerate the tool table in README.md from the @mcp.tool() functions in src/aloof_mcp/server.py."""
import ast, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
def tools():
    tree = ast.parse((ROOT / "src/aloof_mcp/server.py").read_text())
    is_tool = lambda d: isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "tool"
    for f in tree.body:
        if isinstance(f, ast.FunctionDef) and any(is_tool(d) for d in f.decorator_list):
            doc = " ".join((ast.get_docstring(f) or "").split())
            nm = next((k.value.value for d in f.decorator_list if is_tool(d) for k in d.keywords if k.arg == "name"), f.name)
            yield nm, re.split(r"(?<=\.)\s", doc, maxsplit=1)[0]
def table():
    rows = list(tools())
    return f"{len(rows)} tools:\n\n| Tool | What it does |\n|---|---|\n" + "".join(f"| `{n}` | {d.replace('|', '/')} |\n" for n, d in rows)
if __name__ == "__main__":
    p = ROOT / "README.md"; s = p.read_text()
    s = re.sub(r"<!-- tools:start -->.*<!-- tools:end -->", lambda m: f"<!-- tools:start -->\n{table()}<!-- tools:end -->", s, flags=re.S)
    p.write_text(s); print(f"{len(list(tools()))} tools written")
