import pytest

from app.models.enums import LabResultStatus
from app.pipeline.biomarker_normalizer import (
    classify_lab_value,
    get_reference_data,
    normalize_biomarker_name,
    normalize_lab_result,
    normalize_lab_results,
)
from app.schemas.pipeline import ParsedLabResult

pytestmark = pytest.mark.unit


class TestAliasResolution:
    @pytest.mark.parametrize(
        "raw_name,expected",
        [
            ("CRP", "CRP"),
            ("hs-CRP", "CRP"),
            ("C-Reactive Protein", "CRP"),
            ("High Sensitivity CRP", "CRP"),
            ("Homocysteine", "Homocysteine"),
            ("HCY", "Homocysteine"),
            ("Homocyst(e)ine", "Homocysteine"),
            ("Glucose", "Glucose"),
            ("Fasting Glucose", "Glucose"),
            ("FBG", "Glucose"),
            ("Glucose, Serum", "Glucose"),
            ("HbA1c", "HbA1c"),
            ("Hemoglobin A1c", "HbA1c"),
            ("A1c", "HbA1c"),
            ("Glycated Hemoglobin", "HbA1c"),
            ("Insulin", "Insulin"),
            ("Fasting Insulin", "Insulin"),
            ("Uric Acid", "Uric Acid"),
            ("Urate", "Uric Acid"),
            ("LDL", "LDL"),
            ("LDL Cholesterol", "LDL"),
            ("LDL-C", "LDL"),
            ("Low Density Lipoprotein", "LDL"),
            ("HDL", "HDL"),
            ("HDL Cholesterol", "HDL"),
            ("HDL-C", "HDL"),
            ("Triglycerides", "Triglycerides"),
            ("Trig", "Triglycerides"),
            ("ALT", "ALT"),
            ("ALT (SGPT)", "ALT"),
            ("Alanine Aminotransferase", "ALT"),
            ("AST", "AST"),
            ("AST/SGOT", "AST"),
            ("Aspartate Aminotransferase", "AST"),
            ("Vitamin D", "Vitamin D"),
            ("Vitamin D, 25-Hydroxy", "Vitamin D"),
            ("25-OH Vitamin D", "Vitamin D"),
            ("Vit D", "Vitamin D"),
            ("TSH", "TSH"),
            ("Thyroid Stimulating Hormone", "TSH"),
            ("Thyrotropin", "TSH"),
            ("Vitamin B12", "B12"),
            ("B12", "B12"),
            ("Cobalamin", "B12"),
            ("Folate", "Folate"),
            ("Folic Acid", "Folate"),
            ("Serum Folate", "Folate"),
            ("Ferritin", "Ferritin"),
            ("Serum Ferritin", "Ferritin"),
            ("ApoB", "ApoB"),
            ("Apolipoprotein B", "ApoB"),
            ("GGT", "GGT"),
            ("Gamma Glutamyl Transferase", "GGT"),
            ("Creatinine", "Creatinine"),
            ("Serum Creatinine", "Creatinine"),
            ("eGFR", "eGFR"),
            ("GFR", "eGFR"),
            ("Estimated GFR", "eGFR"),
            ("Lp(a)", "Lp(a)"),
            ("Lipoprotein(a)", "Lp(a)"),
            ("Free T3", "Free T3"),
            ("FT3", "Free T3"),
            ("Free T4", "Free T4"),
            ("FT4", "Free T4"),
            ("Cortisol", "Cortisol"),
            ("AM Cortisol", "Cortisol"),
            ("DHEA-S", "DHEA-S"),
            ("DHEAS", "DHEA-S"),
        ],
    )
    def test_alias_resolves_to_canonical_name(self, raw_name, expected):
        assert normalize_biomarker_name(raw_name) == expected

    def test_alias_lookup_is_case_insensitive(self):
        assert normalize_biomarker_name("crp") == "CRP"
        assert normalize_biomarker_name("Crp") == "CRP"
        assert normalize_biomarker_name("CRP") == "CRP"

    def test_alias_lookup_ignores_surrounding_whitespace(self):
        assert normalize_biomarker_name("   CRP   ") == "CRP"

    def test_alias_lookup_collapses_punctuation(self):
        assert normalize_biomarker_name("C-Reactive Protein") == "CRP"
        assert normalize_biomarker_name("C.Reactive.Protein") == "CRP"

    def test_unrecognized_name_returns_none(self):
        assert normalize_biomarker_name("Some Totally Unknown Marker XYZ") is None

    def test_empty_string_returns_none(self):
        assert normalize_biomarker_name("") is None


