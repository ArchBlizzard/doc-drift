# The demo run: DocDrift vs asking the AI directly, side by side

This is the exact comparison run shown in the solution video, started from
the web UI against the real, unmodified Kaggle description of
`uciml/red-wine-quality-cortez-et-al-2009` (Database Contents License; the
description is the dataset's own card, byte for byte). Both sides used the
same model, `claude-opus-5`.

- `agent/` is the DocDrift side: `ledger.jsonl` (every claim, its check
  source, the mutation-test results, and the execution evidence),
  `messages.jsonl` (every prompt and reply verbatim), `audit.md`, and
  `verdicts.json`. Result: 1 violated, 13 hold, 13 set aside, 111s.
- `baseline/` is the ask-the-AI-directly side: one message holding the card,
  the column types, and the first 50 rows (`messages.jsonl` has it verbatim),
  plus its `verdicts.json`. Result: 1 violated, 15 hold, 17 set aside, 83s.

The moment that matters: on the card's 10 point scale claim, the agent's
executed check found only six quality values, 3 through 8, across all 1,599
rows (violated, with the computed proof), while the direct ask set the same
sentence aside. Several of the direct ask's "hold" verdicts cite only "the
50 visible rows" as their basis; that is visible in its own reply text.
