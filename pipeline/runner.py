"""Runs a team's challenge_1b pipeline on one batch of tickets.

Steps run in pipeline.yaml order: split, normalize (optional), triage,
verify, route, render_report. Every skill call counts against the call
budget; the provided scripts are free. Everything that happens is written
to a plain-text trace so teams can see where points leak.
"""

from .scripts import (
    check_triage,
    format_tickets,
    format_violations,
    parse_checker,
    parse_normalize,
    parse_router,
    render_report,
    ticket_sort_key,
)
from .spec import CALL_BUDGET

RETRY_TEMPLATE = """{prompt}

---
Your previous reply was:
{previous}

It was rejected for these reasons:
{feedback}

Reply again with the corrected list for the same tickets, in the same format and nothing else."""


class BudgetExhausted(Exception):
    pass


class ModelUnavailable(Exception):
    """Raised by call_model when the model can't be reached at all (outage,
    rate limit). It aborts the run instead of reading as an empty reply, so
    an outage is never scored against the team."""


class _Run:
    def __init__(self, config, call_model):
        self.config = config
        self.call_model = call_model
        self.calls = 0
        self.trace = []
        self.compliance = []  # (step, line, passed) for first-try outputs only

    def log(self, text=""):
        self.trace.append(text)

    def call(self, label, prompt):
        if self.calls >= CALL_BUDGET:
            self.log(f"!! call budget of {CALL_BUDGET} used up; skipping {label}")
            raise BudgetExhausted()
        self.calls += 1
        try:
            reply = self.call_model(prompt) or ""
        except ModelUnavailable:
            raise
        except Exception as e:  # any other failed call still counts, and reads as an empty reply
            self.log(f"!! call {self.calls} ({label}) failed: {e}")
            reply = ""
        self.log(f"[call {self.calls}] {label}")
        for line in reply.strip().splitlines() or ["(empty reply)"]:
            self.log(f"    | {line}")
        return reply

    def first_try(self, step, results):
        self.compliance.extend((step, line, ok) for line, ok in results)

    def prompt(self, skill, **values):
        text = self.config["skills"][skill]["instructions"]
        for key, value in values.items():
            text = text.replace("{" + key + "}", value)
        return text


