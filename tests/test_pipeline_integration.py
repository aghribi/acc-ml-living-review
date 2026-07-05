"""End-to-end pipeline test with mocked fetchers and a fake adjudicator.

Verifies the funnel invariants without any network or model download:
- gates and adjudicator route papers to accepted/rejected/pending,
- only accepted papers reach the published JSON,
- decisions are terminal: a second run adjudicates nothing.
"""

import json

import pytest

import living_review.pipeline as pipeline_mod
import living_review.relevance as relevance_mod
from living_review.adjudicator import AdjudicationResult
from living_review.data_model import Paper
from living_review.pipeline import LivingReviewPipeline


class FakeAdjudicator:
    """Deterministic scores by title keyword; counts invocations."""

    def __init__(self):
        self.calls = 0
        self.seen = []

    def adjudicate(self, papers):
        self.calls += 1
        self.seen.extend(p.title for p in papers)
        results = []
        for p in papers:
            score = 0.95 if "linac" in p.title.lower() else 0.05
            decision = "accepted" if score >= 0.85 else "rejected"
            results.append(
                AdjudicationResult(decision=decision, score=score, model="fake", revision=None)
            )
        return results


def _fixture_papers():
    def paper(**kw):
        base = {"authors": ["A. Author"], "year": 2024, "date": "2024-05-01", "source": "arxiv"}
        base.update(kw)
        return Paper.from_source(base)

    return [
        # auto-accept: acc-ph primary
        paper(title="RL control of the booster", abstract="Beam control with RL at the synchrotron.",
              arxiv_id="2405.00001", arxiv_categories=["physics.acc-ph", "cs.LG"]),
        # gray -> fake NLI accepts ("linac")
        paper(title="Neural surrogate of a linac injector", venue="NeurIPS Workshop",
              abstract="We model beam dynamics of the linac injector with neural networks.",
              arxiv_id="2405.00002", arxiv_categories=["cs.LG"]),
        # auto-reject: foreign domain, no accel vocab
        paper(title="Machine learning for customer churn", venue="Marketing Science",
              abstract="Churn prediction for e-commerce marketing campaigns.", doi="10.1/churn"),
        # gray -> fake NLI rejects
        paper(title="Deep learning for civil engineering columns", venue="Engineering Structures",
              abstract="We predict beam and column failure loads in buildings with deep learning.",
              doi="10.1/civil"),
        # empty abstract -> pending
        paper(title="Untitled accelerator note", abstract="", venue="Some Journal", doi="10.1/empty"),
    ]


@pytest.fixture
def run_pipeline(tmp_path, monkeypatch):
    """Factory running the pipeline in a tmp dir with mocked externals."""

    def _run(adjudicator, papers):
        import datetime as dt

        (tmp_path / "site").mkdir(exist_ok=True)  # exporters resolve against site/
        monkeypatch.setattr(pipeline_mod, "fetch_arxiv", lambda s, e: papers)
        # No network in enrichment or pending-ranking
        monkeypatch.setattr(relevance_mod, "backfill_abstracts", lambda ps: 0)
        monkeypatch.setattr(relevance_mod, "rank_pending", lambda ps: list(ps))
        # No MiniLM: classification stub assigns a real category
        monkeypatch.setattr(
            pipeline_mod,
            "classify_papers",
            lambda ps: [setattr(p, "categories", [{"label": "Operations & Control", "score": 0.6}]) for p in ps],
        )
        pipe = LivingReviewPipeline(
            dt.date(2024, 5, 1),
            dt.date(2024, 5, 31),
            sources=["arxiv"],
            output_dir=str(tmp_path),
            db_path=str(tmp_path / "data" / "db.json"),
            adjudicator=adjudicator,
        )
        pipe.export_pdf = False
        pipe.export_bibtex = False
        pipe.run()
        return pipe

    return _run


class TestPipelineEndToEnd:
    def test_routing_and_publication(self, tmp_path, run_pipeline):
        adj = FakeAdjudicator()
        run_pipeline(adj, _fixture_papers())

        db = json.loads((tmp_path / "data" / "db.json").read_text())
        decisions = {p["title"]: p["review"]["decision"] for p in db["papers"].values()}
        assert decisions["RL control of the booster"] == "accepted"
        assert decisions["Neural surrogate of a linac injector"] == "accepted"
        assert decisions["Machine learning for customer churn"] == "rejected"
        assert decisions["Deep learning for civil engineering columns"] == "rejected"
        assert decisions["Untitled accelerator note"] == "pending"

        # Published JSON contains only the accepted two
        published = json.loads((tmp_path / "site" / "data" / "livingreview.json").read_text())
        titles = {p["title"] for p in published["papers"].values()}
        assert titles == {"RL control of the booster", "Neural surrogate of a linac injector"}

        # Pending queue holds the empty-abstract paper
        queue = json.loads((tmp_path / "data" / "pending_review.json").read_text())
        assert [q["title"] for q in queue] == ["Untitled accelerator note"]
        assert queue[0]["review"]["rule"] == "empty_abstract"

        # Provenance recorded
        churn = next(p for p in db["papers"].values() if "churn" in p["title"])
        assert churn["review"]["stage"] == "gate"
        assert churn["review"]["rule"] == "auto_reject:foreign_domain"

    def test_second_run_adjudicates_nothing_terminal(self, tmp_path, run_pipeline):
        adj = FakeAdjudicator()
        run_pipeline(adj, _fixture_papers())
        first_gray = list(adj.seen)

        # Second run: same papers arrive again from the fetcher
        run_pipeline(adj, _fixture_papers())
        # Terminal decisions are never re-adjudicated: only the pending
        # empty-abstract paper could return, and it gates to pending before
        # reaching the adjudicator — so no new adjudications at all.
        assert adj.seen == first_gray

        db = json.loads((tmp_path / "data" / "db.json").read_text())
        assert len(db["papers"]) == 5  # no duplicates from the re-fetch

    def test_flipped_adjudicator_cannot_rewrite_decisions(self, tmp_path, run_pipeline):
        run_pipeline(FakeAdjudicator(), _fixture_papers())

        class AcceptEverything:
            def adjudicate(self, papers):
                return [
                    AdjudicationResult(decision="accepted", score=1.0, model="flip", revision=None)
                    for _ in papers
                ]

        run_pipeline(AcceptEverything(), _fixture_papers())
        db = json.loads((tmp_path / "data" / "db.json").read_text())
        decisions = {p["title"]: p["review"]["decision"] for p in db["papers"].values()}
        # The civil-engineering paper was NLI-rejected on run 1; a changed
        # adjudicator must not resurrect it.
        assert decisions["Deep learning for civil engineering columns"] == "rejected"


class TestOthersOnlyDemotion:
    def test_others_only_paper_is_withheld(self, make_paper):
        from living_review.relevance import demote_others_only, set_review

        good = make_paper(title="Good paper")
        good.categories = [{"label": "Surrogate Models", "score": 0.5}]
        set_review(good, "accepted", "gate", "auto_accept:acc-ph")
        stray = make_paper(title="Stray paper")
        stray.categories = [{"label": "Others", "score": 0.0}]
        set_review(stray, "accepted", "nli", score=0.9)

        publishable = demote_others_only([good, stray])
        assert publishable == [good]
        assert stray.review["decision"] == "pending"
        assert stray.review["rule"] == "others_only"
