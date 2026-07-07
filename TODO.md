# TODO — deferred work

Deliberately deferred items from the 2026-07 methodology overhaul, in
priority order.

## 1. Gold-standard hard slices (highest leverage)

The eval benchmark currently uses gate-derived easy slices only. Hand-label
the boundary cases per `SCOPE.md` and drop them into `data/eval/gold/`
(format in `data/eval/gold/README.md`):

- ~50 in-scope papers with no venue signal (proton-therapy beam delivery,
  medical-linac QA, accelerator ML published in ML venues),
- ~50 out-of-scope near-misses (treatment planning, synchrotron sample
  analysis, tokamak control).

A few hours of labeling; it turns every future threshold/model/vocabulary
change into a measurement on the boundary that actually matters.

## 2. Instruct-LLM adjudicator backend

`living_review/adjudicator.py` defines the `Adjudicator` protocol;
`LLMAdjudicator` is a stub. Implement it to apply the full `SCOPE.md`
rubric via a small instruct model (API or local), returning decision +
one-line justification stored in `review`. Then evaluate against the NLI
baseline on the gold slices and decide the cascade (NLI primary + LLM on
the uncertain band, or LLM primary). At ~10–40 gray-zone papers/night the
API cost is cents/month. Keep it out of the nightly critical path
(failures → pending, retried next night).

## 3. Historical recall / citation-graph expansion (partially done)

`living-review backfill-history` covers INSPIRE/OpenAlex/Crossref wide
date ranges. Remaining: one-hop citation expansion from the Reviews-category
papers via the INSPIRE literature API (`references` / `citations`) to find
1990s papers keyword queries miss; add recovered founding papers to
`data/eval/positives.json`.

## 4. Facet taxonomy redesign

The 16 flat categories mix technique / subsystem / artifact-type axes.
Split into facets (technique × accelerator subsystem × facility × paper
type), assign via the adjudicator (one structured call), and add faceted
browsing to the Hugo site. Bigger site change — coordinate with layouts.

## 5. arXiv paper update

Update the companion paper at `../living_review_paper` to describe the new
methodology (funnel, SCOPE criterion, terminal decisions, eval benchmark,
calibration numbers from `docs/source/methodology.rst`).

## 6. Smaller items

- Early-break optimization in `fetch_arxiv` pagination (currently relies on
  the date-bounded query to terminate).
- Point Decap CMS at a curation UI for `data/db.json` review decisions
  (today: hand-edit + `curated: true`).
- Venue normalization (map raw venue strings to canonical names) — would
  sharpen both the whitelist gate and the site's venue facet.
