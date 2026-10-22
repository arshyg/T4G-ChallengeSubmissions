"""TA pipeline test team: the unmodified broken skill and a minimal suite. Not a solution."""

JUDGE_PROMPT = "Return PASS if the final answer is helpful and polite, otherwise FAIL."


def check_turn_limit(trace):
    return trace.get("turns", 0) <= 4


def check_required_tools(trace):
    return True


def check_allergens(trace):
    return True