class TestGetReferenceData:
    def test_known_biomarker_returns_data(self):
        data = get_reference_data("CRP")
        assert data is not None
        assert data["category"] == "inflammatory"

    def test_unknown_biomarker_returns_none(self):
        assert get_reference_data("Not A Real Biomarker") is None

    def test_catalog_has_200_plus_biomarkers(self):
        from app.knowledge_graph.biomarker_catalog import BIOMARKER_ENTRIES

        assert len(BIOMARKER_ENTRIES) >= 200

    def test_core_biomarkers_still_present(self):
        for name in ("CRP", "Glucose", "HbA1c", "LDL", "HDL", "TSH", "ALT", "Creatinine"):
            assert get_reference_data(name) is not None

    def test_magnesium_is_now_a_tracked_biomarker(self):
        assert get_reference_data("Magnesium") is not None

    @pytest.mark.parametrize(
        "name,category",
        [
            ("CRP", "inflammatory"),
            ("Homocysteine", "inflammatory"),
            ("Glucose", "metabolic"),
            ("HbA1c", "metabolic"),
            ("Insulin", "metabolic"),
            ("Uric Acid", "metabolic"),
            ("LDL", "lipid"),
            ("HDL", "lipid"),
            ("Triglycerides", "lipid"),
            ("ApoB", "lipid"),
            ("Lp(a)", "lipid"),
            ("ALT", "hepatic"),
            ("AST", "hepatic"),
            ("GGT", "hepatic"),
            ("Creatinine", "renal"),
            ("eGFR", "renal"),
            ("Vitamin D", "hormonal"),
            ("TSH", "hormonal"),
            ("Free T3", "hormonal"),
            ("Free T4", "hormonal"),
            ("Cortisol", "hormonal"),
            ("DHEA-S", "hormonal"),
            ("B12", "nutritional"),
            ("Folate", "nutritional"),
            ("Ferritin", "iron_metabolism"),
        ],
    )
    def test_category_assignment(self, name, category):
        assert get_reference_data(name)["category"] == category


class TestClassifyLabValueBoundaries:
    def test_value_at_critical_low_boundary_is_critical_low(self):
        # critical_low uses <=, so a value exactly at the threshold is critical.
        status = classify_lab_value(54.0, 70.0, 99.0, 70.0, 85.0, critical_low=54.0, critical_high=250.0)
        assert status == LabResultStatus.CRITICAL_LOW

    def test_value_just_below_critical_low_is_critical_low(self):
        status = classify_lab_value(53.9, 70.0, 99.0, 70.0, 85.0, critical_low=54.0, critical_high=250.0)
        assert status == LabResultStatus.CRITICAL_LOW

    def test_value_at_critical_high_boundary_is_critical_high(self):
        # critical_high uses >=, so a value exactly at the threshold is critical.
        status = classify_lab_value(250.0, 70.0, 99.0, 70.0, 85.0, critical_low=54.0, critical_high=250.0)
        assert status == LabResultStatus.CRITICAL_HIGH

    def test_value_just_above_reference_high_but_below_critical_is_high(self):
        status = classify_lab_value(249.0, 70.0, 99.0, 70.0, 85.0, critical_low=54.0, critical_high=250.0)
        assert status == LabResultStatus.HIGH

    def test_value_at_reference_high_boundary_is_not_high(self):
        # reference_high uses strict >, so a value exactly at the boundary is not HIGH.
        status = classify_lab_value(99.0, 70.0, 99.0, 70.0, 85.0, critical_low=54.0, critical_high=250.0)
        assert status == LabResultStatus.NORMAL

    def test_value_at_reference_low_boundary_is_not_low(self):
        # reference_low uses strict <, so a value exactly at the boundary is not LOW.
        status = classify_lab_value(0.0, 0.0, 3.0, 0.0, 1.0, critical_low=None, critical_high=10.0)
        assert status == LabResultStatus.OPTIMAL  # 0.0 also falls within the optimal range

    def test_value_just_below_reference_low_is_low(self):
        status = classify_lab_value(55.0, 70.0, 99.0, 70.0, 85.0, critical_low=54.0, critical_high=250.0)
        assert status == LabResultStatus.LOW

    def test_value_at_optimal_low_boundary_is_optimal(self):
        status = classify_lab_value(70.0, 70.0, 99.0, 70.0, 85.0, critical_low=54.0, critical_high=250.0)
        assert status == LabResultStatus.OPTIMAL

    def test_value_at_optimal_high_boundary_is_optimal(self):
        status = classify_lab_value(85.0, 70.0, 99.0, 70.0, 85.0, critical_low=54.0, critical_high=250.0)
        assert status == LabResultStatus.OPTIMAL

    def test_value_between_optimal_high_and_reference_high_is_normal(self):
        status = classify_lab_value(86.0, 70.0, 99.0, 70.0, 85.0, critical_low=54.0, critical_high=250.0)
        assert status == LabResultStatus.NORMAL

    def test_no_optimal_range_given_falls_back_to_normal(self):
        status = classify_lab_value(50.0, 10.0, 100.0)
        assert status == LabResultStatus.NORMAL

    def test_no_reference_range_at_all_is_normal(self):
        status = classify_lab_value(50.0, None, None)
        assert status == LabResultStatus.NORMAL

    def test_critical_low_none_means_low_values_only_low_not_critical(self):
        status = classify_lab_value(-100.0, 0.0, 3.0, 0.0, 1.0, critical_low=None, critical_high=10.0)
        assert status == LabResultStatus.LOW

    def test_hdl_style_biomarker_with_no_critical_high(self):
        # HDL has critical_high=None, so very high values should just be HIGH, never CRITICAL_HIGH.
        status = classify_lab_value(1000.0, 40.0, 100.0, 60.0, 100.0, critical_low=20.0, critical_high=None)
        assert status == LabResultStatus.HIGH

    def test_hdl_style_biomarker_critical_low_boundary(self):
        status = classify_lab_value(20.0, 40.0, 100.0, 60.0, 100.0, critical_low=20.0, critical_high=None)
        assert status == LabResultStatus.CRITICAL_LOW


