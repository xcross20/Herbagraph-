"""Test-type router tests."""

import pytest

from app.models.enums import LabResultStatus, RecommendationTree
from app.pipeline.pathway_mapper import map_pathways
from app.pipeline.test_type_router import route_recommendation_trees
from app.schemas.pipeline import NormalizedLabResult

pytestmark = pytest.mark.unit


def _h_pylori_lab():
    return NormalizedLabResult(
        biomarker_name="H. pylori Urea Breath Test",
        raw_test_name="H. pylori Urea Breath Test",
        value=1.0,
        status=LabResultStatus.HIGH,
        category="infectious_disease",
        qualitative_label="DETECTED",
    )


def test_h_pylori_routes_etiological_primary():
    labs = [_h_pylori_lab()]
    pathways = map_pathways(labs)
    routing = route_recommendation_trees(labs, pathways)
    assert RecommendationTree.ETIOLOGICAL in routing.trees
    assert routing.primary_tree == RecommendationTree.ETIOLOGICAL
    assert "H. pylori Urea Breath Test" in routing.biomarkers_by_tree[RecommendationTree.ETIOLOGICAL]


def test_crp_routes_signaling_only():
    labs = [
        NormalizedLabResult(
            biomarker_name="CRP",
            raw_test_name="CRP",
            value=5.0,
            unit="mg/L",
            status=LabResultStatus.HIGH,
            category="inflammatory",
        )
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.SIGNALING
    assert RecommendationTree.ETIOLOGICAL not in routing.trees


def test_pancreatic_elastase_low_routes_nutritional_repletion():
    labs = [
        NormalizedLabResult(
            biomarker_name="Pancreatic Elastase",
            raw_test_name="Pancreatic Elastase",
            value=85.0,
            unit="ug/g",
            status=LabResultStatus.CRITICAL_LOW,
            category="gi_stool",
        )
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.NUTRITIONAL_REPLETION
    assert RecommendationTree.NUTRITIONAL_REPLETION in routing.trees
    assert "Pancreatic Elastase" in routing.biomarkers_by_tree[RecommendationTree.NUTRITIONAL_REPLETION]


def test_fecal_calprotectin_routes_etiological_primary():
    labs = [
        NormalizedLabResult(
            biomarker_name="Fecal Calprotectin",
            raw_test_name="Fecal Calprotectin",
            value=185.0,
            unit="ug/g",
            status=LabResultStatus.HIGH,
            category="gi_stool",
        )
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.ETIOLOGICAL
    assert RecommendationTree.ETIOLOGICAL in routing.trees
    assert "Fecal Calprotectin" in routing.biomarkers_by_tree[RecommendationTree.ETIOLOGICAL]


def test_fecal_lactoferrin_routes_etiological_primary():
    labs = [
        NormalizedLabResult(
            biomarker_name="Fecal Lactoferrin",
            raw_test_name="Fecal Lactoferrin",
            value=85.0,
            unit="ug/mL",
            status=LabResultStatus.CRITICAL_HIGH,
            category="gi_stool",
        )
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.ETIOLOGICAL
    assert RecommendationTree.ETIOLOGICAL in routing.trees
    assert "Fecal Lactoferrin" in routing.biomarkers_by_tree[RecommendationTree.ETIOLOGICAL]


def test_high_soluble_transferrin_receptor_routes_nutritional_repletion():
    labs = [
        NormalizedLabResult(
            biomarker_name="Soluble Transferrin Receptor",
            raw_test_name="Soluble Transferrin Receptor, Serum",
            value=2.5,
            unit="mg/L",
            status=LabResultStatus.HIGH,
            category="iron_metabolism",
        )
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.NUTRITIONAL_REPLETION
    assert "Soluble Transferrin Receptor" in routing.biomarkers_by_tree[RecommendationTree.NUTRITIONAL_REPLETION]


def test_low_prealbumin_routes_nutritional_repletion():
    labs = [
        NormalizedLabResult(
            biomarker_name="Prealbumin",
            raw_test_name="Prealbumin",
            value=12.0,
            unit="mg/dL",
            status=LabResultStatus.LOW,
            category="nutritional",
        )
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.NUTRITIONAL_REPLETION
    assert "Prealbumin" in routing.biomarkers_by_tree[RecommendationTree.NUTRITIONAL_REPLETION]


def test_high_homocysteine_in_mixed_inflammatory_panel_keeps_signaling_primary():
    labs = [
        NormalizedLabResult(
            biomarker_name="CRP",
            raw_test_name="CRP",
            value=8.2,
            unit="mg/L",
            status=LabResultStatus.HIGH,
            category="inflammatory",
        ),
        NormalizedLabResult(
            biomarker_name="Homocysteine",
            raw_test_name="Homocysteine",
            value=16.8,
            unit="umol/L",
            status=LabResultStatus.HIGH,
            category="inflammatory",
        ),
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.SIGNALING
    assert RecommendationTree.NUTRITIONAL_REPLETION not in routing.trees


def test_high_homocysteine_routes_nutritional_repletion():
    labs = [
        NormalizedLabResult(
            biomarker_name="Homocysteine",
            raw_test_name="Homocysteine",
            value=16.8,
            unit="umol/L",
            status=LabResultStatus.HIGH,
            category="inflammatory",
        )
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.NUTRITIONAL_REPLETION
    assert RecommendationTree.NUTRITIONAL_REPLETION in routing.trees
    assert "Homocysteine" in routing.biomarkers_by_tree[RecommendationTree.NUTRITIONAL_REPLETION]


def test_low_hemoglobin_routes_nutritional_repletion():
    labs = [
        NormalizedLabResult(
            biomarker_name="Hemoglobin",
            raw_test_name="Hemoglobin",
            value=10.5,
            unit="g/dL",
            status=LabResultStatus.LOW,
            category="cbc",
        )
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.NUTRITIONAL_REPLETION
    assert RecommendationTree.NUTRITIONAL_REPLETION in routing.trees
    assert "Hemoglobin" in routing.biomarkers_by_tree[RecommendationTree.NUTRITIONAL_REPLETION]


def test_high_uibc_routes_nutritional_repletion():
    labs = [
        NormalizedLabResult(
            biomarker_name="UIBC",
            raw_test_name="Unsaturated Iron Binding Capacity",
            value=400.0,
            unit="ug/dL",
            status=LabResultStatus.HIGH,
            category="iron_metabolism",
        )
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.NUTRITIONAL_REPLETION
    assert RecommendationTree.NUTRITIONAL_REPLETION in routing.trees
    assert "UIBC" in routing.biomarkers_by_tree[RecommendationTree.NUTRITIONAL_REPLETION]


def test_high_tibc_routes_nutritional_repletion():
    labs = [
        NormalizedLabResult(
            biomarker_name="TIBC",
            raw_test_name="Iron Binding Capacity",
            value=480.0,
            unit="ug/dL",
            status=LabResultStatus.HIGH,
            category="iron_metabolism",
        )
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.NUTRITIONAL_REPLETION
    assert RecommendationTree.NUTRITIONAL_REPLETION in routing.trees
    assert "TIBC" in routing.biomarkers_by_tree[RecommendationTree.NUTRITIONAL_REPLETION]


def test_high_methylmalonic_acid_routes_nutritional_repletion():
    labs = [
        NormalizedLabResult(
            biomarker_name="Methylmalonic Acid",
            raw_test_name="Methylmalonic Acid",
            value=450.0,
            unit="nmol/L",
            status=LabResultStatus.HIGH,
            category="nutritional",
        )
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.NUTRITIONAL_REPLETION
    assert RecommendationTree.NUTRITIONAL_REPLETION in routing.trees
    assert "Methylmalonic Acid" in routing.biomarkers_by_tree[RecommendationTree.NUTRITIONAL_REPLETION]


def test_celiac_ttg_routes_celiac_tree():
    labs = [
        NormalizedLabResult(
            biomarker_name="tTG IgA",
            raw_test_name="tTG IgA",
            value=1.0,
            status=LabResultStatus.HIGH,
            category="celiac_serology",
            qualitative_label="POSITIVE",
        )
    ]
    routing = route_recommendation_trees(labs, map_pathways(labs))
    assert routing.primary_tree == RecommendationTree.CELIAC