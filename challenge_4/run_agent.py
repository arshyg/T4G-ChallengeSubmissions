"""Runs your skill.md with your MCP server on a question, the way the benchmark does.

    GEMINI_API_KEY=... python challenge_4/run_agent.py teams/challenge_4/<your-team> "What did Dana Reyes say about tariffs on the June 4 podcast?"
    GEMINI_API_KEY=... python challenge_4/run_agent.py teams/challenge_4/<your-team> --practice

Options:
    --practice                  run every question in practice_questions.json
    --simulate-timeout TOOL     make that tool time out (query_media_metrics or search_transcript_segments)

Prints each tool call with its arguments and what came back, the final answer, and a
grounding check: every quote must match a returned passage word for word, and every
citation (episode_id @ HH:MM:SS) must be a passage the agent actually retrieved.
Practice uses the free gemini-3.5-flash (set BENCHMARK_MODEL to change it); the official
benchmark uses Gemini 3.1 Pro, so behavior can differ. Doesn't touch the leaderboard.
"""
import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from orca_mcp import KIT, find_server, open_server, result_payload

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MAX_TOOL_ROUNDS = 6
QUOTE = re.compile(r"[\"“]([^\"“”]{12,}?)[\"”]")
CITATION = re.compile(r"([a-z]+(?:-[a-z0-9]+)+)\s*@\s*(\d{2}:\d{2}:\d{2})")


def load_skill(team):
    path = Path(team) / "skill.md" if Path(team).is_dir() else Path(team).with_name("skill.md")
    if not path.is_file():
        sys.exit(f"No skill.md at {path}.")
    text = path.read_text(encoding="utf-8")
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) == 3:
            return parts[2].strip()
    return text.strip()


def make_client():
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("The openai package isn't installed: pip install -r requirements.txt")
    gemini, router = os.environ.get("GEMINI_API_KEY"), os.environ.get("OPENROUTER_API_KEY")
    if gemini:
        return OpenAI(api_key=gemini, base_url=GEMINI_BASE_URL, timeout=120, max_retries=2), \
            os.environ.get("BENCHMARK_MODEL") or "gemini-3.5-flash"
    if router:
        return OpenAI(api_key=router, base_url=OPENROUTER_BASE_URL, timeout=120, max_retries=2), \
            os.environ.get("BENCHMARK_MODEL") or "google/gemini-3.5-flash"
    sys.exit("Set GEMINI_API_KEY first (free key at https://aistudio.google.com). "
             "To check your server without a key, use check_server.py.")


def _simplify(schema):
    # Model APIs accept a smaller JSON-schema dialect than MCP: collapse Optional[X]
    # (anyOf X|null) to X and drop titles. Your server's real schema is checked separately.
    if isinstance(schema, dict):
        if "anyOf" in schema:
            branches = [b for b in schema["anyOf"] if b.get("type") != "null"]
            if len(branches) == 1:
                merged = {k: v for k, v in schema.items() if k not in ("anyOf", "default")}
                merged.update(branches[0])
                schema = merged
        return {k: _simplify(v) for k, v in schema.items() if k not in ("title", "additionalProperties")}
    if isinstance(schema, list):
        return [_simplify(v) for v in schema]
    return schema


def _show(payload, error):
    if error:
        return "ERROR: " + str(payload)[:300]
    if isinstance(payload, dict) and "results" in payload:
        if not payload["results"]:
            return "no passages found"
        return "\n".join(f"{r['episode_id']} @ {r['timestamp']}  {r['speaker']}: {r['text'][:110]}"
                         for r in payload["results"])
    if isinstance(payload, dict) and "total_mentions" in payload:
        peak = payload.get("peak") or {}
        return (f"{payload['total_mentions']} mentions ({payload['platform']}, {payload['start_date']} to "
                f"{payload['end_date']}); peak {peak.get('period_start')} with {peak.get('mentions')}")
    return str(payload)[:300]


async def _complete(client, model, messages, tools, log):
    # Free Gemini keys allow only a few requests a minute: wait and retry instead of failing.
    for wait in (20, 40, 60, None):
        try:
            return client.chat.completions.create(
                model=model, messages=messages, tools=tools, temperature=0,
                max_tokens=int(os.environ.get("BENCHMARK_MAX_TOKENS", "8192")))
        except Exception as exc:
            if getattr(exc, "status_code", None) != 429 or wait is None:
                raise
            log(f"  (rate limited by the API; waiting {wait}s and retrying)")
            await asyncio.sleep(wait)


async def run_question(session, client, model, skill, question, max_rounds=MAX_TOOL_ROUNDS, log=print):
    tools = [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                               "parameters": _simplify(t.inputSchema)}}
             for t in (await session.list_tools()).tools]
    messages = [{"role": "system", "content": skill}, {"role": "user", "content": question}]
    trace = {"question": question, "calls": [], "answer": None, "stopped": None}
    for round_no in range(max_rounds + 1):
        response = await _complete(client, model, messages, tools, log)
        message = response.choices[0].message
        if not message.tool_calls:
            trace["answer"] = message.content or ""
            break
        if round_no == max_rounds:
            trace["stopped"] = f"still calling tools after {max_rounds} rounds"
            break
        messages.append(message.model_dump(exclude_none=True))
        for call in message.tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments or "{}")
                error, payload = result_payload(await asyncio.wait_for(session.call_tool(name, args), timeout=30))
            except Exception as exc:
                args = args if "args" in locals() and isinstance(args, dict) else {}
                error, payload = True, f"{type(exc).__name__}: {exc}"
            trace["calls"].append({"tool": name, "arguments": args, "error": error, "result": payload})
            log(f"\n→ {name}({', '.join(f'{k}={v!r}' for k, v in args.items())})")
            log("  " + _show(payload, error).replace("\n", "\n  "))
            messages.append({"role": "tool", "tool_call_id": call.id,
                             "content": payload if isinstance(payload, str) else json.dumps(payload)})
            args = None
    return trace


