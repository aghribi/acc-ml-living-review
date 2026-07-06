Living Review Documentation
===========================

This project provides tools for building *living reviews* of
machine learning and accelerator physics publications. It includes:

- Fetchers for arXiv, InspireHEP, HAL, OpenAlex, Crossref.
- A staged relevance funnel: metadata enrichment, deterministic gates,
  and a zero-shot NLI adjudicator with a human pending queue.
- Identifier-graph + fuzzy-title deduplication.
- Category classification and statistics computation.
- Export to JSON (published site data), BibTeX, and PDF.
- A full pipeline + CLI for automation.

Contents
--------

.. toctree::
   :maxdepth: 2
   :caption: Methodology

   methodology

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   living_review
