"""
db.py
=====

Database utilities for the **Living Review** project.

This module manages the canonical JSON database that stores all papers
collected and merged from multiple sources. The DB is the *single source
of truth* for the project, shared between:

- The pipeline (which updates it with new/merged entries),
- Hugo (which reads it via `.Site.Data.livingreview`),
- Decap CMS (which allows human editing/validation).

Canonical location
------------------
    site/data/livingreview.json

Structure of DB file
--------------------
{
    "papers": {
        "<dedup_key>": { ... paper fields ... },
        ...
    }
}

Helper functions are provided to:
- Load/save the DB,
- Add or update entries,
- Merge DBs or lists of papers,
- Promote manual submissions (approved via CMS).
"""

import json
import glob
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional

import difflib

from .config import FUZZY_TITLE_THRESHOLD
from .data_model import Paper
from .utils import canonical_ids, simplify_title


class DB:
    """
    Representation of the Living Review database.

    Attributes
    ----------
    entries : dict
        Dictionary mapping canonical paper ids (``doi:...``, ``arxiv:...``,
        ``hash:...``) → Paper objects. An auxiliary identifier index maps
        every known normalized identifier of an entry to its key, so an
        incoming record merges with an existing one when they share *any*
        identifier; records without shared identifiers fall back to fuzzy
        title matching within the same publication year (± 1).
    """

    def __init__(self, entries: Dict[str, Paper] = None):
        self.entries: Dict[str, Paper] = {}
        self._id_index: Dict[str, str] = {}
        self._year_index: Dict[int, list] = defaultdict(list)
        for p in (entries or {}).values():
            self._merge_one(p)

    # ------------------------
    # Core methods
    # ------------------------
    @classmethod
    def load(cls, path: str | Path) -> "DB":
        """Load the canonical DB from JSON (re-keyed by canonical paper id)."""
        path = Path(path)
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        papers = raw.get("papers", {})
        entries = {}
        if isinstance(papers, dict):
            for k, d in papers.items():
                try:
                    entries[k] = Paper.from_dict(d)
                except Exception as e:
                    print(f"[warn] Skipping invalid entry {k}: {e}")
        return cls(entries)

    def save(self, path: str | Path) -> None:
        """Save the canonical DB to JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"papers": {k: v.to_dict() for k, v in self.entries.items()}},
                f,
                indent=2,
                ensure_ascii=False,
            )

    def add_or_update(self, paper: Paper) -> None:
        """Add a new paper or merge it into an existing entry."""
        self._merge_one(paper)

    def merge(self, other: "DB") -> int:
        """Merge another DB into this one with deduplication + status promotion."""
        return self.merge_from_list(list(other.entries.values()))

    def merge_from_list(self, papers: List[Paper]) -> int:
        """Merge a list of Paper objects into this DB."""
        updates = 0
        for paper in papers:
            if self._merge_one(paper):
                updates += 1
        return updates

    def _find_existing(self, paper: Paper) -> Optional[str]:
        """Key of the entry this paper duplicates, or None."""
        for cid in canonical_ids(paper):
            if cid in self._id_index:
                return self._id_index[cid]
        if paper.id in self.entries:
            return paper.id
        # Fuzzy fallback: same title within year ± 1, no shared identifier.
        # Year-bucketed over cached simplified titles, with difflib's cheap
        # ratios as guards — an unbucketed scan re-simplifying both titles
        # per pair is O(n^2) regex+difflib work on DB.load (minutes at ~2k).
        simple = simplify_title(paper.title) or ""
        if not simple:
            return None
        matcher = difflib.SequenceMatcher(None, "", simple)
        years = [paper.year - 1, paper.year, paper.year + 1] if paper.year else [0]
        for y in years:
            for key, cur_simple in self._year_index.get(y or 0, []):
                if abs(len(cur_simple) - len(simple)) > 0.3 * max(len(simple), 1):
                    continue
                matcher.set_seq1(cur_simple)
                if matcher.real_quick_ratio() < FUZZY_TITLE_THRESHOLD:
                    continue
                if matcher.quick_ratio() < FUZZY_TITLE_THRESHOLD:
                    continue
                if matcher.ratio() >= FUZZY_TITLE_THRESHOLD and key in self.entries:
                    return key
        return None

    def _index(self, key: str, paper: Paper) -> None:
        for cid in canonical_ids(paper):
            self._id_index[cid] = key
        bucket = self._year_index[paper.year or 0]
        simple = simplify_title(paper.title) or ""
        if not any(k == key for k, _ in bucket):
            bucket.append((key, simple))

    def _merge_one(self, paper: Paper) -> bool:
        """Merge a single Paper into the DB (insert or field-wise merge)."""
        key = self._find_existing(paper)
        if key is None:
            self.entries[paper.id] = paper
            self._index(paper.id, paper)
            return True
        current = self.entries[key]
        # Field-wise merge honoring `curated` and terminal `review` decisions
        # (a whole-record replacement would clobber both).
        changed = current.merge_with(paper)
        # The merge may have upgraded the canonical id (hash: -> doi:/arxiv:)
        # or contributed new identifiers; keep key and index in step.
        if current.id != key:
            del self.entries[key]
            self.entries[current.id] = current
            for cid, k in list(self._id_index.items()):
                if k == key:
                    self._id_index[cid] = current.id
            for bucket in self._year_index.values():
                for i, (k, s) in enumerate(bucket):
                    if k == key:
                        bucket[i] = (current.id, s)
        self._index(current.id, current)
        return changed

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries.values())


# ------------------------
# Manual submissions
# ------------------------

SUBMISSIONS_BASE = Path("site/data/submissions")

def load_submissions(status: str = "pending") -> List[dict]:
    """
    Load manual submissions from JSON files by status.

    Parameters
    ----------
    status : str
        One of {"pending", "approved", "rejected"}.

    Returns
    -------
    list of dict
        List of paper dictionaries from submission files.
    """
    folder = SUBMISSIONS_BASE / status
    out = []
    for fname in glob.glob(str(folder / "*.json")):
        try:
            with open(fname, "r", encoding="utf-8") as f:
                entry = json.load(f)
                out.append(entry)
        except Exception as e:
            print(f"[warn] Failed to load submission {fname}: {e}")
    return out


def promote_manual_submissions(db: DB) -> int:
    """
    Promote CMS-approved manual submissions into the DB.

    Reads from `site/data/submissions/approved/`.

    Parameters
    ----------
    db : DB
        The database to update.

    Returns
    -------
    int
        Number of promoted entries.
    """
    approved = load_submissions("approved")
    papers = []
    for raw in approved:
        try:
            # Force source="manual"
            raw["source"] = "manual"
            papers.append(Paper.from_dict(raw))
        except Exception as e:
            print(f"[warn] Skipping invalid submission: {e}")
    return db.merge_from_list(papers)
