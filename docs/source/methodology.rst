Methodology: the relevance funnel
=================================

How papers enter the published review. The editorial criterion — *does the
ML touch the machine or the beam?* — is written in ``SCOPE.md`` at the
repository root; this page describes the machinery that applies it.

Overview
--------

.. code-block:: text

   fetchers ─→ enrich (abstract backfill) ─→ dedup ─→ canonical DB (data/db.json)
                                                          │ undecided papers only
                                                          ▼
                                      Stage B: deterministic gates (gates.py)
                                                          │ gray zone
                                                          ▼
                                      Stage C: zero-shot NLI (adjudicator.py)
                                                          │
                        accepted ─→ classify ─→ export ─→ site/data/livingreview.json
                        rejected ─→ kept in db.json with provenance, never re-scored
                        pending  ─→ db.json + data/pending_review.json (human queue)

Two files, two roles:

- ``data/db.json`` — the **canonical DB**: every paper ever seen, with its
  decision and provenance. Committed to git.
- ``site/data/livingreview.json`` — the **published artifact**: accepted
  papers only, regenerated on every run, rendered by Hugo. Never
  hand-edited.

Stage A — Fetch, enrich, deduplicate
------------------------------------

Sources: arXiv (per-keyword queries over ``physics.acc-ph`` and
``cs.AI/cs.LG/stat.ML``, date-bounded via ``submittedDate`` ranges),
InspireHEP, HAL, OpenAlex, Crossref (plus optional Semantic Scholar,
Springer, PubMed).

Papers with empty abstracts are backfilled from Crossref (JATS stripped),
OpenAlex (inverted index reconstructed), and arXiv (batched ``id_list``)
before any scoring — a third of the historical corpus lacked abstracts,
which systematically corrupted similarity scores.

Deduplication is two-pass: a union-find over normalized identifiers (DOI,
arXiv id incl. DataCite ``10.48550/arXiv.*`` DOIs, INSPIRE id) merges
records sharing *any* identifier; the remainder is fuzzy-matched on
simplified titles (ratio ≥ 0.93) within publication year ± 1.

Stage B — Deterministic gates
-----------------------------

Cheap, auditable rules decide the unambiguous ends
(``living_review/gates.py``):

**Auto-accept**

- primary arXiv category ``physics.acc-ph``; or
- venue matches the accelerator-venue whitelist (PRAB, JACoW conferences,
  NIM-A, JINST, …) *and* an ML keyword appears in title+abstract.

**Auto-reject** — conjunctions only, never venue or domain alone (medical
accelerator papers are in scope, see ``SCOPE.md``):

- "accelerator" appears only in compute-hardware context (DNN, FPGA,
  ASIC, …) *and* the text has **zero** accelerator-system vocabulary; or
- **zero** accelerator-system vocabulary *and* a clear foreign-domain
  signal (education, civil engineering, medical imaging, finance, …).

All vocabularies are word-boundary regexes in ``living_review/config.py``.

Stage C — Zero-shot NLI adjudication
------------------------------------

The gray zone is scored by a zero-shot NLI cross-encoder
(``MoritzLaurer/deberta-v3-base-zeroshot-v2.0``) against the hypothesis:

    "This paper applies machine learning or artificial intelligence to a
    particle accelerator, beamline, or particle beam."

Three-way outcome with thresholds from ``config.NLI_THRESHOLDS``
(calibrated 2026-07 on the gate-derived easy slices — 142 positives / 96
negatives):

- score ≥ **0.90** → accepted (2/96 easy negatives clear this bar, both
  genuinely borderline accelerator-shielding papers),
- score ≤ **0.15** → rejected (8/142 easy positives fall below it — all of
  them auto-accept at the gates in production and never reach the NLI),
- otherwise → **pending**: the human review queue
  (``data/pending_review.json``, ranked most-relevant-first).

Papers with empty abstracts that do not auto-accept go straight to
pending — title-only adjudication is not trusted.

*Calibration caveat:* the easy slices are gate-derived, so they bound the
NLI only on unambiguous cases. The genuinely contested boundary (medical
beam delivery, light-source science) is pinned only once the hand-labeled
gold slices exist — see ``data/eval/gold/README.md``. Re-run
``scripts/calibrate_thresholds.py`` after any model or vocabulary change.

Terminal decisions and provenance
---------------------------------

Every decision is recorded on the paper as ``review = {decision, stage,
rule, score, model, model_revision, timestamp}``. Accepted/rejected
decisions are **terminal**: nightly runs only funnel *undecided* papers,
so a model or threshold change can never silently rewrite the archive.
Reversing a decision is a human act: edit ``data/db.json``, set
``review.stage: human`` and ``curated: true`` (curated fields survive all
merges).

Human curation
--------------

- The pending queue (``data/pending_review.json``, or
  ``living-review review`` on the command line) is the triage inbox.
- New papers are contributed via the site's submission form; approved
  submissions land in ``site/data/submissions/approved/`` and are promoted
  by the nightly run (``--promote-manual``).
- The published JSON is read-only build output; all human edits belong in
  the canonical DB or the submissions folder.

Quality gates in CI
-------------------

The nightly workflow refuses to commit if the published set shrinks, grows
more than 10 % in one run, or a new title trips a spam heuristic
(``scripts/sanity_check.py``). The eval benchmark
(``tests/eval/test_eval_benchmark.py``, ``pytest -m slow``) fails when
funnel precision/recall on the eval slices degrade.
