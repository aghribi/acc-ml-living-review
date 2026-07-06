"""Regression benchmark: gates + NLI against the eval slices.

Slow (loads the NLI model). Run with `pytest -m slow tests/eval` or full
`pytest`. Fails if precision/recall on the easy slices degrade — any change
to gate vocabularies, the NLI model, or thresholds must keep these bars.

Hand-labeled hard slices dropped into data/eval/gold/*.json (see the README
there) are picked up automatically and reported per-file.
"""

import json
from pathlib import Path

import pytest

from living_review.adjudicator import NLIAdjudicator
from living_review.data_model import Paper
from living_review.gates import ACCEPT, REJECT, apply_gates

EVAL_DIR = Path(__file__).resolve().parents[2] / "data" / "eval"

pytestmark = pytest.mark.slow


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _paper(rec):
    return Paper.from_dict(
        {"id": rec.get("id", ""), "title": rec["title"], "abstract": rec.get("abstract", ""),
         "venue": rec.get("venue"), "year": rec.get("year")}
    )


def _funnel_decisions(records):
    """Gate + NLI decision for each record (no pending shortcut for empties)."""
    papers = [_paper(r) for r in records]
    decisions = [None] * len(papers)
    gray_idx = []
    for i, p in enumerate(papers):
        g = apply_gates(p)
        if g.decision == ACCEPT:
            decisions[i] = "accepted"
        elif g.decision == REJECT:
            decisions[i] = "rejected"
        else:
            gray_idx.append(i)
    if gray_idx:
        adj = NLIAdjudicator()
        for i, r in zip(gray_idx, adj.adjudicate([papers[i] for i in gray_idx])):
            decisions[i] = r.decision
    return decisions


@pytest.fixture(scope="module")
def eval_sets():
    pos_file = EVAL_DIR / "positives.json"
    neg_file = EVAL_DIR / "negatives.json"
    if not pos_file.exists() or not neg_file.exists():
        pytest.skip("eval sets not generated yet (run: living-review migrate --gates-only)")
    return _load(pos_file), _load(neg_file)


class TestEasySlices:
    def test_positives_recall(self, eval_sets):
        positives, _ = eval_sets
        decisions = _funnel_decisions(positives)
        rejected = sum(1 for d in decisions if d == "rejected")
        recall_floor = 1 - rejected / len(decisions)
        assert recall_floor >= 0.90, f"{rejected}/{len(decisions)} easy positives rejected"

    def test_negatives_precision(self, eval_sets):
        _, negatives = eval_sets
        decisions = _funnel_decisions(negatives)
        accepted = sum(1 for d in decisions if d == "accepted")
        precision_floor = 1 - accepted / len(decisions)
        assert precision_floor >= 0.95, f"{accepted}/{len(decisions)} easy negatives accepted"


class TestGoldSlices:
    def test_gold_slices_if_present(self):
        gold_files = sorted((EVAL_DIR / "gold").glob("*.json"))
        if not gold_files:
            pytest.skip("no gold slices yet (see data/eval/gold/README.md)")
        for f in gold_files:
            records = _load(f)
            decisions = _funnel_decisions(records)
            wrong = [
                (r["title"], d)
                for r, d in zip(records, decisions)
                if (r["label"] and d == "rejected") or (not r["label"] and d == "accepted")
            ]
            # Hard slices: require 85% non-contradiction (pending is fine)
            assert len(wrong) <= 0.15 * len(records), f"{f.name}: {wrong[:5]}"