def run_pipeline(config, tickets, call_model):
    run = _Run(config, call_model)
    skills = config["skills"]
    total = len(tickets)
    texts = {ticket["id"]: ticket["text"] for ticket in tickets}

    def chunk_tickets(chunk):
        return [{"id": ticket["id"], "text": texts[ticket["id"]]} for ticket in chunk]

    # split
    size = config["chunk_size"]
    chunks = [tickets[i:i + size] for i in range(0, total, size)]
    run.log(f"== split: {total} tickets -> {len(chunks)} chunk(s) of up to {size}")
    run.log(f"   worst case {config['worst_case_calls']} calls (budget {CALL_BUDGET})")

    # normalize
    if "normalize" in skills:
        run.log("")
        run.log("== normalize")
        for index, chunk in enumerate(chunks, 1):
            try:
                reply = run.call(f"normalize chunk {index}", run.prompt("normalize", tickets=format_tickets(chunk)))
            except BudgetExhausted:
                break
            new_texts, results, dropped = parse_normalize(reply, chunk)
            run.first_try("normalize", results)
            texts.update(new_texts)
            for line in dropped:
                run.log(f"   dropped (wrong ID, order or pattern): {line[:100]}")
            kept_original = len(chunk) - len(new_texts)
            if kept_original:
                run.log(f"   {kept_original} ticket(s) kept their original text")

    # triage
    run.log("")
    run.log("== triage")
    triage_replies = {}
    for index, chunk in enumerate(chunks, 1):
        try:
            triage_replies[index] = run.call(f"triage chunk {index}", run.prompt("triage", tickets=format_tickets(chunk_tickets(chunk))))
        except BudgetExhausted:
            run.log(f"   chunk {index} was never triaged and contributes nothing")

    # verify
    run.log("")
    run.log("== verify")
    urgent, review = {}, set()
    for index, chunk in enumerate(chunks, 1):
        if index not in triage_replies:
            continue
        chunk_ids = [ticket["id"] for ticket in chunk]
        chunk_text = format_tickets(chunk_tickets(chunk))
        base_prompt = run.prompt("triage", tickets=chunk_text)
        reply = triage_replies[index]
        _, _, first_results = check_triage(reply, chunk_ids)
        run.first_try("triage", first_results)
        checked_once = False
        attempt = 0

        while True:
            chunk_urgent, violations, _ = check_triage(reply, chunk_ids)
            if violations:
                run.log(f"   chunk {index}: check_triage found {len(violations)} violation(s)")
                feedback = format_violations(violations)
                for line in feedback.splitlines():
                    run.log(f"     {line}")
                failed_ids = {v["ticket"] for v in violations if v["ticket"]}
            else:
                run.log(f"   chunk {index}: check_triage passed ({len(chunk_urgent)} urgent)")
                try:
                    checker_reply = run.call(
                        f"checker chunk {index}" + (f" (after retry {attempt})" if attempt else ""),
                        run.prompt("checker", tickets=chunk_text, triage_output=reply.strip()),
                    )
                except BudgetExhausted:
                    run.log(f"   chunk {index}: accepted unchecked")
                    urgent.update(chunk_urgent)
                    break
                verdict, disputed, feedback, results, dropped = parse_checker(checker_reply, chunk_ids)
                if not checked_once:
                    run.first_try("checker", results)
                    checked_once = True
                for line in dropped:
                    run.log(f"   dropped checker line: {line[:100]}")
                if verdict != "FAIL":
                    if verdict is None:
                        run.log(f"   chunk {index}: checker verdict unreadable, treated as PASS")
                    else:
                        run.log(f"   chunk {index}: PASS")
                    urgent.update(chunk_urgent)
                    break
                run.log(f"   chunk {index}: FAIL, disputes {', '.join(disputed) or 'no readable ticket IDs'}")
                failed_ids = set(disputed)

            if attempt >= config["max_retries"]:
                run.log(f"   chunk {index}: still failing after {attempt} retr{'y' if attempt == 1 else 'ies'}; "
                        f"to review: {', '.join(sorted(failed_ids, key=ticket_sort_key)) or 'none'}")
                review |= failed_ids
                urgent.update({t: entry for t, entry in chunk_urgent.items() if t not in failed_ids})
                break

            attempt += 1
            try:
                reply = run.call(
                    f"triage chunk {index} (retry {attempt})",
                    RETRY_TEMPLATE.format(prompt=base_prompt, previous=reply.strip() or "(empty)", feedback=feedback or "(no details given)"),
                )
            except BudgetExhausted:
                review |= failed_ids
                urgent.update({t: entry for t, entry in chunk_urgent.items() if t not in failed_ids})
                break

    # route
    run.log("")
    run.log("== route")
    routes = {}
    urgent_ids = sorted(urgent, key=ticket_sort_key)
    if urgent_ids:
        urgent_text = "\n".join(f"{t}: {texts[t]}" for t in urgent_ids)
        try:
            reply = run.call(f"router ({len(urgent_ids)} tickets)", run.prompt("route", urgent_tickets=urgent_text))
            routes, results, dropped = parse_router(reply, urgent_ids)
            run.first_try("router", results)
            for line in dropped:
                run.log(f"   dropped router line: {line[:100]}")
        except BudgetExhausted:
            pass
        unrouted = [t for t in urgent_ids if t not in routes]
        if unrouted:
            run.log(f"   unrouted: {', '.join(unrouted)}")
    else:
        run.log("   no urgent tickets; router not called")

    # render_report
    report = render_report(urgent, routes, review, total)
    run.log("")
    run.log("== render_report")
    for line in report.splitlines():
        run.log(f"   {line}")
    passed = sum(1 for _, _, ok in run.compliance if ok)
    run.log("")
    run.log(f"== {run.calls} model call(s); {passed}/{len(run.compliance)} first-try output lines matched their contract")

    return {
        "report": report,
        "urgent": urgent,
        "routes": routes,
        "review": review,
        "calls": run.calls,
        "compliance": run.compliance,
        "trace": "\n".join(run.trace) + "\n",
    }
