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
    "fine structure", "atomic levels", "earthquake", "tsunami", "climate",
    "weather", "natural disaster", "hardware acceleration", "gpu acceleration",
    "cuda", "fpga", "embedded device", "structural assessment",
    "hardware accelerator", "cnn accelerator", "vlsi", "asic",
    "embedded system", "chip", "processor", "microcontroller",
    "on-chip", "edge computing", "internet of things", "iot",
    "soc", "gpu", "hardware trojan", "secure hardware", "neural engine"
]

# ---------------------------
# Stage B gate vocabularies (see gates.py)
# All matched as word-boundary regexes, never bare substrings.
# ---------------------------

VENUE_WHITELIST_PATTERNS = [
    r"phys\w*\.?\s*rev\w*\.?\s*accel\w*\.?\s*(and|&)?\s*beams",
    r"special\s*topics\W*accelerators\s*(and|&)\s*beams",
    r"\bPRAB\b",
    r"\bPR-?STAB\b",
    r"\bIPAC\b", r"\bLINAC\s*\d*\b", r"\bICALEPCS\b", r"\bNAPAC\b",
    r"\bHB\s?20\d\d\b", r"\bIBIC\b", r"\bFEL\s?20\d\d\b", r"\bJACoW\b",
    r"\bEPAC\b", r"\bPAC\s?[' ]?\d\d\b", r"\bCOOL\b", r"\bDIPAC\b",
    r"nucl(ear|\.?)\s*instrum(ents|\.?)\s*(and|&)?\s*methods.*\bA\b",
    r"\bNIM[- ]?A\b",
    r"journal of instrumentation", r"\bJINST\b",
]
"""Venues that publish accelerator work; whitelist-venue AND any ML keyword
auto-accepts (Stage B). Matching is case-insensitive regex on the venue string."""

ACCEL_SYSTEM_VOCAB = [
    r"particle accelerator", r"\blinacs?\b", r"\bcyclotrons?\b",
    r"\bsynchrotrons?\b", r"storage rings?", r"\bcolliders?\b",
    r"beam ?lines?", r"\bbeam\b", r"\bbeams\b",
    r"rf cavit(y|ies)", r"\bcavit(y|ies)\b", r"\bcryomodules?\b",
    r"\bklystrons?\b", r"\bundulators?\b", r"\bwigglers?\b",
    r"\bemittance\b", r"\bwakefields?\b", r"\bbetatron\b",
    r"\bquadrupoles?\b", r"\bsextupoles?\b", r"\bdipole magnets?\b",
    r"\bmagnets?\b", r"\bseptum\b", r"\bkickers?\b", r"\bcollimators?\b",
    r"\binjectors?\b", r"\bgantry\b", r"\bgantries\b",
    r"\bdosimetry\b", r"\bdosimetric\b", r"proton therapy", r"ion therapy",
    r"\bradiotherapy\b", r"\bBPMs?\b", r"beam position monitors?",
    r"free[- ]electron lasers?", r"\bFEL\b", r"light sources?",
    r"synchrotron radiation", r"\bSRF\b", r"\bLHC\b", r"\bCERN\b",
    r"\bFermilab\b", r"\bDESY\b", r"\bXFEL\b", r"\bSLAC\b", r"\bLCLS\b",
    r"\bGANIL\b", r"\bFRIB\b", r"\bCEBAF\b", r"\bJ-PARC\b", r"\bBNL\b",
    r"\bluminosity\b", r"beam dynamics", r"beam loss", r"beam halo",
    r"\bbunch(es)?\b", r"charged particles?",
]
"""Word-boundary patterns whose presence indicates the paper talks about an
accelerator/beam system at all. Zero hits is a necessary condition for
auto-rejection (never sufficient alone)."""

