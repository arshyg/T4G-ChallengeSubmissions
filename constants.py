import os

from openai import OpenAI

USE_GEMINI_DIRECT = bool(os.environ.get("GEMINI_API_KEY"))

# BENCHMARK_MODEL lets you override the model without editing code.
# Google's own API uses names without the "google/" prefix.
MODEL = os.environ.get(
    "BENCHMARK_MODEL",
    "gemini-3.1-pro-preview" if USE_GEMINI_DIRECT else "google/gemini-3.1-pro-preview",
)
REQUIRED_SKILL_FIELDS = ["name", "description", "instructions"]

# Harder cases are worth fewer points: they're graded on softer signals
# (self-consistency, borderline classifications) so a partial-credit miss
# shouldn't swing the leaderboard as much as missing an easy case outright.
DIFFICULTY_POINTS = {
    "baseline": 25,
    "medium": 15,
    "hard": 5,
}
# Fallback for cases whose "difficulty" isn't one of the tiers above, so a
# new dataset that doesn't use baseline/medium/hard still scores instead of crashing.
DEFAULT_CASE_POINTS = 10

if USE_GEMINI_DIRECT:
    client = OpenAI(
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=os.environ["GEMINI_API_KEY"],
    )
else:
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.environ.get("OPENROUTER_API_KEY"),
    )
