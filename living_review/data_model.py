"""
data_model.py
=============

Data model definitions for the **Living Review** project.

This module defines the `Paper` dataclass, the central representation of
a scientific paper throughout the pipeline. It ensures consistent handling
of metadata, provenance, and status progression, and provides helpers for
deduplication and serialization.

Contents
--------
- `Paper`: dataclass representing a paper with metadata, provenance,
  and audit trail.
- `status_rank`: helper to order publication statuses.
- `_canonical_key`: helper to generate fallback IDs for deduplication.

Canonical use
-------------
- Every paper is represented internally as a `Paper` object.
- Papers are serialized into the canonical JSON DB
  (`site/data/livingreview.json`) via `Paper.to_dict()`.
- Papers can be reconstructed from the DB via `Paper.from_dict()`,
  guaranteeing a stable round-trip between memory and storage.

Typical Usage
-------------
>>> from living_review.data_model import Paper
>>> raw = {"title": "AI for Beam Dynamics", "authors": ["A. Researcher"],
...        "arxiv_id": "1234.5678", "source": "arxiv"}
>>> p = Paper.from_source(raw)
>>> p.key_for_dedup()
('1234.5678', '', 'ai for beam dynamics')
>>> d = p.to_dict()
>>> Paper.from_dict(d).id
'arxiv:1234.5678'
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import hashlib

from .utils import norm_space, norm_doi, norm_arxiv_id, simplify_title, first_author_key


# Publication status ordering (used in merges/status promotion)
STATUS_ORDER = ["pending", "submitted", "preprint", "accepted", "published", "retracted"]


def status_rank(status: Optional[str]) -> int:
    """
    Return integer rank of a status (higher = more advanced).

    Parameters
    ----------
    status : str or None
        Status string (pending, preprint, published...).

    Returns
    -------
    int
        Position in STATUS_ORDER, or -1 if unknown.
    """
    if not status:
        return -1
    try:
        return STATUS_ORDER.index(status)
    except ValueError:
        return -1


def _canonical_key(title: str, year: Optional[int], first_author: Optional[str]) -> str:
    """
    Build a stable hash key for fallback deduplication.

    Parameters
    ----------
    title : str
        Paper title (simplified).
    year : int, optional
        Publication year.
    first_author : str, optional
        First author string.

    Returns
    -------
    str
        Short SHA1-based hash (12 characters).
    """
    base = f"{first_author or ''}:{year or ''}:{simplify_title(title) or ''}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


@dataclass
class Paper:
    """
    Representation of a scientific paper.

    Attributes
    ----------
    id : str
        Canonical identifier (e.g. "doi:...", "arxiv:...", or "hash:...").
    doi : str, optional
        Digital Object Identifier if available.
    arxiv_id : str, optional
        arXiv identifier if available.
    inspire_id : str, optional
        INSPIRE identifier if available.
    title : str
        Title of the paper.
    authors : list of str
        List of author names.
    abstract : str, optional
        Abstract or summary of the paper.
    date : str, optional
        ISO date string (YYYY-MM-DD).
    year : int, optional
        Publication year.
    venue : str, optional
        Journal or conference venue.
    status : str, optional
        Publication status (pending, preprint, published...).
    categories : list of str
        Classification categories assigned to the paper.
    keywords : list of str
        List of keywords associated with the paper.
    curated : bool
        Whether this entry has been manually curated (protected from overwrite).
    notes : str, optional
        Free-text notes by curators.
    links : dict
        Dictionary of useful links (arXiv, DOI, PDF, publisher).
    sources : list of dict
        Provenance info (which fetcher, when).
    history : list of dict
        Change history (merges, status updates).
    last_updated : str, optional
        Timestamp of last update in ISO format.
    """

    id: str
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    inspire_id: Optional[str] = None

    title: str = ""
    authors: List[str] = field(default_factory=list)
    abstract: Optional[str] = None
    date: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    status: Optional[str] = None

    categories: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    curated: bool = False
    notes: Optional[str] = None

    links: Dict[str, str] = field(default_factory=dict)
    sources: List[Dict[str, str]] = field(default_factory=list)
    history: List[Dict[str, str]] = field(default_factory=list)

    last_updated: Optional[str] = None

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def from_source(raw: Dict) -> "Paper":
        """
        Build a Paper from raw metadata (dict).

        Normalizes identifiers, title, and authors, and ensures provenance.
        Will assign a canonical `id` of form:
        - doi:... (if DOI available),
        - arxiv:... (if arXiv available),
        - hash:... (fallback hash if no DOI/arXiv).

        Parameters
        ----------
        raw : dict
            Raw metadata from a fetcher.

        Returns
        -------
        Paper
            A new Paper object.
        """
        doi = norm_doi(raw.get("doi"))
        ax = norm_arxiv_id(raw.get("arxiv_id") or raw.get("arxiv") or raw.get("ArXiv"))
        title = norm_space(raw.get("title") or "") or ""
        authors = [norm_space(a) for a in (raw.get("authors") or []) if a and a.strip()]
        first = first_author_key(authors)

        # Try to determine year
        year = raw.get("year")
        date = raw.get("date")
        if (not year) and date:
            try:
                year = int(date[:4])
            except Exception:
                year = None

        # Canonical identifier
        if doi:
            cid = f"doi:{doi}"
        elif ax:
            cid = f"arxiv:{ax}"
        else:
            cid = f"hash:{_canonical_key(title, year, first)}"

        # Status
        status = raw.get("status") or ("preprint" if ax and not doi else None)
        now = datetime.utcnow().isoformat(timespec="seconds") + "Z"

        return Paper(
            id=cid,
            doi=doi,
            arxiv_id=ax,
            inspire_id=raw.get("inspire_id"),
            title=title,
            authors=authors,
            abstract=raw.get("abstract"),
            date=date,
            year=year,
            venue=raw.get("venue") or raw.get("journal") or ("arXiv" if ax else None),
            status=status,
            categories=list(dict.fromkeys(raw.get("categories") or [])),
            keywords=list(dict.fromkeys(raw.get("keywords") or [])),
            curated=bool(raw.get("curated", False)),
            notes=raw.get("notes"),
            links={k: v for k, v in (raw.get("links") or {}).items() if v},
            sources=[{"source": raw.get("source", "unknown"), "seen_at": now}],
            history=[],
            last_updated=now,
        )

    @staticmethod
    def from_dict(d: Dict) -> "Paper":
        """
        Reconstruct a Paper object from its dictionary representation.

        Used when loading from the canonical DB (`site/data/livingreview.json`).

        Parameters
        ----------
        d : dict
            Dictionary with Paper fields, as produced by `to_dict()`.

        Returns
        -------
        Paper
            A Paper instance with all fields populated.
        """
        return Paper(
            id=d.get("id", ""),
            doi=norm_doi(d.get("doi")),
            arxiv_id=norm_arxiv_id(d.get("arxiv_id")),
            inspire_id=d.get("inspire_id"),
            title=norm_space(d.get("title") or ""),
            authors=[norm_space(a) for a in (d.get("authors") or [])],
            abstract=d.get("abstract"),
            date=d.get("date"),
            year=d.get("year"),
            venue=d.get("venue"),
            status=d.get("status"),
            categories=list(d.get("categories") or []),
            keywords=list(d.get("keywords") or []),
            curated=bool(d.get("curated", False)),
            notes=d.get("notes"),
            links=d.get("links") or {},
            sources=d.get("sources") or [],
            history=d.get("history") or [],
            last_updated=d.get("last_updated"),
        )

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def key_for_dedup(self) -> Tuple[str, str, str]:
        """
        Generate a key for deduplication.

        Returns
        -------
        tuple of str
            (arxiv_id, doi, simplified_title)
        """
        return (self.arxiv_id or "", self.doi or "", simplify_title(self.title) or "")

    def to_dict(self) -> Dict:
        """
        Serialize Paper to a JSON-safe dict.

        This is the method used when writing to the canonical DB
        (`site/data/livingreview.json`). It ensures:
        - Normalized identifiers,
        - Always includes categories/keywords as lists,
        - Timestamps in ISO format.

        Returns
        -------
        dict
            Dictionary representation of the Paper.
        """
        d = asdict(self)
        d["doi"] = norm_doi(self.doi)
        d["arxiv_id"] = norm_arxiv_id(self.arxiv_id)
        d["categories"] = list(self.categories or [])
        d["keywords"] = list(self.keywords or [])
        return d
