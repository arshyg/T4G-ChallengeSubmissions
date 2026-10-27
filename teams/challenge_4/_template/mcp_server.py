"""Orca Lite MCP server: starter. Copy to your team folder as mcp_server.py and finish the TODOs.

Expose the two backend functions in orca_backend.py as MCP tools. This should be a thin
wrapper: call the backend function and return its result, nothing more. Match
tool_manifest.json exactly (tool names, parameter names, types, enums, required vs
optional), and give each tool a short description so the model can tell when to use it.

Check your server (it starts it for you, so you never run this file directly):
    python challenge_4/check_server.py teams/challenge_4/<your-team>
"""
from typing import Literal, Optional

from mcp.server.fastmcp import FastMCP

import orca_backend

mcp = FastMCP("orca-lite")


# The pattern, on a toy tool that isn't part of the challenge (delete it when you're done).
# The function's type hints become the tool's parameter schema: a Literal[...] becomes an
# enum, and Optional[...] = None makes a parameter optional.
@mcp.tool(name="echo", description="Repeats a word back. Only here as an example.")
def echo(word: str, times: Optional[Literal[1, 2, 3]] = None) -> str:
    return " ".join([word] * (times or 1))


# TODO 1: register orca_backend.query_media_metrics as the tool "query_media_metrics".
#   Parameters (see tool_manifest.json): candidate (required, one of the three candidates),
#   platform, start_date, end_date, granularity ("day", "week" or "month"; default "week").


# TODO 2: register orca_backend.search_transcript_segments as "search_transcript_segments".
#   Parameters: query (required), speaker, platform, start_date, end_date, top_k (default 5).


if __name__ == "__main__":
    mcp.run()
