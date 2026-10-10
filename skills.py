"""Loading and validating a single skill file (shared by the single-skill
scorer and the challenge_1b pipeline runner)."""

import os

import yaml

# Kept here rather than in constants.py so validating a submission doesn't
# need an API key (constants.py builds the model client on import).
REQUIRED_SKILL_FIELDS = ["name", "description", "instructions"]


def describe_yaml_error(error, filename="skill.md"):
    # Students hit this most often from an unquoted ": " inside a value, or
    # instructions text that isn't indented under "instructions: |", so point
    # at the exact spot instead of surfacing a raw PyYAML traceback.
    mark = getattr(error, "problem_mark", None)
    problem = getattr(error, "problem", None) or str(error)
    location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
    return (
        f"{filename} is not valid YAML{location}: {problem}. "
        "Put long or colon-containing values in an indented block under \"key: |\" or \"key: >\"."
    )


def load_skill(skill_path):
    filename = os.path.basename(skill_path)
    parse_error = None
    try:
        with open(skill_path, "r") as f:
            skill = yaml.safe_load(f)
    except yaml.YAMLError as e:
        skill = None
        parse_error = describe_yaml_error(e, filename)

    if skill is not None and not isinstance(skill, dict):
        parse_error = f"{filename} must be a YAML mapping with name, description, and instructions keys"
        skill = None

    skill_dir = os.path.dirname(skill_path)
    team_name = os.path.basename(os.path.normpath(skill_dir)) if skill_dir else "Unknown Team"

    return {
        "team_name": team_name,
        "filename": filename,
        "instructions": skill.get("instructions", "") if skill else "",
        "raw": skill or {},
        "parse_error": parse_error,
    }


def validate_skill(skill, required_placeholders=()):
    if skill["parse_error"]:
        return False, skill["parse_error"]
    for field in REQUIRED_SKILL_FIELDS:
        if not skill["raw"].get(field):
            return False, f"{skill['filename']}: missing required field: {field}"
    for placeholder in required_placeholders:
        if placeholder not in skill["instructions"]:
            return False, f"{skill['filename']}: instructions must contain the literal placeholder {placeholder}"
    return True, None
