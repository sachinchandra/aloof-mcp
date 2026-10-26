"""Start the server over stdio and list its tools (no network calls to the API are made)."""
import ast, asyncio, pathlib, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
SRC = pathlib.Path(__file__).resolve().parent.parent / "src"
def expected():
    tree = ast.parse((SRC / "aloof_mcp/server.py").read_text())
    tool = lambda d: isinstance(d, ast.Call) and getattr(d.func, "attr", "") == "tool"
    nm = lambda f: next((k.value.value for d in f.decorator_list if tool(d) for k in d.keywords if k.arg == "name"), f.name)
    return {nm(f) for f in tree.body if isinstance(f, ast.FunctionDef) and any(tool(d) for d in f.decorator_list)}
async def _list():
    p = StdioServerParameters(command=sys.executable, args=["-m", "aloof_mcp"], env={"PYTHONPATH": str(SRC)})
    async with stdio_client(p) as (r, w), ClientSession(r, w) as s:
        await s.initialize(); return {t.name for t in (await s.list_tools()).tools}
def test_stdio_lists_all_tools():
    names = asyncio.run(_list())
    assert names == expected() and len(names) == 25
def test_legacy_names_opt_in():
    import os
    os.environ["ALOOF_MCP_TOOLS"] = "legacy"
    try:
        p = StdioServerParameters(command=sys.executable, args=["-m", "aloof_mcp"], env={"PYTHONPATH": str(SRC), "ALOOF_MCP_TOOLS": "legacy"})
        async def go():
            async with stdio_client(p) as (r, w), ClientSession(r, w) as s:
                await s.initialize(); return {t.name for t in (await s.list_tools()).tools}
        names = asyncio.run(go())
    finally: os.environ.pop("ALOOF_MCP_TOOLS")
    assert len(names) == 47 and {"get_status", "diagnose_app", "inspect"} <= names
