"""Orca Lite backend: the two capabilities your MCP server exposes. Don't rewrite these.

query_media_metrics(...)         -> mention counts and trends from corpus/mentions.csv
search_transcript_segments(...)  -> ranked transcript passages via rag_pipeline.py

Bad arguments raise ValueError with a message the model can read. For testing graceful
failure, setting ORCA_SIMULATE_TIMEOUT to a tool name (e.g. search_transcript_segments)
makes that function raise TimeoutError, the way a slow archive service would.
"""
import csv
import datetime as dt
import os
from pathlib import Path

from rag_pipeline import get_index

CORPUS = Path(__file__).resolve().parent / "corpus"
CANDIDATES = ("Dana Reyes", "Marcus Whitfield", "Priya Anand")
PLATFORMS = ("youtube", "tiktok", "cable", "podcast")
GRANULARITIES = ("day", "week", "month")
ARCHIVE_START, ARCHIVE_END = dt.date(2026, 5, 1), dt.date(2026, 7, 31)
_ROWS = None


def _maybe_timeout(tool):
    if tool in (os.environ.get("ORCA_SIMULATE_TIMEOUT") or "").split(","):
        raise TimeoutError(f"{tool} timed out after 10 seconds (archive service unavailable)")


def _date(value, name, default):
    if value in (None, ""):
        return default
    try:
        day = dt.date.fromisoformat(str(value))
    except ValueError:
        raise ValueError(f"{name} must be a date like 2026-06-04, got {value!r}")
    if not ARCHIVE_START <= day <= ARCHIVE_END:
        raise ValueError(f"{name} {day} is outside the archive ({ARCHIVE_START} to {ARCHIVE_END})")
    return day


def _window(start_date, end_date):
    start = _date(start_date, "start_date", ARCHIVE_START)
    end = _date(end_date, "end_date", ARCHIVE_END)
    if start > end:
        raise ValueError(f"start_date {start} is after end_date {end}")
    return start, end


def _platform(platform):
    if platform in (None, "", "all"):
        return None
    value = str(platform).lower()
    if value not in PLATFORMS:
        raise ValueError(f"platform must be one of {', '.join(PLATFORMS)}, got {platform!r}")
    return value


def _candidate(name):
    text = str(name or "").strip().lower()
    for cand in CANDIDATES:
        if text in (cand.lower(), cand.split()[-1].lower()):
            return cand
    raise ValueError(f"candidate must be one of {', '.join(CANDIDATES)}, got {name!r}")


def _rows():
    global _ROWS
    if _ROWS is None:
        with open(CORPUS / "mentions.csv", encoding="utf-8") as f:
            _ROWS = [dict(r, date=dt.date.fromisoformat(r["date"]), mentions=int(r["mentions"]))
                     for r in csv.DictReader(f)]
    return _ROWS


def _period(day, granularity):
    if granularity == "day":
        return day
    if granularity == "week":
        return day - dt.timedelta(days=day.weekday())
    return day.replace(day=1)


def query_media_metrics(candidate, platform=None, start_date=None, end_date=None, granularity="week"):
    """Mention counts for one candidate, optionally for one platform and date window.

    Returns the total, a per-period series (day / week starting Monday / month), the peak
    period, and per-platform totals when no platform is given.
    """
    _maybe_timeout("query_media_metrics")
    cand = _candidate(candidate)
    plat = _platform(platform)
    start, end = _window(start_date, end_date)
    if granularity not in GRANULARITIES:
        raise ValueError(f"granularity must be one of {', '.join(GRANULARITIES)}, got {granularity!r}")
    series, by_platform = {}, {}
    for r in _rows():
        if r["candidate"] != cand or not start <= r["date"] <= end or (plat and r["platform"] != plat):
            continue
        key = _period(r["date"], granularity).isoformat()
        series[key] = series.get(key, 0) + r["mentions"]
        by_platform[r["platform"]] = by_platform.get(r["platform"], 0) + r["mentions"]
    points = [{"period_start": k, "mentions": v} for k, v in sorted(series.items())]
    result = {
        "candidate": cand, "platform": plat or "all", "start_date": start.isoformat(),
        "end_date": end.isoformat(), "granularity": granularity,
        "total_mentions": sum(by_platform.values()), "series": points,
        "peak": max(points, key=lambda p: p["mentions"]) if points else None,
    }
    if plat is None:
        result["by_platform"] = by_platform
    return result


def search_transcript_segments(query, speaker=None, platform=None, start_date=None, end_date=None, top_k=5):
    """Transcript passages relevant to `query`, best first, each with its episode and timestamp.

    Filters narrow the search before ranking. An empty `results` list means the archive has
    no relevant passage for that query and those filters.
    """
    _maybe_timeout("search_transcript_segments")
    if not str(query or "").strip():
        raise ValueError("query must not be empty")
    plat = _platform(platform)
    start, end = _window(start_date, end_date)
    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        raise ValueError(f"top_k must be a whole number from 1 to 10, got {top_k!r}")
    if not 1 <= top_k <= 10:
        raise ValueError(f"top_k must be from 1 to 10, got {top_k}")
    who = str(speaker or "").strip().lower()

    def keep(seg):
        if plat and seg["platform"] != plat:
            return False
        if not start <= dt.date.fromisoformat(seg["date"]) <= end:
            return False
        if who and who not in (seg["speaker"].lower(), seg["speaker"].split()[-1].lower()):
            return False
        return True

    results = get_index().search(query, keep=keep, top_k=top_k)
    out = {
        "query": query,
        "filters": {"speaker": speaker or None, "platform": plat, "start_date": start.isoformat(),
                    "end_date": end.isoformat(), "top_k": top_k},
        "results": results,
    }
    if not results:
        out["note"] = "No transcript segment in the archive matched this query and these filters."
    return out
