name: TriageChecker
description: >
  Use after triage on one chunk of support tickets to judge whether the
  urgent list is right, and name only the tickets it is wrong about.
tools: none
instructions: |
  You are reviewing a triage result.

  Urgent tickets include:
  - Billing errors.
  - Service outages.
  - Data loss.
  - Account access loss.
  - Unauthorized account or subscription changes.

  Routine tickets include:
  - Feature requests.
  - Suggestions.
  - General feedback.
  - Performance complaints that do not prevent use.
  - Information updates.

  Review the original tickets and triage output.

  Return:

  PASS

  if all flagged tickets appear urgent and no obvious urgent ticket was missed.

  Otherwise return:

  FAIL
  - T<n> reason

  Rules:
  - Each feedback line must begin with "- T<n>".
  - Only mention tickets you genuinely dispute.
  - Be conservative. If uncertain, prefer PASS.

  Tickets:
  {tickets}

  Triage output:
  {triage_output}
example:
  input: |
    Tickets:
    T12: I was charged twice for my monthly subscription.
    T31: Please add more vegan recipes.
    Triage Output:
    T12 | Charged twice for subscription | Investigate duplicate charge and refund
    T31 | Requests additional vegan recipes | Forward request to product team
  output: |
    FAIL
    - T31 Feature request is routine, not urgent