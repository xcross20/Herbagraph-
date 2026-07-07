"""OCR-garbled lab names should still resolve to catalog biomarkers."""

import pytest

from app.pipeline.user_biomarker_profile import resolve_canonical_name

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "raw,canonical",
    [
        ("emuloV lleC naeM (MCV)", "MCV"),
        ("nibolgomeH lleC naeM (MCH)", "MCH"),
        ("htdiW tsiD lleC deR (RDW)", "RDW"),
        ("Cell doolB deR (CBR)", "RBC"),
        ("nibolgomeH (HB/Hgb)", "Hemoglobin"),
        ("tircotameH (HCT)", "Hematocrit"),
    ],
)
def test_ocr_garbled_names_resolve(raw, canonical):
    assert resolve_canonical_name(raw) == canonical


@pytest.mark.parametrize(
    "raw,canonical",
    [
        ("CRP (calc)", "CRP"),
        ("LDL Cholesterol Calc", "LDL"),
        ("ldl chol calc", "LDL"),
        ("Mean Cell Volume (MCV) - quest", "MCV"),
    ],
)
def test_lab_portal_suffixes_still_resolve(raw, canonical):
    assert resolve_canonical_name(raw) == canonical


@pytest.mark.parametrize(
    "raw,canonical",
    [
        ("Iron, Total", "Iron"),
        ("Vitamin D, 25-OH", "Vitamin D"),
        ("Vit D 25-Hydroxy", "Vitamin D"),
        ("Vitamin B-12", "B12"),
        ("Folate (Folic Acid), Serum", "Folate"),
        ("Homocysteine, Plasma", "Homocysteine"),
        ("Methylmalonic Acid, Serum", "Methylmalonic Acid"),
        ("Zinc, Plasma", "Zinc"),
        ("Calcium, Total", "Calcium"),
        ("Potassium, Serum", "Potassium"),
        ("Copper, Serum", "Copper"),
        ("Selenium, Serum", "Selenium"),
        ("Magnesium, RBC", "Magnesium"),
        ("% Saturation", "Transferrin Saturation"),
        ("Iron Binding Capacity", "TIBC"),
        ("Unsaturated Iron Binding Capacity", "UIBC"),
        ("Vitamin A, Serum", "Vitamin A"),
        ("Vitamin E, Serum", "Vitamin E"),
        ("Vitamin K, Plasma", "Vitamin K"),
        ("Thiamine, Plasma", "Vitamin B1"),
        ("Riboflavin, Plasma", "Vitamin B2"),
        ("Pyridoxine, Plasma", "Vitamin B6"),
        ("Vitamin C, Plasma", "Vitamin C"),
        ("Prealbumin, Serum", "Prealbumin"),
    ],
)
def test_nutrient_portal_names_resolve(raw, canonical):
    assert resolve_canonical_name(raw) == canonical


def test_low_iron_portal_name_fires_nutrient_pathways():
    from app.pipeline.biomarker_normalizer import classify_lab_value, get_reference_data
    from app.pipeline.biological_systems import compute_biological_systems
    from app.pipeline.pathway_mapper import map_pathways
    from app.schemas.pipeline import NormalizedLabResult

    canonical = resolve_canonical_name("Iron, Total")
    assert canonical == "Iron"
    ref = get_reference_data("Iron")
    status = classify_lab_value(
        35,
        ref["reference_low"],
        ref["reference_high"],
        ref.get("optimal_low"),
        ref.get("optimal_high"),
        ref.get("critical_low"),
        ref.get("critical_high"),
    )
    lab = NormalizedLabResult(
        biomarker_name="Iron",
        raw_test_name="Iron, Total",
        value=35,
        unit="mcg/dL",
        reference_range_low=ref["reference_low"],
        reference_range_high=ref["reference_high"],
        status=status,
        category=ref["category"],
    )
    pathways = map_pathways([lab])
    codes = {p.pathway_code for p in pathways}
    assert "IRON_HEPCIDIN" in codes
    assert "NUTRIENT_DEFICIENCY" in codes
    nutrient = next(s for s in compute_biological_systems(pathways) if s["system_code"] == "nutrient_status")
    assert nutrient["signal_level"] >= 2


@pytest.mark.parametrize(
    "raw_name,canonical,value,unit",
    [
        ("Calcium, Total", "Calcium", 7.8, "mg/dL"),
        ("Potassium, Serum", "Potassium", 3.2, "mmol/L"),
    ],
)
def test_low_electrolyte_portal_names_fire_nutrient_pathways(raw_name, canonical, value, unit):
    from app.pipeline.biomarker_normalizer import classify_lab_value, get_reference_data
    from app.pipeline.pathway_mapper import map_pathways

    from app.schemas.pipeline import NormalizedLabResult

    assert resolve_canonical_name(raw_name) == canonical
    ref = get_reference_data(canonical)
    status = classify_lab_value(
        value,
        ref["reference_low"],
        ref["reference_high"],
        ref.get("optimal_low"),
        ref.get("optimal_high"),
        ref.get("critical_low"),
        ref.get("critical_high"),
    )
    lab = NormalizedLabResult(
        biomarker_name=canonical,
        raw_test_name=raw_name,
        value=value,
        unit=unit,
        reference_range_low=ref["reference_low"],
        reference_range_high=ref["reference_high"],
        status=status,
        category=ref["category"],
    )
    codes = {p.pathway_code for p in map_pathways([lab])}
    assert "NUTRIENT_DEFICIENCY" in codes


def test_low_transferrin_saturation_portal_name_fires_iron_pathway():
    from app.pipeline.biomarker_normalizer import classify_lab_value, get_reference_data
    from app.pipeline.pathway_mapper import map_pathways
    from app.schemas.pipeline import NormalizedLabResult

    raw_name = "% Saturation"
    canonical = "Transferrin Saturation"
    assert resolve_canonical_name(raw_name) == canonical
    ref = get_reference_data(canonical)
    status = classify_lab_value(
        12.0,
        ref["reference_low"],
        ref["reference_high"],
        ref.get("optimal_low"),
        ref.get("optimal_high"),
        ref.get("critical_low"),
        ref.get("critical_high"),
    )
    lab = NormalizedLabResult(
        biomarker_name=canonical,
        raw_test_name=raw_name,
        value=12.0,
        unit="%",
        reference_range_low=ref["reference_low"],
        reference_range_high=ref["reference_high"],
        status=status,
        category=ref["category"],
    )
    codes = {p.pathway_code for p in map_pathways([lab])}
    assert "IRON_HEPCIDIN" in codes