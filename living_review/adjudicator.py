"""
adjudicator.py
==============

Stage C of the relevance funnel: model-based adjudication of the gray zone.

Papers that neither auto-accept nor auto-reject in Stage B (gates.py) are
scored by a zero-shot NLI cross-encoder against the scope hypothesis from
SCOPE.md. Three-way outcome:

- score >= NLI_THRESHOLDS["accept"]  -> accepted
- score <= NLI_THRESHOLDS["reject"]  -> rejected
- otherwise                          -> pending (human review queue)

The adjudicator is a pluggable protocol so an instruct-LLM backend can be
added later (see TODO.md) without touching the funnel. Any failure inside
an adjudicator marks the batch `pending` rather than aborting the pipeline
run — papers are simply retried the next night.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Protocol

from .config import NLI_HYPOTHESIS, NLI_MODEL, NLI_MODEL_REVISION, NLI_THRESHOLDS
from .data_model import Paper


@dataclass
class AdjudicationResult:
    decision: str            # "accepted" | "rejected" | "pending"
    score: Optional[float]   # entailment score in [0, 1], None on error
    model: str
    revision: Optional[str]
    rule: Optional[str] = None  # e.g. "adjudicator_error"


class Adjudicator(Protocol):
    """Anything that can score papers against the SCOPE.md criterion."""

    def adjudicate(self, papers: List[Paper]) -> List[AdjudicationResult]:
        ...


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class NLIAdjudicator:
    """
    Zero-shot NLI cross-encoder adjudicator.

    Uses a HuggingFace `zero-shot-classification` pipeline with the pinned
    model/revision from config. The model is loaded lazily on first use and
    cached for the process lifetime.
    """

    def __init__(
        self,
        model: str = NLI_MODEL,
        revision: Optional[str] = NLI_MODEL_REVISION,
        thresholds: dict = None,
        hypothesis: str = NLI_HYPOTHESIS,
    ):
        self.model_name = model
        self.revision = revision
        self.thresholds = thresholds or dict(NLI_THRESHOLDS)
        self.hypothesis = hypothesis
        self._pipe = None

    def _load(self):
        if self._pipe is None:
            from transformers import pipeline

            from .classifier import device_str

            device = device_str()
            print(f"[info] Loading NLI model {self.model_name} on {device}")
            self._pipe = pipeline(
                "zero-shot-classification",
                model=self.model_name,
                revision=self.revision,
                device=device,
            )
        return self._pipe

    def score(self, papers: List[Paper]) -> List[float]:
        """Entailment scores in [0, 1] for each paper (title + abstract)."""
        pipe = self._load()
        texts = [f"{p.title or ''}. {p.abstract or ''}"[:3000] for p in papers]
        # hypothesis_template gets the single candidate label interpolated;
        # we pass the full scope hypothesis as the label.
        out = pipe(
            texts,
            candidate_labels=[self.hypothesis],
            hypothesis_template="{}",
            multi_label=True,
            batch_size=8,
        )
        if isinstance(out, dict):
            out = [out]
        return [r["scores"][0] for r in out]

    def adjudicate(self, papers: List[Paper]) -> List[AdjudicationResult]:
        if not papers:
            return []
        try:
            scores = self.score(papers)
        except Exception as e:
            print(f"[warn] NLI adjudication failed ({e}); marking batch pending")
            return [
                AdjudicationResult(
                    decision="pending",
                    score=None,
                    model=self.model_name,
                    revision=self.revision,
                    rule="adjudicator_error",
                )
                for _ in papers
            ]
        results = []
        for s in scores:
            if s >= self.thresholds["accept"]:
                decision = "accepted"
            elif s <= self.thresholds["reject"]:
                decision = "rejected"
            else:
                decision = "pending"
            results.append(
                AdjudicationResult(
                    decision=decision,
                    score=round(float(s), 4),
                    model=self.model_name,
                    revision=self.revision,
                )
            )
        return results


class LLMAdjudicator:
    """
    Instruct-LLM adjudicator applying the full SCOPE.md rubric.

    Deferred — see TODO.md. Kept here so the funnel interface is already
    shaped for it.
    """

    def adjudicate(self, papers: List[Paper]) -> List[AdjudicationResult]:
        raise NotImplementedError(
            "LLM adjudication is deferred; see TODO.md. Use NLIAdjudicator."
        )
