# Gold-standard hard slices (TODO)

The easy-slice benchmark (`../positives.json`, `../negatives.json`) is
gate-derived: positives come from accelerator venues / `physics.acc-ph`,
negatives from unambiguous auto-rejects. It bounds the adjudicator only on
easy cases.

What is missing — and what this directory is the hook for — are the
**hand-labeled hard slices** where the real editorial boundary lives:

- medical accelerator papers (proton-therapy beam delivery, medical-linac
  QA) that are IN scope but carry no venue signal,
- downstream-product medical papers (treatment planning, image analysis)
  that are OUT,
- light-source papers: beamline/machine ML (in) vs sample analysis (out),
- accelerator-ML papers published in ML venues (in, no venue signal).

## Format

Drop any number of `*.json` files here, each a list of records:

```json
[
  {
    "id": "doi:10.1000/example",
    "title": "...",
    "abstract": "...",
    "label": true
  }
]
```

`label`: `true` = in scope per SCOPE.md, `false` = out of scope.

`tests/eval/test_eval_benchmark.py` automatically picks these files up and
reports precision/recall per slice. Label against SCOPE.md; when a case is
genuinely contested, resolve it by amending SCOPE.md's worked examples
first, then label.

Target: ~50 in-scope + ~50 out-of-scope boundary papers. A few hours of
labeling — the single highest-leverage investment left in the methodology
(see TODO.md).
