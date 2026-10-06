# T4G Challenge Submissions

Write a prompt ("skill") for a challenge, test it locally, then submit it by
pull request. Once a day an automated grader runs every submitted skill
against that challenge's graded test cases and updates the leaderboard.

## Layout

```
teams/<challenge>/_template/skill.md    # copy this to start
teams/<challenge>/<your-team>/skill.md  # your submission
test_cases/<challenge>/practice_batch.yaml  # practice cases you can test against
graders/                                # the exact scoring logic used for real grading
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

This scores your skill on the practice cases using the same model and
grader as the real run. The first run sets up a local Python environment
automatically. Re-running with nothing changed is free; add `--force` to re-grade anyway.

## 3. Submit

Commit **only** your `skill.md`, push to your fork, and open a pull request
into this repo's `main` branch.

A check runs on your PR and merges it automatically if:

- it changes exactly one file, `teams/<challenge>/<your-team>/skill.md`
- the challenge is open
- the file is valid YAML with `name`, `description`, and `instructions`
- `instructions` contains the challenge's placeholder
- the team folder is new, or was first submitted by you

If the check fails it comments on the PR explaining why. Fix it and push to
the same PR.

To update your submission later, open a new PR that edits the same file.
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

### Troubleshooting

| Error | Fix |
|---|---|
| `401 ACCESS_TOKEN_TYPE_UNSUPPORTED` | Create a new key in AI Studio and use that |
| `429 ... limit: 0` | That model isn't on the free tier; leave `BENCHMARK_MODEL` unset or use `gemini-3.5-flash` |
| `503 ... high demand` | Google is busy; wait a minute and run again |

Never commit your API key or paste it into a file in the repo.
