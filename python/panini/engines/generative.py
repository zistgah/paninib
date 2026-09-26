# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Generative sequence engine over the existing provider contract."""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..artifact_util import artifact_digest
from ..providers import GenerativeModelProvider, ModelCandidate, UnavailableGenerativeProvider
from .sequence import SequenceEngine


class GenerativeSequenceEngine:
    def __init__(self, provider: Optional[GenerativeModelProvider] = None) -> None:
        self.provider = provider or UnavailableGenerativeProvider()
        self.seq = SequenceEngine()

    def capabilities(self) -> Dict[str, Any]:
        return {"engine": "GenerativeSequenceEngine", "class": "ENGINE", "provider_available": bool(self.provider.available()), "scientific_model": False, "note": "does not silently substitute a language model as established biology"}

    def generate(self, constraint: Any) -> Optional[ModelCandidate]:
        if not self.provider.available():
            return None
        return self.provider.propose(constraint)

    def normalize(self, candidate: ModelCandidate) -> Dict[str, Any]:
        proposal = dict(candidate.proposal or {})
        edits = self.seq.normalize_edits(list(proposal.get("edits") or []))
        proposal["edits"] = [e.to_dict() for e in edits]
        return proposal

    def extract_sequence_intent(self, candidate: ModelCandidate) -> Dict[str, Any]:
        proposal = self.normalize(candidate)
        return {"assembly": proposal.get("assembly"), "reference": proposal.get("reference"), "edits": proposal.get("edits") or []}

    def score_metadata(self, candidate: ModelCandidate) -> Dict[str, Any]:
        return {"confidence": candidate.confidence, "status": candidate.status, "validation_status": candidate.validation_status, "assumptions": list(candidate.assumptions), "evidence": list(candidate.evidence)}

    def compare(self, a: ModelCandidate, b: ModelCandidate) -> Dict[str, Any]:
        return {"same_provider": a.provider == b.provider, "same_digest": a.to_dict().get("digest") == b.to_dict().get("digest"), "confidence_delta": float(a.confidence) - float(b.confidence)}

    def reject(self, candidate: ModelCandidate, reason: str) -> ModelCandidate:
        candidate.status = "REJECTED"
        candidate.validation_status = "REJECTED"
        candidate.assumptions = list(candidate.assumptions) + [f"rejected:{reason}"]
        return candidate

    def pipeline(self, constraint: Any) -> Dict[str, Any]:
        cand = self.generate(constraint)
        if cand is None:
            return {"status": "UNAVAILABLE", "candidate": None, "note": "provider unavailable; no sequence invented"}
        norm = self.normalize(cand)
        payload = {"status": "CANDIDATE", "candidate": cand.to_dict(), "normalized": norm, "sequence_intent": self.extract_sequence_intent(cand), "scores": self.score_metadata(cand), "provenance": cand.provenance}
        payload["digest"] = artifact_digest({"cid": cand.candidate_id, "norm": norm})
        return payload
