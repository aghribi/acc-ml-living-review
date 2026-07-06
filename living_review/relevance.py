"""
relevance.py
============

Funnel orchestration: which papers enter the published review.

Nightly flow (see SCOPE.md for the editorial criterion):

1. Select *undecided* papers — no terminal accepted/rejected decision.
   Pending papers ARE retried (abstract backfill may have progressed,
   thresholds may have moved); accepted/rejected are never touched.
2. Backfill missing abstracts (enrich.py).
3. Stage B deterministic gates (gates.py): auto-accept / auto-reject /
   gray. Empty-abstract non-accepts go straight to pending.
4. Stage C adjudicator (adjudicator.py) on the gray zone.

Every decision is recorded in `Paper.review` with full provenance.
Accepted/rejected decisions are terminal: nights after a decision, the
paper is skipped entirely — this is what makes the pipeline incremental
and keeps a model/threshold change from silently rewriting the archive.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional

from .adjudicator import Adjudicator
from .data_model import Paper
from .db import DB
from .enrich import backfill_abstracts
from .gates import ACCEPT, GRAY, REJECT, apply_gates, has_machine_vocab

TERMINAL = ("accepted", "rejected")


def set_review(
    paper: Paper,
    decision: str,
    stage: str,
    rule: Optional[str] = None,
    score: Optional[float] = None,
    model: Optional[str] = None,
    revision: Optional[str] = None,
) -> None:
    """Record a relevance decision with provenance on a paper."""
    paper.review = {
        "decision": decision,
        "stage": stage,
        "rule": rule,
        "score": score,
        "model": model,
        "model_revision": revision,
        "timestamp": datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z"),
    }


def undecided_papers(db: DB) -> List[Paper]:
    """Papers without a terminal decision (pending ones are retried)."""
    return [p for p in db if p.review.get("decision") not in TERMINAL]


def run_funnel(db: DB, adjudicator: Adjudicator) -> Dict[str, int]:
    """
    Run backfill → gates → adjudicator over all undecided papers in the DB.

    Returns
    -------
    dict
        Outcome counts: undecided, enriched, gate_accepted, gate_rejected,
        pending_empty_abstract, adjudicated, nli_accepted, nli_rejected,
        nli_pending.
    """
    undecided = undecided_papers(db)
    counts = {
        "undecided": len(undecided),
        "enriched": 0,
        "gate_accepted": 0,
        "gate_rejected": 0,
        "pending_empty_abstract": 0,
        "adjudicated": 0,
        "nli_accepted": 0,
        "nli_rejected": 0,
        "nli_pending": 0,
    }
    if not undecided:
        return counts

    counts["enriched"] = backfill_abstracts(undecided)

    gray: List[Paper] = []
    for p in undecided:
        result = apply_gates(p)
        if result.decision == ACCEPT:
            set_review(p, "accepted", "gate", result.rule)
            counts["gate_accepted"] += 1
        elif result.decision == REJECT:
            set_review(p, "rejected", "gate", result.rule)
            counts["gate_rejected"] += 1
        elif result.rule in ("empty_abstract", "detector_context"):
            # Not trusted to the NLI (title-only papers, and detector-analysis
            # papers the NLI systematically over-scores); human queue.
            set_review(p, "pending", "gate", result.rule)
            counts["pending_empty_abstract"] += 1
        else:
            gray.append(p)

    counts["adjudicated"] = len(gray)
    for p, r in zip(gray, adjudicator.adjudicate(gray)):
        decision, rule = r.decision, r.rule
        # False-negative guard (2026-07 benchmark): never auto-reject a paper
        # that explicitly names accelerator machinery on an NLI score alone.
        if decision == "rejected" and has_machine_vocab(f"{p.title or ''} {p.abstract or ''}"):
            decision, rule = "pending", "nli_reject_machine_vocab"
        set_review(
            p, decision, "nli",
            rule=rule, score=r.score, model=r.model, revision=r.revision,
        )
        counts[f"nli_{decision}"] += 1
    return counts


def accepted_papers(db: DB) -> List[Paper]:
    return [p for p in db if p.review.get("decision") == "accepted"]


def pending_papers(db: DB) -> List[Paper]:
    return [p for p in db if p.review.get("decision") == "pending"]


def demote_others_only(papers: List[Paper]) -> List[Paper]:
    """
    Split classified papers into publishable ones and Others-only strays.

    A paper whose only category is `Others` at score 0.0 fit nothing in the
    taxonomy — treated as a triage signal, not a published category: it is
    demoted to pending (human queue) and withheld from the export.

    Returns
    -------
    list of Paper
        The publishable subset (papers not demoted).
    """
    publishable = []
    for p in papers:
        cats = p.categories or []
        if len(cats) == 1 and cats[0].get("label") == "Others" and not cats[0].get("score"):
            set_review(p, "pending", "classifier", "others_only")
        else:
            publishable.append(p)
    return publishable


def rank_pending(papers: List[Paper]) -> List[Paper]:
    """
    Sort the pending queue most-relevant-first for human review, using the
    MiniLM similarity to the accelerator+ML reference queries (its only
    remaining scoring role). Falls back to unranked order on any failure.
    """
    if not papers:
        return []
    try:
        from .classifier import dual_semantic_scores

        sa, sm, _ = dual_semantic_scores([f"{p.title}. {p.abstract or ''}" for p in papers])
        order = sorted(range(len(papers)), key=lambda i: sa[i] + sm[i], reverse=True)
        return [papers[i] for i in order]
    except Exception as e:
        print(f"[warn] pending-queue ranking unavailable: {e}")
        return list(papers)


def export_pending_queue(db: DB, path) -> int:
    """Write the ranked pending queue to a JSON file for human review."""
    import json
    from pathlib import Path

    queue = rank_pending(pending_papers(db))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            "id": p.id,
            "title": p.title,
            "year": p.year,
            "venue": p.venue,
            "abstract": (p.abstract or "")[:600],
            "review": p.review,
            "links": p.links,
        }
        for p in queue
    ]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    return len(payload)
