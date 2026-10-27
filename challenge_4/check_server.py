"""Checks your MCP server the way the benchmark's setup check does (no API key needed).

    python challenge_4/check_server.py teams/challenge_4/<your-team>

Starts your mcp_server.py, compares its tools to tool_manifest.json, then makes one
real call to each tool. Prints what's wrong, and exits 1 if anything is.
"""
import asyncio
import sys

from orca_mcp import MANIFEST, compare_tool, find_server, open_server, result_payload

SAMPLE_CALLS = {
    "query_media_metrics": {"candidate": "Dana Reyes", "platform": "podcast",
                            "start_date": "2026-06-01", "end_date": "2026-06-30"},
    "search_transcript_segments": {"query": "tariffs", "speaker": "Dana Reyes"},
}
EXPECTED_KEY = {"query_media_metrics": "total_mentions", "search_transcript_segments": "results"}


async def check(server):
    ok = True
    async with open_server(server) as session:
        print("✓ server started")
        tools = {t.name: t for t in (await session.list_tools()).tools}
        for spec in MANIFEST["tools"]:
            name = spec["name"]
            if name not in tools:
                print(f"✗ {name}: not exposed")
                ok = False
                continue
            problems = compare_tool(tools[name], spec)
            if problems:
                ok = False
                print(f"✗ {name} schema: " + "; ".join(problems))
            else:
                print(f"✓ {name} schema matches the manifest")
            is_error, payload = result_payload(await session.call_tool(name, SAMPLE_CALLS[name]))
            if is_error or not isinstance(payload, dict) or EXPECTED_KEY[name] not in payload:
                ok = False
                print(f"✗ {name} sample call failed: {str(payload)[:300]}")
            else:
                shown = payload["total_mentions"] if name == "query_media_metrics" else f"{len(payload['results'])} passages"
                print(f"✓ {name} sample call returned {shown}")
        extra = sorted(set(tools) - {s["name"] for s in MANIFEST["tools"]})
        if extra:
            print("! extra tools (fine, but the model will see them too): " + ", ".join(extra))
    return ok


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__.strip())
    server = find_server(sys.argv[1])
    try:
        ok = asyncio.run(asyncio.wait_for(check(server), timeout=60))
    except Exception as exc:
        reason = "it took too long to respond" if isinstance(exc, TimeoutError) else "see its output above"
        print(f"✗ server failed to start or crashed ({reason})")
        ok = False
    print("\nOK: server matches the manifest" if ok else "\nNOT READY: fix the ✗ lines above")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
