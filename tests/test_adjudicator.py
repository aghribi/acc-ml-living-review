"""Tests for the Stage C NLI adjudicator."""

import pytest

from living_review.adjudicator import AdjudicationResult, NLIAdjudicator


class TestThresholdLogic:
    def _adjudicator_with_scores(self, monkeypatch, scores):
        adj = NLIAdjudicator(thresholds={"accept": 0.85, "reject": 0.25})
        monkeypatch.setattr(adj, "score", lambda papers: scores)
        return adj

    def test_three_way_decision(self, monkeypatch, make_paper):
        adj = self._adjudicator_with_scores(monkeypatch, [0.95, 0.5, 0.1])
        results = adj.adjudicate([make_paper(), make_paper(), make_paper()])
        assert [r.decision for r in results] == ["accepted", "pending", "rejected"]
        assert results[0].score == 0.95
        assert results[0].model == adj.model_name

    def test_boundary_values(self, monkeypatch, make_paper):
        adj = self._adjudicator_with_scores(monkeypatch, [0.85, 0.25])
        results = adj.adjudicate([make_paper(), make_paper()])
        assert [r.decision for r in results] == ["accepted", "rejected"]

    def test_error_marks_batch_pending(self, monkeypatch, make_paper):
        adj = NLIAdjudicator()
        monkeypatch.setattr(
            adj, "score", lambda papers: (_ for _ in ()).throw(RuntimeError("model down"))
        )
        results = adj.adjudicate([make_paper(), make_paper()])
        assert all(r.decision == "pending" for r in results)
        assert all(r.rule == "adjudicator_error" for r in results)
        assert all(r.score is None for r in results)

    def test_empty_input(self):
        assert NLIAdjudicator().adjudicate([]) == []


@pytest.mark.slow
class TestNLISmoke:
    """Downloads the real model; run with `pytest -m slow` or full `pytest`."""

    def test_obvious_accept_scores_above_obvious_reject(self, make_paper):
        adj = NLIAdjudicator()
        genuine = make_paper(
            title="Reinforcement learning for online tuning of the LCLS linac",
            abstract="We use RL to tune quadrupole magnets and RF phases of the "
            "linear accelerator, maximizing FEL pulse energy of the light source.",
        )
        junk = make_paper(
            title="Machine learning for customer churn prediction in retail",
            abstract="We predict which customers will leave a subscription service "
            "using gradient boosted trees on purchase histories.",
        )
        s_genuine, s_junk = adj.score([genuine, junk])
        assert s_genuine > s_junk
        assert s_genuine > 0.5
        assert s_junk < 0.5
