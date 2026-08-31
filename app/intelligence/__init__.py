"""app/intelligence — shared reasoning infrastructure.

HerbaGraph Reasoning Core. Phase 1: thin adapters around existing Discovery modules.
All engines are consumed by Discovery and will be consumed by Personal Evidence modules.

Architecture: docs/personal-evidence/REASONING_CORE_ARCHITECTURE.md

Import direction:
    app/intelligence/* → app/discovery.* (adapters)
    app/discovery/* → app/intelligence.* (after Phase 1 shim removal)
    app/personal_evidence/* → app/intelligence.* (future consumers)

Invariant: no module in app/intelligence/ may import from
app/personal_evidence/ or app/api/.
"""

from app.intelligence.identity import (
    ClaimTransferResult,
    assess_claim_transfer,
    available_forms,
    elemental_amount,
    form_code_for,
    forms_not_rankable_on_generic_effectiveness,
    identity_of,
    known_layers,
    layer_for,
    load_composition_graph,
    overlay_uses_existing_layers,
    parent_of,
    source_for,
    synonym_to_code,
)
from app.intelligence.measurements import (
    CoverageAssessment,
    CoverageRelation,
    assess_coverage,
    catalog_version,
    explain_coverage,
    test_known,
)
from app.intelligence.scientific_governance import (
    ScientificGovernanceResult,
    validate_scientific_output,
)

__all__ = [
    # identity
    "assess_claim_transfer",
    "ClaimTransferResult",
    "elemental_amount",
    "form_code_for",
    "forms_not_rankable_on_generic_effectiveness",
    "identity_of",
    "known_layers",
    "layer_for",
    "load_composition_graph",
    "overlay_uses_existing_layers",
    "parent_of",
    "source_for",
    "synonym_to_code",
    "available_forms",
    # measurements
    "CoverageAssessment",
    "CoverageRelation",
    "assess_coverage",
    "catalog_version",
    "explain_coverage",
    "test_known",
    # scientific governance
    "ScientificGovernanceResult",
    "validate_scientific_output",
]
