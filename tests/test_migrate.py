"""Regression tests for the one-off migration, incl. the already-migrated
source footgun: migrating the published (accepted-only, decided) JSON must
carry decisions over instead of publishing an empty set."""

import json

import pytest

import living_review.migrate as migrate_mod
from living_review.adjudicator import AdjudicationResult
from living_review.data_model import Paper
from living_review.migrate import migrate


class AcceptLinacs:
    def adjudicate(self, papers):
        return [
            AdjudicationResult(
                decision="accepted" if "linac" in p.title.lower() else "rejected",
                score=0.95 if "linac" in p.title.lower() else 0.05,
                model="fake",
                revision=None,
            )
            for p in papers
        ]


def _legacy_file(tmp_path):
    papers = {
        "k1": {"id": "arxiv:2401.1", "arxiv_id": "2401.1", "title": "RL at the synchrotron",
               "abstract": "Beam control with RL.", "year": 2024,
               "arxiv_categories": ["physics.acc-ph"]},
        "k2": {"id": "doi:10.1/a", "doi": "10.1/a", "title": "Neural surrogate of a linac",
               "abstract": "We model the linac injector beam.", "year": 2024,
               "venue": "NeurIPS Workshop"},
        "k3": {"id": "doi:10.1/b", "doi": "10.1/b", "title": "Customer churn prediction",
               "abstract": "Churn for marketing.", "year": 2024, "venue": "Marketing"},
    }
    f = tmp_path / "legacy.json"
    f.write_text(json.dumps({"papers": papers}), encoding="utf-8")
    return f


@pytest.fixture
def run_migrate(tmp_path, monkeypatch):
    (tmp_path / "site").mkdir()
    monkeypatch.setattr(migrate_mod, "backfill_abstracts", lambda ps: 0)
    monkeypatch.setattr(migrate_mod, "fetch_arxiv_metadata", lambda ids: {})
    monkeypatch.setattr(
        migrate_mod, "classify_papers",
        lambda ps: [setattr(p, "categories", [{"label": "Operations & Control", "score": 0.6}]) for p in ps],
    )
    monkeypatch.setattr(migrate_mod, "export_pdf", lambda *a, **k: None)
    monkeypatch.setattr(migrate_mod, "export_bibtex", lambda *a, **k: None)

    def _run(source):
        migrate(
            source=str(source),
            db_path=str(tmp_path / "data" / "db.json"),
            report_path=str(tmp_path / "data" / "migration_dropped.md"),
            eval_dir=str(tmp_path / "data" / "eval"),
            adjudicator=AcceptLinacs(),
            output_dir=str(tmp_path),
        )
        db = json.loads((tmp_path / "data" / "db.json").read_text())
        pub = json.loads((tmp_path / "site" / "data" / "livingreview.json").read_text())
        return db, pub

    return _run


class TestMigrate:
    def test_fresh_migration(self, tmp_path, run_migrate):
        db, pub = run_migrate(_legacy_file(tmp_path))
        assert len(db["papers"]) == 3
        titles = {p["title"] for p in pub["papers"].values()}
        assert titles == {"RL at the synchrotron", "Neural surrogate of a linac"}
        report = (tmp_path / "data" / "migration_dropped.md").read_text()
        assert "Customer churn prediction" in report

    def test_remigrating_published_output_keeps_accepted(self, tmp_path, run_migrate):
        # Regression: a second migrate pointed at the published JSON must not
        # publish an empty set — decided papers carry over.
        run_migrate(_legacy_file(tmp_path))
        _, pub2 = run_migrate(tmp_path / "site" / "data" / "livingreview.json")
        titles = {p["title"] for p in pub2["papers"].values()}
        assert titles == {"RL at the synchrotron", "Neural surrogate of a linac"}
