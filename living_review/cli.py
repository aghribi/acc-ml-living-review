"""
cli.py
======

Command-line interface (CLI) for the Living Review pipeline.

Subcommands
-----------
- ``run``     : nightly pipeline (fetch → dedup → funnel → classify → export)
- ``review``  : print the pending human-review queue
- ``migrate`` : one-off migration of the legacy published DB into the
                canonical data/db.json (see migrate.py)

Backward compatibility: invoking without a subcommand behaves like ``run``
(the CI workflow predates subcommands).

Typical Usage
-------------
Run a full scan of the last 30 days from all sources:

    $ python -m living_review.cli run --days 30 --sources all

Disable PDF export but keep BibTeX:

    $ python -m living_review.cli run --no-pdf

Show the pending queue:

    $ python -m living_review.cli review
"""

import argparse
import datetime as dt
import sys

COMMANDS = ("run", "review", "migrate", "backfill-history")


def _add_run_parser(sub):
    p = sub.add_parser("run", help="Run the nightly pipeline")
    p.add_argument("--days", type=int, default=30,
                   help="Number of days back to scan (default: 30)")
    p.add_argument("--sources", type=str, default="all",
                   help="Comma-separated list: arxiv,inspire,hal,openalex,"
                        "crossref,semanticscholar,springer,pubmed,all (default: all)")
    p.add_argument("--output", type=str, default=".",
                   help="Base directory of the repo (default: current dir)")
    p.add_argument("--db-path", type=str, default="data/db.json",
                   help="Canonical DB path (default: data/db.json)")
    p.add_argument("--chunk-size", type=int, default=None,
                   help="Number of papers per export chunk (optional)")
    p.add_argument("--promote-manual", action="store_true",
                   help="Promote CMS-approved submissions into the DB")
    p.add_argument("--no-pdf", action="store_true", help="Disable PDF export")
    p.add_argument("--no-bibtex", action="store_true", help="Disable BibTeX export")
    return p


def _add_review_parser(sub):
    p = sub.add_parser("review", help="Print the pending human-review queue")
    p.add_argument("--db-path", type=str, default="data/db.json")
    p.add_argument("--limit", type=int, default=30)
    return p


def _add_migrate_parser(sub):
    p = sub.add_parser("migrate",
                       help="One-off: migrate the legacy published DB into data/db.json")
    p.add_argument("--source", type=str, default="site/data/livingreview.json")
    p.add_argument("--db-path", type=str, default="data/db.json")
    p.add_argument("--report", type=str, default="data/migration_dropped.md")
    p.add_argument("--eval-dir", type=str, default="data/eval")
    p.add_argument("--dry-run", action="store_true",
                   help="Write nothing; print the would-be outcome summary")
    p.add_argument("--gates-only", action="store_true",
                   help="Stop after Stage B gates (emit eval sets, no DB); "
                        "used to calibrate NLI thresholds before deciding")
    return p


def cmd_run(args):
    from .pipeline import LivingReviewPipeline

    end = dt.date.today()
    start = end - dt.timedelta(days=args.days)

    sources = args.sources.split(",")
    if "all" in sources:
        sources = ["arxiv", "inspire", "hal", "openalex", "crossref"]

    pipe = LivingReviewPipeline(
        start, end,
        sources=sources,
        output_dir=args.output,
        db_path=args.db_path,
        promote_manual=args.promote_manual,
        chunking={"size": args.chunk_size} if args.chunk_size else None,
    )
    pipe.export_pdf = not args.no_pdf
    pipe.export_bibtex = not args.no_bibtex
    pipe.run()


def cmd_review(args):
    from .db import DB
    from .relevance import pending_papers, rank_pending

    db = DB.load(args.db_path)
    queue = rank_pending(pending_papers(db))
    print(f"{len(queue)} papers pending review (showing up to {args.limit})\n")
    for p in queue[: args.limit]:
        rule = p.review.get("rule") or p.review.get("stage")
        score = p.review.get("score")
        score_s = f" score={score}" if score is not None else ""
        print(f"- [{rule}{score_s}] {p.title} ({p.year}, {p.venue})")


def _add_history_parser(sub):
    p = sub.add_parser("backfill-history",
                       help="One-off: sweep 1990+ historical windows through the funnel")
    p.add_argument("--from-year", type=int, default=1990)
    p.add_argument("--to-year", type=int, default=None)
    p.add_argument("--db-path", type=str, default="data/db.json")
    p.add_argument("--output", type=str, default=".")
    p.add_argument("--chunk-years", type=int, default=2)
    p.add_argument("--dry-run", action="store_true")
    return p


def cmd_history(args):
    from .history import backfill_history

    backfill_history(
        from_year=args.from_year,
        to_year=args.to_year,
        db_path=args.db_path,
        output_dir=args.output,
        chunk_years=args.chunk_years,
        dry_run=args.dry_run,
    )


def cmd_migrate(args):
    from .migrate import migrate

    migrate(
        source=args.source,
        db_path=args.db_path,
        report_path=args.report,
        eval_dir=args.eval_dir,
        dry_run=args.dry_run,
        gates_only=args.gates_only,
    )


def main(argv=None):
    """Entry point for the Living Review CLI."""
    argv = list(sys.argv[1:] if argv is None else argv)
    # Backward compatibility: no subcommand -> "run"
    if not argv or argv[0] not in COMMANDS and argv[0] not in ("-h", "--help"):
        argv.insert(0, "run")

    ap = argparse.ArgumentParser(
        prog="living-review",
        description="Living Review: ML/AI for Accelerator Physics",
    )
    sub = ap.add_subparsers(dest="command", required=True)
    _add_run_parser(sub)
    _add_review_parser(sub)
    _add_migrate_parser(sub)

    args = ap.parse_args(argv)
    {"run": cmd_run, "review": cmd_review, "migrate": cmd_migrate}[args.command](args)


if __name__ == "__main__":
    main()
