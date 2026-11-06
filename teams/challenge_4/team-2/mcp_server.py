"""Orca Lite MCP server: starter. Copy to your team folder as mcp_server.py and finish the TODOs.

Expose the two backend functions in orca_backend.py as MCP tools. This should be a thin
wrapper: call the backend function and return its result, nothing more. Match
tool_manifest.json exactly (tool names, parameter names, types, enums, required vs
optional), and give each tool a short description so the model can tell when to use it.

Check your server (it starts it for you, so you never run this file directly):
    python challenge_4/check_server.py teams/challenge_4/<your-team>
"""
from typing import Literal, Optional

from mcp.server.fastmcp import FastMCP  # pyright: ignore[reportMissingImports]

import orca_backend

mcp = FastMCP("orca-lite")

CandidateLiteral = Literal["Dana Reyes", "Marcus Whitfield", "Priya Anand"]
PlatformLiteral = Literal["youtube", "tiktok", "cable", "podcast"]


# Tool 1: register orca_backend.query_media_metrics
@mcp.tool(
    name="query_media_metrics",
    description="Retrieve candidate mention counts, volumes, and trends across media platforms and time periods.",
)
def query_media_metrics(
    candidate: CandidateLiteral,
    platform: Optional[PlatformLiteral] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: Literal["day", "week", "month"] = "week",
):
    return orca_backend.query_media_metrics(
        candidate=candidate,
        platform=platform,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
    )


# Tool 2: register orca_backend.search_transcript_segments
@mcp.tool(
    name="search_transcript_segments",
    description="Search media transcripts for spoken statements, quotes, and topics by a speaker.",
)
def search_transcript_segments(
    query: str,
    speaker: Optional[CandidateLiteral] = None,
    platform: Optional[PlatformLiteral] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    top_k: int = 5,
):
    return orca_backend.search_transcript_segments(
        query=query,
        speaker=speaker,
        platform=platform,
        start_date=start_date,
        end_date=end_date,
        top_k=top_k,
    )


if __name__ == "__main__":
    mcp.run()