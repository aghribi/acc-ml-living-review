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
>>> from living_review.classifier import filter_relevant_papers, classify_papers
>>> papers = load_some_papers()
>>> relevant = filter_relevant_papers(papers)
>>> classify_papers(relevant)
"""

import re
from typing import List, Dict, Tuple
import torch
from sentence_transformers import SentenceTransformer, util

from .data_model import Paper
from .config import CATEGORY_DESCRIPTIONS, ACCEL_KEYWORDS, ML_KEYWORDS

# ---------------------------------------------------------------------
# Negative keywords (noise filter)
# ---------------------------------------------------------------------
NEGATIVE_KEYWORDS = [
    "beam search", "electron beam lithography", "laser beam welding",
    "calorimeter", "jet", "particle detectors", "higgs", "dark matter",
    "cross-section", "jet tagging", "spectroscopy", "beta decay",
    "fine structure", "atomic levels", "earthquake", "tsunami", "climate", 
    "weather", "natural disaster", "hardware acceleration", "gpu acceleration", 
    "cuda", "fpga", "embedded device", "structural assessment"
]

NEGATIVE_KEYWORDS += [
    "hardware accelerator", "cnn accelerator", "fpga", "vlsi", "asic", 
    "embedded system", "chip", "processor", "microcontroller", 
    "on-chip", "edge computing", "internet of things", "iot", 
    "soc", "gpu", "hardware trojan", "secure hardware", "neural engine"
]


# ---------------------------------------------------------------------
# Reference semantic queries
# ---------------------------------------------------------------------
REF_QUERY_ACCEL = (
    "particle accelerator, accelerator physics, beam dynamics, synchrotron, collider, linac, "
    "superconducting cavity, RF cavity, cryomodule, beamline, accelerator design, accelerator tuning, "
    "beam diagnostics, emittance, luminosity optimization, accelerator operation, accelerator maintenance, "
    "accelerator fault detection, accelerator reliability, accelerator control, beam optics, beam instrumentation, "
    "beam monitoring, beam feedback, beam loss, quench prevention, free electron laser, undulator, "
    "plasma wakefield acceleration, synchrotron radiation, light source, FEL, BPM, SRF, particle beam, "
    "charged particle, ion beam, electron beam, proton beam"
)
REF_QUERY_ML = (
    "machine learning, deep learning, reinforcement learning, surrogate model, anomaly detection, "
    "graph neural network, physics-informed neural network, foundation model, agentic AI, neural network, "
    "autoencoder, GAN, diffusion model, transformer, supervised learning, unsupervised learning, "
    "semi-supervised learning, classification, regression, clustering, dimensionality reduction, "
    "feature engineering, time series, forecasting, optimization, policy learning, LLM, large language model, "
    "causal inference, causality, interpretability, explainable AI, XAI, anomaly detection, fault detection"
)
REF_QUERY_NOISE = (
    "cloud computing, workflow platform, Kubernetes, Docker, infrastructure, virtualization, "
    "particle detectors, calorimeter, jet tagging, Higgs, dark matter, spectroscopy, "
    "cross-section measurement, beta spectroscopy, atomic fine structure,"
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


# ---------------------------------------------------------------------
# Pre-filtering: relevance
# ---------------------------------------------------------------------

def filter_relevant_papers(
    papers: List[Paper],
    accel_threshold: float = 0.13,
    ml_threshold: float = 0.18
) -> List[Paper]:
    """
    Filter a list of papers to retain only those relevant to both
    accelerator physics and machine learning, while excluding noisy
    domains (detectors, spectroscopy, HEP analysis, etc.).

    Parameters
    ----------
    papers : list of Paper
        Papers to filter. Each must expose `.title` and `.abstract`.
    accel_threshold : float, optional
        Minimum cosine similarity with the accelerator query (default=0.13).
    ml_threshold : float, optional
        Minimum cosine similarity with the ML query (default=0.18).

    Returns
    -------
    list of Paper
        Subset of input papers deemed relevant.
    """
    if not papers:
        return []
    texts = [f"{p.title}. {p.abstract}" for p in papers]
    scores_accel, scores_ml, scores_noise = dual_semantic_scores(texts)

    kept = []
    for p, sa, sm, sn in zip(papers, scores_accel, scores_ml, scores_noise):
        txt = f"{p.title} {p.abstract}".lower()
        if any(neg in txt for neg in NEGATIVE_KEYWORDS):
            continue
        if sa >= accel_threshold and sm >= ml_threshold and sa > sn:
            kept.append(p)
    return kept


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

    Should be applied **after** `filter_relevant_papers()`.

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

        # Keyword overrides
        if any(w in lowtxt for w in reviews_keywords):
            cats.append({"label": "Reviews", "score": 1.0})
        if "surrogate model" in lowtxt:
            cats.append({"label": "Surrogate Models", "score": 1.0})
        if any(w in lowtxt for w in ["framework", "tool", "library", "package", "geoff"]):
            cats.append({"label": "Tools & Libraries", "score": 1.0})

        # Deduplicate by highest score
        dedup = {}
        for c in cats:
            if c["label"] not in dedup or c["score"] > dedup[c["label"]]["score"]:
                dedup[c["label"]] = c
        cats = list(dedup.values())

        if not cats:
            cats = [{"label": "Others", "score": 0.0}]

        p.categories = cats
