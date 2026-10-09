name: TicketTriage
description: >
  Use on one chunk of EuroChef+ support tickets (English, French, Dutch
  or German) to find the urgent ones and say what to do about each.
tools: none
instructions: |
  [Start from your Part 1 skill. It MUST contain the literal placeholder
  {tickets} — the runner inserts one "T<n>: <text>" line per ticket in
  this chunk there.

  Return one line per urgent ticket, exactly:
    T<n> | summary (under 20 words, in English) | next action
  or the single word NONE if no ticket in the chunk is urgent.
  No count line, no bullets, no other text: the provided check_triage
  script rejects anything else, and render_report writes the count.

  If the checker or the script rejects your reply, the runner re-sends this
  prompt with your previous reply and the feedback appended.]
example:
  input: |
    [a short 2-3 ticket sample you write yourself, mixing languages]
  output: |
    [what your skill should produce for that sample]
