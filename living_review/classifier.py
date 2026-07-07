"""
classifier.py
=============

This module provides semantic filtering and classification utilities for
scientific papers in the context of machine-learning applications to
particle accelerator physics.

It uses a pre-trained `sentence-transformers` model (MiniLM-L6-v2) to
compute embeddings for papers, accelerator/ML reference queries, and
category descriptions. Papers are first filtered for relevance
(accelerators ∧ ML, excluding domain noise), and then assigned to
categories using semantic similarity and keyword heuristics.

Key Features
------------
- Device selection (CPU/GPU/MPS) for embedding computation
- On-demand lazy loading of the semantic model
- Semantic relevance filtering using accelerator/ML/noise queries
- Category classification with thresholds, keyword overrides, and
  deduplication

Typical Usage
-------------
>>> from living_review.data_model import Paper
>>> from living_review.classifier import classify_papers
>>> papers = load_accepted_papers()   # relevance is decided by relevance.py
>>> classify_papers(papers)
"""

import re
from typing import List, Dict, Tuple
import torch
from sentence_transformers import SentenceTransformer, util

from .data_model import Paper
from .config import (
    CATEGORY_DESCRIPTIONS,
    ACCEL_KEYWORDS,
    ML_KEYWORDS,
    NEGATIVE_KEYWORDS,
    REF_QUERY_ACCEL,
    REF_QUERY_ML,
    REF_QUERY_NOISE,
)


# ---------------------------------------------------------------------
# Semantic model utils
# ---------------------------------------------------------------------

def device_str() -> str:
    """
    Select the most appropriate device for embedding computation.

    Returns
    -------
    str
        `"mps"` if Apple Metal backend is available,
        `"cuda"` if NVIDIA GPU CUDA backend is available,
        otherwise `"cpu"`.
    """
    if torch.backends.mps.is_available():
        return "mps"
    if torch.cuda.is_available():
        return "cuda"
    return "cpu"


SEM_MODEL = None
def load_sem_model() -> SentenceTransformer:
    """
    Lazy-load the sentence transformer model used for semantic similarity.

    Loads `all-MiniLM-L6-v2` from HuggingFace Hub on the first call and
    caches it globally. Subsequent calls return the cached model.

    Returns
    -------
    SentenceTransformer
        The loaded MiniLM model, bound to the appropriate device.
    """
    global SEM_MODEL
    if SEM_MODEL is None:
        dev = device_str()
        print(f"[info] Loading MiniLM on {dev}")
        SEM_MODEL = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2", device=dev)
    return SEM_MODEL


def dual_semantic_scores(texts: List[str]) -> Tuple[List[float], List[float], List[float]]:
    """
    Compute semantic relevance scores of input texts with respect to
    accelerator physics, machine learning, and noise queries.

    Parameters
    ----------
    texts : list of str
        List of textual inputs (title + abstract concatenated).

    Returns
    -------
    tuple of lists
        (scores_accel, scores_ml, scores_noise), each a list of floats
        aligned with the input order.
    """
    if not texts:
        return [], [], []
    model = load_sem_model()
    emb_accel = model.encode([REF_QUERY_ACCEL], convert_to_tensor=True)[0]
    emb_ml = model.encode([REF_QUERY_ML], convert_to_tensor=True)[0]
    emb_noise = model.encode([REF_QUERY_NOISE], convert_to_tensor=True)[0]
    emb_t = model.encode(texts, convert_to_tensor=True, batch_size=64)
    scores_accel = util.cos_sim(emb_accel, emb_t)[0].cpu().tolist()
    scores_ml = util.cos_sim(emb_ml, emb_t)[0].cpu().tolist()
    scores_noise = util.cos_sim(emb_noise, emb_t)[0].cpu().tolist()
    return scores_accel, scores_ml, scores_noise


# NOTE: the former cosine-threshold relevance filter
# (`filter_relevant_papers`, thresholds 0.13/0.18) was removed: measured on
# the deployed DB, the accelerator threshold rejected 0 of 576 papers. The
# relevance decision now lives in the staged funnel (gates.py +
# adjudicator.py, orchestrated by relevance.py). `dual_semantic_scores` is
# retained for ranking the pending queue and as an optional dedup
# tie-breaker only — it no longer gates anything.


# ---------------------------------------------------------------------
# Category classification
# ---------------------------------------------------------------------

def classify_papers(papers: List[Paper], threshold: float = 0.25, max_cats: int = 2) -> None:
    """
    Assign semantic categories to each paper.

    Uses a combination of:
    - semantic similarity with predefined category descriptions,
    - special handling for review papers,
    - keyword overrides (e.g. "surrogate model" → Surrogate Models).

    Should be applied only to papers accepted by the relevance funnel.

    Parameters
    ----------
    papers : list of Paper
        Papers to classify in-place (field `categories` updated).
    threshold : float, optional
        Minimum similarity required to assign a category (default=0.25).
    max_cats : int, optional
        Maximum number of categories to keep per paper (default=2).

    Returns
    -------
    None
        Papers are modified in place. Each `.categories` becomes a list
        of dicts with fields: `{"label": str, "score": float}`.

    Notes
    -----
    - If no category passes the thresholds, a default `Others` category
      with score 0.0 is assigned.
    - Deduplication ensures the highest score per label is kept.
    """
    if not papers:
        return
    model = load_sem_model()

    # Precompute category embeddings
    cat_texts = list(CATEGORY_DESCRIPTIONS.values())
    cat_labels = list(CATEGORY_DESCRIPTIONS.keys())
    emb_cats = model.encode(cat_texts, convert_to_tensor=True)

    # Batch encode papers
    texts = [f"{p.title}. {p.abstract}" for p in papers]
    emb_papers = model.encode(texts, convert_to_tensor=True, batch_size=64)
    sims_all = util.cos_sim(emb_papers, emb_cats).cpu().numpy()

    reviews_keywords = ["review", "survey", "state of the art"]

    for p, sims, text in zip(papers, sims_all, texts):
        lowtxt = text.lower()
        lowtitle = (p.title or "").lower()
        cats: List[Dict] = []

        for i, s in enumerate(sims):
            label = cat_labels[i]

            if label == "Reviews":
                if s >= 0.45 and any(w in lowtxt for w in reviews_keywords):
                    cats.append({"label": label, "score": float(s)})
                continue

            if label == "Novel Applications" and s < 0.30:
                continue

            if s >= threshold:
                cats.append({"label": label, "score": float(s)})

        # Keep top-k
        cats = sorted(cats, key=lambda c: c["score"], reverse=True)[:max_cats]

        # Keyword overrides: only when the keyword appears in the TITLE, and
        # never with a forced score of 1.0 (that labeled DNN-hardware surveys
        # "Reviews" with full confidence) — floor at 0.5 instead.
        def _override(label):
            cats.append({"label": label, "score": max(0.5, float(sims[cat_labels.index(label)]))})

        if any(w in lowtitle for w in reviews_keywords):
            _override("Reviews")
        if "surrogate model" in lowtitle:
            _override("Surrogate Models")
        if any(w in lowtitle for w in ["framework", "toolkit", "library", "package"]):
            _override("Tools & Libraries")

        # Deduplicate by highest score
        dedup = {}
        for c in cats:
            if c["label"] not in dedup or c["score"] > dedup[c["label"]]["score"]:
                dedup[c["label"]] = c
        cats = list(dedup.values())

        if not cats:
            cats = [{"label": "Others", "score": 0.0}]

        p.categories = cats
