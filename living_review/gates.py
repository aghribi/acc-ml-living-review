"""
gates.py
========

Stage B of the relevance funnel: deterministic accept/reject rules.

Papers arriving from the fetchers are first checked against cheap,
auditable rules before any model runs:

AUTO-ACCEPT
    - primary arXiv category is ``physics.acc-ph``; or
    - the venue matches the accelerator-venue whitelist (PRAB, JACoW
      conferences, NIM-A, ...) AND any ML keyword appears in title+abstract.

AUTO-REJECT (conjunctions only — never venue or domain alone; medical
accelerator papers such as proton-therapy beam delivery are in scope)
    - "accelerator/acceleration" appears only in compute-hardware context
      (DNN/FPGA/ASIC/...) AND the text has zero accelerator-system
      vocabulary hits; or
    - zero accelerator-system vocabulary AND a clear foreign-domain signal
      (education, civil engineering, medical imaging, finance, ...).

Everything else is GRAY and goes to the Stage C adjudicator. Papers with
empty abstracts that do not auto-accept are gray with rule
``empty_abstract`` — the funnel routes them straight to the pending queue
because title-only adjudication is not trusted (see SCOPE.md).

All patterns are word-boundary regexes (see config.py) — the previous
substring matching rejected any text containing "jet", "chip", or "soc".
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Pattern

from .config import (
    ACCEL_SYSTEM_VOCAB,
    DETECTOR_ANALYSIS_TERMS,
    FOREIGN_DOMAIN_TERMS,
    HARDWARE_CONTEXT_TERMS,
    MACHINE_SUBSYSTEM_VOCAB,
    ML_KEYWORDS,
    VENUE_WHITELIST_PATTERNS,
)
from .data_model import Paper

ACCEPT = "accept"
REJECT = "reject"
GRAY = "gray"


@dataclass
class GateResult:
    decision: str  # "accept" | "reject" | "gray"
    rule: str      # e.g. "auto_accept:acc-ph", "auto_reject:hw_accelerator_context"


def _compile(patterns: List[str]) -> List[Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


_VENUE_RE = _compile(VENUE_WHITELIST_PATTERNS)
_ACCEL_RE = _compile(ACCEL_SYSTEM_VOCAB)
_MACHINE_RE = _compile(MACHINE_SUBSYSTEM_VOCAB)
_DETECTOR_RE = _compile(DETECTOR_ANALYSIS_TERMS)
_HARDWARE_RE = _compile(HARDWARE_CONTEXT_TERMS)
_FOREIGN_RE = _compile(FOREIGN_DOMAIN_TERMS)
# ML keywords as word-boundary patterns, plural-tolerant ("RL"/"GAN" as
# substrings are as dangerous as "jet" was).
_ML_RE = _compile([r"\b" + re.escape(kw) + r"s?\b" for kw in ML_KEYWORDS])

_ACCELERATOR_WORD_RE = re.compile(r"\baccelerat(or|ors|ion|ing|e|ed|es)\b", re.IGNORECASE)


def _any(patterns: List[Pattern], text: str) -> bool:
    return any(p.search(text) for p in patterns)


def _count(patterns: List[Pattern], text: str) -> int:
    return sum(1 for p in patterns if p.search(text))


def venue_is_whitelisted(venue: Optional[str]) -> bool:
    """True if the venue matches the accelerator-venue whitelist."""
    return bool(venue) and _any(_VENUE_RE, venue)


def apply_gates(paper: Paper) -> GateResult:
    """
    Apply Stage B deterministic rules to one paper.

    Returns
    -------
    GateResult
        decision in {"accept", "reject", "gray"} plus the rule that fired.
    """
    text = f"{paper.title or ''} {paper.abstract or ''}"

    # ---- AUTO-ACCEPT ----
    if paper.arxiv_categories and paper.arxiv_categories[0] == "physics.acc-ph":
        return GateResult(ACCEPT, "auto_accept:acc-ph")

    has_ml = _any(_ML_RE, text)
    if venue_is_whitelisted(paper.venue) and has_ml:
        return GateResult(ACCEPT, "auto_accept:venue_whitelist")

    # ---- Signals for rejection rules ----
    accel_vocab_hits = _count(_ACCEL_RE, text)
    has_hardware = _any(_HARDWARE_RE, text)
    mentions_accelerator = bool(_ACCELERATOR_WORD_RE.search(text))

    # ---- AUTO-REJECT: DNN-hardware "accelerator" papers ----
    if mentions_accelerator and has_hardware and accel_vocab_hits == 0:
        return GateResult(REJECT, "auto_reject:hw_accelerator_context")

    # ---- AUTO-REJECT: clearly foreign domain, no beam/machine vocabulary ----
    if accel_vocab_hits == 0 and _any(_FOREIGN_RE, text):
        return GateResult(REJECT, "auto_reject:foreign_domain")

    # ---- Detector-analysis context: route to pending, not the NLI ----
    # ML on detector products at a collider (tracking, PID, triggers) is out
    # of scope but scores 0.92-0.99 with the NLI (the dominant false-positive
    # class in the 2026-07 model benchmark). Facility names alone don't make
    # it machine ML; genuine crossover papers carry machine-subsystem terms.
    if _any(_DETECTOR_RE, text) and not _any(_MACHINE_RE, text):
        return GateResult(GRAY, "detector_context")

    # ---- GRAY ----
    if not (paper.abstract or "").strip():
        return GateResult(GRAY, "empty_abstract")
    return GateResult(GRAY, "gray_zone")
