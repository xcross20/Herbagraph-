"""Ensure full biomarker catalog has pathway mapping coverage."""

import pytest

from app.knowledge_graph.biomarker_catalog import REFERENCE_DATA
from app.pipeline.pathway_mapper import _PATHWAY_CONFIGS, get_pathways_for_biomarker
from app.pipeline.user_biomarker_profile import resolve_canonical_name

pytestmark = pytest.mark.unit


def test_every_catalog_biomarker_has_pathway_rules():
    missing = [name for name in REFERENCE_DATA if not get_pathways_for_biomarker(name)]
    assert not missing, f"Biomarkers without pathway rules: {missing[:20]}"


def test_pathway_rule_count_covers_catalog():
    covered = {rule[0] for rule in _PATHWAY_CONFIGS}
    assert len(covered) == len(REFERENCE_DATA)


@pytest.mark.parametrize(
    "raw_name,canonical",
    [
        ("Mean Cell Hemoglobin (MCH)", "MCH"),
        ("Mean Cell Volume (MCV)", "MCV"),
        ("Red Cell Distribution Width (RDW)", "RDW"),
        ("White Blood Cell (WBC)", "WBC"),
        ("Red Blood Cell (RBC)", "RBC"),
        ("Neutrophil (absolute)", "Absolute Neutrophils"),
        ("Lymphocyte (absolute)", "Absolute Lymphocytes"),
    ],
)
def test_catalog_aliases_resolve(raw_name, canonical):
    assert resolve_canonical_name(raw_name) == canonical