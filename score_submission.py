import argparse
import csv
import glob
import hashlib
import os

import yaml

import graders
from constants import DEFAULT_CASE_POINTS, DIFFICULTY_POINTS, MODEL, REQUIRED_SKILL_FIELDS, client
from graders import GRADERS


def describe_yaml_error(error):
    # Students hit this most often from an unquoted ": " inside a value, or
    # instructions text that isn't indented under "instructions: |", so point
    # at the exact spot instead of surfacing a raw PyYAML traceback.
    mark = getattr(error, "problem_mark", None)
    problem = getattr(error, "problem", None) or str(error)
    location = f" at line {mark.line + 1}, column {mark.column + 1}" if mark else ""
    return (
        f"skill.md is not valid YAML{location}: {problem}. "
        "Put long or colon-containing values in an indented block under \"key: |\" or \"key: >\"."
    )


def load_skill(skill_path):
    parse_error = None
    try:
        with open(skill_path, "r") as f:
            skill = yaml.safe_load(f)
    except yaml.YAMLError as e:
        skill = None
        parse_error = describe_yaml_error(e)

    if skill is not None and not isinstance(skill, dict):
        parse_error = "skill.md must be a YAML mapping with name, description, and instructions keys"
        skill = None

    skill_dir = os.path.dirname(skill_path)
    team_name = os.path.basename(os.path.normpath(skill_dir)) if skill_dir else "Unknown Team"

    return {
        "team_name": team_name,
        "instructions": skill.get("instructions", "") if skill else "",
        "raw": skill or {},
        "parse_error": parse_error,
    }


def validate_skill(skill):
    if skill["parse_error"]:
        return False, skill["parse_error"]
    for field in REQUIRED_SKILL_FIELDS:
        if not skill["raw"].get(field):
            return False, f"Missing required field: {field}"
    return True, None


def discover_case_files(cases_path):
    if os.path.isfile(cases_path):
        return [cases_path]
    return sorted(glob.glob(os.path.join(cases_path, "*.yaml")))


def load_cases(cases_path):
    cases = []
    for case_file in discover_case_files(cases_path):
        with open(case_file, "r") as f:
            case = yaml.safe_load(f)
        if not case:
            print(f"Skipping empty/invalid case file: {case_file}")
            continue
        cases.append(case)
    return cases


def graders_fingerprint():
    hasher = hashlib.sha256()
    graders_dir = os.path.dirname(graders.__file__)
    for path in sorted(glob.glob(os.path.join(graders_dir, "*.py"))):
        with open(path, "rb") as f:
            hasher.update(f.read())
    return hasher.hexdigest()


def compute_state_hash(skill_path, cases_path):
    hasher = hashlib.sha256()
    with open(skill_path, "rb") as f:
        hasher.update(f.read())
    for case_file in discover_case_files(cases_path):
        with open(case_file, "rb") as f:
            hasher.update(f.read())
    hasher.update(graders_fingerprint().encode())
    return hasher.hexdigest()


def call_model(prompt):
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=32768,
    )
    return response.choices[0].message.content


def score_case(case, skill):
    grader = GRADERS.get(case.get("category"))
    if grader is None:
        raise ValueError(f"no grader registered for category '{case.get('category')}'")

    prompt = grader.build_prompt(case, skill["instructions"])

    trials = case.get("trials", 1)
    best_fraction = 0.0
    best_response = ""
    for _ in range(trials):
        try:
            response_text = call_model(prompt)
        except Exception as e:
            print(f"Trial failed for case {case.get('case_id')}: {e}")
            continue
        fraction = grader.score(case, response_text)
        if fraction >= best_fraction:
            best_fraction = fraction
            best_response = response_text
    return best_fraction, best_response


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--skill", required=True)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--out", default="results")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-grade even if the skill, cases, and grader code are unchanged since the last run",
    )
    args = parser.parse_args()

    skill = load_skill(args.skill)
    state_hash = compute_state_hash(args.skill, args.cases)
    hash_path = os.path.join(args.out, f"{skill['team_name']}.hash")

    if not args.force and os.path.exists(hash_path):
        with open(hash_path) as f:
            if f.read().strip() == state_hash:
                print(f"No change to skill/cases/grading code for {skill['team_name']}, skipping (use --force to re-grade)")
                return

    os.makedirs(args.out, exist_ok=True)

    def save_hash():
        with open(hash_path, "w") as f:
            f.write(state_hash)

    is_valid, error = validate_skill(skill)
    invalid_path = os.path.join(args.out, f"{skill['team_name']}.invalid")
    output_path = os.path.join(args.out, f"{skill['team_name']}.csv")

    # Clear the previous run's opposite outcome, so a since-fixed skill isn't
    # still reported invalid (and a now-broken one doesn't keep its old score).
    stale_path = output_path if not is_valid else invalid_path
    if os.path.exists(stale_path):
        os.remove(stale_path)

    if not is_valid:
        with open(invalid_path, "w") as f:
            f.write(error)
        print(f"Skill validation failed: {error}")
        save_hash()
        return

    cases = load_cases(args.cases)
    rows = []

    for case in cases:
        if case.get("practice"):
            print(f"Skipping practice case {case['case_id']} (not graded)")
            continue

        max_points = DIFFICULTY_POINTS.get(case.get("difficulty"), DEFAULT_CASE_POINTS)

        try:
            best_fraction, best_response = score_case(case, skill)
        except Exception as e:
            print(f"Error processing case {case['case_id']}: {e}")
            rows.append({"case_id": case["case_id"], "score": 0, "max_points": max_points, "response": ""})
            continue

        rows.append({
            "case_id": case["case_id"],
            "score": round(best_fraction * max_points),
            "max_points": max_points,
            "response": best_response,
        })

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["case_id", "score", "max_points", "response"])
        writer.writeheader()
        writer.writerows(rows)

    save_hash()
    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
