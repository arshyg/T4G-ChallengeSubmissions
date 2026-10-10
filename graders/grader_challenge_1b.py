"""Grader for challenge_1b (the ticket-triage pipeline).

Scores one pipeline run on one batch, entirely from the run's results and
trace: no LLM judges anything here.

  classification  +1 urgent listed, +0.5 urgent sent to review,
                  -0.5 routine listed, -0.1 routine sent to review;
                  divided by the batch's urgent count, floored at 0
  routing         share of truly urgent listed tickets routed to a team
                  the ticket's labels accept
  efficiency      1.0 at <= 8 calls, falling linearly to 0 at 20
  compliance      share of first-try skill output lines that matched
                  their contract
"""

PIPELINE = True

FULL_CREDIT_CALLS = 8
ZERO_CREDIT_CALLS = 20


def _classification(urgent_ids, review_ids, truly_urgent):
    if not truly_urgent:
        return 1.0 if not urgent_ids else 0.0
    points = 0.0
    for ticket in urgent_ids:
        points += 1.0 if ticket in truly_urgent else -0.5
    for ticket in review_ids:
        points += 0.5 if ticket in truly_urgent else -0.1
    return max(0.0, min(1.0, points / len(truly_urgent)))


def _routing(routes, urgent_ids, truly_urgent, accepted_teams):
    correct_listed = [t for t in urgent_ids if t in truly_urgent]
    if not correct_listed:
        return 0.0
    hits = sum(1 for t in correct_listed if routes.get(t) in accepted_teams.get(t, ["other"]))
    return hits / len(correct_listed)


def _efficiency(calls):
    if calls <= FULL_CREDIT_CALLS:
        return 1.0
    return max(0.0, (ZERO_CREDIT_CALLS - calls) / (ZERO_CREDIT_CALLS - FULL_CREDIT_CALLS))


def _compliance(lines):
    if not lines:
        return 1.0
    return sum(1 for _, _, ok in lines if ok) / len(lines)


def score_run(case, run):
    """Returns (weighted fraction in [0, 1], {component: fraction})."""
    ground_truth = case["ground_truth"]
    truly_urgent = set(ground_truth["urgent_ids"])
    accepted_teams = ground_truth.get("teams", {})
    urgent_ids = set(run["urgent"])
    review_ids = set(run["review"]) - urgent_ids

    components = {
        "classification": _classification(urgent_ids, review_ids, truly_urgent),
        "routing": _routing(run["routes"], urgent_ids, truly_urgent, accepted_teams),
        "efficiency": _efficiency(run["calls"]),
        "compliance": _compliance(run["compliance"]),
    }
    weights = case["grading_weights"]
    return sum(weights[key] * components[key] for key in weights), components
