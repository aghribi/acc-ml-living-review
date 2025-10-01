# ---------------------------
# JSON Export (canonical DB)
# ---------------------------
def export_json(papers, stats, outdir, chunking=None):
    """
    Export the canonical JSON database for Hugo and Decap CMS.

    Output files:
    - site/data/livingreview.json   (stats first, then papers)
    - site/data/statistics.json     (simplified global stats)

    Parameters
    ----------
    papers : list of Paper
        List of processed Paper objects.
    stats : dict
        Computed statistics (per_year, per_category, etc.).
    outdir : str or Path
        Base directory of the Hugo project.
    chunking : dict, optional
        If provided, writes chunked JSON files (e.g. for batch exports).
    """
    from collections import OrderedDict
    outpath = _resolve_outpath(Path(outdir), kind="json")
    outpath.mkdir(parents=True, exist_ok=True)

    # papers dict keyed by dedup key
    papers_dict = {str(p.key_for_dedup()): p.to_dict() for p in papers}

    # Ensure stats is written first
    result = OrderedDict()
    result["stats"] = stats
    result["papers"] = papers_dict

    # Write main livingreview.json
    fname = outpath / "livingreview.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[ok] JSON DB (stats + papers) written → {fname}")

    # Write simplified statistics.json
    # ⚠️ This is separate from `stats` — it’s the summary file
    global_stats = {
        "total_papers": len(papers),
        "total_categories": len(stats.get("per_category", {})),
        "last_updated": stats.get("last_updated", ""),
        "next_update": stats.get("next_update", ""),
        "latest_papers": stats.get("monthly_trends", {}).get(max(stats.get("monthly_trends", {}), default=""), 0),
        "latest_month": max(stats.get("monthly_trends", {}), default="")
    }
    sname = outpath / "statistics.json"
    with open(sname, "w", encoding="utf-8") as f:
        json.dump(global_stats, f, indent=2, ensure_ascii=False)
    print(f"[ok] Global statistics file written → {sname}")
