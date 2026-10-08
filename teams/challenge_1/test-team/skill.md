name: TestTeamSkill
description: >
  Use when given a set of customer support tickets and you need to
  separate Urgent from Routine and get a summary of what needs
  immediate attention.
tools: none
instructions: |
  You will be given a set of customer support tickets: {tickets}

  For each ticket, classify it as Urgent or Routine.
  - Urgent: anything involving data loss, billing errors, security issues, or a customer explicitly saying they want to cancel.
  - Routine: everything else, including general questions and minor bugs.

  Output only the urgent tickets, one markdown bullet each, in this exact form:
  - T<n>: <one-sentence summary, under 20 words>. Next action: <suggested action>.

  End with exactly this line and nothing after it:
  X of N tickets required urgent action.
  where N is the number of tickets given and X is the number of bullets you wrote.

example:
  input: |
    Ticket 1: "My credit card was charged twice for the same order."
    Ticket 2: "How do I change my email address on file?"
    Ticket 3: "All my saved data disappeared after the last update."
  output: |
    Urgent tickets:
    - Ticket 1: Customer was double-charged and needs a billing correction.
    - Ticket 3: Customer lost all saved data after an update.

    Total Urgent: 2
