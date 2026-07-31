"""Seed MODULATES / TARGETS / INHIBITS graph edges for the canonical rec engine.

Sources
-------
1. Curated evidence claims (PMID-backed) → CLINICAL_HUMAN / OBSERVATIONAL edges
2. Catalog mechanism heuristics for interventions without claims → PREDICTED edges

Pathway and biomarker nodes are registered as canonical entities (HG-PATH-*, HG-BMK-*).
Idempotent: skips edges that already exist for the same (source, target, relationship).
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.knowledge_graph.entity_registry import (
    normalize_entity_name,
    register_entity,
)
from app.knowledge_graph.food_catalog import FOOD_INTERVENTIONS
from app.knowledge_graph.herb_catalog import HERB_INTERVENTIONS
from app.knowledge_graph.peptide_catalog import PEPTIDE_EVIDENCE_CLAIMS, PEPTIDE_INTERVENTIONS
from app.knowledge_graph.phytochemical_catalog import PHYTOCHEMICAL_COMPOUNDS
from app.knowledge_graph.seed_data import EVIDENCE_CLAIMS, INTERVENTIONS
from app.knowledge_graph.supplement_catalog import SUPPLEMENT_INTERVENTIONS
from app.knowledge_graph.tier_a_catalog import TIER_A_INTERVENTIONS
from app.knowledge_graph.tier_a_evidence import TIER_A_EVIDENCE_CLAIMS
from app.models.canonical_entity import CanonicalEntity, GraphEdge
from app.models.enums import (
    CanonicalEntityType,
    CoverageTier,
    EntityReviewStatus,
    GraphEvidenceType,
    GraphRelationshipType,
)
from app.pipeline.pathway_mapper import PATHWAY_DISPLAY_NAMES

# Mechanism text → pathway codes (heuristic for claim-less catalog rows)
_MECHANISM_PATHWAY_HINTS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"nf[-\s]?κ?b|nfkb|inflammatory|cox-?2|5-?lox|cytokine", re.I), "NF_KB"),
    (re.compile(r"il-?6|jak|stat3", re.I), "IL6_JAK_STAT3"),
    (re.compile(r"ampk|energy sensing|metabolic", re.I), "AMPK"),
    (re.compile(r"insulin|pi3k|akt|glycemic|glucose", re.I), "INSULIN_PI3K_AKT"),
    (re.compile(r"nrf2|antioxidant|glutathione|oxidative", re.I), "NRF2"),
    (re.compile(r"mtor|autophagy", re.I), "MTOR_AUTOPHAGY"),
    (re.compile(r"cortisol|hpa|stress|adaptogen", re.I), "HPA_AXIS"),
    (re.compile(r"thyroid|tsh|hpt", re.I), "THYROID_HPT"),
    (re.compile(r"lipid|ldl|cholesterol|hepatic fat|nafld", re.I), "HEPATIC_LIPID"),
    (re.compile(r"methyl|one-carbon|homocysteine|folate|b12|cobalamin", re.I), "ONE_CARBON_METHYLATION"),
    (re.compile(r"glp-?1|incretin", re.I), "GLP1_INCRETINS"),
    (re.compile(r"mitochondr|nad\+|coq10|coenzyme q", re.I), "MITOCHONDRIAL_NAD"),
    (re.compile(r"iron|hepcidin|ferritin|anemi", re.I), "IRON_HEPCIDIN"),
    (re.compile(r"uric|purine|gout", re.I), "PURINE_URIC_ACID"),
    (re.compile(r"vitamin d|vdr|25-?oh", re.I), "VITAMIN_D_RECEPTOR"),
    (re.compile(r"renal|kidney|egfr|creatinine", re.I), "RENAL_FILTRATION"),
    (re.compile(r"h\.?\s*pylori|gastric|ulcer|dyspepsia", re.I), "GASTRIC_COLONIZATION"),
    (re.compile(r"mucos|barrier|gut|intestin|ibd|ibs", re.I), "GI_MUCOSAL_BARRIER"),
    (re.compile(r"pathogen|antimicrobial|antibacterial|antiviral", re.I), "PATHOGEN_BURDEN"),
    (re.compile(r"biofilm", re.I), "BIOFILM_ADHESION"),
    (re.compile(r"ige|mast cell|allerg|histamine", re.I), "IGE_SENSITIZATION"),
    (re.compile(r"autoimmune|rheumat|joint", re.I), "AUTOIMMUNE_TARGETING"),
    (re.compile(r"celiac|gluten|antigen", re.I), "FOOD_ANTIGEN_EXPOSURE"),
    (re.compile(r"urinary|uti|bladder|mannose", re.I), "URINARY_PATHOGEN"),
    (re.compile(r"respiratory|lung|sputum|throat|cough", re.I), "RESPIRATORY_PATHOGEN"),
    (re.compile(r"hepatitis|viral liver|hepatotropic", re.I), "HEPATOTROPIC_VIRAL"),
    (re.compile(r"cyp|drug metabol|pgx|pharmacogen", re.I), "DRUG_METABOLISM_VARIANT"),
    (re.compile(r"nutrient|replet|deficien|mineral|vitamin", re.I), "NUTRIENT_DEFICIENCY"),
]

_CATEGORY_DEFAULT_PATHWAYS: dict[str, list[str]] = {
    "herb": ["NF_KB", "HPA_AXIS"],
    "phytochemical": ["NF_KB", "NRF2", "AMPK"],
    "supplement": ["NUTRIENT_DEFICIENCY", "AMPK"],
    "food": ["NRF2", "NUTRIENT_DEFICIENCY", "HEPATIC_LIPID"],
    "peptide": ["AMPK", "INSULIN_PI3K_AKT"],
    "medication": ["DRUG_METABOLISM_VARIANT"],
    "exercise": ["AMPK", "INSULIN_PI3K_AKT"],
    "sleep": ["HPA_AXIS"],
    "stress_reduction": ["HPA_AXIS"],
    "behavior": ["AMPK", "HPA_AXIS"],
}

_EVIDENCE_LEVEL_TO_GRAPH: dict[str, tuple[GraphEvidenceType, float]] = {
    "high": (GraphEvidenceType.META_ANALYTIC, 0.9),
    "moderate": (GraphEvidenceType.CLINICAL_HUMAN, 0.75),
    "low": (GraphEvidenceType.OBSERVATIONAL_HUMAN, 0.55),
    "preclinical": (GraphEvidenceType.PREDICTED, 0.35),
}


def _all_claims() -> list[dict]:
    return [*TIER_A_EVIDENCE_CLAIMS, *PEPTIDE_EVIDENCE_CLAIMS, *EVIDENCE_CLAIMS]


def _all_catalog_entries() -> list[dict]:
    return [
        *TIER_A_INTERVENTIONS,
        *PEPTIDE_INTERVENTIONS,
        *HERB_INTERVENTIONS,
        *SUPPLEMENT_INTERVENTIONS,
        *FOOD_INTERVENTIONS,
        *PHYTOCHEMICAL_COMPOUNDS,
        *INTERVENTIONS,
    ]


def pathways_from_mechanism(mechanism: str | None, category: str | None = None) -> list[str]:
    codes: list[str] = []
    text = mechanism or ""
    for pattern, code in _MECHANISM_PATHWAY_HINTS:
        if pattern.search(text) and code not in codes:
            codes.append(code)
    if not codes and category:
        for code in _CATEGORY_DEFAULT_PATHWAYS.get(category, ["NUTRIENT_DEFICIENCY"]):
            if code not in codes:
                codes.append(code)
    return codes[:4]


async def _ensure_pathway_entity(db: AsyncSession, pathway_code: str) -> CanonicalEntity:
    display = PATHWAY_DISPLAY_NAMES.get(pathway_code, pathway_code.replace("_", " ").title())
    return await register_entity(
        db,
        canonical_name=pathway_code,
        display_name=display,
        entity_type=CanonicalEntityType.PATHWAY,
        coverage_tier=CoverageTier.TIER_A,
        review_status=EntityReviewStatus.PRODUCTION_APPROVED,
        notes="Pathway node for graph recommendation engine",
    )


async def _ensure_biomarker_entity(db: AsyncSession, biomarker_name: str) -> CanonicalEntity:
    return await register_entity(
        db,
        canonical_name=biomarker_name,
        display_name=biomarker_name,
        entity_type=CanonicalEntityType.BIOMARKER,
        coverage_tier=CoverageTier.TIER_B,
        review_status=EntityReviewStatus.MACHINE_VERIFIED,
        notes="Biomarker node for TARGETS edges",
    )


async def _ensure_intervention_entity(
    db: AsyncSession,
    name: str,
    category: str | None = None,
) -> CanonicalEntity:
    from app.knowledge_graph.entity_registry import intervention_category_to_entity_type
    from app.models.enums import InterventionCategory

    entity_type = CanonicalEntityType.SUPPLEMENT
    if category:
        try:
            entity_type = intervention_category_to_entity_type(InterventionCategory(category))
        except ValueError:
            entity_type = CanonicalEntityType.SUPPLEMENT
    return await register_entity(
        db,
        canonical_name=name,
        display_name=name,
        entity_type=entity_type,
        coverage_tier=CoverageTier.TIER_B,
        review_status=EntityReviewStatus.MACHINE_GENERATED,
        notes="Registered during graph edge seed",
    )


async def _edge_exists(
    db: AsyncSession,
    source_id,
    target_id,
    relationship: str,
) -> bool:
    row = await db.execute(
        select(GraphEdge.id)
        .where(
            GraphEdge.source_entity_id == source_id,
            GraphEdge.target_entity_id == target_id,
            GraphEdge.relationship_type == relationship,
        )
        .limit(1)
    )
    return row.scalar_one_or_none() is not None


async def _add_edge(
    db: AsyncSession,
    *,
    source: CanonicalEntity,
    target: CanonicalEntity,
    relationship: GraphRelationshipType,
    evidence_type: GraphEvidenceType,
    confidence: float,
    citation: str | None,
    provenance: str,
    notes: str | None = None,
    direction: str | None = None,
    review_status: EntityReviewStatus = EntityReviewStatus.MACHINE_GENERATED,
) -> bool:
    if await _edge_exists(db, source.id, target.id, relationship.value):
        return False
    db.add(
        GraphEdge(
            source_entity_id=source.id,
            target_entity_id=target.id,
            relationship_type=relationship.value,
            direction=direction,
            evidence_type=evidence_type.value,
            citation=citation,
            confidence=confidence,
            review_status=review_status.value,
            source_provenance=provenance,
            notes=notes,
        )
    )
    return True


async def bootstrap_graph_modulation_edges(db: AsyncSession) -> dict[str, int]:
    """Seed pathway→intervention MODULATES and intervention→biomarker TARGETS edges."""
    stats = {
        "claims_processed": 0,
        "modulates_from_claims": 0,
        "targets_from_claims": 0,
        "modulates_from_catalog": 0,
        "pathways_registered": 0,
        "interventions_registered": 0,
        "edges_skipped": 0,
    }

    pathway_cache: dict[str, CanonicalEntity] = {}
    intervention_cache: dict[str, CanonicalEntity] = {}

    async def pathway(code: str) -> CanonicalEntity:
        if code not in pathway_cache:
            pathway_cache[code] = await _ensure_pathway_entity(db, code)
            stats["pathways_registered"] += 1
        return pathway_cache[code]

    async def intervention(name: str, category: str | None = None) -> CanonicalEntity:
        key = normalize_entity_name(name)
        if key not in intervention_cache:
            intervention_cache[key] = await _ensure_intervention_entity(db, name, category)
            stats["interventions_registered"] += 1
        return intervention_cache[key]

    # --- 1) Evidence claims → high-confidence edges ---
    claimed_interventions: set[str] = set()
    for claim in _all_claims():
        stats["claims_processed"] += 1
        name = claim.get("intervention_name")
        if not name:
            continue
        claimed_interventions.add(name)
        pathway_code = claim.get("pathway_code")
        pmid = str(claim.get("pmid") or "") or None
        level = claim.get("evidence_level", "low")
        ev_type, conf = _EVIDENCE_LEVEL_TO_GRAPH.get(level, (GraphEvidenceType.MECHANISTIC, 0.5))
        effect = (claim.get("effect") or "").lower()
        if effect == "decreases":
            rel = GraphRelationshipType.INHIBITS
            direction = "down"
        elif effect == "increases":
            rel = GraphRelationshipType.ACTIVATES
            direction = "up"
        else:
            rel = GraphRelationshipType.MODULATES
            direction = None

        interv = await intervention(name)
        if pathway_code:
            path_ent = await pathway(pathway_code)
            # Intervention modulates pathway (source=intervention, target=pathway)
            # and inverse: pathway is modulated by intervention for graph traversal both ways
            created = await _add_edge(
                db,
                source=interv,
                target=path_ent,
                relationship=rel,
                evidence_type=ev_type,
                confidence=conf,
                citation=f"PMID:{pmid}" if pmid else None,
                provenance="evidence_claim",
                notes=claim.get("summary"),
                direction=direction,
                review_status=EntityReviewStatus.PRODUCTION_APPROVED
                if level in ("high", "moderate")
                else EntityReviewStatus.MACHINE_VERIFIED,
            )
            if created:
                stats["modulates_from_claims"] += 1
            else:
                stats["edges_skipped"] += 1
            # Also store MODULATES edge pathway → intervention for rec engine lookup
            created2 = await _add_edge(
                db,
                source=path_ent,
                target=interv,
                relationship=GraphRelationshipType.MODULATES,
                evidence_type=ev_type,
                confidence=conf,
                citation=f"PMID:{pmid}" if pmid else None,
                provenance="evidence_claim_inverse",
                notes=f"Inverse: {claim.get('summary') or name}",
                direction=direction,
                review_status=EntityReviewStatus.PRODUCTION_APPROVED
                if level in ("high", "moderate")
                else EntityReviewStatus.MACHINE_VERIFIED,
            )
            if created2:
                stats["modulates_from_claims"] += 1

        biomarker = claim.get("biomarker_name")
        if biomarker:
            bmk = await _ensure_biomarker_entity(db, biomarker)
            created = await _add_edge(
                db,
                source=interv,
                target=bmk,
                relationship=GraphRelationshipType.TARGETS,
                evidence_type=ev_type,
                confidence=conf * 0.95,
                citation=f"PMID:{pmid}" if pmid else None,
                provenance="evidence_claim",
                notes=claim.get("summary"),
                direction=direction,
            )
            if created:
                stats["targets_from_claims"] += 1
            else:
                stats["edges_skipped"] += 1

    # --- 2) Catalog rows without claims → PREDICTED MODULATES ---
    seen_names: set[str] = set()
    for entry in _all_catalog_entries():
        name = entry.get("name")
        if not name or name in seen_names:
            continue
        seen_names.add(name)
        if name in claimed_interventions:
            continue
        category = entry.get("category") or "supplement"
        mechanism = entry.get("mechanism") or entry.get("description") or ""
        # Phytochemical compounds often put mechanism in description
        pathways = pathways_from_mechanism(mechanism, category)
        if not pathways:
            continue
        interv = await intervention(name, category)
        for code in pathways:
            path_ent = await pathway(code)
            created = await _add_edge(
                db,
                source=path_ent,
                target=interv,
                relationship=GraphRelationshipType.MODULATES,
                evidence_type=GraphEvidenceType.PREDICTED,
                confidence=0.32,
                citation=None,
                provenance="catalog_mechanism_heuristic",
                notes=f"Predicted from mechanism: {(mechanism or '')[:180]}",
                review_status=EntityReviewStatus.MACHINE_GENERATED,
            )
            if created:
                stats["modulates_from_catalog"] += 1
            else:
                stats["edges_skipped"] += 1
            # intervention → pathway as well
            await _add_edge(
                db,
                source=interv,
                target=path_ent,
                relationship=GraphRelationshipType.MODULATES,
                evidence_type=GraphEvidenceType.PREDICTED,
                confidence=0.32,
                citation=None,
                provenance="catalog_mechanism_heuristic",
                notes=f"Predicted: {name} ↔ {code}",
                review_status=EntityReviewStatus.MACHINE_GENERATED,
            )

        # Compound primary_target → TARGETS if present
        for compound in entry.get("compounds") or []:
            target_name = compound.get("primary_target")
            if not target_name:
                continue
            # Represent molecular targets as biomarker-like nodes for TARGETS edges
            target_ent = await register_entity(
                db,
                canonical_name=f"target:{target_name}",
                display_name=str(target_name),
                entity_type=CanonicalEntityType.COMPOUND,
                coverage_tier=CoverageTier.TIER_C,
                review_status=EntityReviewStatus.MACHINE_GENERATED,
                notes="Molecular target node from catalog",
            )
            await _add_edge(
                db,
                source=interv,
                target=target_ent,
                relationship=GraphRelationshipType.TARGETS,
                evidence_type=GraphEvidenceType.MECHANISTIC,
                confidence=0.4,
                citation=None,
                provenance="catalog_primary_target",
                notes=compound.get("role"),
            )

    await db.flush()
    await db.commit()
    return stats
