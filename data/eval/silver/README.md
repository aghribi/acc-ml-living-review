# Silver labels: model-judged benchmark (2026-07)

`fable-judged-2026-07.json` — all 531 DB papers blind-judged against
`SCOPE.md` by a frontier LLM (Claude Fable 5, 6 independent batches;
BORDERLINE verdicts excluded → 518 labels, 209 in-scope). The judges saw
title/abstract/venue/year only — never the funnel's decision or
categories.

These are **silver**, not gold: model-judged, not human-verified. Use them
to seed the gold hard slices (validate a disagreement, then promote it to
`../gold/`), not as CI ground truth.

`disagreements-2026-07.json` — every funnel-vs-judge disagreement:
false positives (published but judged out), false negatives (rejected but
judged in), and the judged composition of the pending queue.

Headline numbers from the benchmark (see repo discussion / methodology docs):

- published precision 88% — dominated by one systematic miss: HEP
  **detector-analysis ML** (track reconstruction, PID, triggers) that the
  NLI scores 0.92–0.99;
- rejection purity 94%;
- gates disagree 0–7% per rule; the NLI stage disagrees 17% — the gates
  are the strong stage, the NLI is the weak one;
- pending queue: 116/141 judged out, 22 judged in;
- category any-label agreement only 52% — the classifier over-assigns
  Novel Applications / Statistics & Trends / Tools & Libraries where the
  judge picks specific labels (Beam Diagnostics, Surrogate Models, …).
