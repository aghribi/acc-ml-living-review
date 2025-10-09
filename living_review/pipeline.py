"""
pipeline.py
===========

Main orchestration pipeline for the **Living Review** project.

The `LivingReviewPipeline` class coordinates the entire workflow:
1. Load existing DB (if present).
2. Fetch papers from multiple bibliographic sources (arXiv, InspireHEP,
   HAL, OpenAlex, Crossref).
3. Deduplicate & merge into canonical DB (preprint → journal, DOI, etc.).
4. Optionally ingest CMS-approved manual submissions.
5. Filter papers for semantic relevance (accelerators ∧ ML).
6. Classify papers into categories.
7. Compute statistics.
8. Export results to Hugo site in multiple formats.

Canonical DB location
---------------------
The canonical JSON database is stored in the Hugo site’s `/data/` folder:

    site/data/livingreview.json

This file is:
- Updated by this pipeline when merging new papers,
- Exported again at the end of the run (papers + stats),
- Read by Hugo templates (`.Site.Data.livingreview`),
- Editable via Decap CMS.

Other outputs
-------------
- BibTeX → `site/static/downloads/livingreview.bib`
- PDF    → `site/static/downloads/livingreview.pdf`

(Note: HTML export has been removed — Hugo now builds pages directly from the JSON DB.)
"""

import os, time
from .fetchers import fetch_arxiv, fetch_inspire, fetch_hal, fetch_openalex, fetch_crossref, fetch_semanticscholar, fetch_springer, fetch_pubmed
from .classifier import filter_relevant_papers, classify_papers
from .stats import compute_stats
from .exporters import export_json, export_bibtex, export_pdf
from .config import DEFAULT_THRESHOLDS
from .db import DB, promote_manual_submissions


class LivingReviewPipeline:
    """
    Orchestrates the end-to-end Living Review workflow.
    """

    def __init__(self, start, end, sources=None, thresholds=None,
                 output_dir=".", chunking=None,
                 db_path="site/data/livingreview.json",
                 promote_manual=False):
        """
        Parameters
        ----------
        start, end : datetime.date
            Date window for fetching new papers.
        sources : list of str
            Bibliographic sources to query (default: all).
        thresholds : dict
            Relevance thresholds for accelerator/ML filtering.
        output_dir : str
            Base directory of the Hugo project (default ".").
        chunking : dict, optional
            If set, export results in chunks (batches of papers).
        db_path : str
            Path to canonical JSON DB (default: site/data/livingreview.json).
        promote_manual : bool
            If True, promote CMS-approved submissions into the DB.
        """
        self.start = start
        self.end = end
        self.sources = sources or ["arxiv", "inspire", "hal", "openalex", "crossref"]
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.output_dir = output_dir
        self.chunking = chunking
        self.db_path = db_path
        self.promote_manual = promote_manual

        self.papers = []   # working list after DB load + ingest
        self.stats = {}
        self.start_time = None

        # Flags controlled from CLI
        self.export_pdf = True
        self.export_bibtex = True

        # --- Print config summary ---
        print("[config] Sources:", ", ".join(self.sources))
        print("[config] Thresholds:", self.thresholds)
        print("[config] Output dir:", self.output_dir)
        print("[config] DB path:", self.db_path)
        if self.chunking:
            print(f"[config] Chunking enabled: {self.chunking['size']} papers per chunk")

    def run(self):
        """Execute the pipeline end-to-end."""
        self.start_time = time.time()
        print(f"[info] Fetching papers {self.start} → {self.end}")

        # --- Load DB ---
        db = DB.load(self.db_path)
        print(f"[info] Loaded DB with {len(db)} existing entries")

        # --- Fetch & merge ---
        if "arxiv" in self.sources:
            print("[info] Ingesting arXiv:", db.merge_from_list(fetch_arxiv(self.start, self.end)))
        if "inspire" in self.sources:
            print("[info] Ingesting Inspire:", db.merge_from_list(fetch_inspire(self.start, self.end)))
        if "hal" in self.sources:
            print("[info] Ingesting HAL:", db.merge_from_list(fetch_hal(self.start, self.end)))
        if "openalex" in self.sources:
            print("[info] Ingesting OpenAlex:", db.merge_from_list(fetch_openalex(self.start, self.end)))
        if "crossref" in self.sources:
            print("[info] Ingesting CrossRef:", db.merge_from_list(fetch_crossref(self.start, self.end)))
        if "semanticscholar" in self.sources:
            print("[info] Ingesting Semantic Scholar:", db.merge_from_list(fetch_semanticscholar(self.start, self.end)))
        if "springer" in self.sources:
            print("[info] Ingesting Springer:", db.merge_from_list(fetch_springer(self.start, self.end)))
        if "pubmed" in self.sources:
            print("[info] Ingesting PubMed:", db.merge_from_list(fetch_pubmed(self.start, self.end)))

        # --- Manual submissions (from CMS) ---
        if self.promote_manual:
            promoted = promote_manual_submissions(db)
            print("[info] Promoting manual submissions:", promoted)

        # --- Save merged DB ---
        db.save(self.db_path)
        print(f"[info] DB saved with {len(db)} entries → {self.db_path}")

        # --- Prepare working list ---
        self.papers = list(db.entries.values())
        print(f"[info] {len(self.papers)} unique papers in working set")

        # --- Semantic filtering (accelerator + ML relevance) ---
        accel_th = self.thresholds.get("accel", 0.13)
        ml_th = self.thresholds.get("ml", 0.18)
        print(f"[info] Filtering papers with thresholds accel≥{accel_th}, ml≥{ml_th}")
        self.papers = filter_relevant_papers(
            self.papers,
            accel_threshold=accel_th,
            ml_threshold=ml_th
        )
        print(f"[info] {len(self.papers)} papers kept after semantic filtering")

        # --- Classification ---
        print("[info] Classifying papers")
        classify_papers(self.papers)

        # --- Export ---
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
            msg = "[info] Exporting JSON (DB)"
            if self.export_bibtex:
                msg += " + BibTeX"
            if self.export_pdf:
                msg += " + PDF"
            print(msg)

            # JSON export overwrites canonical DB with latest stats + papers
            export_json(self.papers, self.stats, self.output_dir)
            if self.export_bibtex:
                export_bibtex(self.papers, self.output_dir)
            if self.export_pdf:
                export_pdf(self.papers, self.stats, self.output_dir)

        # --- Summary ---
        elapsed = time.time() - self.start_time
        total_papers = len(self.papers)
        print(f"[ok] Export completed → Hugo site directories")
        print(f"[summary] {total_papers} papers processed")
        print(f"[summary] Runtime: {elapsed:.2f} seconds")
