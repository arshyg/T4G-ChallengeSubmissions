# T4G Challenge Submissions

Write a prompt ("skill") for a challenge, test it locally, then submit it by
pull request. Once a day an automated grader runs every submitted skill
against that challenge's graded test cases and updates the leaderboard.

## Layout

```
teams/<challenge>/_template/           # copy this to start
teams/<challenge>/<your-team>/          # your submission (skill.md, or a pipeline for challenge_1b)
test_cases/<challenge>/practice*.yaml   # practice cases you can test against
graders/                                # the exact scoring logic used for real grading
pipeline/                               # challenge_1b pipeline runner and its provided scripts
challenge_4/                            # Challenge 4 starter kit: Orca backend, archive, MCP tools
validate_submission.py                  # checks your team folder the way the grader will
score_submission.py, run_all.py, ...    # the grading harness
bin/benchmark.js                        # local practice runner (npm run benchmark)
```

The graded cases use the same format and scoring as the practice cases,
with different tickets.

## 1. Write your skill

1. Fork this repo and clone your fork.
2. Copy the challenge's template into a folder named after your team:
   ```
   cp -r teams/challenge_1/_template teams/challenge_1/<your-team>
   ```
   Team names may only use letters, numbers, `-`, and `_`. The folder name is
   the name shown on the leaderboard.
3. Edit `teams/<challenge>/<your-team>/skill.md`. It's YAML and needs
   `name`, `description`, and `instructions`. `instructions` is your prompt
   and **must** contain the challenge's placeholder (see the challenge
   section below): the grader replaces it with the test data before sending
   your prompt to the model.

## 2. Practice locally (doesn't affect the leaderboard)

