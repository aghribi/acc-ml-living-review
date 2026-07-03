"""Shared fixtures for the living_review test suite."""

import pytest

from living_review.data_model import Paper


@pytest.fixture
def make_paper():
    """Factory for Paper objects with sensible defaults."""

    def _make(**kwargs):
        raw = {
            "title": kwargs.pop("title", "A Test Paper on Beam Dynamics"),
            "authors": kwargs.pop("authors", ["Jane Doe", "John Smith"]),
            "abstract": kwargs.pop("abstract", "We study machine learning for beam control."),
            "year": kwargs.pop("year", 2024),
            "date": kwargs.pop("date", "2024-05-01"),
            "venue": kwargs.pop("venue", "Phys. Rev. Accel. Beams"),
            "source": kwargs.pop("source", "test"),
        }
        raw.update(kwargs)
        return Paper.from_source(raw)

    return _make
