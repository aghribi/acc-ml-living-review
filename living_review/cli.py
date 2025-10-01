"""
cli.py
======

Command-line interface (CLI) for the Living Review pipeline.

This script allows users to run the **Living Review: ML/AI for Accelerator Physics**
pipeline directly from the terminal. It provides options to configure the scan
window, data sources, classification thresholds, and output location.

Main Features
-------------
- Configure the date range (number of days back from today).
- Select which data sources to query (arXiv, Inspire, HAL, OpenAlex, Crossref).
- Override default accelerator/ML relevance thresholds.
- Control output directory and chunk size for large runs.
- Optionally enable incremental mode (not yet fully implemented).
- Enable/disable PDF and BibTeX exports.

Typical Usage
-------------
Run a full scan of the last 30 days from all sources with default thresholds:

    $ python -m living_review.cli

Run a 60-day scan only from arXiv and Inspire with custom thresholds:

    $ python -m living_review.cli --days 60 --sources arxiv,inspire \\
           --accel-threshold 0.15 --ml-threshold 0.20 --output results

Disable PDF export but keep BibTeX:

    $ python -m living_review.cli --no-pdf
"""

import argparse
import datetime as dt
from .pipeline import LivingReviewPipeline
from .config import DEFAULT_THRESHOLDS


def main():
    """
    Entry point for the Living Review CLI.

    Parses command-line arguments, builds the date range and configuration,
    initializes the `LivingReviewPipeline`, and runs it.
    """
    ap = argparse.ArgumentParser(
        description="Living Review: ML/AI for Accelerator Physics"
    )
    ap.add_argument("--days", type=int, default=30,
                    help="Number of days back to scan (default: 30)")
    ap.add_argument("--sources", type=str, default="all",
                    help="Comma-separated list: arxiv,inspire,hal,openalex,crossref,all (default: all)")
    ap.add_argument("--accel-threshold", type=float, default=None,
                    help=f"Threshold for accelerator relevance (default: {DEFAULT_THRESHOLDS['accel']})")
    ap.add_argument("--ml-threshold", type=float, default=None,
                    help=f"Threshold for ML/AI relevance (default: {DEFAULT_THRESHOLDS['ml']})")
    ap.add_argument("--output", type=str, default="output",
                    help="Directory for JSON/HTML/PDF/BibTeX outputs (default: output)")
    ap.add_argument("--chunk-size", type=int, default=None,
                    help="Number of papers per chunk (optional)")
    ap.add_argument("--incremental", action="store_true",
                    help="Run incrementally, skipping already scanned periods")

    # --- New flags for export control ---
    ap.add_argument("--no-pdf", action="store_true",
                    help="Disable PDF export")
    ap.add_argument("--no-bibtex", action="store_true",
                    help="Disable BibTeX export")

    args = ap.parse_args()

    # --- Date range ---
    end = dt.date.today()
    start = end - dt.timedelta(days=args.days)

    # --- Sources ---
    sources = args.sources.split(",")
    if "all" in sources:
        sources = ["arxiv", "inspire", "hal", "openalex", "crossref"]

    # --- Thresholds (override defaults only if user provided values) ---
    thresholds = {
        "accel": args.accel_threshold if args.accel_threshold is not None else DEFAULT_THRESHOLDS["accel"],
        "ml": args.ml_threshold if args.ml_threshold is not None else DEFAULT_THRESHOLDS["ml"],
    }

    # --- Pipeline ---
    pipe = LivingReviewPipeline(
        start, end,
        sources=sources,
        thresholds=thresholds,
        output_dir=args.output,
        chunking={"size": args.chunk_size} if args.chunk_size else None
    )

    # Attach export control flags
    pipe.export_pdf = not args.no_pdf
    pipe.export_bibtex = not args.no_bibtex

    if args.incremental:
        print("[warn] Incremental mode not fully implemented yet, running full scan.")

    pipe.run()


if __name__ == "__main__":
    main()
