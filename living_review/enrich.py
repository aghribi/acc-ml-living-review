"""
enrich.py
=========

Metadata backfill for papers with missing abstracts.

A third of the historical DB entries carry empty abstracts (one root cause:
OpenAlex returns `abstract_inverted_index`, not `abstract`). Since both the
relevance funnel and category classification score `title + abstract`,
papers without abstracts are systematically mis-scored. This module fills
the gap before any scoring runs:

1. Crossref by DOI (`/works/{doi}`, JATS markup stripped),
2. OpenAlex by DOI (`/works/doi:{doi}`, inverted index reconstructed),
3. arXiv by id (batched `id_list` queries, <= 100 ids per call).

Existing non-empty abstracts are never overwritten. All network failures
are warnings — enrichment must never break a pipeline run.
"""

import re
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from .data_model import Paper
from .utils import SESSION

CROSSREF_WORKS = "https://api.crossref.org/works/"
OPENALEX_WORKS = "https://api.openalex.org/works/"


def strip_jats(text: Optional[str]) -> str:
    """Remove JATS/XML tags and collapse whitespace in a Crossref abstract."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Crossref abstracts often start with a literal "Abstract" heading
    text = re.sub(r"^abstract[\s:]*", "", text, flags=re.IGNORECASE)
    return text


def reconstruct_openalex_abstract(inv: Optional[Dict[str, List[int]]]) -> str:
    """Rebuild plain text from an OpenAlex `abstract_inverted_index`."""
    if not inv:
        return ""
    positions = []
    for word, idxs in inv.items():
        for i in idxs:
            positions.append((i, word))
    return " ".join(w for _, w in sorted(positions))


def _crossref_abstract(doi: str, session) -> str:
    try:
        r = session.get(CROSSREF_WORKS + doi, timeout=30)
        r.raise_for_status()
        return strip_jats(r.json().get("message", {}).get("abstract"))
    except Exception as e:
        print(f"[warn] Crossref abstract lookup failed for {doi}: {e}")
        return ""


def _openalex_abstract(doi: str, session) -> str:
    try:
        r = session.get(OPENALEX_WORKS + f"doi:{doi}", timeout=30)
        r.raise_for_status()
        return reconstruct_openalex_abstract(r.json().get("abstract_inverted_index"))
    except Exception as e:
        print(f"[warn] OpenAlex abstract lookup failed for {doi}: {e}")
        return ""


def _arxiv_abstracts(ids: List[str]) -> Dict[str, str]:
    """Fetch abstracts for a list of arXiv ids (batched, best-effort)."""
    out: Dict[str, str] = {}
    if not ids:
        return out
    try:
        import arxiv

        from .utils import norm_arxiv_id

        client = arxiv.Client(page_size=100, delay_seconds=3)
        for i in range(0, len(ids), 100):
            chunk = ids[i : i + 100]
            try:
                search = arxiv.Search(id_list=chunk)
                for r in client.results(search):
                    ax = norm_arxiv_id(r.get_short_id())
                    if ax and r.summary:
                        out[ax] = re.sub(r"\s+", " ", r.summary).strip()
            except Exception as e:
                print(f"[warn] arXiv batch abstract lookup failed: {e}")
    except Exception as e:
        print(f"[warn] arXiv abstract lookup unavailable: {e}")
    return out


def backfill_abstracts(
    papers: Iterable[Paper],
    session=None,
    arxiv_lookup=_arxiv_abstracts,
) -> int:
    """
    Fill empty abstracts in place from Crossref, OpenAlex, and arXiv.

    Parameters
    ----------
    papers : iterable of Paper
        Papers to enrich; only those with empty abstracts are touched.
    session : requests.Session, optional
        HTTP session (injectable for tests); defaults to the shared one.
    arxiv_lookup : callable, optional
        `list[str] -> dict[arxiv_id, abstract]` (injectable for tests).

    Returns
    -------
    int
        Number of abstracts filled.
    """
    session = session or SESSION
    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    filled = 0

    need_arxiv: List[Paper] = []
    for p in papers:
        if (p.abstract or "").strip():
            continue
        abstract, source = "", None
        if p.doi:
            abstract = _crossref_abstract(p.doi, session)
            source = "crossref"
            if not abstract:
                abstract = _openalex_abstract(p.doi, session)
                source = "openalex"
        if abstract:
            p.abstract = abstract
            p.history.append({"event": "enriched", "source": source, "at": now})
            filled += 1
        elif p.arxiv_id:
            need_arxiv.append(p)

    if need_arxiv:
        found = arxiv_lookup([p.arxiv_id for p in need_arxiv])
        for p in need_arxiv:
            abstract = found.get(p.arxiv_id)
            if abstract:
                p.abstract = abstract
                p.history.append({"event": "enriched", "source": "arxiv", "at": now})
                filled += 1

    return filled
