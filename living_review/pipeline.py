"""
pipeline.py
===========

Main orchestration pipeline for the **Living Review** project.

The `LivingReviewPipeline` class coordinates the entire workflow:
1. Load the canonical DB (`data/db.json`; falls back to the legacy
   published file on first run).
2. Fetch papers from multiple bibliographic sources (arXiv, InspireHEP,
   HAL, OpenAlex, Crossref) and merge/deduplicate them into the DB.
3. Optionally ingest CMS-approved manual submissions.
4. Run the relevance funnel over *undecided* papers only
   (enrich → gates → NLI adjudicator, see relevance.py / SCOPE.md).
   Accepted/rejected decisions are terminal.
5. Classify accepted papers into categories; Others-only strays are
   demoted to the pending queue.
6. Compute statistics and export.

Data files
----------
- `data/db.json`               : canonical DB — every paper ever seen,
                                 with decision provenance. Committed.
- `data/pending_review.json`   : ranked human-review queue (regenerated).
- `site/data/livingreview.json`: published, accepted-only, derived — what
                                 Hugo renders. Never hand-edited.
- BibTeX → `site/static/downloads/livingreview.bib`
- PDF    → `site/static/downloads/livingreview.pdf`
"""

import os
import time
from pathlib import Path

from .adjudicator import NLIAdjudicator
from .classifier import classify_papers
from .db import DB, promote_manual_submissions
from .exporters import export_bibtex, export_json, export_pdf
from .fetchers import (
    fetch_arxiv,
    fetch_crossref,
    fetch_hal,
    fetch_inspire,
    fetch_openalex,
    fetch_pubmed,
    fetch_semanticscholar,
    fetch_springer,
)
from .relevance import (
    accepted_papers,
    demote_others_only,
    export_pending_queue,
    run_funnel,
)
from .stats import compute_stats

DEFAULT_DB_PATH = "data/db.json"
LEGACY_DB_PATH = "site/data/livingreview.json"
PENDING_QUEUE_PATH = "data/pending_review.json"


class LivingReviewPipeline:
    """
    Orchestrates the end-to-end Living Review workflow.
    """

    def __init__(self, start, end, sources=None,
                 output_dir=".", chunking=None,
                 db_path=DEFAULT_DB_PATH,
                 promote_manual=False,
                 adjudicator=None):
        """
        Parameters
        ----------
        start, end : datetime.date
            Date window for fetching new papers.
        sources : list of str
            Bibliographic sources to query (default: all).
        output_dir : str
            Base directory of the Hugo project (default ".").
        chunking : dict, optional
            If set, export results in chunks (batches of papers).
        db_path : str
            Path to the canonical JSON DB (default: data/db.json).
        promote_manual : bool
            If True, promote CMS-approved submissions into the DB.
        adjudicator : Adjudicator, optional
            Stage C adjudicator; defaults to the NLI one (injectable
            for tests).
        """
        self.start = start
        self.end = end
        self.sources = sources or ["arxiv", "inspire", "hal", "openalex", "crossref"]
        self.output_dir = output_dir
        self.chunking = chunking
        self.db_path = db_path
        self.promote_manual = promote_manual
        self.adjudicator = adjudicator

        self.papers = []   # publishable list after funnel + classification
        self.stats = {}
        self.start_time = None

        # Flags controlled from CLI
        self.export_pdf = True
        self.export_bibtex = True

        # --- Print config summary ---
        print("[config] Sources:", ", ".join(self.sources))
        print("[config] Output dir:", self.output_dir)
        print("[config] DB path:", self.db_path)
        if self.chunking:
            print(f"[config] Chunking enabled: {self.chunking['size']} papers per chunk")

    def _load_db(self) -> DB:
        db_file = Path(self.db_path)
        legacy = Path(self.output_dir) / LEGACY_DB_PATH
        if not db_file.exists() and legacy.exists():
            print(f"[info] {self.db_path} absent; bootstrapping from {legacy}")
            return DB.load(legacy)
        return DB.load(db_file)

    def run(self):
        """Execute the pipeline end-to-end."""
        self.start_time = time.time()
        print(f"[info] Fetching papers {self.start} → {self.end}")

        # --- Load DB ---
        db = self._load_db()
        print(f"[info] Loaded DB with {len(db)} existing entries")

        # --- Fetch & merge ---
        fetchers = {
            "arxiv": fetch_arxiv,
            "inspire": fetch_inspire,
            "hal": fetch_hal,
            "openalex": fetch_openalex,
            "crossref": fetch_crossref,
            "semanticscholar": fetch_semanticscholar,
            "springer": fetch_springer,
            "pubmed": fetch_pubmed,
        }
        for name in self.sources:
            fetch = fetchers.get(name)
            if fetch is None:
                print(f"[warn] Unknown source '{name}', skipping")
                continue
            print(f"[info] Ingesting {name}:", db.merge_from_list(fetch(self.start, self.end)))

        # --- Manual submissions (from CMS) ---
        if self.promote_manual:
            promoted = promote_manual_submissions(db)
            print("[info] Promoting manual submissions:", promoted)

        # --- Relevance funnel over undecided papers only ---
        adjudicator = self.adjudicator or NLIAdjudicator()
        counts = run_funnel(db, adjudicator)
        print(f"[info] Funnel: {counts}")

        # --- Classification of accepted papers ---
        accepted = accepted_papers(db)
        print(f"[info] Classifying {len(accepted)} accepted papers")
        classify_papers(accepted)
        self.papers = demote_others_only(accepted)
        demoted = len(accepted) - len(self.papers)
        if demoted:
            print(f"[info] {demoted} Others-only papers demoted to pending queue")

        # --- Persist canonical DB (all papers + decisions) ---
        db.save(self.db_path)
        print(f"[info] Canonical DB saved with {len(db)} entries → {self.db_path}")
        n_pending = export_pending_queue(db, Path(self.output_dir) / PENDING_QUEUE_PATH)
        print(f"[info] Pending queue: {n_pending} papers → {PENDING_QUEUE_PATH}")

        # --- Export published artifacts (accepted only) ---
        os.makedirs(self.output_dir, exist_ok=True)

        if self.chunking:
            chunk_size = self.chunking.get("size", 100)
            print(f"[info] Exporting in batches of {chunk_size} papers")
            for i in range(0, len(self.papers), chunk_size):
                batch = self.papers[i:i + chunk_size]
                batch_stats = compute_stats(batch)
                batch_index = i // chunk_size + 1
                print(f"[info] Exporting batch {batch_index} ({len(batch)} papers)")
                export_json(batch, batch_stats, self.output_dir, chunking={"index": batch_index})
                if self.export_bibtex:
                    export_bibtex(batch, self.output_dir)
                if self.export_pdf:
                    export_pdf(batch, batch_stats, self.output_dir)
        else:
            print("[info] Computing stats")
            self.stats = compute_stats(self.papers)
            msg = "[info] Exporting JSON (published)"
            if self.export_bibtex:
                msg += " + BibTeX"
            if self.export_pdf:
                msg += " + PDF"
            print(msg)

            export_json(self.papers, self.stats, self.output_dir)
            if self.export_bibtex:
                export_bibtex(self.papers, self.output_dir)
            if self.export_pdf:
                export_pdf(self.papers, self.stats, self.output_dir)

        # --- Summary ---
        elapsed = time.time() - self.start_time
        print(f"[ok] Export completed → Hugo site directories")
        print(f"[summary] {len(self.papers)} papers published, {n_pending} pending")
        print(f"[summary] Runtime: {elapsed:.2f} seconds")
