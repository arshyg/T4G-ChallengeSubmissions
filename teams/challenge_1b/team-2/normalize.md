name: TicketNormalizer
description: >
  Optional. Use on one chunk of support tickets to rewrite them (e.g.
  translate them into English) before triage sees them.
tools: none
instructions: |
  [Only used if pipeline.yaml has a "normalize: normalize.md" step, which
  costs one extra call per chunk. Delete this file if you don't use it.

  It MUST contain the literal placeholder {tickets}. Return the same
  number of "T<n>: <text>" lines, with the same IDs in the same order;
  your text replaces the ticket text for every later step.]
example:
  input: |
    [two tickets in French or Dutch]
  output: |
    [the same two lines, translated]
