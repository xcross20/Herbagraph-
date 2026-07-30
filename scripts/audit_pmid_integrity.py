#!/usr/bin/env python3
"""Audit PMID ↔ intervention alignment for catalog evidence claims."""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.knowledge_graph.lifestyle_evidence import LIFESTYLE_EVIDENCE_CLAIMS
from app.knowledge_graph.peptide_catalog import PEPTIDE_EVIDENCE_CLAIMS
from app.knowledge_graph.tier_a_evidence import TIER_A_EVIDENCE_CLAIMS

EUTILS_SUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# Curated denylist: PMID cited for intervention but PubMed title is a known mismatch.
KNOWN_MISMATCHES: tuple[tuple[str, str], ...] = (
    ("19811613", "Berberine"),
    ("22052330", "NAC"),
    ("22332023", "Quercetin"),
    ("31082617", "Intermittent Fasting"),
    ("20181910", "Sprint Interval Training"),
    ("20181910", "Low-Volume HIIT"),
    ("19139357", "Bright Light Therapy (Morning)"),
    ("19139357", "Morning Daylight Exposure"),
    ("29299576", "Sleep Hygiene Optimization"),
    ("8887515", "Tabata Protocol HIIT"),
    ("12415774", "Mastic Gum"),
    ("12633146", "Sertraline"),
    ("11719700", "Warfarin"),
    ("11788644", "DHEA Supplementation"),
    ("14518967", "Radon Mitigation"),
    ("10639537", "Atorvastatin"),
    ("29483066", "Caloric Restriction (25% Deficit)"),
    ("18539900", "Losartan"),
    ("16741042", "Omeprazole"),
    ("12069847", "Combined Oral Contraceptives"),
    ("20301728", "Hydrocortisone (Physiologic Replacement)"),
    ("15811834", "Mold Remediation (Professional)"),
    ("19578931", "Low-VOC Interior Environment"),
    ("29143705", "HIIT"),
    ("22796411", "Moderate Continuous Training"),
    ("25050941", "Resistance Training (Progressive Overload)"),
    ("24781874", "Yoga (Hatha, Structured Sessions)"),
    ("24781874", "Yoga Nidra (Guided Deep Relaxation)"),
    ("23419799", "Progressive Muscle Relaxation for Sleep"),
    ("23419799", "Progressive Muscle Relaxation (Jacobson)"),
    ("22281765", "Gluten Elimination Diet"),
    ("22471465", "5:2 Intermittent Fasting"),
    ("22536472", "Lisinopril"),
    ("24104941", "Low FODMAP Diet (3-Phase Monash)"),
    ("22874878", "Loving-Kindness Meditation (Metta)"),
    ("26054060", "Sleep Hygiene Optimization"),
    ("26054060", "Chronotherapy (Fixed Sleep-Wake Schedule)"),
    ("28605662", "Metformin"),
    ("28605662", "Insulin (Basal-Bolus Regimen)"),
    ("26001012", "Empagliflozin"),
    ("24251359", "Ezetimibe"),
    ("25231448", "Levothyroxine"),
    ("25231448", "Desiccated Thyroid (NDT)"),
    ("28135739", "Low-Dose Aspirin"),
    ("25491287", "4-7-8 Breathing for Sleep Onset"),
    ("25491287", "Box Breathing (4-4-4-4)"),
    ("25491287", "4-7-8 Breathing (Paced Relaxation)"),
    ("29222155", "HEPA Air Filtration"),
    ("29222155", "Indoor PM2.5 Reduction Protocol"),
    ("29606987", "GLP-1 Receptor Agonists (Class)"),
    ("29606987", "Semaglutide"),
    ("29744750", "Digital CBT-I (Sleepio/shleep)"),
    ("34758247", "GLP-1/GIP Dual Agonists (Class)"),
    ("34758247", "Tirzepatide"),
    ("35660750", "Tirzepatide"),
    ("17367341", "Exenatide"),
    ("26284720", "Dulaglutide"),
    ("20592281", "Tesamorelin"),
    ("30383229", "Bremelanotide"),
    ("15755489", "Thymosin Alpha-1"),
    ("30556385", "Collagen Peptides"),
    ("12970137", "AOD-9604"),
    ("20188091", "BPC-157"),
    ("15777684", "TB-500"),
    ("19156720", "Luteolin"),
    ("22436759", "Alpha Lipoic Acid"),
    ("25905401", "B12"),
    ("25905401", "Folate"),
    ("22363840", "Zinc"),
    ("23794341", "Sulforaphane"),
    ("26477902", "Anthocyanins"),
    ("24861000", "Resveratrol"),
    ("27055820", "Omega-3"),
    ("28829906", "Milk Thistle"),
    ("28829906", "Silymarin"),
    ("29202458", "NAD+ Precursors (NR/NMN)"),
    ("29480512", "Boswellia serrata"),
    ("30313004", "Iron"),
    ("30313004", "B12"),
    ("31068556", "Vitamin D"),
    ("22735274", "Omega-3"),
    ("31150318", "Curcumin"),
    ("31150318", "Turmeric"),
    ("32721537", "Berberine"),
    ("35681097", "Colostrum"),
    ("38013123", "NAC"),
    ("8962062", "DGL Licorice"),
    ("41356921", "EGCG"),
    ("31138798", "Nature Exposure (120 min/week)"),
    ("36126026", "Estradiol Hormone Therapy"),
    ("36126026", "Progesterone (Bioidentical)"),
    ("23587449", "Water Filtration (Carbon + RO)"),
)