def _norm(text):
    return " ".join(text.replace("’", "'").replace("‘", "'").split())


def grounding_report(trace):
    """(ok, lines): quotes must be verbatim from a retrieved passage; citations must be retrieved passages."""
    retrieved, titles = {}, set()
    for call in trace["calls"]:
        if call["tool"] == "search_transcript_segments" and not call["error"] and isinstance(call["result"], dict):
            for r in call["result"].get("results", []):
                retrieved[(r["episode_id"], r["timestamp"])] = _norm(r["text"])
                titles.update(_norm(r.get(k, "")).lower() for k in ("episode_title", "show"))
    answer = trace["answer"] or ""
    lines, ok = [], True
    for quote in QUOTE.findall(answer):
        if _norm(quote).lower() in titles:
            lines.append(f"\u00b7 quoted an episode or show title (fine): \"{quote[:80]}\"")
            continue
        found = any(_norm(quote) in text for text in retrieved.values())
        ok &= found
        lines.append(f"{'✓' if found else '✗'} quote {'matches a retrieved passage' if found else 'is NOT in any retrieved passage'}: \"{quote[:80]}\"")
    for episode, stamp in sorted(set(CITATION.findall(answer))):
        found = (episode, stamp) in retrieved
        ok &= found
        lines.append(f"{'✓' if found else '✗'} citation {episode} @ {stamp} {'was retrieved' if found else 'was NOT retrieved'}")
    if not lines:
        lines.append("· no quotes or citations in the answer")
    return ok, lines


def _innermost(exc):
    # The MCP client wraps errors in exception groups; find the real one.
    while getattr(exc, "exceptions", None):
        exc = exc.exceptions[0]
    return exc


def _reason(exc):
    exc = _innermost(exc)
    return f"{type(exc).__name__}: {str(exc)[:300]}"


async def run(team, questions, simulate_default=None):
    server, skill = find_server(team), load_skill(team)
    client, model = make_client()
    print(f"Model: {model}")
    traces = []
    for q in questions:
        print("\n" + "=" * 78 + f"\nQ: {q['question']}")
        timeout_tool = q.get("simulate_timeout", simulate_default)
        if timeout_tool:
            print(f"(simulating a timeout in {timeout_tool})")
        try:
            async with open_server(server, simulate_timeout=timeout_tool) as session:
                trace = await run_question(session, client, model, skill, q["question"])
        except Exception as exc:
            print(f"\n\u2717 run stopped: {_reason(exc)}")
            if getattr(_innermost(exc), "status_code", None) == 429:
                print("  That's the API's rate limit or daily quota. Wait a minute (or until tomorrow for the\n"
                      "  daily quota) and try again; running one question at a time uses fewer requests.")
            elif not hasattr(_innermost(exc), "status_code"):
                print(f"  If your server didn't start, run: python challenge_4/check_server.py {team}")
            sys.exit(1)
        if trace["stopped"]:
            print(f"\n✗ stopped: {trace['stopped']}")
        print("\n--- Answer ---\n" + (trace["answer"] or "(no answer)"))
        print("\n--- Grounding check ---")
        _, lines = grounding_report(trace)
        print("\n".join(lines))
        tools_used = [c["tool"] for c in trace["calls"]]
        print(f"Tools called: {', '.join(tools_used) or 'none'}")
        if q.get("what_good_looks_like"):
            print("What a good run looks like: " + q["what_good_looks_like"])
        traces.append(dict(trace, id=q.get("id")))
    out = Path(".benchmark-cache") / "challenge_4" / Path(team).resolve().name / "last_run.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(traces, indent=2, default=str))
    print(f"\nFull traces saved to {out}")


def main():
    parser = argparse.ArgumentParser(description="Run your Orca Lite skill + MCP server on a question.")
    parser.add_argument("team", help="your team folder, e.g. teams/challenge_4/my-team")
    parser.add_argument("question", nargs="?", help="a question to ask (or use --practice)")
    parser.add_argument("--practice", action="store_true", help="run every question in practice_questions.json")
    parser.add_argument("--simulate-timeout", choices=["query_media_metrics", "search_transcript_segments"])
    args = parser.parse_args()
    if args.practice:
        questions = json.loads((KIT / "practice_questions.json").read_text(encoding="utf-8"))["questions"]
    elif args.question:
        questions = [{"question": args.question}]
    else:
        parser.error("give a question or --practice")
    try:
        sys.stdout.reconfigure(errors="replace")
    except AttributeError:
        pass
    asyncio.run(run(args.team, questions, args.simulate_timeout))


if __name__ == "__main__":
    main()
