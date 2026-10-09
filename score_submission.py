import argparse
import csv
import glob
import hashlib
import os
import sys
import time

import openai
import yaml

import graders
import pipeline
from constants import DEFAULT_CASE_POINTS, DIFFICULTY_POINTS, MODEL, client
from graders import GRADERS
from skills import load_skill, validate_skill


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
    # The pipeline runner and skill loader decide scores too, so a change to
    # either re-grades just like a grader change does.
    hasher = hashlib.sha256()
    code_paths = (
        glob.glob(os.path.join(os.path.dirname(graders.__file__), "*.py"))
        + glob.glob(os.path.join(os.path.dirname(pipeline.__file__), "*.py"))
        + [os.path.join(os.path.dirname(os.path.abspath(__file__)), "skills.py")]
    )
    for path in sorted(code_paths):
        with open(path, "rb") as f:
            hasher.update(f.read())
    return hasher.hexdigest()


def submission_files(submission_path):
    if os.path.isfile(submission_path):
        return [submission_path]
    return sorted(
        os.path.join(submission_path, name) for name in os.listdir(submission_path)
        if os.path.isfile(os.path.join(submission_path, name))
    )


def compute_state_hash(submission_path, cases_path):
    hasher = hashlib.sha256()
    for path in submission_files(submission_path):
        hasher.update(os.path.basename(path).encode())
        with open(path, "rb") as f:
            hasher.update(f.read())
    for case_file in discover_case_files(cases_path):
        with open(case_file, "rb") as f:
            hasher.update(f.read())
    hasher.update(graders_fingerprint().encode())
    return hasher.hexdigest()


# Overloaded / rate-limited providers (e.g. Gemini's free tier returning
# "503 high demand") usually recover within a minute or two, so wait and retry
# rather than recording the failure as a score of 0.
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
RETRY_DELAYS_SECONDS = [5, 15, 30, 60]


class ModelUnavailableError(Exception):
    """Every trial for a case failed to get a response from the model."""


def _is_retryable(error):
    if isinstance(error, (openai.APIConnectionError, openai.APITimeoutError)):
        return True
    if isinstance(error, openai.APIStatusError) and error.status_code in RETRYABLE_STATUS_CODES:
        # Gemini's "429 ... limit: 0" means the model isn't on the free tier at
        # all; waiting won't help.
        return "limit: 0" not in str(error)
    return False


def call_model(prompt):
    for attempt, delay in enumerate([0] + RETRY_DELAYS_SECONDS):
        if delay:
            print(f"  Model unavailable, retrying in {delay}s ({attempt}/{len(RETRY_DELAYS_SECONDS)})...")
            time.sleep(delay)
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.choices[0].message.content
        except Exception as e:
            if not _is_retryable(e) or attempt == len(RETRY_DELAYS_SECONDS):
                raise
            print(f"  {e}")


def pipeline_call_model(prompt):
    # Retries are exhausted by now. An outage aborts the batch (so it isn't
    # scored); any other error reads as an empty reply in the trace.
    try:
        return call_model(prompt)
    except Exception as e:
        if _is_retryable(e):
            raise pipeline.ModelUnavailable(str(e))
        raise


def score_case(case, skill):
    grader = GRADERS.get(case.get("category"))
    if grader is None:
        raise ValueError(f"no grader registered for category '{case.get('category')}'")

    prompt = grader.build_prompt(case, skill["instructions"])

    trials = case.get("trials", 1)
    best_fraction = 0.0
    best_response = ""
    last_error = None
    succeeded = 0
    for _ in range(trials):
        try:
            response_text = call_model(prompt)
        except Exception as e:
            print(f"Trial failed for case {case.get('case_id')}: {e}")
            last_error = e
            continue
        succeeded += 1
        fraction = grader.score(case, response_text)
        if fraction >= best_fraction:
            best_fraction = fraction
            best_response = response_text
    if succeeded == 0:
        raise ModelUnavailableError(str(last_error))
    return best_fraction, best_response


PIPELINE_COMPONENTS = ["classification", "routing", "efficiency", "compliance"]


