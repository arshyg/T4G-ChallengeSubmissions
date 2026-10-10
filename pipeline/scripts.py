"""The provided deterministic scripts for challenge_1b, plus the line parsers
for each skill's output contract. No model calls happen here."""

import re

TEAMS = ("billing", "technical", "account", "other")
MAX_SUMMARY_WORDS = 20  # summaries must be under this many words

TICKET_ID_RE = re.compile(r"\bT(\d+)\b")
TRIAGE_LINE_RE = re.compile(r"^(T\d+)\s*\|([^|]*)\|([^|]*)$")
CHECKER_VERDICT_RE = re.compile(r"^(PASS|FAIL)\.?$", re.IGNORECASE)
CHECKER_FEEDBACK_RE = re.compile(r"^-\s*(T\d+)\b")
ROUTER_LINE_RE = re.compile(rf"^(T\d+)\s*\|\s*({'|'.join(TEAMS)})\s*$", re.IGNORECASE)
NORMALIZE_LINE_RE = re.compile(r"^(T\d+):\s*(\S.*)$")


def ticket_sort_key(ticket_id):
    return int(ticket_id[1:])


def nonempty_lines(text):
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def format_tickets(tickets):
    return "\n".join(f"{ticket['id']}: {ticket['text']}" for ticket in tickets)


def check_triage(reply, chunk_ids):
    """Format check for one triage reply against its chunk.

    Returns (urgent, violations, lines):
      urgent      {ticket_id: {"summary", "next_action"}} from the lines that passed
      violations  [{"ticket": id-or-None, "rule": text}] in reply order
      lines       [(line, passed)] for contract-compliance scoring; an empty
                  reply counts as one failed line
    """
    chunk_ids = set(chunk_ids)
    lines = nonempty_lines(reply)
    urgent, violations, results = {}, [], []

    if not lines:
        violations.append({"ticket": None, "rule": "reply is empty; return the urgent lines, or NONE"})
        return urgent, violations, [("", False)]

    has_none = any(line.upper() == "NONE" for line in lines)
    if has_none and len(lines) == 1:
        return urgent, violations, [(lines[0], True)]

    for line in lines:
        if line.upper() == "NONE":
            violations.append({"ticket": None, "rule": "NONE is mixed with other lines; use NONE only when no ticket is urgent"})
            results.append((line, False))
            continue
        match = TRIAGE_LINE_RE.match(line)
        if not match or not match.group(2).strip() or not match.group(3).strip():
            id_match = TICKET_ID_RE.search(line)
            ticket = f"T{id_match.group(1)}" if id_match else None
            violations.append({"ticket": ticket if ticket in chunk_ids else None,
                               "rule": f"line does not match 'T<n> | summary | next action': {line[:80]}"})
            results.append((line, False))
            continue
        ticket, summary, next_action = match.group(1), match.group(2).strip(), match.group(3).strip()
        if ticket not in chunk_ids:
            violations.append({"ticket": None, "rule": f"{ticket} is not in this chunk"})
            results.append((line, False))
            continue
        if ticket in urgent:
            violations.append({"ticket": ticket, "rule": f"{ticket} is listed more than once"})
            results.append((line, False))
            continue
        words = len(summary.split())
        if words >= MAX_SUMMARY_WORDS:
            violations.append({"ticket": ticket, "rule": f"summary has {words} words; it must be under {MAX_SUMMARY_WORDS}"})
            results.append((line, False))
            continue
        urgent[ticket] = {"summary": summary, "next_action": next_action}
        results.append((line, True))

    return urgent, violations, results


def format_violations(violations):
    return "\n".join(f"- {v['ticket']}: {v['rule']}" if v["ticket"] else f"- {v['rule']}" for v in violations)


def parse_checker(reply, chunk_ids):
    """Returns (verdict, disputed_ids, feedback_text, lines, dropped).

    verdict is "PASS", "FAIL", or None when the first line is neither.
    """
    chunk_ids = set(chunk_ids)
    lines = nonempty_lines(reply)
    results, dropped, disputed = [], [], []
    if not lines:
        return None, disputed, "", [("", False)], dropped

    verdict_match = CHECKER_VERDICT_RE.match(lines[0])
    verdict = verdict_match.group(1).upper() if verdict_match else None
    results.append((lines[0], verdict is not None))
    if verdict is None:
        dropped.append(lines[0])

    feedback_lines = []
    for line in lines[1:]:
        match = CHECKER_FEEDBACK_RE.match(line)
        ok = verdict == "FAIL" and match is not None and match.group(1) in chunk_ids
        results.append((line, ok))
        if not ok:
            dropped.append(line)
            continue
        feedback_lines.append(line)
        if match.group(1) not in disputed:
            disputed.append(match.group(1))
    return verdict, disputed, "\n".join(feedback_lines), results, dropped


def parse_router(reply, urgent_ids):
    """Returns ({ticket_id: team}, lines, dropped)."""
    urgent_ids = set(urgent_ids)
    routes, results, dropped = {}, [], []
    lines = nonempty_lines(reply)
    if not lines:
        return routes, [("", False)], dropped
    for line in lines:
        match = ROUTER_LINE_RE.match(line)
        ok = match is not None and match.group(1) in urgent_ids and match.group(1) not in routes
        results.append((line, ok))
        if not ok:
            dropped.append(line)
            continue
        routes[match.group(1)] = match.group(2).lower()
    return routes, results, dropped


def parse_normalize(reply, chunk):
    """Returns ({ticket_id: new_text}, lines, dropped). Each line must carry
    the ID of the ticket in the same position, so IDs and order are kept."""
    expected = [ticket["id"] for ticket in chunk]
    texts, results, dropped = {}, [], []
    lines = nonempty_lines(reply)
    if not lines:
        return texts, [("", False)], dropped
    for index, line in enumerate(lines):
        match = NORMALIZE_LINE_RE.match(line)
        ok = match is not None and index < len(expected) and match.group(1) == expected[index]
        results.append((line, ok))
        if not ok:
            dropped.append(line)
            continue
        texts[match.group(1)] = match.group(2).strip()
    return texts, results, dropped


def _sentence(text):
    text = text.strip()
    return text if text.endswith((".", "!", "?")) else text + "."


def render_report(urgent, routes, review_ids, total_tickets):
    """The final report: one bullet per urgent ticket in ticket order, the
    review line (when there is one), then the count line."""
    lines = []
    for ticket in sorted(urgent, key=ticket_sort_key):
        entry = urgent[ticket]
        team = routes.get(ticket, "unrouted")
        lines.append(f"- {ticket} [{team}]: {_sentence(entry['summary'])} Next action: {_sentence(entry['next_action'])}")
    if review_ids:
        lines.append("Needs review: " + ", ".join(sorted(review_ids, key=ticket_sort_key)))
    lines.append(f"{len(urgent)} of {total_tickets} tickets required urgent action.")
    return "\n".join(lines)
