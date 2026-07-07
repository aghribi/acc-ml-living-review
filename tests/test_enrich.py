"""Tests for abstract backfill (enrich.py) with stubbed HTTP."""

import pytest

from living_review.enrich import (
    backfill_abstracts,
    reconstruct_openalex_abstract,
    strip_jats,
)


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Maps URL substrings to canned responses; anything else 404s."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        for frag, resp in self.routes.items():
            if frag in url:
                return resp
        return FakeResponse({}, status=404)


class TestStripJats:
    def test_removes_tags_and_heading(self):
        raw = "<jats:p>Abstract We study <jats:italic>beams</jats:italic>.</jats:p>"
        assert strip_jats(raw) == "We study beams ."

    def test_empty(self):
        assert strip_jats(None) == ""


class TestInvertedIndex:
    def test_reconstruction_orders_words(self):
        inv = {"beams": [2], "We": [0], "study": [1]}
        assert reconstruct_openalex_abstract(inv) == "We study beams"

    def test_repeated_words(self):
        inv = {"the": [0, 2], "beam": [1, 3]}
        assert reconstruct_openalex_abstract(inv) == "the beam the beam"

    def test_empty(self):
        assert reconstruct_openalex_abstract(None) == ""


class TestBackfillAbstracts:
    def test_crossref_fills_empty_abstract(self, make_paper):
        p = make_paper(abstract="", doi="10.1/x")
        session = FakeSession(
            {"crossref.org": FakeResponse({"message": {"abstract": "<jats:p>Found text</jats:p>"}})}
        )
        n = backfill_abstracts([p], session=session, arxiv_lookup=lambda ids: {})
        assert n == 1
        assert p.abstract == "Found text"
        assert p.history[-1]["event"] == "enriched"
        assert p.history[-1]["source"] == "crossref"

    def test_openalex_fallback_when_crossref_empty(self, make_paper):
        p = make_paper(abstract="", doi="10.1/y")
        session = FakeSession(
            {
                "crossref.org": FakeResponse({"message": {}}),
                "openalex.org": FakeResponse(
                    {"abstract_inverted_index": {"Rebuilt": [0], "text": [1]}}
                ),
            }
        )
        n = backfill_abstracts([p], session=session, arxiv_lookup=lambda ids: {})
        assert n == 1
        assert p.abstract == "Rebuilt text"

    def test_arxiv_batch_for_papers_without_doi(self, make_paper):
        p = make_paper(abstract="", arxiv_id="2401.00001")
        n = backfill_abstracts(
            [p],
            session=FakeSession({}),
            arxiv_lookup=lambda ids: {"2401.00001": "arXiv summary text"},
        )
        assert n == 1
        assert p.abstract == "arXiv summary text"
        assert p.history[-1]["source"] == "arxiv"

    def test_existing_abstract_never_overwritten(self, make_paper):
        p = make_paper(abstract="original text", doi="10.1/z")
        session = FakeSession(
            {"crossref.org": FakeResponse({"message": {"abstract": "other"}})}
        )
        n = backfill_abstracts([p], session=session, arxiv_lookup=lambda ids: {})
        assert n == 0
        assert p.abstract == "original text"
        assert session.calls == []

    def test_network_failure_is_nonfatal(self, make_paper):
        p = make_paper(abstract="", doi="10.1/fail")
        session = FakeSession({"crossref.org": FakeResponse({}, status=500)})
        n = backfill_abstracts([p], session=session, arxiv_lookup=lambda ids: {})
        assert n == 0
        assert (p.abstract or "") == ""
