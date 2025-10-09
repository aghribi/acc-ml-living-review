"""
fetchers.py (corrected)
=======================

Same structure as the original version, but venue fields now reflect
the actual journal or conference name when available.
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
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1,
                    status_forcelist=[500, 502, 503, 504])
    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.mount("https://", HTTPAdapter(max_retries=retries))
    return session


SESSION = make_session()


# ---------------------------
# Helper for venue normalization
# ---------------------------

def normalize_venue(raw_venue, source: str) -> str:
    """
    Clean and normalize a venue name across fetchers.
    """
    if isinstance(raw_venue, list):
        raw_venue = raw_venue[0] if raw_venue else None
    if raw_venue:
        return raw_venue.replace("&amp;", "&").strip().rstrip(".")
    fallback = {
        "arxiv": "arXiv",
        "inspire": "InspireHEP",
        "hal": "HAL",
        "openalex": "OpenAlex",
        "crossref": "Unknown Journal (Crossref)",
    }
    return fallback.get(source, "Unknown Venue")


# ---------------------------
# arXiv fetcher
# ---------------------------

def arxiv_query_for_window() -> List[str]:
    queries = []
    for ml_kw in ML_KEYWORDS:
        ml_q = f'all:"{ml_kw}"' if " " in ml_kw else f"all:{ml_kw}"
        queries.append(f'(cat:physics.acc-ph) AND ({ml_q})')
    sec = " OR ".join([f"cat:{c}" for c in ["cs.AI", "cs.LG", "stat.ML"]])
    for acc_kw in ACCEL_KEYWORDS:
        acc_q = f'all:"{acc_kw}"' if " " in acc_kw else f"all:{acc_kw}"
        queries.append(f'({sec}) AND ({acc_q})')
    queries.append(f'(cat:physics.acc-ph) AND (cat:cs.AI OR cat:cs.LG OR cat:stat.ML)')
    return queries


def fetch_arxiv(start: dt.date, end: dt.date) -> List[Paper]:
    client = arxiv.Client(page_size=ARXIV_PAGE_SIZE, delay_seconds=3, num_retries=2)
    papers: List[Paper] = []
    for q in arxiv_query_for_window():
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
                venue = normalize_venue(getattr(r, "journal_ref", None), "arxiv")
                raw = {
                    "title": (r.title or "").strip(),
                    "authors": [a.name for a in getattr(r, "authors", [])],
                    "abstract": r.summary or "",
                    "date": d.isoformat(),
                    "year": d.year,
                    "arxiv_id": (r.get_short_id().replace("arXiv:", "")
                                 if hasattr(r, "get_short_id") else None),
                    "doi": getattr(r, "doi", None),
                    "venue": venue,
                    "status": "preprint",
                    "links": {"arxiv": r.entry_id or ""},
                    "source": "arxiv",
                }
                papers.append(Paper.from_source(raw))
        except Exception as e:
            print(f"[warn] arXiv fetch error: {e}")
    return papers


# ---------------------------
# Inspire-HEP fetcher
# ---------------------------

def fetch_inspire(start: dt.date, end: dt.date, rows: int = 50, max_pages: int = 5) -> List[Paper]:
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
        for h in data.get("hits", {}).get("hits", []):
            meta = h.get("metadata", {})
            date_str = meta.get("earliest_date", "1900-01-01")
            try:
                date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            except Exception:
                continue
            if not within_range(date, start, end):
                continue
            venue = normalize_venue(
                meta.get("publication_info", [{}])[0].get("journal_title"), "inspire"
            )
            raw = {
                "title": meta.get("titles", [{}])[0].get("title", ""),
                "authors": [a.get("full_name", "") for a in meta.get("authors", [])],
                "abstract": meta.get("abstracts", [{}])[0].get("value", ""),
                "date": date.isoformat(),
                "year": date.year,
                "doi": meta.get("doi"),
                "venue": venue,
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
    for doc in resp.json().get("response", {}).get("docs", []):
        date_str = doc.get("producedDate_s") or doc.get("submittedDate_s")
        try:
            d = dt.date.fromisoformat(date_str[:10])
        except Exception:
            continue
        if not (start <= d <= end):
            continue
        venue = normalize_venue((doc.get("journalTitle_s") or [None])[0], "hal")
        raw = {
            "title": (doc.get("title_s") or [""])[0],
            "authors": doc.get("authFullName_s", []),
            "abstract": (doc.get("abstract_s") or [""])[0],
            "date": d.isoformat(),
            "year": d.year,
            "doi": (doc.get("doiId_s") or [None])[0],
            "venue": venue,
            "status": "submitted",
            "links": {"hal": f"https://hal.archives-ouvertes.fr/{doc.get('halId_s', '')}"},
            "source": "hal",
        }
        papers.append(Paper.from_source(raw))
    return papers


# ---------------------------
# OpenAlex fetcher
# ---------------------------

def fetch_openalex(start: dt.date, end: dt.date) -> List[Paper]:
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
    for item in resp.json().get("results", []):
        date_str = item.get("publication_date") or item.get("from_publication_date")
        try:
            d = dt.date.fromisoformat(date_str)
        except Exception:
            continue
        if not (start <= d <= end):
            continue
        venue = normalize_venue(item.get("host_venue", {}).get("display_name"), "openalex")
        authors = [a.get("author", {}).get("display_name", "") for a in item.get("authorships", [])]
        raw = {
            "title": item.get("title", ""),
            "authors": authors,
            "abstract": item.get("abstract", ""),
            "date": d.isoformat(),
            "year": d.year,
            "doi": item.get("doi"),
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
    for item in resp.json().get("message", {}).get("items", []):
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
        authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in item.get("author", [])]
        doi = item.get("DOI")
        venue = normalize_venue((item.get("container-title") or [None])[0], "crossref")
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
