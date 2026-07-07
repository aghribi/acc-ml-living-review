# 🌐 ML/AI for Particle Accelerators — Living Review

This repository hosts the **Living Review of Machine Learning (ML) and Artificial Intelligence (AI) applications in Particle Accelerator Science**.  
It is maintained by the accelerator physics and AI-for-science community, and aims to provide a continuously updated reference of methods, datasets, and results at the intersection of **accelerator physics** and **data-driven techniques**.

---

## 📖 About the Living Review

- A **community-driven review**: contributions are welcome from researchers, engineers, and students.  
- Built as a **Hugo static site**, hosted on GitHub Pages.  
- Content is managed through **Decap CMS** (Netlify-compatible admin interface).  
- The review is **automatically updated** from structured data and can be browsed interactively by category, keyword, facility, or year.

👉 **Website:** [ML/AI Living Review for Accelerators](https://aghribi.github.io/acc-ml-living-review/)  
👉 **Admin interface (contributors only):** `/admin/`  

---

## 📂 Repository Structure

```
acc-ml-living-review/
├── SCOPE.md             # Editorial criterion: what belongs in the review
├── data/
│   ├── db.json          # Canonical DB: every paper + decision provenance
│   ├── pending_review.json  # Human-review queue (regenerated nightly)
│   └── eval/            # Relevance-funnel evaluation slices
├── site/                # Hugo site source
│   ├── content/         # Pages (Markdown)
│   ├── layouts/         # Templates and partials
│   ├── static/          # Static assets (figures, CSS, downloads)
│   └── data/            # Published data (accepted papers only, derived)
├── living_review/       # Python pipeline
│   ├── fetchers.py      # Sources: arXiv, INSPIRE, HAL, OpenAlex, Crossref
│   ├── enrich.py        # Abstract backfill (Crossref/OpenAlex/arXiv)
│   ├── dedup.py         # Identifier-graph + fuzzy-title deduplication
│   ├── gates.py         # Stage B: deterministic accept/reject rules
│   ├── adjudicator.py   # Stage C: zero-shot NLI relevance adjudication
│   ├── relevance.py     # Funnel orchestration, terminal decisions
│   ├── classifier.py    # Category classification
│   ├── exporters.py     # Export JSON/BibTeX/PDF for the site
│   └── pipeline.py      # End-to-end pipeline
├── scripts/             # CI sanity gate, NLI threshold calibration
├── tests/               # Pytest suite incl. funnel eval benchmark
└── README.md            # This file
```

**How papers get in** (see `SCOPE.md` and the methodology page of the
docs): fetch → enrich → dedup → deterministic gates → NLI adjudicator →
human pending queue. Accepted/rejected decisions are terminal and carry
full provenance; `site/data/livingreview.json` is derived build output
containing accepted papers only.

---

## 🚀 Getting Started

### 1. Clone the repository
```bash
git clone https://github.com/aghribi/acc-ml-living-review.git
cd acc-ml-living-review
```

### 2. Build the Hugo site locally
You need [Hugo Extended](https://gohugo.io/getting-started/installing/):
```bash
cd site
hugo server
```
Then visit [http://localhost:1313](http://localhost:1313).

### 3. Update the Living Review database
The pipeline fetches papers, runs the relevance funnel, and updates the exports:

```bash
pip install -e ".[dev]"
python -m living_review.cli run --days 30 --sources all
```

Inspect the human-review queue:
```bash
python -m living_review.cli review
```

Run the test suite (fast tests only; add `-m slow` for the model-based
eval benchmark):
```bash
pytest -m "not slow"
```

---

## ✨ Features

- **Interactive browsing**: search by keywords, collapse/expand sections.  
- **Statistics & trends**: publication counts per year, category, and facility.  
- **Downloadable data**: JSON, BibTeX, PDF snapshot.  
- **Community contributions**: easy editing via Decap CMS.  

---

## 🙌 Contributing

We welcome new contributors!  

- **To edit content**:  
  Log in via the `/admin/` page (Decap CMS) with GitHub Identity.  
- **To extend the pipeline**:  
  Submit PRs to improve fetchers, classifiers, or exporters.  
- **To add a paper manually**:  
  Open an issue or edit the data file in `site/data/livingreview.json`.

👉 Check the [Contributors](https://github.com/aghribi/acc-ml-living-review/graphs/contributors) page for the growing community.

---

## 📜 Cite Us

If you use this living review in your research, please cite:

```bibtex
@misc{hepmllivingreview,
    author       = "{HEP ML Community}",
    title        = "{A Living Review of Machine Learning for Particle Accelerators}",
    year         = {2025},
    url          = {https://aghribi.github.io/acc-ml-living-review/}
}
```

---

## 📧 Contact

Maintained by the **Accelerator Physics & AI community**.  
Contact: [Adnan Ghribi](https://github.com/aghribi) (CNRS–GANIL).  

---

## 🔖 License

This project is released under the **MIT License**.  
See [LICENSE](./LICENSE) for details.
