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
├── site/                # Hugo site source
│   ├── content/         # Pages (Markdown)
│   ├── layouts/         # Templates and partials
│   ├── static/          # Static assets (figures, CSS, downloads)
│   └── data/            # Living review database (JSON, CSV, etc.)
├── living_review/       # Python pipeline to fetch, classify, export papers
│   ├── fetchers.py      # Sources: arXiv, INSPIRE, HAL, OpenAlex, Crossref
│   ├── classifiers.py   # ML-based categorization
│   ├── exporters.py     # Export JSON/BibTeX/PDF for the site
│   └── pipeline.py      # End-to-end pipeline
└── README.md            # This file
```

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
The pipeline fetches papers and updates the JSON/exports:
```bash
cd living_review
python -m living_review.pipeline
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
Lead coordination: [Adnan Ghribi](https://github.com/aghribi) (CNRS–GANIL).  

---

## 🔖 License

This project is released under the **MIT License**.  
See [LICENSE](./LICENSE) for details.
