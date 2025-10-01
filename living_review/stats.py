"""
stats.py
========

Computation of summary statistics for the **Living Review** project.

This module aggregates counts of papers by year, category, venue, keyword,
and monthly trends. These statistics are used for reporting and visualizations
in the exported JSON/HTML outputs.

Contents
--------
- KEYWORDS: predefined list of relevant keywords to track.
- compute_stats: aggregate statistics from a list of papers.

Typical Usage
-------------
>>> from living_review.stats import compute_stats
>>> stats = compute_stats(papers)
>>> stats["per_year"]
{'2024': 15, '2025': 7}
"""

from collections import Counter
import re
from datetime import date, datetime

# ---------------------------
# Keywords of interest
# ---------------------------

KEYWORDS = [
    "control", "beam", "HPC", "cloud", "uncertainty quantification",
    "proton therapy", "federated learning", "data management",
    "transformer", "optimization", "anomaly detection",
    "time series", "diagnostics", "reinforcement learning",
    "RF cavity", "feature store", "GPU", "deep learning",
    "surrogate model", "GAN"
]


# ---------------------------
# Statistics computation
# ---------------------------

def compute_stats(papers):
    """
    Compute aggregated statistics from a list of papers.

    Parameters
    ----------
    papers : list of Paper
        Papers to analyze. Each must have attributes `.year`, `.categories`,
        `.venue`, `.title`, `.abstract`, and `.date` (string ISO or datetime).

    Returns
    -------
    dict
        Dictionary with the following keys:
        - "per_year": counts of papers per publication year.
        - "per_category": counts of papers per semantic category.
        - "per_venue/journal": counts of papers per venue/journal.
        - "per_keyword": counts of predefined keywords matched in titles/abstracts.
        - "monthly_trends": counts of papers per month (YYYY-MM).
    """
    per_year = Counter()
    per_category = Counter()
    per_venue = Counter()
    per_keyword = Counter()
    monthly_trends = Counter()

    for p in papers:
        # --- Year ---
        if getattr(p, "year", None):
            per_year[str(p.year)] += 1

        # --- Categories (normalize dict vs string) ---
        for cat in getattr(p, "categories", []):
            if isinstance(cat, dict):
                label = cat.get("label", "Unknown")
            else:
                label = str(cat)
            per_category[label] += 1

        # --- Venue ---
        venue = getattr(p, "venue", None) or "Unknown"
        per_venue[venue] += 1

        # --- Keywords in title + abstract ---
        text = f"{getattr(p, 'title', '')} {getattr(p, 'abstract', '')}".lower()
        for kw in KEYWORDS:
            if re.search(rf"\b{re.escape(kw.lower())}\b", text):
                per_keyword[kw] += 1

        # --- Monthly trends ---
        d = None
        raw_date = getattr(p, "date", None)
        if isinstance(raw_date, str):
            try:
                d = datetime.fromisoformat(raw_date).date()
            except Exception:
                pass
        elif isinstance(raw_date, date):
            d = raw_date
        if d:
            ym = d.strftime("%Y-%m")
            monthly_trends[ym] += 1

    return {
        "per_year": dict(per_year),
        "per_category": dict(per_category),
        "per_venue/journal": dict(per_venue),
        "per_keyword": dict(per_keyword),
        "monthly_trends": dict(monthly_trends),
    }