# Intervention → title keywords (any match passes). Extend as aliases are discovered.
_INTERVENTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "NAC": ("nac", "acetylcysteine", "n-acetyl"),
    "Omega-3": ("omega", "fish oil", "epa", "dha"),
    "Intermittent Fasting": ("fasting", "intermittent", "time-restricted"),
    "5:2 Intermittent Fasting": ("fasting", "intermittent", "5:2"),
    "DGL Licorice": ("licorice", "deglycyrrhizinated", "dgl"),
    "CoQ10": ("coenzyme q", "coq10", "ubiquinone"),
    "Milk Thistle": ("silymarin", "milk thistle"),
    "EGCG": ("egcg", "green tea", "epigallocatechin"),
    "HIIT": ("high-intensity", "interval", "hiit"),
    "Norwegian 4×4 HIIT": ("interval", "vo2max", "high-intensity", "aerobic", "norwegian"),
    "Low-Volume HIIT": ("high-intensity", "interval", "hiit"),
    "Tabata Protocol HIIT": ("high-intensity", "intermittent", "interval", "tabata"),
    "Morning Daylight Exposure": ("bright", "light", "therapy", "daylight", "morning"),
    "Warfarin": ("warfarin", "anticoagulant", "stroke", "fibrillation"),
    "Sertraline": ("sertraline", "antidepressant", "ssri", "depressive"),
    "Thermal Comfort Optimization": ("body heating", "sleep", "bath", "shower", "thermal"),
    "GLP-1 Receptor Agonists (Class)": ("glp-1", "glp", "agonist", "cardiovascular"),
    "GLP-1/GIP Dual Agonists (Class)": ("glp-1", "gip", "tirzepatide", "dual"),
    "Progesterone (Bioidentical)": ("menopausal", "hormone", "therapy", "progesterone"),
    "DHEA Supplementation": ("dehydroepiandrosterone", "dhea", "adrenal", "androgen"),
    "HEPA Air Filtration": ("clean air", "indoor", "filtration", "hepa", "household"),
    "Indoor PM2.5 Reduction Protocol": ("clean air", "indoor", "particulate", "pm2.5", "household"),
    "Alpha Lipoic Acid": ("lipoic", "alpha-lipoic", "alpha lipoic"),
    "B12": ("b12", "vitamin b12", "cobalamin"),
    "Folate": ("folate", "folic"),
    "Zinc": ("zinc",),
    "Luteolin": ("luteolin",),
    "Semaglutide": ("semaglutide",),
    "Tirzepatide": ("tirzepatide",),
    "Exenatide": ("exenatide",),
    "Dulaglutide": ("dulaglutide",),
    "Tesamorelin": ("tesamorelin",),
    "Bremelanotide": ("bremelanotide",),
    "Thymosin Alpha-1": ("thymosin",),
    "Collagen Peptides": ("collagen",),
    "AOD-9604": ("aod", "9604"),
    "BPC-157": ("bpc", "pentadecapeptide"),
    "TB-500": ("thymosin", "beta-4", "beta 4", "tβ4"),
    "NAD+ Precursors (NR/NMN)": ("nicotinamide", "nad", "nmn", "riboside"),
    "Vitamin D": ("vitamin d", "vitamin", "25-hydroxy", "25-hydroxyvitamin"),
    "Iron": ("iron",),
    "Calcium": ("calcium",),
    "Potassium": ("potassium",),
    "Copper": ("copper",),
    "Selenium": ("selenium",),
    "Vitamin C": ("vitamin c", "ascorbic"),
    "Glutamine": ("glutamine",),
    "Vitamin B6": ("vitamin b6", "pyridoxine", "b6"),
    "Vitamin B1": ("vitamin b1", "thiamine", "thiamin", "b1"),
    "Vitamin B2": ("vitamin b2", "riboflavin", "b2"),
    "Vitamin A": ("vitamin a", "retinol"),
    "Vitamin E": ("vitamin e", "tocopherol"),
    "Vitamin K2": ("vitamin k", "k2", "menaquinone", "mk-7"),
    "Boswellia serrata": ("boswellia",),
    "Silymarin": ("silymarin",),
    "Turmeric": ("turmeric", "curcumin"),
    "Curcumin": ("curcumin", "turmeric"),
    "Berberine": ("berberine", "berberrubine"),
    "Allicin": ("allicin", "garlic", "allium"),
    "Anthocyanins": ("anthocyanin", "cherry", "berry"),
    "Pancreatin": ("pancreatin", "pancreatic", "exocrine pancreatic"),
    "Colostrum": ("colostrum",),
    "Lactoferrin": ("lactoferrin",),
    "Andrographis": ("andrographis", "andrographolide", "kalmegh"),
    "Rhodiola rosea": ("rhodiola", "rosavin", "salidroside"),
    "Olive Leaf": ("olive", "oleuropein", "olive leaf"),
    "Chamomile": ("chamomile", "matricaria", "chamomilla"),
    "Peppermint": ("peppermint", "mentha", "menthol"),
    "Holy Basil": ("holy basil", "ocimum", "tulsi", "sanctum"),
    "Slippery Elm": ("slippery elm", "ulmus", "mucilage"),
    "Goldenseal": ("goldenseal", "hydrastis", "berberine"),
    "Licorice Root": ("licorice", "liquorice", "glycyrrhiza", "glycyrrhizin"),
    "Mindfulness-Based Stress Reduction": ("mindfulness", "mbsr", "meditation", "stress"),
}


