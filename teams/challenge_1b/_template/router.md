name: TicketRouter
description: >
  Use on a list of urgent EuroChef+ support tickets to assign each one to
  the billing, technical, account or other team.
tools: none
instructions: |
  [Your router. It MUST contain the literal placeholder {urgent_tickets}
  — the runner inserts one "T<n>: <text>" line per urgent ticket from
  every chunk there.

  Return one line per ticket, exactly:
    T<n> | team
  where team is billing, technical, account or other. Keep it small: one
  example per team is plenty.]
example:
  input: |
    [two or three urgent tickets you write yourself]
  output: |
    [one "T<n> | team" line each]
