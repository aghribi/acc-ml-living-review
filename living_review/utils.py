"""
utils.py
========

Utility functions for the **Living Review** project.

This module provides helper functions for:
- Deduplicating papers based on unique keys.
- Normalizing identifiers (DOI, arXiv ID).
- Cleaning up LaTeX markup and titles for comparison.
- Fuzzy similarity scoring between titles.
- Checking if a date lies within a given range.

Contents
--------
- deduplicate: remove duplicate papers by `(arxiv_id, doi, normalized_title)`.
- within_range: test whether a date falls within [start, end].
- norm_doi: normalize DOI strings to a canonical form.
- norm_arxiv_id: normalize arXiv identifiers to a canonical form.
- simplify_title: lowercase, strip LaTeX and punctuation for fuzzy matching.
- first_author_key: heuristic to extract first author surname.
- similar_title: fuzzy similarity score between two titles.

Typical Usage
-------------
>>> from living_review.utils import norm_doi, simplify_title, within_range
>>> norm_doi("https://doi.org/10.1103/PhysRevLett.123.456")
'10.1103/physrevlett.123.456'
>>> simplify_title("A {LaTeX} Example: On $\\alpha$-decay")
'a latex example on alpha decay'
>>> within_range(dt.date(2025, 1, 10), start, end)
True
"""

import datetime as dt
import re
import difflib
from typing import Optional, List
import requests
from requests.adapters import HTTPAdapter, Retry

def deduplicate(papers):
    """
    Remove duplicate papers based on their deduplication key.

    Each `Paper` must implement `.key_for_dedup()` which returns a tuple
    `(arxiv_id, doi, normalized_title)`. Duplicates are detected when
    this key repeats.

    Parameters
    ----------
    papers : list of Paper
        Papers to deduplicate.

    Returns
    -------
    list of Paper
        Deduplicated list of papers (order preserved: first occurrence kept).
    """
    seen = set()
    out = []
    for p in papers:
        k = p.key_for_dedup()
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def within_range(d: dt.date, start: dt.date, end: dt.date) -> bool:
    """
    Check whether a date lies within a given range [start, end].

    Parameters
    ----------
    d : datetime.date
        Date to test.
    start : datetime.date
        Start of the range.
    end : datetime.date
        End of the range.

    Returns
    -------
    bool
        True if `start <= d <= end`, otherwise False.
    """
    return (start is None or d >= start) and (end is None or d <= end)


# ----------------------------------------------------------------------
# Normalization helpers
# ----------------------------------------------------------------------

def norm_space(s: Optional[str]) -> Optional[str]:
    """Collapse multiple spaces and trim a string."""
    return re.sub(r"\s+", " ", s.strip()) if s else s


def norm_doi(doi: Optional[str]) -> Optional[str]:
    """Normalize DOI to lowercase without URL prefixes."""
    if not doi:
        return None
    doi = doi.strip().lower()
    doi = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi)
    doi = re.sub(r"^doi:\s*", "", doi)
    return doi or None


def norm_arxiv_id(ax: Optional[str]) -> Optional[str]:
    """Normalize arXiv identifiers (remove prefix and version)."""
    if not ax:
        return None
    s = ax.strip()
    s = s.replace("https://arxiv.org/abs/", "").replace("http://arxiv.org/abs/", "")
    s = s.replace("arxiv:", "").replace("ArXiv:", "").replace("ARXIV:", "")
    s = s.split("v")[0]  # drop explicit version for canonical id
    return s or None


def _strip_tex(s: str) -> str:
    """Remove LaTeX markup and braces from a string."""
    s = re.sub(r"\\[a-zA-Z]+(\[[^\]]*\])?(\{[^}]*\})?", " ", s)
    s = s.replace("{", " ").replace("}", " ")
    return re.sub(r"\s+", " ", s).strip()


def simplify_title(t: Optional[str]) -> Optional[str]:
    """Lowercase, strip LaTeX, punctuation, and extra spaces from title."""
    if not t:
        return None
    t = _strip_tex(t).lower()
    t = re.sub(r"[^\w\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def first_author_key(authors: List[str]) -> Optional[str]:
    """
    Heuristic key for first author: uses last token of first author's name.
    Returns lowercase surname or None if unavailable.
    """
    if not authors:
        return None
    parts = re.split(r"\s+", authors[0].strip())
    return parts[-1].lower() if parts else None


def similar_title(a: str, b: str) -> float:
    """
    Compute fuzzy similarity ratio between two titles.

    Parameters
    ----------
    a, b : str
        Titles to compare.

    Returns
    -------
    float
        Similarity ratio in [0, 1], where 1 = identical.
    """
    return difflib.SequenceMatcher(None, simplify_title(a) or "", simplify_title(b) or "").ratio()

def make_session():
    """
    Create a shared requests.Session with retry strategy.
    Retries on server errors (500, 502, 503, 504) up to 3 times with
    exponential backoff.
    """
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1,
                    status_forcelist=[500, 502, 503, 504])
    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session

# global session instance
SESSION = make_session()