"""Tests for identifier normalization and canonical id helpers in utils.py."""

import pytest

from living_review.utils import canonical_ids, norm_arxiv_id, norm_doi, similar_title


class TestNormDoi:
    def test_plain_doi_lowercased(self):
        assert norm_doi("10.1103/PhysRevLett.123.456") == "10.1103/physrevlett.123.456"

    def test_url_prefixes_stripped(self):
        assert norm_doi("https://doi.org/10.1000/xyz") == "10.1000/xyz"
        assert norm_doi("http://dx.doi.org/10.1000/xyz") == "10.1000/xyz"

    def test_doi_prefix_stripped(self):
        assert norm_doi("doi: 10.1000/xyz") == "10.1000/xyz"

    def test_empty_returns_none(self):
        assert norm_doi(None) is None
        assert norm_doi("") is None


class TestNormArxivId:
    def test_new_style_id(self):
        assert norm_arxiv_id("2401.12345") == "2401.12345"

    def test_version_suffix_stripped(self):
        assert norm_arxiv_id("2401.12345v2") == "2401.12345"
        assert norm_arxiv_id("2401.12345v10") == "2401.12345"

    def test_abs_url_stripped(self):
        assert norm_arxiv_id("https://arxiv.org/abs/2401.12345v1") == "2401.12345"
        assert norm_arxiv_id("http://arxiv.org/abs/2401.12345") == "2401.12345"

    def test_prefix_stripped_case_insensitive(self):
        assert norm_arxiv_id("arXiv:2401.12345") == "2401.12345"
        assert norm_arxiv_id("ARXIV:2401.12345") == "2401.12345"

    def test_old_style_id_with_v_in_archive_name_survives(self):
        # Regression: the old implementation split on the first "v",
        # truncating archive names like "solv-int/9701001" to "sol".
        assert norm_arxiv_id("solv-int/9701001") == "solv-int/9701001"
        assert norm_arxiv_id("physics/0605197v2") == "physics/0605197"
        assert norm_arxiv_id("hep-ex/9901001") == "hep-ex/9901001"

    def test_empty_returns_none(self):
        assert norm_arxiv_id(None) is None
        assert norm_arxiv_id("") is None


class TestCanonicalIds:
    def test_all_identifiers_present(self, make_paper):
        p = make_paper(doi="10.1000/XYZ", arxiv_id="2401.12345v3", inspire_id="123456")
        assert canonical_ids(p) == {
            "doi:10.1000/xyz",
            "arxiv:2401.12345",
            "inspire:123456",
        }

    def test_missing_identifiers_omitted(self, make_paper):
        p = make_paper()
        assert canonical_ids(p) == set()

    def test_only_doi(self, make_paper):
        p = make_paper(doi="10.1000/abc")
        assert canonical_ids(p) == {"doi:10.1000/abc"}


class TestSimilarTitle:
    def test_identical_after_latex_stripping(self):
        a = "Machine {Learning} for Beam Dynamics!"
        b = "machine learning for beam dynamics"
        assert similar_title(a, b) == 1.0

    def test_different_titles_low_score(self):
        assert similar_title("Beam dynamics with ML", "Customer churn prediction") < 0.5