class TestNormalizeLabResult:
    def test_known_biomarker_uses_canonical_reference_data(self):
        parsed = ParsedLabResult(
            raw_test_name="hs-CRP", value=8.2, unit="mg/L",
            reference_range_low=0.0, reference_range_high=5.0,  # lab's own range, should be overridden
        )
        result = normalize_lab_result(parsed)
        assert result.biomarker_name == "CRP"
        assert result.raw_test_name == "hs-CRP"
        assert result.reference_range_low == 0.0
        assert result.reference_range_high == 5.0  # lab-provided range is preferred when present
        assert result.status == LabResultStatus.HIGH
        assert result.category == "inflammatory"

    def test_unrecognized_biomarker_falls_back_to_lab_reference_range(self):
        parsed = ParsedLabResult(
            raw_test_name="Some Weird Marker", value=50.0, unit="ng/mL",
            reference_range_low=10.0, reference_range_high=40.0,
        )
        result = normalize_lab_result(parsed)
        assert result.biomarker_name == "Some Weird Marker"
        assert result.reference_range_low == 10.0
        assert result.reference_range_high == 40.0
        assert result.status == LabResultStatus.HIGH
        assert result.category is None

    def test_unrecognized_biomarker_with_no_range_at_all_is_normal(self):
        parsed = ParsedLabResult(raw_test_name="Mystery Marker", value=5.0)
        result = normalize_lab_result(parsed)
        assert result.biomarker_name == "Mystery Marker"
        assert result.reference_range_low is None
        assert result.reference_range_high is None
        assert result.status == LabResultStatus.NORMAL
        assert result.category is None

    def test_optimal_value_for_known_biomarker(self):
        parsed = ParsedLabResult(raw_test_name="Glucose", value=80.0, unit="mg/dL")
        result = normalize_lab_result(parsed)
        assert result.biomarker_name == "Glucose"
        assert result.status == LabResultStatus.OPTIMAL

    def test_critical_value_for_known_biomarker(self):
        parsed = ParsedLabResult(raw_test_name="Glucose", value=40.0, unit="mg/dL")
        result = normalize_lab_result(parsed)
        assert result.status == LabResultStatus.CRITICAL_LOW


class TestNormalizeLabResults:
    def test_normalizes_a_list_of_parsed_results(self):
        parsed_list = [
            ParsedLabResult(raw_test_name="CRP", value=8.2, unit="mg/L"),
            ParsedLabResult(raw_test_name="Glucose", value=95.0, unit="mg/dL"),
            ParsedLabResult(raw_test_name="Unknown Marker", value=1.0),
        ]
        results = normalize_lab_results(parsed_list)
        assert len(results) == 3
        assert results[0].biomarker_name == "CRP"
        assert results[1].biomarker_name == "Glucose"
        assert results[2].biomarker_name == "Unknown Marker"

    def test_empty_list_returns_empty_list(self):
        assert normalize_lab_results([]) == []
