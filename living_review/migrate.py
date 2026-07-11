"""
migrate.py
==========

One-off migration of the legacy published DB into the canonical
`data/db.json`, cleaning it through the relevance funnel.

Procedure:
1. Load the legacy `site/data/livingreview.json` (papers only).
2. Deduplicate (identifier graph + fuzzy titles).
3. Backfill arXiv subject categories + missing abstracts (network).
4. Apply Stage B gates; emit the easy-slice eval sets
   (`data/eval/positives.json` = gate-auto-accepts,
   `data/eval/negatives.json` = gate-auto-rejects).
5. Unless `gates_only`, adjudicate the gray zone with the NLI model.
6. Write: `data/db.json` (every paper + decision provenance), the
   regenerated accepted-only published JSON + BibTeX + PDF, and
   `data/migration_dropped.md` — a human-readable table of every dropped
   paper, to be eyeballed BEFORE the branch is merged. Rescuing a paper =
   set `review.decision: accepted`, `review.stage: human`, `curated: true`
   in data/db.json (and remove it from the negatives eval file).

Decisions carry `stage: "migration:gate"` / `"migration:nli"` so this run
stays distinguishable from nightly ones.
"""

import json
from pathlib import Path
from typing import List, Optional

from .adjudicator import NLIAdjudicator
from .classifier import classify_papers
from .data_model import Paper
from .db import DB
from .dedup import dedup_papers
from .enrich import backfill_abstracts, fetch_arxiv_metadata
from .exporters import export_bibtex, export_json, export_pdf
from .gates import ACCEPT, REJECT, apply_gates
from .relevance import demote_others_only, export_pending_queue, set_review
from .stats import compute_stats

PENDING_QUEUE_PATH = "data/pending_review.json"


def _load_legacy_papers(source: str) -> List[Paper]:
    with open(source, encoding="utf-8") as f:
        raw = json.load(f)
    papers = []
    for d in raw.get("papers", {}).values():
        try:
            papers.append(Paper.from_dict(d))
        except Exception as e:
            print(f"[warn] Skipping invalid legacy entry: {e}")
    return papers


def _eval_record(p: Paper) -> dict:
    return {
        "id": p.id,
        "title": p.title,
        "abstract": p.abstract or "",
        "venue": p.venue,
        "year": p.year,
        "rule": p.review.get("rule"),
    }


