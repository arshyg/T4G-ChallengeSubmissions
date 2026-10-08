# Copy this folder to teams/challenge_1/<your-team>/ and edit the copy.
#
# This file is YAML. Keep "instructions" (and any long or colon-containing
# value) as an indented block under "key: |" so colons and quotes inside it
# don't break parsing. Every line in the block needs the same indentation.
name: YourTeamSkill
description: >
  Triage a batch of customer-support tickets and list only the urgent ones.
instructions: |
  You are triaging customer-support tickets for EuroChef+, a cooking-video
  streaming service. Here are the tickets, one per line:

  {tickets}

  Decide which tickets are urgent. (Write your own criteria here.)

  Output format: nothing except the lines below.
  - One markdown bullet per urgent ticket, like:
    - T4: Charged twice this month and wants the duplicate refunded. Next action: refund the duplicate charge.
  - A final line: "X of N tickets required urgent action." where N is the
    number of tickets given and X is the number of bullets you wrote.
