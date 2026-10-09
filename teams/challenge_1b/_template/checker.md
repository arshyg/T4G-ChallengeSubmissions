name: TriageChecker
description: >
  Use after triage on one chunk of support tickets to judge whether the
  urgent list is right, and name only the tickets it is wrong about.
tools: none
instructions: |
  [Your checker. It MUST contain both literal placeholders: {tickets}
  (the chunk's "T<n>: <text>" lines) and {triage_output} (triage's reply
  for that chunk).

  check_triage has already verified the format, so judge only urgency:
  e.g. a billing or access-loss ticket triage missed, or a feature request
  it flagged.

  Return exactly PASS, or FAIL followed by one line per disputed ticket,
  each starting with "- T<n>". On a final failure the tickets you name go
  to the review list, and each routine ticket sent there costs points, so
  name only tickets you doubt.]
example:
  input: |
    [a short chunk of tickets plus a triage reply you write yourself]
  output: |
    [PASS, or FAIL with "- T<n> ..." lines]