def _dropped_report(papers: List[Paper], path: Path) -> None:
    lines = [
        "# Migration: dropped papers",
        "",
        "Every paper rejected by the funnel during the one-off migration.",
        "Review this list BEFORE merging. To rescue a paper: in `data/db.json`",
        "set its `review.decision` to `accepted`, `review.stage` to `human`,",
        "`curated` to `true` — and delete it from `data/eval/negatives.json`.",
        "",
        f"Total dropped: **{len(papers)}**",
        "",
        "| Title | Venue | Year | Stage | Rule / score |",
        "|---|---|---|---|---|",
    ]
    for p in sorted(papers, key=lambda x: (x.review.get("rule") or "", x.title or "")):
        why = p.review.get("rule") or f"nli score={p.review.get('score')}"
        title = (p.title or "").replace("|", "\\|")[:110]
        venue = (p.venue or "")[:40].replace("|", "\\|")
        lines.append(f"| {title} | {venue} | {p.year or ''} | {p.review.get('stage')} | {why} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def migrate(
    source: str = "site/data/livingreview.json",
    db_path: str = "data/db.json",
    report_path: str = "data/migration_dropped.md",
    eval_dir: str = "data/eval",
    dry_run: bool = False,
    gates_only: bool = False,
    adjudicator=None,
    output_dir: str = ".",
):
    """Run the one-off migration. See module docstring."""
    papers = _load_legacy_papers(source)
    print(f"[info] Legacy DB: {len(papers)} entries")

    papers = dedup_papers(papers)
    print(f"[info] After dedup: {len(papers)} unique works")

    # --- Backfill arXiv categories (needed for the acc-ph auto-accept) ---
    need_cats = [p.arxiv_id for p in papers if p.arxiv_id and not p.arxiv_categories]
    if need_cats:
        print(f"[info] Fetching arXiv categories for {len(need_cats)} papers")
        meta = fetch_arxiv_metadata(need_cats)
        for p in papers:
            m = meta.get(p.arxiv_id or "")
            if m:
                p.arxiv_categories = m["arxiv_categories"]
                if not (p.abstract or "").strip() and m["abstract"]:
                    p.abstract = m["abstract"]

    # --- Backfill abstracts (Crossref / OpenAlex / arXiv) ---
    empty_before = sum(1 for p in papers if not (p.abstract or "").strip())
    filled = backfill_abstracts(papers)
    print(f"[info] Abstract backfill: {filled}/{empty_before} empty abstracts filled")

    # Guard against migrating an already-migrated file (e.g. the published
    # JSON after a previous run): decided papers pass through unchanged.
    decided = sum(1 for p in papers if p.review.get("decision"))
    if decided:
        print(f"[warn] Source already carries {decided} decisions — carrying them over")

    # --- Stage B gates ---
    gray: List[Paper] = []
    accepted, rejected, pending = [], [], []
    for p in papers:
        prior = p.review.get("decision")
        if prior == "accepted":
            accepted.append(p)
            continue
        if prior == "rejected":
            rejected.append(p)
            continue
        result = apply_gates(p)
        if result.decision == ACCEPT:
            set_review(p, "accepted", "migration:gate", result.rule)
            accepted.append(p)
        elif result.decision == REJECT:
            set_review(p, "rejected", "migration:gate", result.rule)
            rejected.append(p)
        elif result.rule in ("empty_abstract", "detector_context"):
            set_review(p, "pending", "migration:gate", result.rule)
            pending.append(p)
        else:
            gray.append(p)
    print(
        f"[info] Gates: {len(accepted)} accepted, {len(rejected)} rejected, "
        f"{len(pending)} pending (empty abstract), {len(gray)} gray"
    )

    # --- Eval sets (gate-derived easy slices) ---
    eval_dir = Path(eval_dir)
    if not dry_run:
        eval_dir.mkdir(parents=True, exist_ok=True)
        (eval_dir / "positives.json").write_text(
            json.dumps([_eval_record(p) for p in accepted], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (eval_dir / "negatives.json").write_text(
            json.dumps([_eval_record(p) for p in rejected], indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[info] Eval sets written → {eval_dir}/positives.json, negatives.json")

    if gates_only:
        print("[info] gates_only: stopping before NLI adjudication (no DB written)")
        return

    # --- Stage C: NLI over the gray zone ---
    from .gates import has_machine_vocab, has_ml_vocab

    adjudicator = adjudicator or NLIAdjudicator()
    for p, r in zip(gray, adjudicator.adjudicate(gray)):
        decision, rule = r.decision, r.rule
        text = f"{p.title or ''} {p.abstract or ''}"
        if decision == "rejected" and has_machine_vocab(text) and has_ml_vocab(text):
            decision, rule = "pending", "nli_reject_machine_vocab"
        set_review(p, decision, "migration:nli",
                   rule=rule, score=r.score, model=r.model, revision=r.revision)
        {"accepted": accepted, "rejected": rejected, "pending": pending}[decision].append(p)
    print(
        f"[info] Final: {len(accepted)} accepted, {len(rejected)} rejected, "
        f"{len(pending)} pending"
    )

    if dry_run:
        print("[info] dry-run: nothing written")
        for p in rejected[:20]:
            print(f"  - would drop: {p.title[:90]}  [{p.review.get('rule')}]")
        return

    # --- Classify accepted, demote Others-only strays ---
    classify_papers(accepted)
    publishable = demote_others_only(accepted)
    if len(publishable) != len(accepted):
        print(f"[info] {len(accepted) - len(publishable)} Others-only papers demoted to pending")

    # --- Write canonical DB, report, published artifacts ---
    db = DB()
    db.merge_from_list(papers)
    db.save(db_path)
    print(f"[info] Canonical DB → {db_path} ({len(db)} papers)")

    _dropped_report(rejected, Path(report_path))
    print(f"[info] Dropped-papers report → {report_path}")
    export_pending_queue(db, Path(output_dir) / PENDING_QUEUE_PATH)

    stats = compute_stats(publishable)
    export_json(publishable, stats, output_dir)
    export_bibtex(publishable, output_dir)
    export_pdf(publishable, stats, output_dir)
    print(f"[ok] Migration complete: {len(publishable)} papers published")
