"""MCP wrappers for the Orca Lite archive capabilities."""
from typing import Literal, Optional

from mcp.server.fastmcp import FastMCP

import orca_backend

mcp = FastMCP("orca-lite")


@mcp.tool(
    name="query_media_metrics",
    description="Get candidate mention counts, trends, peaks, or platform comparisons.",
)
def query_media_metrics(
    candidate: Literal["Dana Reyes", "Marcus Whitfield", "Priya Anand"],
    platform: Optional[Literal["youtube", "tiktok", "cable", "podcast"]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    granularity: Optional[Literal["day", "week", "month"]] = "week",
) -> dict:
    return orca_backend.query_media_metrics(
        candidate=candidate,
        platform=platform,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity or "week",
    )


@mcp.tool(
    name="search_transcript_segments",
    description="Find exact transcript passages about a topic, with episode and timestamp evidence.",
)
def search_transcript_segments(
    query: str,
    speaker: Optional[str] = None,
    platform: Optional[Literal["youtube", "tiktok", "cable", "podcast"]] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    top_k: int = 5,
) -> dict:
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