def _claims_with_pmids() -> list[dict]:
    claims: list[dict] = []
    for claim in [*TIER_A_EVIDENCE_CLAIMS, *LIFESTYLE_EVIDENCE_CLAIMS, *PEPTIDE_EVIDENCE_CLAIMS]:
        pmid = claim.get("pmid")
        intervention = claim.get("intervention_name")
        if pmid and intervention:
            claims.append(claim)
    return claims


def _title_keywords(intervention: str) -> tuple[str, ...]:
    if intervention in _INTERVENTION_KEYWORDS:
        return _INTERVENTION_KEYWORDS[intervention]
    tokens = re.findall(r"[a-z0-9]+", intervention.lower())
    distinctive = tuple(t for t in tokens if len(t) >= 4)
    if distinctive:
        return distinctive
    return (intervention.lower(),)


def _fetch_titles(pmids: list[str]) -> dict[str, str]:
    if not pmids:
        return {}
    titles: dict[str, str] = {}
    batch_size = 100
    for i in range(0, len(pmids), batch_size):
        batch = pmids[i : i + batch_size]
        url = f"{EUTILS_SUMMARY}?db=pubmed&id={','.join(batch)}&retmode=json"
        req = urllib.request.Request(url, headers={"User-Agent": "herbagraph-pmid-audit/1.0"})
        try:
            ctx = ssl.create_default_context()
            try:
                import certifi

                ctx.load_verify_locations(certifi.where())
            except ImportError:
                pass
            with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
                payload = json.load(resp)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"WARN: PubMed esummary fetch failed: {exc}")
            return titles
        result = payload.get("result", {})
        for uid in result.get("uids", []):
            if uid == "uids":
                continue
            entry = result.get(uid, {})
            titles[uid] = entry.get("title", "").lower()
    return titles


def main() -> int:
    strict = os.environ.get("HERBAGRAPH_PMID_AUDIT_STRICT", "0") == "1"
    claims = _claims_with_pmids()
    by_pmid: dict[str, list[dict]] = defaultdict(list)
    for claim in claims:
        by_pmid[str(claim["pmid"])].append(claim)

    failures: list[str] = []
    warnings: list[str] = []

    for pmid, intervention in KNOWN_MISMATCHES:
        for claim in by_pmid.get(pmid, []):
            if claim["intervention_name"] == intervention:
                failures.append(
                    f"KNOWN_MISMATCH pmid={pmid} intervention={intervention} "
                    f"biomarker={claim.get('biomarker_name')} pathway={claim.get('pathway_code')}"
                )

    unique_pmids = sorted(by_pmid)
    titles = _fetch_titles(unique_pmids) if strict else {}

    for pmid in unique_pmids:
        title = titles.get(pmid, "")
        if not title:
            continue
        for claim in by_pmid[pmid]:
            intervention = claim["intervention_name"]
            keywords = _title_keywords(intervention)
            if not any(kw in title for kw in keywords):
                warnings.append(
                    f"TITLE_MISMATCH pmid={pmid} intervention={intervention} "
                    f"title={title[:80]!r} keywords={keywords}"
                )

    print(f"Claims with PMIDs: {len(claims)}")
    print(f"Unique PMIDs: {len(unique_pmids)}")
    print(f"Mode: {'strict (title keywords)' if strict else 'denylist only (set HERBAGRAPH_PMID_AUDIT_STRICT=1 for full)'}")
    if strict:
        print(f"Titles fetched: {len(titles)}")

    if warnings:
        print(f"\nPMID title warnings: {len(warnings)}")
        for line in warnings[:20]:
            print(f"  - {line}")
        if len(warnings) > 20:
            print(f"  ... and {len(warnings) - 20} more")

    if failures:
        print(f"\nPMID integrity failures: {len(failures)}")
        for line in failures:
            print(f"  - {line}")
        return 1

    print("All mandatory PMID integrity checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())