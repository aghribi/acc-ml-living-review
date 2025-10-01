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
from pathlib import Path
from typing import Dict, List

from .data_model import Paper, status_rank


class DB:
    """
    Representation of the Living Review database.

    Attributes
    ----------
    entries : dict
        Dictionary mapping deduplication keys (as str) → Paper objects.
    """

    def __init__(self, entries: Dict[str, Paper] = None):
        self.entries: Dict[str, Paper] = entries or {}

    # ------------------------
    # Core methods
    # ------------------------
    @classmethod
    def load(cls, path: str | Path) -> "DB":
        """Load the canonical DB from JSON."""
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
        """Add a new paper or update an existing one."""
        key = str(paper.key_for_dedup())
        self.entries[key] = paper

    def merge(self, other: "DB") -> int:
        """Merge another DB into this one with deduplication + status promotion."""
        updates = 0
        for key, paper in other.entries.items():
            if self._merge_one(key, paper):
                updates += 1
        return updates

    def merge_from_list(self, papers: List[Paper]) -> int:
        """Merge a list of Paper objects into this DB."""
        updates = 0
        for paper in papers:
            key = str(paper.key_for_dedup())
            if self._merge_one(key, paper):
                updates += 1
        return updates

    def _merge_one(self, key: str, paper: Paper) -> bool:
        """Merge a single Paper into DB under dedup key."""
        if key not in self.entries:
            self.entries[key] = paper
            return True
        else:
            current = self.entries[key]
            if status_rank(paper.status) > status_rank(current.status):
                self.entries[key] = paper
                return True
            elif paper.status == current.status:
                # Heuristic: prefer richer metadata
                score_new = len(paper.abstract or "") + len(paper.links or {})
                score_old = len(current.abstract or "") + len(current.links or {})
                if score_new > score_old:
                    self.entries[key] = paper
                    return True
        return False

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
