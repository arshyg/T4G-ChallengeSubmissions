"""Checks a team folder the way the grader will, without calling a model or
needing an API key.

    python validate_submission.py teams/challenge_1b/<your-team>
    python validate_submission.py teams/challenge_1/<your-team>

A folder with pipeline.yaml is checked as a pipeline (files present, steps
in order, placeholders, worst case within the call budget); otherwise its
skill.md is checked. Prints OK or the reason, and exits 1 on failure.
"""

import os
import sys

from pipeline import PipelineError, load_pipeline
from skills import load_skill, validate_skill


def validate(team_dir):
    """Returns (ok, message)."""
    if not os.path.isdir(team_dir):
        return False, f"{team_dir} is not a folder"
    if os.path.isfile(os.path.join(team_dir, "pipeline.yaml")):
        try:
            config = load_pipeline(team_dir)
        except PipelineError as e:
            return False, str(e)
        return True, (f"pipeline is valid: chunk_size {config['chunk_size']}, max_retries {config['max_retries']}, "
                      f"worst case {config['worst_case_calls']} calls per batch")
    skill_path = os.path.join(team_dir, "skill.md")
    if not os.path.isfile(skill_path):
        return False, "no skill.md or pipeline.yaml in the team folder"
    ok, error = validate_skill(load_skill(skill_path))
    return ok, "skill.md is valid" if ok else error


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip())
        sys.exit(2)
    ok, message = validate(sys.argv[1])
    print(("OK: " if ok else "INVALID: ") + message)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
