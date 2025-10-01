"""
exporters.py
============

Output/export utilities for the **Living Review** project.

This module provides functions to export processed papers and statistics
into formats directly consumable by the Hugo site and citation managers:

- JSON → site/data/livingreview.json + site/data/statistics.json
- BibTeX → site/static/downloads/livingreview.bib
- PDF → site/static/downloads/livingreview.pdf
"""

import json
from pathlib import Path


# ---------------------------
# Utility: resolve Hugo subfolders
# ---------------------------
def _resolve_outpath(outdir: Path, kind: str) -> Path:
    """
    Always resolve paths relative to the Hugo 'site/' directory at repo root.

    Parameters
    ----------
    outdir : Path
        Base directory of the repo (typically '.').
    kind : str
        One of {"json", "bibtex", "pdf"}.

    Returns
    -------
    Path
        The resolved subdirectory where the file should be written.
    """
def _resolve_outpath(outdir: Path, kind: str) -> Path:
    """
    Always resolve paths relative to the Hugo 'site/' directory.
    If outdir is inside another folder (e.g. 'output'), climb up until 'site/' is found.
    """
    outdir = Path(outdir).resolve()

    # climb up until we find site/
    site_dir = None
    for parent in [outdir] + list(outdir.parents):
        if (parent / "site").exists():
            site_dir = parent / "site"
            break
    if site_dir is None:
        raise FileNotFoundError(f"Could not locate 'site/' directory from {outdir}")

    if kind == "json":
        return site_dir / "data"
    elif kind in {"bibtex", "pdf"}:
        return site_dir / "static" / "downloads"
    return site_dir



# ---------------------------
# JSON Export (canonical DB)
# ---------------------------
def export_json(papers, stats, outdir, chunking=None):
    """
    Export the canonical JSON database for Hugo and Decap CMS.

    Output files:
    - site/data/livingreview.json   (stats first, then papers)
    - site/data/statistics.json     (simplified global stats)
    """
    from collections import OrderedDict
    outpath = _resolve_outpath(Path(outdir), kind="json")
    outpath.mkdir(parents=True, exist_ok=True)

    papers_dict = {str(p.key_for_dedup()): p.to_dict() for p in papers}

    result = OrderedDict()
    result["stats"] = stats
    result["papers"] = papers_dict

    fname = outpath / "livingreview.json"
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[ok] JSON DB (stats + papers) written → {fname}")

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


# ---------------------------
# BibTeX Export
# ---------------------------
def export_bibtex(papers, outdir):
    """
    Export papers into a BibTeX file for citation management.

    Output file: site/static/downloads/livingreview.bib
    """
    outpath = _resolve_outpath(Path(outdir), kind="bibtex")
    outpath.mkdir(parents=True, exist_ok=True)
    fname = outpath / "livingreview.bib"

    bib_entries = []
    for i, p in enumerate(papers, 1):
        key = (p.doi.replace("/", "_") if p.doi else f"paper{i}")
        authors = " and ".join(p.authors)
        year = p.year or (p.date[:4] if isinstance(p.date, str) else getattr(p.date, "year", ""))
        entry = (
            f"@article{{{key},\n"
            f"  title={{ {p.title} }},\n"
            f"  author={{ {authors} }},\n"
            f"  year={{ {year} }},\n"
            f"  journal={{ {p.venue or 'arXiv'} }},\n"
            f"  url={{ {p.links.get('doi') or p.links.get('arxiv') or ''} }},\n"
            f"  doi={{ {p.doi or ''} }}\n"
            f"}}\n"
        )
        bib_entries.append(entry)

    with open(fname, "w", encoding="utf-8") as f:
        f.write("\n".join(bib_entries))
    print(f"[ok] BibTeX file created → {fname}")


# ---------------------------
# PDF Export
# ---------------------------
def export_pdf(papers, stats, outdir):
    """
    Export a printable PDF summary of the review.

    Output file: site/static/downloads/livingreview.pdf
    """
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet

    outpath = _resolve_outpath(Path(outdir), kind="pdf")
    outpath.mkdir(parents=True, exist_ok=True)
    fname = outpath / "livingreview.pdf"

    doc = SimpleDocTemplate(str(fname))
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("Accelerator ML Living Review", styles["Title"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Summary Statistics", styles["Heading2"]))
    for k, v in stats.items():
        story.append(Paragraph(f"{k}: {len(v) if isinstance(v, dict) else v}", styles["Normal"]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Papers", styles["Heading2"]))
    for p in papers:
        authors = ", ".join(p.authors)
        year = p.year or (p.date[:4] if isinstance(p.date, str) else getattr(p.date, "year", ""))
        entry = f"<b>{p.title}</b><br/>{authors} ({year})<br/>{p.venue or 'arXiv'}"
        story.append(Paragraph(entry, styles["Normal"]))
        story.append(Spacer(1, 6))

    doc.build(story)
    print(f"[ok] PDF review created → {fname}")