HARDWARE_CONTEXT_TERMS = [
    r"\bDNNs?\b", r"\bCNNs?\b", r"\binference engines?\b",
    r"\bFPGAs?\b", r"\bASICs?\b", r"\bVLSI\b", r"\bTPUs?\b", r"\bGPUs?\b",
    r"\bsystolic arrays?\b", r"\bquantization\b", r"\bRISC-V\b",
    r"edge (computing|devices?|AI)", r"\bin-memory computing\b",
    r"\bDRAM\b", r"\bSRAM\b", r"compute-in-memory", r"\bCIM\b",
    r"energy[- ]efficien(t|cy)", r"\bthroughput\b", r"\blow[- ]power\b",
    r"hardware[- ](accelerat\w+|architectures?|design)",
    r"neural network accelerat\w+", r"\bchip\b", r"\bSoCs?\b",
    r"\bmicrocontrollers?\b", r"\bembedded systems?\b",
]
"""Compute-hardware context. 'Accelerator' collocated only with these and
zero ACCEL_SYSTEM_VOCAB hits means a DNN-hardware paper (auto-reject)."""

FOREIGN_DOMAIN_TERMS = [
    r"\bearthquakes?\b", r"\btsunamis?\b", r"\bclassrooms?\b",
    r"\bcurricul(um|a)\b", r"\bstudents?\b", r"\bpedagog\w+\b",
    r"\be-?learning\b", r"learning outcomes?", r"\bteaching\b",
    r"\bcustomer churn\b", r"\bmarketing\b", r"\be-?commerce\b",
    r"\bblockchain\b", r"\bcryptocurrenc\w+\b",
    r"\bgenomes?\b", r"\bgenomic\w*\b", r"\bprotein\w*\b",
    r"\bcrops?\b", r"\bagricultur\w+\b", r"\blivestock\b",
    r"\bconcrete\b", r"\bmasonry\b", r"\bpavements?\b", r"\bgeotechnical\b",
    r"\brailways?\b", r"\btraffic\b", r"\bvehicles?\b", r"\bdrones?\b",
    r"\bUAVs?\b", r"\bwireless networks?\b", r"\bbeamforming\b",
    r"\bantennas?\b", r"\bradar\b", r"\b5G\b", r"\b6G\b",
    r"\btumou?rs?\b", r"\bcancer\b", r"\bpatients?\b", r"\bclinical\b",
    r"\bradiograph\w+\b", r"\bMRI\b", r"\bultrasound\b", r"\bdental\b",
    r"\bstock market\b", r"\bfinancial\b", r"\bsentiment analysis\b",
    r"\btokamaks?\b", r"\bstellarators?\b",
]
"""Clear foreign-domain signals. Auto-reject requires one of these AND zero
ACCEL_SYSTEM_VOCAB hits — a proton-therapy paper mentioning 'patients' and
'gantry' is protected by its accelerator vocabulary."""

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

FUZZY_TITLE_THRESHOLD = 0.93
"""float: similar_title score at or above which two id-disjoint records
are considered the same work (see dedup.py)."""

ARXIV_PAGE_SIZE = 100
"""int: Maximum number of results per page in arXiv API queries."""

NLI_MODEL = "MoritzLaurer/deberta-v3-base-zeroshot-v2.0"
"""str: Zero-shot NLI cross-encoder used by the Stage C adjudicator."""

NLI_MODEL_REVISION = None
"""str or None: Pinned HF revision hash for reproducibility (set after
first calibration; None = latest)."""

NLI_HYPOTHESIS = (
    "This paper applies machine learning or artificial intelligence "
    "to a particle accelerator, beamline, or particle beam."
)
"""str: Scope hypothesis, derived from SCOPE.md."""

NLI_THRESHOLDS = {
    "accept": 0.85,
    "reject": 0.25,
}
"""dict: Entailment-score cutoffs. score >= accept -> accepted;
score <= reject -> rejected; in between -> pending (human queue).
Placeholders until scripts/calibrate_thresholds.py runs (see docs)."""
