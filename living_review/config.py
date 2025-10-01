"""
config.py
=========

Central configuration module for the **Living Review** project.

This file collects all constants, keywords, category descriptions,
semantic queries, and thresholds used across the pipeline. Keeping them
centralized ensures consistency between different modules
(fetchers, classifier, pipeline, etc.).

Contents
--------
- Accelerator / ML keywords
- Negative keywords (to filter out noise domains)
- Reference semantic queries (used for similarity scoring)
- Category descriptions (used for classification)
- Default thresholds and constants (date window, API page sizes)

Typical Usage
-------------
>>> from living_review import config
>>> config.ACCEL_KEYWORDS[:5]
['accelerator', 'linac', 'synchrotron', 'collider', 'storage ring']
"""

# ---------------------------
# Accelerator / ML Keywords
# ---------------------------

ACCEL_KEYWORDS = [
    "accelerator", "linac", "synchrotron", "collider", "storage ring",
    "free electron laser", "RF cavity", "superconducting cavity", "cryomodule",
    "beamline", "undulator", "plasma wakefield acceleration", "luminosity", "beam optics",
    "BPM", "SRF", "injector", "beam loss", "emittance", "quench",
    "beam dynamics", "magnet", "dipole", "quadrupole", "sextupole",
    "octupole", "solenoid", "corrector", "chicane", "dogleg", "scraper",
    "collimator", "septum", "kicker", "booster", "decelerator", "target", "beam dump"
]

ML_KEYWORDS = [
    "machine learning", "deep learning", "neural network", "reinforcement learning",
    "bayesian optimization", "anomaly detection", "autoencoder", "GAN", "diffusion",
    "graph neural network", "surrogate", "physics-informed", "PINN", "transformer",
    "foundation model", "agentic AI", "autonomous agent", "LLM", "policy", "RL"
]

NEGATIVE_KEYWORDS = [
    "beam search", "electron beam lithography", "laser beam welding",
    "calorimeter", "jet", "particle detectors", "higgs", "dark matter",
    "cross-section", "jet tagging", "spectroscopy", "beta decay",
    "fine structure", "atomic levels"
]

# ---------------------------
# Semantic reference queries
# ---------------------------

REF_QUERY_ACCEL = (
    "particle accelerator, accelerator physics, beam dynamics, synchrotron, collider, "
    "linac, superconducting cavity, RF cavity, cryomodule, beamline, "
    "accelerator design, accelerator tuning, beam diagnostics, emittance, luminosity optimization, "
    "accelerator operation, accelerator maintenance, accelerator fault detection, accelerator reliability, accelerator control, "
    "beam optics, beam instrumentation, beam monitoring, beam feedback, beam loss, quench prevention, "
    "free electron laser, undulator, plasma wakefield acceleration, synchrotron radiation, light source, FEL, BPM, SRF, "
    "particle beam, charged particle, ion beam, electron beam, proton beam"
)

REF_QUERY_ML = (
    "machine learning, deep learning, reinforcement learning, surrogate model, anomaly detection, "
    "graph neural network, physics-informed neural network, foundation model, agentic AI, neural network, "
    "autoencoder, GAN, diffusion model, transformer, supervised learning, unsupervised learning, "
    "semi-supervised learning, classification, regression, clustering, dimensionality reduction, feature engineering, "
    "time series, forecasting, optimization, policy learning, LLM, large language model, "
    "causal inference, causality, interpretability, explainable AI, XAI, fault detection"
)

REF_QUERY_NOISE = (
    "cloud computing, workflow platform, Kubernetes, Docker, infrastructure, virtualization, "
    "particle detectors, calorimeter, jet tagging, Higgs, dark matter, spectroscopy, "
    "cross-section measurement, beta spectroscopy, atomic fine structure"
)

# ---------------------------
# Categories
# ---------------------------

CATEGORY_DESCRIPTIONS = {
    "Statistics & Trends": "Papers about statistical analysis, bibliometrics, and trends in AI/ML for accelerators",
    "Reviews": "Systematic review papers or surveys explicitly summarizing prior research results in accelerator physics and machine learning excluding software frameworks",
    "Optimization & Control": "Research on optimization algorithms, control systems, tuning, and feedback",
    "Anomaly Detection & Fault Prediction": "Papers on anomaly detection, fault prediction, and predictive maintenance",
    "Reinforcement Learning & Autonomous Systems": "Studies on reinforcement learning, autonomous agents, and self-driving accelerators",
    "Beamline Design & Simulation": "Research on accelerator design, simulation, and modeling",
    "Beam Dynamics": "Research on beam dynamics, instabilities, emittance, optics, and collective effects",
    "Operations & Control": "Papers on accelerator operations, automation, control systems, and stability feedback",
    "RF Systems": "Studies related to RF cavities, superconducting RF, klystrons, and linac RF systems",
    "Beam Diagnostics": "Research on beam diagnostics, beam position monitors, detectors, and instrumentation",
    "Surrogate Models": "Papers on surrogate modeling, reduced models, emulators, and digital twins for accelerators",
    "Novel Applications": "Novel or cross-disciplinary applications of AI/ML in accelerators and related sciences",
    "Data Management": "Research on data pipelines, data management, FAIR data, and feature stores for accelerator AI",
    "By Facility Type": "Papers categorized by specific accelerator facilities such as LHC, FCC, XFEL, SPIRAL2, synchrotron light sources",
    "Tools & Libraries": "Papers introducing or using open-source tools, toolkits, software frameworks, libraries, or packages for accelerator AI/ML",
    "Others": "Papers that do not fit clearly into the defined categories"
}

# ---------------------------
# Thresholds & constants
# ---------------------------

DATE_WINDOW_DAYS = 7
"""int: Default sliding window (in days) for fetching new papers."""

ARXIV_PAGE_SIZE = 100
"""int: Maximum number of results per page in arXiv API queries."""

DEFAULT_THRESHOLDS = {
    "accel": 0.13,
    "ml": 0.18
}
"""dict: Default semantic similarity thresholds for relevance filtering."""
