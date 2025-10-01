"""
fetchers.py
===========

Data-source fetchers for the **Living Review** project.

This module provides functions to query multiple bibliographic APIs
and return lists of `Paper` objects (via `Paper.from_source`).

Supported sources:
- **arXiv**: via `arxiv` Python client.
- **InspireHEP**: via REST API.
- **HAL** (Hyper Articles en Ligne).
- **OpenAlex**.
- **Crossref**.

Each fetcher:
-------------
- Retrieves results within a given date window.
- Normalizes metadata into the canonical schema expected by `Paper`.
- Populates `links`, `status`, and provenance (`source`).

A shared `requests.Session` with retry logic is used for robustness.
"""

import datetime as dt
import requests
from requests.adapters import HTTPAdapter, Retry
from typing import List
import arxiv

from .utils import within_range
from .data_model import Paper
from .config import ACCEL_KEYWORDS, ML_KEYWORDS, ARXIV_PAGE_SIZE


# ---------------------------
# Shared session with retry
# ---------------------------

def make_session():
    """
    Create a `requests.Session` with retry strategy.

    Retries on server errors (500, 502, 503, 504) up to 3 times with
    exponential backoff.

    Returns
    -------
    requests.Session
        Configured session with retry-enabled adapters.
    """
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1,
                    status_forcelist=[500, 502, 503, 504])
    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


SESSION = make_session()


# ---------------------------
# arXiv fetcher
# ---------------------------

def arxiv_query_for_window() -> List[str]:
    """
    Build arXiv queries targeting accelerator physics and ML categories.

    Returns
    -------
    list of str
        Query strings to be passed to the `arxiv` client.
    """
    queries = []
    for ml_kw in ML_KEYWORDS:
        ml_q = f'all:"{ml_kw}"' if " " in ml_kw else f"all:{ml_kw}"
        q = f'(cat:physics.acc-ph) AND ({ml_q})'
        queries.append(q)
    sec = " OR ".join([f"cat:{c}" for c in ["cs.AI", "cs.LG", "stat.ML"]])
    for acc_kw in ACCEL_KEYWORDS:
        acc_q = f'all:"{acc_kw}"' if " " in acc_kw else f"all:{acc_kw}"
        q = f'({sec}) AND ({acc_q})'
        queries.append(q)
    queries.append(f'(cat:physics.acc-ph) AND (cat:cs.AI OR cat:cs.LG OR cat:stat.ML)')
    return queries


def fetch_arxiv(start: dt.date, end: dt.date) -> List[Paper]:
    """
    Fetch papers from arXiv within the given date range.

    Parameters
    ----------
    start : datetime.date
        Start date.
    end : datetime.date
        End date.

    Returns
    -------
    list of Paper
        Papers retrieved from arXiv.
    """
    client = arxiv.Client(page_size=ARXIV_PAGE_SIZE, delay_seconds=3, num_retries=2)
    papers: List[Paper] = []
    queries = arxiv_query_for_window()
    for q in queries:
        search = arxiv.Search(
            query=q,
            sort_by=arxiv.SortCriterion.SubmittedDate,
            sort_order=arxiv.SortOrder.Descending,
            max_results=ARXIV_PAGE_SIZE,
        )
        try:
            for r in client.results(search):
                d = (r.updated or r.published).date()
                if not (start <= d <= end):
                    continue
                raw = {
                    "title": (r.title or "").strip(),
                    "authors": [a.name for a in getattr(r, "authors", [])],
                    "abstract": r.summary or "",
                    "date": d.isoformat(),
                    "year": d.year,
                    "arxiv_id": (r.get_short_id().replace("arXiv:", "")
                                 if hasattr(r, "get_short_id") else None),
                    "doi": None,
                    "venue": "arXiv",
                    "status": "preprint",
                    "links": {"arxiv": r.entry_id or ""},
                    "source": "arxiv",
                }
                papers.append(Paper.from_source(raw))
        except Exception as e:
            print(f"[warn] arXiv fetch error: {e}")
            continue
    return papers


# ---------------------------
# Inspire-HEP fetcher
# ---------------------------

def fetch_inspire(start: dt.date, end: dt.date, rows: int = 50, max_pages: int = 5) -> List[Paper]:
    """
    Fetch papers from InspireHEP API.

    Parameters
    ----------
    start : datetime.date
        Start date.
    end : datetime.date
        End date.
    rows : int, optional
        Number of results per page (default=50).
    max_pages : int, optional
        Maximum number of pages to fetch (default=5).

    Returns
    -------
    list of Paper
        Papers retrieved from InspireHEP.
    """
    url = "https://inspirehep.net/api/literature"
    params = {
        "q": 'title:(accelerator AND "machine learning")',
        "size": rows,
        "sort": "mostrecent",
        "page": 1,
    }

    papers = []
    for page in range(1, max_pages + 1):
        params["page"] = page
        try:
            r = SESSION.get(url, params=params, timeout=20)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[warn] Inspire request failed on page {page}: {e}")
            break

        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break

        for h in hits:
            meta = h.get("metadata", {})
            title = meta.get("titles", [{}])[0].get("title", "")
            abstract = meta.get("abstracts", [{}])[0].get("value", "")
            authors = [a.get("full_name", "") for a in meta.get("authors", [])]
            date_str = meta.get("earliest_date", "1900-01-01")
            try:
                date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                try:
                    date = dt.datetime.strptime(date_str, "%Y").date()
                except Exception:
                    continue

            if not within_range(date, start, end):
                continue

            raw = {
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "date": date.isoformat(),
                "year": date.year,
                "doi": meta.get("doi"),
                "venue": "InspireHEP",
                "status": "published",
                "links": {"inspire": f"https://inspirehep.net/literature/{h.get('id', '')}"},
                "source": "inspire",
            }
            papers.append(Paper.from_source(raw))

    return papers


