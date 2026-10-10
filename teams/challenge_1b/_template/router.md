name: TicketRouter
description: >
  Use on a list of urgent EuroChef+ support tickets to assign each one to
  the billing, technical, account or other team.
tools: none
instructions: |
  [Your router. It MUST contain the literal placeholder {urgent_tickets}
  — the runner inserts one "T<n>: <text>" line per urgent ticket from
  every chunk there.

  Every urgent ticket needs exactly one line, in this form:
    T<n> | team
  where team is billing, technical, account or other.]
example:
  input: |
    [a few urgent tickets you write yourself. Keep it small: one example
    per team is plenty.]
  output: |
    [one "T<n> | team" line for each of those tickets]
