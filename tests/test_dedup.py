"""Tests for two-pass deduplication (identifier graph + fuzzy titles)."""

import json
from pathlib import Path

import pytest

from living_review.data_model import Paper
from living_review.db import DB
from living_review.dedup import dedup_papers
from living_review.utils import canonical_ids

FIXTURES = Path(__file__).parent / "fixtures"


def load_cluster(name):
    with open(FIXTURES / name, encoding="utf-8") as f:
        return [Paper.from_dict(d) for d in json.load(f)]


class TestCanonicalIdsDataCite:
    def test_datacite_arxiv_doi_yields_arxiv_id(self, make_paper):
        p = make_paper(doi="10.48550/arXiv.2510.26805")
        assert "arxiv:2510.26805" in canonical_ids(p)


class TestDedupRealClusters:
    def test_rl_beamline_4x_cluster_collapses_to_one(self):
        # Real cluster from the live DB: arXiv record, DataCite-DOI record,
        # journal-DOI record, and an id-less record — 4 entries, one work.
        papers = load_cluster("dup_cluster_rl_beamline.json")
        assert len(papers) == 4
        merged = dedup_papers(papers)
        assert len(merged) == 1
        p = merged[0]
        # Identifiers accumulated from all records
        assert p.arxiv_id == "2510.26805"
        assert p.doi is not None

    def test_psi_injector_3x_cluster_collapses_to_one(self):
        papers = load_cluster("dup_cluster_psi.json")
        assert len(papers) == 3
        assert len(dedup_papers(papers)) == 1


class TestDedupSynthetic:
    def test_shared_arxiv_id_merges(self, make_paper):
        a = make_paper(title="Title variant one", arxiv_id="2401.00001")
        b = make_paper(title="A very different title", arxiv_id="2401.00001v2")
        assert len(dedup_papers([a, b])) == 1

    def test_transitive_identifier_merge(self, make_paper):
        # a shares arxiv with b; b shares doi with c => all one work
        a = make_paper(title="T1", arxiv_id="2401.00002")
        b = make_paper(title="T2", arxiv_id="2401.00002", doi="10.1/x")
        c = make_paper(title="T3", doi="10.1/x")
        assert len(dedup_papers([a, b, c])) == 1

    def test_fuzzy_title_same_year_merges(self, make_paper):
        a = make_paper(title="Machine Learning for RF Cavity Fault Detection", year=2023)
        b = make_paper(title="Machine learning for RF-cavity fault detection.", year=2023)
        assert len(dedup_papers([a, b])) == 1

    def test_fuzzy_title_adjacent_year_merges(self, make_paper):
        # preprint year N, journal year N+1
        a = make_paper(title="Surrogate models for linac emittance prediction", year=2022)
        b = make_paper(title="Surrogate Models for Linac Emittance Prediction", year=2023)
        assert len(dedup_papers([a, b])) == 1

    def test_different_papers_not_merged(self, make_paper):
        a = make_paper(title="Bayesian optimization of storage ring lattices", year=2023)
        b = make_paper(title="Anomaly detection in cryomodule sensor data", year=2023)
        assert len(dedup_papers([a, b])) == 2

    def test_decided_record_is_primary(self, make_paper):
        a = make_paper(title="Same Paper Title", arxiv_id="2401.00003")
        b = make_paper(title="Same Paper Title", arxiv_id="2401.00003")
        b.review = {"decision": "accepted", "stage": "human"}
        merged = dedup_papers([a, b])
        assert len(merged) == 1
        assert merged[0].review.get("decision") == "accepted"


class TestDBIncrementalDedup:
    def test_incoming_shared_id_merges_into_existing(self, make_paper):
        db = DB()
        db.merge_from_list([make_paper(title="Original title", arxiv_id="2401.00004")])
        db.merge_from_list(
            [make_paper(title="Journal version with amended title", arxiv_id="2401.00004", doi="10.1/j")]
        )
        assert len(db) == 1
        p = next(iter(db))
        assert p.doi == "10.1/j"

    def test_incoming_fuzzy_title_merges(self, make_paper):
        db = DB()
        db.merge_from_list([make_paper(title="Deep learning based beam loss prediction", year=2024)])
        db.merge_from_list([make_paper(title="Deep-Learning-Based Beam Loss Prediction", year=2024, doi="10.1/k")])
        assert len(db) == 1

    def test_key_upgrades_from_hash_to_doi(self, make_paper):
        db = DB()
        a = make_paper(title="Hash keyed paper", year=2024)
        db.merge_from_list([a])
        assert list(db.entries)[0].startswith("hash:")
        db.merge_from_list([make_paper(title="Hash keyed paper", year=2024, doi="10.1/m")])
        assert len(db) == 1
        assert list(db.entries)[0] == "doi:10.1/m"

    def test_load_rekeys_legacy_tuple_keys(self, tmp_path, make_paper):
        # Legacy DB files are keyed by str((arxiv, doi, title)) tuples.
        p = make_paper(doi="10.1/legacy")
        legacy = {"papers": {str(p.key_for_dedup()): p.to_dict()}}
        f = tmp_path / "db.json"
        f.write_text(json.dumps(legacy), encoding="utf-8")
        db = DB.load(f)
        assert list(db.entries) == ["doi:10.1/legacy"]
