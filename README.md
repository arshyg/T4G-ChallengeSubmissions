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

Before you open the PR, run the same check the merge uses (no API key needed):

```
python validate_submission.py teams/<challenge>/<your-team>
```

Submission PRs are merged on a schedule once the deadline passes, then once
a day, so other teams can't read your files early. A PR is merged only if:

- every file it changes is inside one team folder, `teams/<challenge>/<your-team>/`
- for Challenge 1b, the folder passes `validate_submission.py`

A PR that changes anything outside your team folder is left for a TA to
review. A Challenge 1b PR that fails the check stays open with a comment
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