# ---------------------------
# HAL fetcher
# ---------------------------

def fetch_hal(start: dt.date, end: dt.date) -> List[Paper]:
    """
    Fetch papers from HAL API.

    Parameters
    ----------
    start : datetime.date
        Start date.
    end : datetime.date
        End date.

    Returns
    -------
    list of Paper
        Papers retrieved from HAL.
    """
    url = "https://api.archives-ouvertes.fr/search/"
    q = "machine learning accelerator"
    params = {"q": q, "rows": 50, "wt": "json"}
    papers: List[Paper] = []

    try:
        resp = SESSION.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[warn] HAL request failed: {e}")
        return papers

    data = resp.json()
    docs = data.get("response", {}).get("docs", [])

    for doc in docs:
        title = (doc.get("title_s") or [""])[0]
        abstract = (doc.get("abstract_s") or [""])[0]
        date_str = doc.get("producedDate_s") or doc.get("submittedDate_s")
        try:
            d = dt.date.fromisoformat(date_str[:10]) if date_str else None
        except Exception:
            continue
        if not d or not (start <= d <= end):
            continue

        authors = doc.get("authFullName_s", [])
        doi = (doc.get("doiId_s") or [None])[0]
        halid = doc.get("halId_s", "")
        venue = (doc.get("journalTitle_s") or ["HAL"])[0]

        raw = {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "date": d.isoformat(),
            "year": d.year,
            "doi": doi,
            "venue": venue,
            "status": "submitted",
            "links": {"hal": f"https://hal.archives-ouvertes.fr/{halid}"} if halid else {},
            "source": "hal",
        }
        papers.append(Paper.from_source(raw))
    return papers


# ---------------------------
# OpenAlex fetcher
# ---------------------------

def fetch_openalex(start: dt.date, end: dt.date) -> List[Paper]:
    """
    Fetch papers from OpenAlex API.

    Parameters
    ----------
    start : datetime.date
        Start date.
    end : datetime.date
        End date.

    Returns
    -------
    list of Paper
        Papers retrieved from OpenAlex.
    """
    url = "https://api.openalex.org/works"
    flt = f"abstract.search:accelerator machine learning,from_publication_date:{start},to_publication_date:{end}"
    params = {"filter": flt, "per-page": 50}
    papers: List[Paper] = []

    try:
        resp = SESSION.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[warn] OpenAlex request failed: {e}")
        return papers

    data = resp.json()
    results = data.get("results", [])

    for item in results:
        title = item.get("title", "")
        abstract = item.get("abstract", "")
        date_str = item.get("publication_date") or item.get("from_publication_date")
        try:
            d = dt.date.fromisoformat(date_str)
        except Exception:
            continue
        if not (start <= d <= end):
            continue

        authors = []
        for a in item.get("authorships", []):
            auth = a.get("author", {})
            if isinstance(auth, dict):
                authors.append(auth.get("display_name", ""))

        doi = item.get("doi")
        venue = item.get("host_venue", {}).get("display_name", "OpenAlex")

        raw = {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "date": d.isoformat(),
            "year": d.year,
            "doi": doi,
            "venue": venue,
            "status": "published",
            "links": {"openalex": item.get("id", "")},
            "source": "openalex",
        }
        papers.append(Paper.from_source(raw))
    return papers


# ---------------------------
# Crossref fetcher
# ---------------------------

def fetch_crossref(start: dt.date, end: dt.date) -> List[Paper]:
    """
    Fetch papers from Crossref API.

    Parameters
    ----------
    start : datetime.date
        Start date.
    end : datetime.date
        End date.

    Returns
    -------
    list of Paper
        Papers retrieved from Crossref.
    """
    url = "https://api.crossref.org/works"
    q = "accelerator machine learning"
    params = {"query": q, "rows": 50, "sort": "published"}
    papers: List[Paper] = []

    try:
        resp = SESSION.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[warn] Crossref request failed: {e}")
        return papers

    data = resp.json()
    items = data.get("message", {}).get("items", [])

    for item in items:
        title = (item.get("title") or [""])[0]
        abstract = item.get("abstract", "")
        issued = item.get("issued", {}).get("date-parts", [[None]])[0]
        try:
            year = issued[0]
            month = issued[1] if len(issued) > 1 else 1
            day = issued[2] if len(issued) > 2 else 1
            d = dt.date(year, month, day)
        except Exception:
            continue
        if not (start <= d <= end):
            continue

        authors = []
        for a in item.get("author", []):
            given = a.get("given", "")
            family = a.get("family", "")
            authors.append(f"{given} {family}".strip())

        doi = item.get("DOI")
        venue = (item.get("container-title") or ["Crossref"])[0]

        raw = {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "date": d.isoformat(),
            "year": d.year,
            "doi": doi,
            "venue": venue,
            "status": "published",
            "links": {"doi": f"https://doi.org/{doi}", "crossref": item.get("URL", "")},
            "source": "crossref",
        }
        papers.append(Paper.from_source(raw))
    return papers
