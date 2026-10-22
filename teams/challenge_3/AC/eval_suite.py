"""Challenge 3 evaluation suite. Replace the stubs with your hybrid evaluator.

Each check function receives one trace dict and must return a bool
(True = the trace passes that check). See the Challenge 3 section of the
README for the trace fields. Don't make network calls: the grader runs
JUDGE_PROMPT with its own judge model on each trace.
"""

JUDGE_PROMPT = ""  # Your LLM judge rubric: explicit criteria for accuracy, safety and tone.


def check_turn_limit(trace):
    raise NotImplementedError("Implement the turn limit check")


def check_required_tools(trace):
    raise NotImplementedError("Implement the required conversion-tool check")


def check_allergens(trace):
    raise NotImplementedError("Implement the deterministic allergen check")
