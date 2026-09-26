# Copyright © 1993–2026 Abhishek Choudhary. All rights reserved.
"""Tiny open deterministic validation fixture for v0.8 architecture tests.

Not a biological corpus. Dataset selection is deferred.
"""

from __future__ import annotations

from typing import Dict

from .knowledge import KnowledgeRecord, get_knowledge_registry


CASE_SOURCES: Dict[str, str] = {
    "case1_direct": """
organism synthetic {
    intent { use_part reporter_cassette }
    constraints { viability }
    verify { molecular }
}
""",
    "case2_user": """
organism synthetic {
    intent { establish marker }
    assertion {
        bind marker {
            assembly = "demo-v1"
            reference = chrDemo
            operation = REPLACE
            start = 0
            end = 4
            replacement = AAAA
            constrains = marker
        }
    }
    constraints { viability }
    verify { molecular }
}
""",
    "case3_association": """
organism synthetic {
    intent { establish glow_associated }
    constraints { viability }
    verify { molecular }
}
""",
    "case4_inverse": """
organism synthetic {
    intent { establish anti_glow { direction = gof } }
    constraints { viability }
    verify { molecular }
}
""",
    "case5_unavailable": """
organism synthetic {
    intent { establish unknown_marker }
    constraints { viability }
    verify { molecular }
}
""",
    "case6_generative": """
organism synthetic {
    intent { establish model_marker }
    constraints { viability }
    verify { molecular }
}
""",
    "case7_dependent": """
organism synthetic {
    intent {
        use_part reporter_cassette
        establish marker { depends_on = c001_use_part_reporter_cassette }
    }
    constraints { viability }
    verify { molecular }
}
""",
    "case8_conflict": """
organism synthetic {
    intent {
        use_part reporter_cassette { conflicts_with = c002_use_part_other_cassette }
        use_part other_cassette { conflicts_with = c001_use_part_reporter_cassette }
    }
    constraints { viability }
    verify { molecular }
}
""",
}


def seed_inverse_record() -> KnowledgeRecord:
    rec = KnowledgeRecord(
        canonical_id="realize:synthetic:anti_glow",
        namespace="fixture",
        name="anti_glow",
        kind="RealizationMapping",
        source="session",
        provenance="EVIDENCE",
        evidence_status="curated",
        attributes={
            "organism": "synthetic",
            "intent_verb": "establish",
            "intent_name": "anti_glow",
            "association_class": "CAUSALLY_SUPPORTED",
            "causal_basis": "EVIDENCE_BACKED",
            "validation_status": "EXPERIMENTALLY_SUPPORTED",
            "strategy": "KNOWLEDGE_PROVIDER",
            "direction": "lof",
            "licenses_inverse": False,
            "assembly": "demo-v1",
            "reference": "chrDemo",
            "edits": [{"operation": "DELETE", "start": 0, "end": 2, "replacement": ""}],
        },
    )
    get_knowledge_registry().add_record(rec)
    return rec


def seed_conflict_parts() -> None:
    get_knowledge_registry().add_record(KnowledgeRecord(
        canonical_id="realize:synthetic:other_cassette",
        namespace="fixture",
        name="other_cassette",
        kind="RealizationMapping",
        source="session",
        provenance="DESIGN",
        evidence_status="curated",
        attributes={
            "organism": "synthetic",
            "intent_verb": "use_part",
            "intent_name": "other_cassette",
            "association_class": "MECHANISTICALLY_SUPPORTED",
            "causal_basis": "STANDARD_PART",
            "validation_status": "NOT_VALIDATED",
            "strategy": "STANDARD_LIBRARY",
            "assembly": "demo-v1",
            "reference": "chrDemo",
            "edits": [{"operation": "REPLACE", "start": 4, "end": 8, "replacement": "CCCC"}],
        },
    ))
