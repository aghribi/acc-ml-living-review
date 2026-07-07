"""
dedup.py
========

Two-pass deduplication of Paper records.

Pass 1 — identifier graph: papers sharing *any* normalized identifier
(``doi:``, ``arxiv:``, ``inspire:``, see `utils.canonical_ids`) are the same
work; groups are found with a union-find over those identifiers. This also
links DataCite arXiv DOIs (``10.48550/arXiv.XXXX``) to their arXiv record.

Pass 2 — fuzzy titles: remaining records with no shared identifier are
compared within year buckets (year ± 1, to tolerate preprint → journal
transitions) using `utils.similar_title`; pairs at or above
`config.FUZZY_TITLE_THRESHOLD` merge.

Merging delegates to `Paper.merge_with`, so curated fields and terminal
review decisions survive; the primary record of a group is chosen to be the
one carrying a decision (then curated, then richest metadata).
"""

from collections import defaultdict
from typing import Callable, List, Optional

from .config import FUZZY_TITLE_THRESHOLD
from .data_model import Paper
from .utils import canonical_ids, similar_title


class _UnionFind:
    def __init__(self, n: int):
        self.parent = list(range(n))

    def find(self, i: int) -> int:
        while self.parent[i] != i:
            self.parent[i] = self.parent[self.parent[i]]
            i = self.parent[i]
        return i

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _group_priority(p: Paper):
    """Sort key: decided > curated > richest metadata."""
    decided = p.review.get("decision") in ("accepted", "rejected")
    return (decided, p.curated, len(p.abstract or ""), len(p.links or {}))


def merge_group(group: List[Paper]) -> Paper:
    """Merge a group of records for the same work into its primary record."""
    group = sorted(group, key=_group_priority, reverse=True)
    primary = group[0]
    for other in group[1:]:
        primary.merge_with(other)
    return primary


def dedup_papers(
    papers: List[Paper],
    fuzzy_threshold: float = FUZZY_TITLE_THRESHOLD,
    tie_breaker: Optional[Callable[[Paper, Paper], float]] = None,
) -> List[Paper]:
    """
    Deduplicate a list of papers (identifier pass, then fuzzy-title pass).

    Parameters
    ----------
    papers : list of Paper
    fuzzy_threshold : float
        `similar_title` score at or above which two id-disjoint records merge.
    tie_breaker : callable, optional
        Extra similarity function (e.g. embedding cosine) consulted for pairs
        scoring in [fuzzy_threshold - 0.08, fuzzy_threshold); if it returns
        >= 0.9 the pair merges anyway.

    Returns
    -------
    list of Paper
        Deduplicated records, first-seen order preserved.
    """
    if not papers:
        return []

    # ---- Pass 1: identifier graph ----
    uf = _UnionFind(len(papers))
    seen_ids = {}
    for i, p in enumerate(papers):
        for cid in canonical_ids(p):
            if cid in seen_ids:
                uf.union(seen_ids[cid], i)
            else:
                seen_ids[cid] = i

    groups = defaultdict(list)
    for i, p in enumerate(papers):
        groups[uf.find(i)].append(p)
    merged = [merge_group(g) for root, g in sorted(groups.items())]

    # ---- Pass 2: fuzzy titles within year ± 1 ----
    by_year = defaultdict(list)
    for idx, p in enumerate(merged):
        by_year[p.year or 0].append(idx)

    uf2 = _UnionFind(len(merged))
    for year in sorted(by_year):
        candidates = by_year[year] + by_year.get(year + 1, [])
        for i_pos in range(len(candidates)):
            for j_pos in range(i_pos + 1, len(candidates)):
                i, j = candidates[i_pos], candidates[j_pos]
                if uf2.find(i) == uf2.find(j):
                    continue
                a, b = merged[i], merged[j]
                score = similar_title(a.title, b.title)
                if score >= fuzzy_threshold:
                    uf2.union(i, j)
                elif tie_breaker and score >= fuzzy_threshold - 0.08:
                    if tie_breaker(a, b) >= 0.9:
                        uf2.union(i, j)

    groups2 = defaultdict(list)
    for i, p in enumerate(merged):
        groups2[uf2.find(i)].append(p)
    return [merge_group(g) for root, g in sorted(groups2.items())]