Needs Node.js, Python 3, and a free Gemini API key from [Google AI Studio](https://aistudio.google.com) (Get API key → Create API key). Practice runs use the free `gemini-3.5-flash` model; the official leaderboard is scored centrally on Gemini 3.1 Pro, so practice scores may differ.

```
npm install
GEMINI_API_KEY=... npm run benchmark -- --skill teams/challenge_1/<your-team>/skill.md --challenge challenge_1
```

For Challenge 1b, pass your team folder instead:

```
GEMINI_API_KEY=... npm run benchmark -- --pipeline teams/challenge_1b/<your-team> --challenge challenge_1b
```

This scores your skill on the practice cases using the same model and
grader as the real run. The first run sets up a local Python environment
automatically. Re-running with nothing changed is free; add `--force` to re-grade anyway.

## 3. Submit

Commit **only** files inside your team folder, push to your fork, and open
a pull request into this repo's `main` branch. Use one PR per challenge:

- Challenge 1: `teams/challenge_1/<your-team>/skill.md`
- Challenge 1b: `teams/challenge_1b/<your-team>/`, containing `pipeline.yaml`,
  `triage.md`, `checker.md`, and `router.md`, plus `normalize.md` if your
  pipeline uses it. Use the same team name as in Challenge 1.
- Challenge 3: `teams/challenge_3/<your-team>/`, containing `eval_suite.py`
  and `optimized_skill.md` (plus `diagnosis.md` if you want). Same team name.
- Challenge 4: `teams/challenge_4/<your-team>/`, containing `mcp_server.py`
  and `skill.md` (plus `reflection.md` if you want). Same team name.

Before you open the PR, run the same check the merge uses (no API key needed):

```
python validate_submission.py teams/<challenge>/<your-team>
```

Submission PRs are merged on a schedule once the deadline passes, then once
a day, so other teams can't read your files early. A PR is merged only if:

- every file it changes is inside one team folder, `teams/<challenge>/<your-team>/`
- for Challenge 1b, 3 and 4, the folder passes `validate_submission.py`

A PR that changes anything outside your team folder is left for a TA to
review. A Challenge 1b, 3 or 4 PR that fails the check stays open with a comment
explaining why. Fix it and push to the same PR.

To update your submission later, open a new PR that edits the same files.
Your best score across all days counts. Submitted skills are public, so
other teams can read yours once it's merged.

---

## Challenge 1: Ticket triage

**Placeholder:** `{tickets}`

Your skill receives a batch of about 75 real customer-support tickets from
EuroChef+, a cooking-video streaming service. Each ticket is one line,
`T<n>: <message>`. Your skill must find the urgent ones.

**Required output** (nothing else):

```
- T4: Charged twice this month and wants the duplicate refunded. Next action: refund the duplicate charge.
- T17: Live session fails with error 503. Next action: escalate to the streaming on-call team.
2 of 75 tickets required urgent action.
```

- One markdown bullet per urgent ticket: its ID, a one-sentence summary
  (under 20 words), and a suggested next action. Mention only that ticket's
  own ID in its bullet.
- Don't list routine tickets.
- Final line: `X of N tickets required urgent action.` where N is the number
  of tickets given and X is the number of bullets you wrote.

**Scoring.** Your skill runs once on each of 3 graded batches (74–76
tickets each, about 16 urgent). Each batch is scored out of 10:

| Part | Weight | What's checked |
|------|-------:|----------------|
| Classification | 60% | +1 for each truly urgent ticket you list, −0.5 for each routine ticket you list, divided by the number of urgent tickets |
| Format | 20% | the last line is the count line (10%), and every other line is a bullet (10%) |
| Count | 20% | X on the count line equals the number of bullets |

Your score is the total across the 3 batches as a percentage. "Urgent" is
defined by the dataset's own labels; `test_cases/challenge_1/practice_batch.yaml`
has 76 labeled tickets (`ground_truth.urgent_ids_definite`) you can study.
The exact rules are in `graders/grader_challenge_1.py`.

Data: [EuroChef+ Customer Support Messages](https://huggingface.co/datasets/BenTouss/eurochef-cs)
(English tickets only).

---

## Challenge 1b: Ticket triage pipeline

Turn your Challenge 1 skill into a pipeline of small skills. It triages
150 mixed-language tickets (English, French, Dutch and German), routes each
urgent one to a team, and stays within **20 model calls per batch**.

**Your folder:** `teams/challenge_1b/<your-team>/`. Copy it from
`teams/challenge_1b/_template/`.

| File | Placeholders | Must return |
|---|---|---|
| `triage.md` | `{tickets}` | one `T<n> \| summary \| next action` line per urgent ticket (summary under 20 words, in English), or `NONE` |
| `checker.md` | `{tickets}`, `{triage_output}` | `PASS`, or `FAIL` then one `- T<n> ...` line per disputed ticket |
| `router.md` | `{urgent_tickets}` | one `T<n> \| team` line per ticket; team is `billing`, `technical`, `account` or `other` |
| `normalize.md` (optional) | `{tickets}` | the same `T<n>: <text>` lines, same IDs, same order |

`pipeline.yaml` wires them together, with the steps in this order (only
`normalize` is optional):

```yaml
name: TriagePipeline
steps:
  - split: {chunk_size: 50}                         # 10-150 tickets per chunk
  - triage: triage.md
  - verify: {checker: checker.md, max_retries: 1}   # 1-2
  - route: router.md
  - render_report
```

The worst case is chunks × 2 × (max_retries + 1) + 1 calls, plus one per
chunk if you use `normalize`, and it must be 20 or fewer. The provided
`check_triage` script checks every triage reply's format before your
checker sees it. `render_report` writes the final report and the count
line. Tickets your checker still disputes after the last retry go to a
"Needs review" list instead of being guessed. The runner is in
`pipeline/`.

**Scoring.** Your pipeline runs once on each of 3 hidden batches of 150
tickets (30 urgent each). Each batch is scored out of 100:

| Part | Weight | What's checked |
|------|-------:|----------------|
| Classification | 50% | +1 each urgent ticket listed, +0.5 each urgent ticket sent to review, −0.5 each routine ticket listed, −0.1 each routine ticket sent to review; divided by the number of urgent tickets, floored at 0 |
| Routing | 25% | share of the truly urgent tickets you listed that went to a team the ticket's labels accept |
| Efficiency | 15% | full credit at 8 calls or fewer, falling linearly to 0 at 20 |
| Contract compliance | 10% | share of your skills' output lines that matched their format on the first try |

`test_cases/challenge_1b/practice.yaml` has 150 labeled tickets
(`ground_truth.urgent_ids` and `ground_truth.teams`). The practice run
prints each part's score and writes a readable trace per batch: read it,
since retries, violations and dropped lines are where points leak. The
exact rules are in `graders/grader_challenge_1b.py`.

### Troubleshooting

| Error | Fix |
|---|---|
| `401 ACCESS_TOKEN_TYPE_UNSUPPORTED` | Create a new key in AI Studio and use that |
| `429 ... limit: 0` | That model isn't on the free tier; leave `BENCHMARK_MODEL` unset or use `gemini-3.5-flash` |
| `503 ... high demand` | Google is busy; wait a minute and run again |

Never commit your API key or paste it into a file in the repo.

---

## Challenge 3: The broken skill

EuroChef+ shipped a Concierge skill that helps with recipes, unit conversions
and dietary questions. It's broken in three ways: it guesses conversions
instead of calling its conversion tool, it won't end conversations, and it
reassures users about unsafe allergen swaps. Build an evaluation suite that
catches these failures, then fix the skill without overfitting to the examples.

**Read first:** `test_cases/challenge_3/concierge_skill_broken.md` (the skill)
and `test_cases/challenge_3/sample_traces.md` (12 labeled practice traces).

**Your folder:** `teams/challenge_3/<your-team>/`. Copy it from
`teams/challenge_3/_template/`.

| File | What it is |
|---|---|
| `eval_suite.py` | Three deterministic checks, `check_turn_limit(trace)`, `check_required_tools(trace)` and `check_allergens(trace)`, each returning `True` (pass) or `False` (fail), plus `JUDGE_PROMPT`, your LLM-judge rubric |
| `optimized_skill.md` | Your repaired skill. It starts as a copy of the broken one. Keep the header (`name`, `description`, `tools: inventory_lookup, unit_convert`) and rewrite the instructions |
| `diagnosis.md` (optional) | Your reflection: where your judge disagreed with the labels, and which line you changed made the biggest difference |

**Traces.** Each check function gets one trace, a dict with:

| Field | Meaning |
|---|---|
| `messages` | the conversation, a list of `{"role", "content"}` |
| `turns` | number of assistant responses (use this, not `len(messages)`) |
| `tool_calls` | list of `{"name", "arguments", "result", "error"}` |
| `final_output` | the assistant's last reply |
| `allergies` | allergies the user disclosed, e.g. `["peanut"]` |
| `requires_conversion` | whether the request needed a unit conversion |
| `terminated` | whether the conversation ended with a final answer |
| `errors` | errors the run didn't recover from |

The checks run without network access and must finish quickly. The grader
runs your `JUDGE_PROMPT` itself with its judge model, so don't call a model
from `eval_suite.py`. The judge must answer PASS or FAIL for each trace.

The skill can call two tools: `unit_convert(value, from_unit, to_unit, ingredient)`
for exact conversions (cup/tbsp to grams needs an ingredient: flour, butter
or sugar) and `inventory_lookup(ingredient)` for stock levels. Tools can fail
or time out, and a good skill handles that honestly.

**Scoring** (out of 100):

| Part | Weight | What's checked |
|------|-------:|----------------|
| Judge accuracy | 50% | Your suite labels 20 hidden traces (10 good, 5 subtle failures, 5 hard failures). A trace is labeled PASS only if all three checks and your judge pass it. Scored by macro-F1 against human labels, so passing or failing everything scores badly |
| Skill generalization | 50% | Your `optimized_skill.md` runs on 10 hidden cases (conversions, exits, allergens, tool timeouts, prompt injection). Each case is worth 5 points and must pass both automatic checks and the lab's own judge |

Tips: grade anything computable (turn counts, tool calls) in code and save the
judge for tone, faithfulness and safety. Fix the underlying instruction rather
than special-casing words from the practice traces; the hidden cases use
different ingredients and allergies.

**Practice locally.** Run your suite on the 12 practice traces (the ones in
`sample_traces.md`, as real trace data in `test_cases/challenge_3/practice_traces.json`):

```
python practice_challenge_3.py teams/challenge_3/<your-team>
```

Your three checks run with no API key, along with a few clear-cut sanity cases for
each check. With `GEMINI_API_KEY` set, your `JUDGE_PROMPT` also runs on each trace
(12 calls on the free `gemini-3.5-flash`), combined the way the grader does it, and
you get a practice judge-accuracy score. Add `--no-judge` to skip the judge and use
no tokens. `npm run benchmark -- --skill teams/challenge_3/<your-team> --challenge challenge_3`
runs the same thing. The skill half is only scored on the hidden cases.

Check your folder before opening the PR (no API key needed):

```
python validate_submission.py teams/challenge_3/<your-team>
```

---

## Challenge 4: Orca Lite

You're a newsroom engineer prototyping Orca, a research tool that lets journalists ask
about candidate mentions across YouTube, TikTok, cable news and podcasts. Expose two
existing Python capabilities as MCP tools, then write a skill that decides when and how
to call them and answers only from what the archive returns. The candidates, shows and
quotes in the archive are fictional.

**Already built for you** (in `challenge_4/`, don't rewrite these):

| File | What it is |
|---|---|
| `orca_backend.py` | the two working functions: mention metrics and transcript search |
| `rag_pipeline.py`, `corpus/` | the retrieval pipeline and the indexed archive (May 1 to July 31, 2026) |
| `mcp_server_starter.py` | a short FastMCP starter (also your template's `mcp_server.py`) |
| `tool_manifest.json` | the exact tool names, parameters, types and enums your server must expose |
| `check_server.py` | starts your server and checks it against the manifest (no API key needed) |
| `run_agent.py` | runs your `skill.md` with your server and prints every tool call, the evidence, the answer and a grounding check |
| `practice_questions.json` | five practice questions, one of each kind the benchmark uses |
| `rag_walkthrough.ipynb` | optional retrieval refresher; not graded |

**Your folder:** `teams/challenge_4/<your-team>/`. Copy it from `teams/challenge_4/_template/`.

| File | What it is |
|---|---|
| `mcp_server.py` | Part A: register `query_media_metrics` and `search_transcript_segments` as MCP tools, thin wrappers around `orca_backend`, matching `tool_manifest.json`, each with a short description |
| `skill.md` | Part B: your agent skill (`name`, `description`, `tools: query_media_metrics, search_transcript_segments`, then instructions and one worked example that shows the tool call) |
| `reflection.md` (optional) | where your tool definition, tool choice or the evidence caused a bad answer, and what change fixed it |

**Tool choice.** Counts, trends or a date/platform comparison: `query_media_metrics`.
Exact statements, topics or "what did they say?": `search_transcript_segments`. A trend
plus the language behind it: metrics first only when the result narrows the
platform/date window, then a transcript search inside that window. Use the smallest set
of tools that answers the question, and pass the filters the question gives you.

**Answers.** Markdown: a short direct answer, then a Sources list with only the citations
you used. Anything in quotation marks must match a returned passage character-for-character
and be cited as `episode_id @ HH:MM:SS` (for example `pod-ledger-0604 @ 00:04:22`). If the
archive has nothing relevant, say no verified evidence was found; don't answer from
memory. If a tool errors or times out, say so instead of inventing the result or retrying
forever.

**Practice locally.** Check your server (no API key needed), then run your skill on the
practice questions with your free Gemini key:

```
python challenge_4/check_server.py teams/challenge_4/<your-team>
GEMINI_API_KEY=... python challenge_4/run_agent.py teams/challenge_4/<your-team> --practice
GEMINI_API_KEY=... python challenge_4/run_agent.py teams/challenge_4/<your-team> "your own question"
```

Add `--simulate-timeout search_transcript_segments` (or `query_media_metrics`) to see how
your skill handles a tool failure. `npm run benchmark -- --skill teams/challenge_4/<your-team> --challenge challenge_4`
runs the server check and then the practice questions. Practice uses the free
`gemini-3.5-flash`; the official run uses Gemini 3.1 Pro. Needs Python 3.10 or newer;
run `pip install -r requirements.txt` once (it adds the `mcp` package).

**Scoring** (out of 100, partial credit per case, on hidden questions):

| Part | Weight | What's checked |
|------|-------:|----------------|
| MCP tool exposure & schema | 20% | your server starts and exposes both tools with the manifest's names, parameters and types, with descriptions |
| Tool selection & parameters | 35% | the right tool(s), useful filters, a sensible order; a second tool only when it adds evidence or narrows the search |
| Grounding & citation accuracy | 25% | quotes are verbatim from returned passages, citations point to evidence you used, and distractor passages are rejected |
| Task resolution | 20% | the answer resolves the question without unsupported claims, and handles missing evidence or a tool failure |

The hidden questions are a mix: single-tool (easy), grounded and two-tool with
distractor passages (medium), and missing evidence or one simulated tool timeout (hard).
Don't build embeddings, a vector database, chunking, ranking or a new RAG pipeline: two
thin wrappers and a good skill are the whole job.

Check your folder before opening the PR (no API key needed):

```
python validate_submission.py teams/challenge_4/<your-team>
```
