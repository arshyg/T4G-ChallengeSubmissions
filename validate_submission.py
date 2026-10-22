"""Checks a team folder the way the grader will, without calling a model or
needing an API key.

    python validate_submission.py teams/challenge_1b/<your-team>
    python validate_submission.py teams/challenge_1/<your-team>
    python validate_submission.py teams/challenge_3/<your-team>

A folder with pipeline.yaml is checked as a pipeline (files present, steps
in order, placeholders, worst case within the call budget); otherwise its
skill.md is checked. A challenge_3 folder is checked without running any
of its code. Prints OK or the reason, and exits 1 on failure.
"""

import ast
import os
import sys

import yaml

from pipeline import PipelineError, load_pipeline
from skills import load_skill, validate_skill


CH3_REQUIRED = {"eval_suite.py", "optimized_skill.md"}
CH3_OPTIONAL = {"diagnosis.md"}
CH3_CHECKS = ("check_turn_limit", "check_required_tools", "check_allergens")
CH3_TOOLS = {"inventory_lookup", "unit_convert"}


def _is_stub(func):
    for node in ast.walk(func):
        if isinstance(node, ast.Raise) and node.exc is not None:
            target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            if isinstance(target, ast.Name) and target.id == "NotImplementedError":
                return True
    return False


def validate_challenge_3(team_dir):
    """Reads eval_suite.py and optimized_skill.md without executing them."""
    names = {n for n in os.listdir(team_dir) if not n.startswith(".")}
    missing = CH3_REQUIRED - names
    if missing:
        return False, "missing " + ", ".join(sorted(missing))
    extra = names - CH3_REQUIRED - CH3_OPTIONAL
    if extra:
        return False, ("unexpected files: " + ", ".join(sorted(extra)) +
                       " (only eval_suite.py, optimized_skill.md and optionally diagnosis.md)")

    try:
        with open(os.path.join(team_dir, "eval_suite.py"), encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except SyntaxError as e:
        return False, f"eval_suite.py has a syntax error on line {e.lineno}: {e.msg}"
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for name in CH3_CHECKS:
        if name not in functions:
            return False, f"eval_suite.py needs a top-level function {name}(trace)"
        if not functions[name].args.args:
            return False, f"{name} must take one argument (the trace)"
        if _is_stub(functions[name]):
            return False, f"{name} still raises NotImplementedError from the template"
    prompts = [n for n in tree.body if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "JUDGE_PROMPT" for t in n.targets)]
    if not prompts:
        return False, "eval_suite.py needs a JUDGE_PROMPT string"
    try:
        value = ast.literal_eval(prompts[-1].value)
    except ValueError:
        value = None  # built with an expression; can only be checked when it runs
    if isinstance(value, str) and not value.strip():
        return False, "JUDGE_PROMPT is empty"
    if value is not None and not isinstance(value, str):
        return False, "JUDGE_PROMPT must be a string"

    with open(os.path.join(team_dir, "optimized_skill.md"), encoding="utf-8") as f:
        text = f.read()
    if text.startswith("---\n"):
        parts = text.split("---", 2)
        if len(parts) != 3:
            return False, "optimized_skill.md: the --- header is never closed"
        header, body = parts[1], parts[2]
    elif "# Instructions" in text:
        header, body = text.split("# Instructions", 1)
    else:
        return False, "optimized_skill.md needs a YAML header (name, description, tools) and then instructions"
    try:
        meta = yaml.safe_load(header)
    except yaml.YAMLError as e:
        return False, f"optimized_skill.md header isn't valid YAML: {e}"
    if not isinstance(meta, dict) or any(not meta.get(k) for k in ("name", "description", "tools")):
        return False, "optimized_skill.md header needs name, description and tools"
    tools = meta["tools"]
    if isinstance(tools, str):
        tools = [s.strip() for s in tools.split(",")]
    if not isinstance(tools, list) or set(tools) != CH3_TOOLS:
        return False, "optimized_skill.md tools must be exactly inventory_lookup and unit_convert"
    if not body.strip():
        return False, "optimized_skill.md has no instructions"
    return True, "challenge 3 submission is valid"


def validate(team_dir):
    """Returns (ok, message)."""
    if not os.path.isdir(team_dir):
        return False, f"{team_dir} is not a folder"
    if os.path.basename(os.path.dirname(os.path.normpath(team_dir))) == "challenge_3":
        return validate_challenge_3(team_dir)
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
