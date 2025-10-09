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
import os
import datetime as dt
import time
import requests
from requests.adapters import HTTPAdapter, Retry
from typing import List
import arxiv

from .utils import within_range, SESSION
from .data_model import Paper
from .config import ACCEL_KEYWORDS, ML_KEYWORDS, ARXIV_PAGE_SIZE

import xml.etree.ElementTree as ET
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
    Fetch papers from InspireHEP API (AI/ML applied to accelerators).
    """
    url = "https://inspirehep.net/api/literature"
    q = '(accelerator OR "beam dynamics" OR "synchrotron") AND ("machine learning" OR "deep learning" OR "reinforcement learning")'
    params = {"q": q, "size": rows, "sort": "mostrecent", "page": 1}

    papers = []
    for page in range(1, max_pages + 1):
        params["page"] = page
        try:
            r = SESSION.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"[warn] InspireHEP request failed on page {page}: {e}")
            break

        hits = data.get("hits", {}).get("hits", [])
        if not hits:
            break

        for h in hits:
            meta = h.get("metadata", {})
            title = meta.get("titles", [{}])[0].get("title", "").strip()
            abstract = meta.get("abstracts", [{}])[0].get("value", "").strip()
            authors = [a.get("full_name", "").strip() for a in meta.get("authors", []) if a.get("full_name")]

            # --- Date parsing ---
            date_str = meta.get("earliest_date", "")
            date = None
            for fmt in ("%Y-%m-%d", "%Y-%m"):
                try:
                    date = dt.datetime.strptime(date_str, fmt).date()
                    break
                except Exception:
                    continue
            if not date:
                try:
                    date = dt.date(int(date_str), 1, 1)
                except Exception:
                    continue
            if not (start <= date <= end):
                continue

            # --- DOI ---
            doi_list = meta.get("dois", [])
            doi = doi_list[0].get("value") if doi_list else None

            # --- Metadata indicators ---
            doc_types = [t.lower() for t in meta.get("document_type", [])]
            thesis_info = meta.get("thesis_info")
            conf_info = meta.get("conference_info")
            pub_info = meta.get("publication_info")
            arxiv_info = meta.get("arxiv_eprints")

            # Default fallback
            venue = "InspireHEP"
            status = "unknown"

            # --- Type detection ---
            if thesis_info:
                venue = "Thesis"
                degree = thesis_info.get("degree_type", "").lower()
                if "phd" in degree:
                    status = "phd"
                elif any(k in degree for k in ["intern", "master", "stage"]):
                    status = "internship"
                else:
                    status = "thesis"

            elif any("report" in d or "note" in d for d in doc_types):
                venue = "Report"
                status = "report"

            elif conf_info:
                venue = conf_info.get("conference_title", "Conference")
                status = "proceeding"

            elif pub_info:
                status = "published"
                pub = pub_info[0]
                journal = pub.get("journal_title", "Journal")
                venue = journal

            elif arxiv_info:
                venue = "arXiv"
                status = "preprint"

            # --- Fallback heuristic text classification ---
            lowtxt = (title + " " + abstract).lower()
            if venue == "InspireHEP" and status == "unknown":
                if any(k in lowtxt for k in ["internship", "summer student", "summer programme",
                                            "summer program", "student project", "training report",
                                            "intern", "trainee", "stage", "report"]):
                    venue = "Thesis"
                    status = "internship"
                elif "phd" in lowtxt or "doctoral" in lowtxt or "dissertation" in lowtxt:
                    venue = "Thesis"
                    status = "phd"
                elif any(k in lowtxt for k in ["report", "technical note", "internal note"]):
                    venue = "Report"
                    status = "report"
                elif "arxiv" in lowtxt or "preprint" in lowtxt:
                    venue = "arXiv"
                    status = "preprint"

            # --- Build links ---
            links = {"inspire": f"https://inspirehep.net/literature/{h.get('id', '')}"}
            if doi:
                links["doi"] = f"https://doi.org/{doi}"
            if arxiv_info:
                arx = arxiv_info[0].get("value")
                links["arxiv"] = f"https://arxiv.org/abs/{arx}"

            # --- Final assembly ---
            raw = {
                "title": title,
                "authors": authors,
                "abstract": abstract,
                "date": date.isoformat(),
                "year": date.year,
                "doi": doi,
                "venue": venue,
                "status": status,
                "links": links,
                "source": "inspire",
            }

            papers.append(Paper.from_source(raw))

        
        print(f"[info] InspireHEP page {page}: {len(hits)} hits processed")

    print(f"[info] InspireHEP: {len(papers)} total papers collected")
    return papers



# ---------------------------
# HAL fetcher
# ---------------------------

def fetch_hal(start: dt.date, end: dt.date) -> List[Paper]:
    """
    Fetch papers from HAL API (filtered to ML + accelerator physics).
    """
    url = "https://api.archives-ouvertes.fr/search/"
    q = '(("machine learning" OR "deep learning" OR "reinforcement learning") AND (accelerator OR "beam dynamics" OR "synchrotron" OR "particle accelerator"))'
    params = {
        "q": q,
        "fl": "halId_s,title_s,abstract_s,authFullName_s,producedDate_s,submittedDate_s,doiId_s,journalTitle_s,conferenceTitle_s,bookTitle_s,collection_s,labStructName_s",
        "rows": 200,
        "wt": "json",
    }

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
        title_list = doc.get("title_s", [])
        abstract_list = doc.get("abstract_s", [])
        title = next((t for t in title_list if t.strip()), "")
        abstract = next((a for a in abstract_list if a.strip()), "")

        date_str = doc.get("producedDate_s") or doc.get("submittedDate_s")
        try:
            d = dt.date.fromisoformat(date_str[:10]) if date_str else None
        except Exception:
            continue
        if not d or not (start <= d <= end):
            continue

        authors = doc.get("authFullName_s", [])
        doi = doc.get("doiId_s")
        halid = doc.get("halId_s", "")

        # Smart venue extraction
        venue = next(
            (v for v in [
                doc.get("journalTitle_s"),
                doc.get("conferenceTitle_s"),
                doc.get("bookTitle_s"),
                doc.get("collection_s"),
                doc.get("labStructName_s"),
            ] if v),
            "HAL"
        )
        if isinstance(venue, list):
            venue = venue[0]

        links = {"hal": f"https://hal.archives-ouvertes.fr/{halid}"} if halid else {}
        if doi:
            links["doi"] = f"https://doi.org/{doi}"

        raw = {
            "title": title.strip(),
            "authors": authors,
            "abstract": abstract.strip(),
            "date": d.isoformat(),
            "year": d.year,
            "doi": doi,
            "venue": venue.strip() if venue else "HAL",
            "status": "submitted",
            "links": links,
            "source": "hal",
        }
        papers.append(Paper.from_source(raw))

    print(f"[info] HAL: {len(papers)} structured results fetched for {q}")
    return papers

# ---------------------------
# OpenAlex fetcher
# ---------------------------
def _get_openalex_venue(item: dict) -> str:
    """Extract true venue name from OpenAlex record."""
    try:
        # 1. Primary location
        v = (
            item.get("primary_location", {})
                .get("source", {})
                .get("display_name")
        )
        if v:
            return v.strip()

        # 2. Best OA location
        v = (
            item.get("best_oa_location", {})
                .get("source", {})
                .get("display_name")
        )
        if v:
            return v.strip()

        # 3. Any location
        for loc in item.get("locations") or []:
            v = (loc.get("source", {}) or {}).get("display_name")
            if v:
                return v.strip()
    except Exception:
        pass

    return "Unknown Venue"

def fetch_openalex(start: dt.date, end: dt.date) -> List[Paper]:
    """
    Fetch papers from OpenAlex API (60-day windows etc.), and set `venue`
    to the actual journal/conference (not the source name).
    """
    url = "https://api.openalex.org/works"
    flt = (
        f"abstract.search:accelerator machine learning,"
        f"from_publication_date:{start},to_publication_date:{end}"
    )
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

        authors: List[str] = []
        for a in item.get("authorships", []):
            auth = a.get("author", {}) or {}
            name = auth.get("display_name") or ""
            if name:
                authors.append(name)

        doi = item.get("doi")
        venue = _get_openalex_venue(item)

        raw = {
            "title": item.get("title", "") or "",
            "authors": authors,
            "abstract": item.get("abstract", "") or "",
            "date": d.isoformat(),
            "year": d.year,
            "doi": doi,
            "venue": venue,                 # <- now the true journal/conference
            "status": "published",
            "links": {"openalex": item.get("id", "") or ""},
            "source": "openalex",
        }
        papers.append(Paper.from_source(raw))

    return papers

# ---------------------------
# Crossref fetcher
# ---------------------------
def _get_crossref_venue(item: dict) -> str:
    """Extract the best available venue name from a Crossref record."""
    # 1) Journal or proceedings title
    if "container-title" in item and item["container-title"]:
        return item["container-title"][0].strip()

    # 2) Short title
    if "short-container-title" in item and item["short-container-title"]:
        return item["short-container-title"][0].strip()

    # 3) Assertion field (common in Elsevier / Springer metadata)
    for a in item.get("assertion", []) or []:
        if isinstance(a, dict) and a.get("name") in ("journaltitle", "conference-title"):
            val = a.get("value")
            if val:
                return val.strip()

    # 4) Event metadata (conference proceedings)
    ev = item.get("event", {})
    if isinstance(ev, dict):
        v = ev.get("name") or ev.get("title")
        if v:
            return v.strip()

    # 5) Fallback to publisher
    if "publisher" in item and item["publisher"]:
        return item["publisher"].strip()

    return "Unknown Venue"


def fetch_crossref(start: dt.date, end: dt.date) -> List[Paper]:
    """
    Fetch papers from Crossref API across PRAB, JACoW, and general accelerator+ML topics.

    Combines three categories:
    - PRAB (prefix:10.1103 PhysRevAccelBeams)
    - JACoW / IPAC / ICALEPCS / LINAC conference papers
    - Generic 'accelerator machine learning' search

    Parameters
    ----------
    start : datetime.date
    end   : datetime.date

    Returns
    -------
    list of Paper
    """
    url = "https://api.crossref.org/works"
    papers: List[Paper] = []

    # Unified query: OR-combined for broader coverage
    query = (
        "accelerator machine learning "
        "OR PhysRevAccelBeams "
        "OR JACoW "
        "OR IPAC "
        "OR ICALEPCS "
        "OR LINAC"
    )

    params = {
        "query": query,
        "filter": f"from-pub-date:{start},until-pub-date:{end}",
        "rows": 100,
        "sort": "published",
    }

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
        for a in item.get("author", []) or []:
            given = a.get("given", "")
            family = a.get("family", "")
            authors.append(f"{given} {family}".strip())

        doi = item.get("DOI")
        venue = _get_crossref_venue(item)  # robust venue extractor

        raw = {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "date": d.isoformat(),
            "year": d.year,
            "doi": doi,
            "venue": venue,
            "status": "published",
            "links": {
                "doi": f"https://doi.org/{doi}" if doi else None,
                "crossref": item.get("URL", ""),
            },
            "source": "crossref",
        }
        papers.append(Paper.from_source(raw))

    return papers

#---------------------------
# semantic scolar fetcher
#---------------------------

def fetch_semanticscholar(start: dt.date, end: dt.date, limit: int = 100) -> List[Paper]:
    """
    Fetch papers from the Semantic Scholar Graph API related to 
    machine learning and accelerator physics.

    Parameters
    ----------
    start : datetime.date
        Start date.
    end : datetime.date
        End date.
    limit : int, optional
        Max number of results to fetch (default=100).

    Returns
    -------
    list of Paper
        Papers retrieved from Semantic Scholar.
    """
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    q = "machine learning accelerator OR beam dynamics OR accelerator physics"
    params = {
        "query": q,
        "limit": limit,
        "fields": "title,abstract,authors,externalIds,venue,year,publicationDate,url"
    }

    papers: List[Paper] = []

    try:
        resp = SESSION.get(url, params=params, timeout=30)
        if resp.status_code == 429:
            print("[warn] Rate limit hit — sleeping 1s before retrying...")
            time.sleep(1)
            resp = SESSION.get(url, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[warn] Semantic Scholar request failed: {e}")
        return papers


    data = resp.json()
    for item in data.get("data", []):
        # --- extract fields ---
        title = item.get("title", "")
        abstract = item.get("abstract", "")
        authors = [a.get("name", "") for a in item.get("authors", [])]
        date_str = item.get("publicationDate")
        try:
            d = dt.date.fromisoformat(date_str[:10]) if date_str else None
        except Exception:
            # fallback to year-only
            year = item.get("year")
            d = dt.date(year, 1, 1) if year else None
        if not d or not (start <= d <= end):
            continue

        venue = item.get("venue") or "SemanticScholar"
        doi = item.get("externalIds", {}).get("DOI")
        arxiv_id = item.get("externalIds", {}).get("ArXiv")
        url_link = item.get("url", "")

        # --- determine status ---
        status = "published" if venue and venue != "SemanticScholar" else "preprint"

        raw = {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "date": d.isoformat(),
            "year": d.year,
            "doi": doi,
            "arxiv_id": arxiv_id,
            "venue": venue,
            "status": status,
            "links": {
                "semantic": url_link,
                "doi": f"https://doi.org/{doi}" if doi else None,
                "arxiv": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else None,
            },
            "source": "semanticscholar",
        }
        papers.append(Paper.from_source(raw))

    print(f"[info] Semantic Scholar: {len(papers)} papers fetched between {start} and {end}")
    return papers

# ---------------------------
# springer nature fetcher
# ---------------------------

# ---------------------------------------------------------------------
# Springer Nature API
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# Springer Nature (PAM v2 XML endpoint)
# ---------------------------------------------------------------------

def fetch_springer(start: dt.date, end: dt.date, rows: int = 20) -> List[Paper]:
    """
    Fetch papers from Springer Nature API (PAM v2).

    Parameters
    ----------
    start : datetime.date
        Start date.
    end : datetime.date
        End date.
    rows : int, optional
        Number of results to retrieve (default=20).

    Returns
    -------
    list of Paper
        Papers retrieved from Springer.
    """
    API_KEY = os.getenv("SPRINGER_API_KEY")
    if not API_KEY:
        print("[warn] Missing SPRINGER_API_KEY environment variable")
        return []

    base_url = "https://api.springernature.com/meta/v2/pam"
    query = '(keyword:"accelerator") AND ("machine learning" OR "artificial intelligence")'
    params = {
        "q": query,
        "api_key": API_KEY,
        "p": rows,
        "s": 1,
    }

    try:
        resp = SESSION.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[warn] Springer request failed: {e}")
        return []

    try:
        root = ET.fromstring(resp.text)
    except ET.ParseError:
        print("[warn] Springer XML parse error")
        return []

    ns = {
        "pam": "http://prismstandard.org/namespaces/pam/2.2/",
        "xhtml": "http://www.w3.org/1999/xhtml",
        "dc": "http://purl.org/dc/elements/1.1/",
        "prism": "http://prismstandard.org/namespaces/basic/2.2/"
    }

    papers = []
    for rec in root.findall(".//pam:article", ns):
        title = rec.findtext("xhtml:head/dc:title", "", ns)
        abstract = " ".join([p.text or "" for p in rec.findall("xhtml:body/xhtml:p", ns)]).strip()
        authors = [a.text for a in rec.findall("xhtml:head/dc:creator", ns) if a.text]
        doi = rec.findtext("xhtml:head/prism:doi", "", ns)
        venue = rec.findtext("xhtml:head/prism:publicationName", "Springer", ns)
        date_str = rec.findtext("xhtml:head/prism:publicationDate", "", ns)

        try:
            d = dt.date.fromisoformat(date_str[:10]) if date_str else None
        except Exception:
            d = None
        if not d or not within_range(d, start, end):
            continue

        url = rec.findtext("xhtml:head/prism:url", "", ns)

        raw = {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "date": d.isoformat(),
            "year": d.year,
            "doi": doi,
            "venue": venue,
            "status": "published",
            "links": {"springer": url or f"https://doi.org/{doi}" if doi else ""},
            "source": "springer",
        }
        papers.append(Paper.from_source(raw))

    print(f"[info] Springer: {len(papers)} papers parsed")
    return papers

# ---------------------------------------------------------------------
# pubmed fetcher
# ---------------------------------------------------------------------

def fetch_pubmed(start: dt.date, end: dt.date, rows: int = 50) -> List[Paper]:
    """
    Fetch papers from Europe PMC (PubMed interface).

    Parameters
    ----------
    start : datetime.date
        Start date.
    end : datetime.date
        End date.
    rows : int, optional
        Number of results per page (default=50).

    Returns
    -------
    list of Paper
        Papers retrieved from Europe PMC / PubMed.
    """
    base_url = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
    query = "machine learning accelerator physics"
    params = {
        "query": query,
        "format": "json",
        "pageSize": rows,
        "resultType": "lite",
    }

    try:
        resp = SESSION.get(base_url, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"[warn] EuropePMC request failed: {e}")
        return []

    data = resp.json()
    results = data.get("resultList", {}).get("result", [])
    papers: List[Paper] = []

    for r in results:
        title = r.get("title", "")
        abstract = r.get("abstractText", "")
        authors = []
        if "authorList" in r:
            authors = [a.get("fullName") for a in r["authorList"].get("author", []) if a.get("fullName")]
        elif "authorString" in r:
            # fallback simple parse
            authors = [a.strip() for a in r["authorString"].split(",") if a.strip()]

        doi = r.get("doi")
        venue = r.get("journalTitle", "PubMed")
        date_str = r.get("firstPublicationDate") or f"{r.get('pubYear', '')}-01-01"
        try:
            d = dt.date.fromisoformat(date_str[:10]) if date_str else None
        except Exception:
            d = None
        if not d or not within_range(d, start, end):
            continue

        raw = {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "date": d.isoformat(),
            "year": d.year,
            "doi": doi,
            "venue": venue,
            "status": "published",
            "links": {
                "europepmc": f"https://europepmc.org/article/{r.get('source','MED')}/{r.get('id','')}"
            },
            "source": "pubmed",
        }
        papers.append(Paper.from_source(raw))

    print(f"[info] EuropePMC: {len(papers)} papers parsed")
    return papers