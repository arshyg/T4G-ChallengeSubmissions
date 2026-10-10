"""Reading and validating a team's pipeline.yaml (challenge_1b).

This is the same check the submission PR gets: a missing file, a missing or
out-of-order step, or a worst case over the call budget rejects the
pipeline with a one-line reason.
"""

import math
import os

import yaml

from skills import describe_yaml_error, load_skill, validate_skill

CALL_BUDGET = 20
BATCH_SIZE = 150
CHUNK_SIZE_RANGE = (10, 150)
MAX_RETRIES_RANGE = (1, 2)

# Step name -> (required?, skill placeholders it must contain)
STEP_ORDER = ["split", "normalize", "triage", "verify", "route", "render_report"]
REQUIRED_STEPS = {"split", "triage", "verify", "route", "render_report"}
PLACEHOLDERS = {
    "normalize": ["{tickets}"],
    "triage": ["{tickets}"],
    "checker": ["{tickets}", "{triage_output}"],
    "route": ["{urgent_tickets}"],
}


class PipelineError(ValueError):
    pass


def worst_case_calls(chunk_size, max_retries, uses_normalize, batch_size=BATCH_SIZE):
    chunks = math.ceil(batch_size / chunk_size)
    return chunks * 2 * (max_retries + 1) + 1 + (chunks if uses_normalize else 0)


def _parse_step(entry):
    # "render_report" (bare string) or {"triage": "triage.md"} (one-key mapping).
    if isinstance(entry, str):
        return entry, None
    if isinstance(entry, dict) and len(entry) == 1:
        return next(iter(entry.items()))
    raise PipelineError(f"pipeline.yaml: each step must be a name or a one-key mapping, got {entry!r}")


def _int_in_range(value, low, high, label):
    if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
        raise PipelineError(f"pipeline.yaml: {label} must be a whole number from {low} to {high}, got {value!r}")
    return value


def _load_step_skill(team_dir, filename, placeholders, step):
    if not isinstance(filename, str) or os.path.basename(filename) != filename or not filename.endswith(".md"):
        raise PipelineError(f"pipeline.yaml: {step} must name a .md file in your team folder, got {filename!r}")
    path = os.path.join(team_dir, filename)
    if not os.path.isfile(path):
        raise PipelineError(f"{filename} is missing (referenced by the {step} step)")
    skill = load_skill(path)
    is_valid, error = validate_skill(skill, placeholders)
    if not is_valid:
        raise PipelineError(error)
    return skill


def load_pipeline(team_dir):
    """Returns the parsed pipeline config, or raises PipelineError with the reason."""
    pipeline_path = os.path.join(team_dir, "pipeline.yaml")
    if not os.path.isfile(pipeline_path):
        raise PipelineError("pipeline.yaml is missing")
    try:
        with open(pipeline_path) as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise PipelineError(describe_yaml_error(e, "pipeline.yaml"))
    if not isinstance(raw, dict) or not isinstance(raw.get("steps"), list):
        raise PipelineError("pipeline.yaml must be a mapping with a 'steps' list")

    steps = [_parse_step(entry) for entry in raw["steps"]]
    names = [name for name, _ in steps]

    unknown = [name for name in names if name not in STEP_ORDER]
    if unknown:
        raise PipelineError(f"pipeline.yaml: unknown step '{unknown[0]}' (allowed: {', '.join(STEP_ORDER)})")
    duplicated = sorted({name for name in names if names.count(name) > 1})
    if duplicated:
        raise PipelineError(f"pipeline.yaml: step '{duplicated[0]}' appears more than once")
    missing = [name for name in STEP_ORDER if name in REQUIRED_STEPS and name not in names]
    if missing:
        raise PipelineError(f"pipeline.yaml: required step '{missing[0]}' is missing")
    if names != [name for name in STEP_ORDER if name in names]:
        raise PipelineError(f"pipeline.yaml: steps are out of order; expected {' -> '.join(n for n in STEP_ORDER if n in names)}")

    config = dict(steps)

    split = config["split"]
    if not isinstance(split, dict) or "chunk_size" not in split:
        raise PipelineError("pipeline.yaml: split needs {chunk_size: <n>}")
    chunk_size = _int_in_range(split["chunk_size"], *CHUNK_SIZE_RANGE, "split.chunk_size")

    verify = config["verify"]
    if not isinstance(verify, dict) or "checker" not in verify:
        raise PipelineError("pipeline.yaml: verify needs {checker: checker.md, max_retries: <n>}")
    max_retries = _int_in_range(verify.get("max_retries"), *MAX_RETRIES_RANGE, "verify.max_retries")

    if config["render_report"] is not None:
        raise PipelineError("pipeline.yaml: render_report is a provided script and takes no settings")

    skills = {
        "triage": _load_step_skill(team_dir, config["triage"], PLACEHOLDERS["triage"], "triage"),
        "checker": _load_step_skill(team_dir, verify["checker"], PLACEHOLDERS["checker"], "verify.checker"),
        "route": _load_step_skill(team_dir, config["route"], PLACEHOLDERS["route"], "route"),
    }
    uses_normalize = "normalize" in config
    if uses_normalize:
        skills["normalize"] = _load_step_skill(team_dir, config["normalize"], PLACEHOLDERS["normalize"], "normalize")

    worst = worst_case_calls(chunk_size, max_retries, uses_normalize)
    if worst > CALL_BUDGET:
        raise PipelineError(
            f"pipeline.yaml: worst case is {worst} calls per batch, over the {CALL_BUDGET}-call budget "
            f"(chunk_size {chunk_size}, max_retries {max_retries}{', with normalize' if uses_normalize else ''})"
        )

    return {
        "team_name": os.path.basename(os.path.normpath(team_dir)),
        "chunk_size": chunk_size,
        "max_retries": max_retries,
        "skills": skills,
        "worst_case_calls": worst,
    }
