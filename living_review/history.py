"""
history.py
==========

One-off historical recall backfill: the founding literature of ML for
accelerators (1990s neural-network beam control, PAC/EPAC proceedings,
NIM-A) predates both arXiv coverage of the field and the pipeline's
30-day fetch windows, so it never entered the DB. This module sweeps
INSPIRE / OpenAlex / Crossref over wide, year-chunked windows and feeds
everything through the normal relevance funnel — the funnel guards
precision, so the net can be wide.

Recovered historical papers should be added to `data/eval/positives.json`
so the eval benchmark permanently guards against losing them (TODO.md).
Pre-1995 proceedings coverage is best-effort: digitization gaps exist in
every source.
"""

import datetime as dt
from pathlib import Path
from typing import List, Optional

from .adjudicator import NLIAdjudicator
from .classifier import classify_papers
from .db import DB
from .exporters import export_bibtex, export_json, export_pdf
from .fetchers import fetch_crossref, fetch_inspire, fetch_openalex
from .relevance import (
    accepted_papers,
    demote_others_only,
    export_pending_queue,
    run_funnel,
)
from .stats import compute_stats

PENDING_QUEUE_PATH = "data/pending_review.json"


def backfill_history(
    from_year: int = 1990,
    to_year: Optional[int] = None,
    db_path: str = "data/db.json",
    output_dir: str = ".",
    adjudicator=None,
    chunk_years: int = 2,
    dry_run: bool = False,
):
    """
    Sweep historical windows and funnel the results into the DB.

    Parameters
    ----------
    from_year, to_year : int
        Inclusive year range (default 1990 → last year).
    chunk_years : int
        Window width per API sweep — keeps single-page sources
        (OpenAlex/Crossref) from truncating a whole era at once.
    dry_run : bool
        Fetch and report counts, write nothing.
    """
    to_year = to_year or (dt.date.today().year - 1)
    db = DB.load(db_path)
    print(f"[info] DB: {len(db)} entries before historical backfill")

    fetched: List = []
    for year in range(from_year, to_year + 1, chunk_years):
        start = dt.date(year, 1, 1)
        end = dt.date(min(year + chunk_years - 1, to_year), 12, 31)
        print(f"[info] Sweeping {start} → {end}")
        for name, fetch in (
            ("inspire", lambda s, e: fetch_inspire(s, e, rows=50, max_pages=10)),
            ("openalex", fetch_openalex),
            ("crossref", fetch_crossref),
        ):
            try:
                batch = fetch(start, end)
                print(f"[info]   {name}: {len(batch)} papers")
                fetched.extend(batch)
            except Exception as e:
                print(f"[warn]   {name} sweep failed for {start}->{end}: {e}")

    print(f"[info] Historical sweep fetched {len(fetched)} candidate papers")
    if dry_run:
        new = sum(1 for p in fetched if db._find_existing(p) is None)
        print(f"[info] dry-run: {new} would be new; nothing written")
        return

    merged = db.merge_from_list(fetched)
    print(f"[info] Merged into DB: {merged} entries touched, {len(db)} total")

    counts = run_funnel(db, adjudicator or NLIAdjudicator())
    print(f"[info] Funnel: {counts}")

    accepted = accepted_papers(db)
    classify_papers(accepted)
    publishable = demote_others_only(accepted)

    db.save(db_path)
    export_pending_queue(db, Path(output_dir) / PENDING_QUEUE_PATH)
    stats = compute_stats(publishable)
    export_json(publishable, stats, output_dir)
    export_bibtex(publishable, output_dir)
    export_pdf(publishable, stats, output_dir)
    print(f"[ok] Historical backfill complete: {len(publishable)} papers published")