def score_pipeline_case(case, config, trace_dir):
    grader = GRADERS.get(case.get("category"))
    if grader is None or not getattr(grader, "PIPELINE", False):
        raise ValueError(f"no pipeline grader registered for category '{case.get('category')}'")

    try:
        run = pipeline.run_pipeline(config, case["tickets"], pipeline_call_model)
    except pipeline.ModelUnavailable as e:
        raise ModelUnavailableError(str(e))
    fraction, components = grader.score_run(case, run)

    os.makedirs(trace_dir, exist_ok=True)
    with open(os.path.join(trace_dir, f"{case['case_id']}.txt"), "w") as f:
        f.write(f"# {config['team_name']} on {case['case_id']}: {fraction:.1%}\n")
        f.write("# " + ", ".join(f"{key} {value:.1%}" for key, value in components.items()) + "\n\n")
        f.write(run["trace"])
    return fraction, components, run


def main():
    parser = argparse.ArgumentParser()
    submission = parser.add_mutually_exclusive_group(required=True)
    submission.add_argument("--skill", help="A single skill.md (challenge_1)")
    submission.add_argument("--pipeline", help="A team folder with pipeline.yaml (challenge_1b)")
    parser.add_argument("--cases", required=True)
    parser.add_argument("--out", default="results")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-grade even if the skill, cases, and grader code are unchanged since the last run",
    )
    args = parser.parse_args()

    if args.pipeline:
        team_name = os.path.basename(os.path.normpath(args.pipeline))
        try:
            config = pipeline.load_pipeline(args.pipeline)
            is_valid, error = True, None
        except pipeline.PipelineError as e:
            is_valid, error = False, str(e)
    else:
        skill = load_skill(args.skill)
        team_name = skill["team_name"]
        is_valid, error = validate_skill(skill)

    state_hash = compute_state_hash(args.pipeline or args.skill, args.cases)
    hash_path = os.path.join(args.out, f"{team_name}.hash")

    if not args.force and os.path.exists(hash_path):
        with open(hash_path) as f:
            if f.read().strip() == state_hash:
                print(f"No change to submission/cases/grading code for {team_name}, skipping (use --force to re-grade)")
                return

    os.makedirs(args.out, exist_ok=True)

    def save_hash():
        with open(hash_path, "w") as f:
            f.write(state_hash)

    invalid_path = os.path.join(args.out, f"{team_name}.invalid")
    output_path = os.path.join(args.out, f"{team_name}.csv")

    # Clear the previous run's opposite outcome, so a since-fixed skill isn't
    # still reported invalid (and a now-broken one doesn't keep its old score).
    stale_path = output_path if not is_valid else invalid_path
    if os.path.exists(stale_path):
        os.remove(stale_path)

    if not is_valid:
        with open(invalid_path, "w") as f:
            f.write(error)
        print(f"Submission validation failed: {error}")
        save_hash()
        return

    cases = load_cases(args.cases)
    rows = []
    unavailable_cases = []

    for case in cases:
        if case.get("practice"):
            print(f"Skipping practice case {case['case_id']} (not graded)")
            continue

        max_points = case.get("points", DIFFICULTY_POINTS.get(case.get("difficulty"), DEFAULT_CASE_POINTS))

        if args.pipeline:
            try:
                fraction, components, run = score_pipeline_case(case, config, os.path.join(args.out, f"{team_name}.traces"))
            except ModelUnavailableError:
                unavailable_cases.append(case["case_id"])
                continue
            except Exception as e:
                print(f"Error processing case {case['case_id']}: {e}")
                rows.append({"case_id": case["case_id"], "score": 0, "max_points": max_points, "response": ""})
                continue
            row = {
                "case_id": case["case_id"],
                "score": round(fraction * max_points),
                "max_points": max_points,
                "response": run["report"],
                "calls": run["calls"],
            }
            row.update({key: round(components[key], 4) for key in PIPELINE_COMPONENTS})
            rows.append(row)
            continue

        try:
            best_fraction, best_response = score_case(case, skill)
        except ModelUnavailableError:
            unavailable_cases.append(case["case_id"])
            continue
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

    # A model outage isn't the skill's fault: don't record a 0 or cache this
    # state, so the next run (or tomorrow's scheduled run) grades it for real.
    if unavailable_cases:
        print(
            f"\nCouldn't get a response from the model for {', '.join(unavailable_cases)}, "
            "so nothing was scored or saved. The model is probably overloaded or your API "
            "key/credits have a problem; check the errors above and run again in a minute."
        )
        sys.exit(2)

    fieldnames = ["case_id", "score", "max_points", "response"]
    if args.pipeline:
        fieldnames += PIPELINE_COMPONENTS + ["calls"]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    save_hash()
    print(f"Wrote {len(rows)} rows to {output_path}")


if __name__ == "__main__":
    main()
