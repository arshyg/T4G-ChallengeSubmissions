"""Shared helpers for check_server.py and run_agent.py (provided; you don't need to change it).

Starts a team's mcp_server.py over stdio with this kit on its import path, and compares
the tools it exposes against tool_manifest.json.
"""
import json
import os
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

KIT = Path(__file__).resolve().parent
MANIFEST = json.loads((KIT / "tool_manifest.json").read_text(encoding="utf-8"))


def find_server(path):
    path = Path(path).resolve()
    server = path / "mcp_server.py" if path.is_dir() else path
    if not server.is_file():
        sys.exit(f"No mcp_server.py at {server}. Copy teams/challenge_4/_template first.")
    return server


@asynccontextmanager
async def open_server(server, simulate_timeout=None):
    env = {k: v for k, v in os.environ.items() if not k.endswith("_API_KEY")}
    env["PYTHONPATH"] = str(KIT) + os.pathsep + env.get("PYTHONPATH", "")
    if simulate_timeout:
        env["ORCA_SIMULATE_TIMEOUT"] = simulate_timeout
    params = StdioServerParameters(command=sys.executable, args=[str(server)], env=env, cwd=str(Path(server).parent))
    # The server's own log lines go to a temp file and are only shown if it crashes.
    with tempfile.TemporaryFile("w+", encoding="utf-8") as server_log:
        started = False
        try:
            async with stdio_client(params, errlog=server_log) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    started = True
                    yield session
        except BaseException:
            if started:
                raise
            server_log.seek(0)
            lines = [line for line in server_log.read().splitlines() if line.strip()]
            if lines:
                print("Server output before it stopped:\n    " + "\n    ".join(lines[-8:]), file=sys.stderr)
            raise


def _flatten(prop):
    # FastMCP writes Optional[X] as anyOf [X, null]; read the non-null branch.
    types, enum = set(), None
    for branch in prop.get("anyOf", [prop]):
        if branch.get("type") and branch.get("type") != "null":
            types.add(branch["type"])
        if "enum" in branch:
            enum = [v for v in branch["enum"] if v is not None]
    return types, enum


def compare_tool(tool, spec):
    """Problems with one exposed tool compared to its manifest entry (empty list = matches)."""
    problems = []
    if not (tool.description or "").strip():
        problems.append("has no description")
    schema = tool.inputSchema or {}
    props = schema.get("properties", {})
    required = set(schema.get("required", []))
    expected = spec["parameters"]
    missing = [p for p in expected if p not in props]
    extra = [p for p in props if p not in expected]
    if missing:
        problems.append("missing parameter(s): " + ", ".join(missing))
    if extra:
        problems.append("unexpected parameter(s): " + ", ".join(extra))
    for name, want in expected.items():
        if name not in props:
            continue
        types, enum = _flatten(props[name])
        if want["type"] not in types:
            problems.append(f"{name} should be {want['type']}, is {', '.join(sorted(types)) or 'untyped'}")
        if "enum" in want and set(enum or []) != set(want["enum"]):
            problems.append(f"{name} should only allow {', '.join(map(str, want['enum']))}")
        if want["required"] and name not in required:
            problems.append(f"{name} should be required")
        if not want["required"] and name in required:
            problems.append(f"{name} should be optional")
    return problems


def result_payload(result):
    """A tool call's result as (is_error, python value or text)."""
    if getattr(result, "structuredContent", None):
        payload = result.structuredContent
        if set(payload) == {"result"}:
            payload = payload["result"]
        return bool(result.isError), payload
    text = "\n".join(getattr(c, "text", "") for c in result.content or [])
    try:
        return bool(result.isError), json.loads(text)
    except ValueError:
        return bool(result.isError), text
