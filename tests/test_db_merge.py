"""Tests for Paper.merge_with and DB merge semantics."""

import pytest

from living_review.data_model import Paper, status_rank
from living_review.db import DB


class TestStatusRank:
    def test_core_order(self):
        assert status_rank("published") > status_rank("preprint") > status_rank("pending")

    def test_legacy_statuses_ranked(self):
        # Legacy values from the live DB must rank deterministically (was -1).
        assert status_rank("proceeding") == status_rank("published")
        assert status_rank("report") == status_rank("published")
        assert status_rank("phd") == status_rank("published")
        assert status_rank("internship") == status_rank("preprint")
        assert status_rank("unknown") == -1
        assert status_rank(None) == -1


class TestMergeWith:
    def test_fills_missing_identifiers_and_upgrades_hash_id(self, make_paper):
        a = make_paper(title="Same Work")
        assert a.id.startswith("hash:")
        b = make_paper(title="Same Work", doi="10.1000/abc")
        assert a.merge_with(b)
        assert a.doi == "10.1000/abc"
        assert a.id == "doi:10.1000/abc"

    def test_prefers_longer_abstract(self, make_paper):
        a = make_paper(abstract="short")
        b = make_paper(abstract="a much longer abstract with details")
        a.merge_with(b)
        assert a.abstract == "a much longer abstract with details"

    def test_prefers_real_venue_over_placeholder(self, make_paper):
        a = make_paper(venue="arXiv")
        b = make_paper(venue="Phys. Rev. Accel. Beams")
        a.merge_with(b)
        assert a.venue == "Phys. Rev. Accel. Beams"

    def test_status_promotion(self, make_paper):
        a = make_paper(status="preprint")
        b = make_paper(status="published")
        a.merge_with(b)
        assert a.status == "published"

    def test_unions_links_and_sources(self, make_paper):
        a = make_paper(links={"arxiv": "http://a"}, source="arxiv")
        b = make_paper(links={"doi": "http://d"}, source="crossref")
        a.merge_with(b)
        assert a.links == {"arxiv": "http://a", "doi": "http://d"}
        assert len(a.sources) == 2

    def test_curated_fields_protected(self, make_paper):
        a = make_paper(abstract="curator-approved abstract", venue="IPAC'23", status="published")
        a.curated = True
        a.notes = "hand-checked"
        b = make_paper(
            abstract="a much longer machine-fetched abstract that would normally win",
            venue="Some Other Venue",
            status="retracted",
        )
        a.merge_with(b)
        assert a.abstract == "curator-approved abstract"
        assert a.venue == "IPAC'23"
        assert a.status == "published"
        assert a.notes == "hand-checked"

    def test_terminal_review_never_overwritten(self, make_paper):
        a = make_paper()
        a.review = {"decision": "accepted", "stage": "human"}
        b = make_paper()
        b.review = {"decision": "rejected", "stage": "nli", "score": 0.1}
        a.merge_with(b)
        assert a.review["decision"] == "accepted"
        assert a.review["stage"] == "human"

    def test_undecided_adopts_incoming_decision(self, make_paper):
        a = make_paper()
        b = make_paper()
        b.review = {"decision": "rejected", "stage": "gate", "rule": "hw_accelerator"}
        a.merge_with(b)
        assert a.review["decision"] == "rejected"

    def test_pending_is_not_terminal(self, make_paper):
        a = make_paper()
        a.review = {"decision": "pending", "stage": "nli"}
        b = make_paper()
        b.review = {"decision": "accepted", "stage": "human"}
        a.merge_with(b)
        assert a.review["decision"] == "accepted"

    def test_no_change_returns_false(self, make_paper):
        a = make_paper(doi="10.1000/x", abstract="same")
        b = make_paper(doi="10.1000/x", abstract="same")
        b.sources = list(a.sources)  # identical provenance
        assert a.merge_with(b) is False
        assert a.history == []


class TestDBMerge:
    def test_merge_same_key_merges_fields(self, make_paper):
        db = DB()
        a = make_paper(doi="10.1000/x", abstract="short")
        b = make_paper(doi="10.1000/x", abstract="much longer abstract here")
        b.sources = [{"source": "crossref", "seen_at": "2024-01-01T00:00:00Z"}]
        db.merge_from_list([a])
        db.merge_from_list([b])
        assert len(db) == 1
        merged = next(iter(db))
        assert merged.abstract == "much longer abstract here"

    def test_curated_survives_db_merge(self, make_paper):
        db = DB()
        a = make_paper(doi="10.1000/x", abstract="curated text")
        a.curated = True
        db.merge_from_list([a])
        b = make_paper(doi="10.1000/x", abstract="incoming much longer abstract text")
        db.merge_from_list([b])
        assert next(iter(db)).abstract == "curated text"
