from pathlib import Path

import pytest

from app.pipeline.lab_parser import parse_lab_file, parse_lab_line, parse_lab_text
from app.schemas.pipeline import ParsedLabResult

pytestmark = pytest.mark.unit


class TestParenthesizedRangePattern:
    """Pattern 1: Quest-style 'Name    value  unit   (low-high)'."""

    def test_basic_parenthesized_range(self):
        result = parse_lab_line("CRP    8.20  mg/L   (0.00-3.00)")
        assert result == ParsedLabResult(
            raw_test_name="CRP",
            value=8.2,
            unit="mg/L",
            reference_range_low=0.0,
            reference_range_high=3.0,
            raw_line="CRP    8.20  mg/L   (0.00-3.00)",
        )

    def test_multi_word_name(self):
        result = parse_lab_line("LDL Cholesterol Calc    130  mg/dL   (0-99)")
        assert result is not None
        assert result.raw_test_name == "LDL Cholesterol Calc"
        assert result.value == 130.0

    def test_range_joined_with_word_to(self):
        result = parse_lab_line("CRP    1.00  mg/L   (0.00 to 3.00)")
        assert result is not None
        assert result.reference_range_low == 0.0
        assert result.reference_range_high == 3.0

    def test_less_than_value_is_parsed(self):
        result = parse_lab_line("Ferritin     <5   ng/mL   (20.00-250.00)")
        assert result is not None
        assert result.value == 5.0

    def test_no_unit_still_matches(self):
        result = parse_lab_line("TSH    2.10   (0.40-4.00)")
        assert result is not None
        assert result.unit is None
        assert result.value == 2.1


class TestPlainRangePattern:
    """Pattern 2: LabCorp-style 'Name  value unit  [flag]  low-high'."""

    def test_basic_plain_range(self):
        result = parse_lab_line("Glucose   95  mg/dL  H  70-99")
        assert result == ParsedLabResult(
            raw_test_name="Glucose",
            value=95.0,
            unit="mg/dL",
            reference_range_low=70.0,
            reference_range_high=99.0,
            raw_line="Glucose   95  mg/dL  H  70-99",
        )

    def test_plain_range_without_flag(self):
        result = parse_lab_line("ALT   22  U/L  7-56")
        assert result is not None
        assert result.reference_range_low == 7.0
        assert result.reference_range_high == 56.0

    def test_plain_range_with_asterisk_flag(self):
        result = parse_lab_line("Insulin   5.2   uIU/mL   *   2.6-24.9")
        assert result is not None
        assert result.raw_test_name == "Insulin"
        assert result.value == 5.2

    def test_plain_range_with_low_flag(self):
        result = parse_lab_line("Magnesium   1.5  mg/dL  L  1.7-2.2")
        assert result is not None
        assert result.value == 1.5

    def test_single_space_separator_does_not_match(self):
        # Both range patterns require 2+ spaces after the test name.
        assert parse_lab_line("AST 18 U/L 10-40") is None


class TestPipeDelimitedPattern:
    """Pattern 3: 'Name | value | unit | low-high'."""

    def test_basic_pipe_delimited(self):
        result = parse_lab_line("Homocysteine | 12.5 | umol/L | 5-15")
        assert result == ParsedLabResult(
            raw_test_name="Homocysteine",
            value=12.5,
            unit="umol/L",
            reference_range_low=5.0,
            reference_range_high=15.0,
            raw_line="Homocysteine | 12.5 | umol/L | 5-15",
        )

    def test_pipe_delimited_with_empty_unit(self):
        result = parse_lab_line("B12 | 450 |  | 200-900")
        assert result is not None
        assert result.unit is None
        assert result.value == 450.0

    def test_pipe_delimited_no_spaces_around_pipes(self):
        result = parse_lab_line("Magnesium|1.9|mg/dL|1.7-2.2")
        assert result is not None
        assert result.raw_test_name == "Magnesium"
        assert result.value == 1.9


class TestQuestReferenceRangePattern:
    """Pattern 5: Quest PDF 'Name value Reference Range: low-high unit'."""

    def test_quest_dash_range_with_unit(self):
        result = parse_lab_line("GLUCOSE 76 Reference Range: 65-99 mg/dL")
        assert result is not None
        assert result.raw_test_name == "GLUCOSE"
        assert result.value == 76.0
        assert result.reference_range_low == 65.0
        assert result.reference_range_high == 99.0
        assert result.unit == "mg/dL"

    def test_quest_greater_than_range(self):
        result = parse_lab_line("HDL CHOLESTEROL 56 Reference Range: >39 mg/dL")
        assert result is not None
        assert result.value == 56.0
        assert result.reference_range_low == 39.0

    def test_quest_less_than_range(self):
        result = parse_lab_line("LDL-CHOLESTEROL 57 Reference Range: <100 mg/dL (calc)")
        assert result is not None
        assert result.raw_test_name == "LDL-CHOLESTEROL"
        assert result.reference_range_high == 100.0
        assert result.unit == "mg/dL"

    def test_quest_tsh_with_reflex_in_name(self):
        result = parse_lab_line("TSH W/REFLEX TO FT4 0.55 Reference Range: 0.40-4.50 mIU/L")
        assert result is not None
        assert result.value == 0.55
        assert result.unit == "mIU/L"

    def test_quest_qualitative_line_skipped(self):
        assert parse_lab_line("GLUCOSE NEGATIVE Reference Range: NEGATIVE") is None

    def test_real_quest_fixture_parses_core_panel(self):
        fixture = (
            Path(__file__).resolve().parent.parent / "fixtures" / "quest_labreport_excerpt.txt"
        )
        if not fixture.exists():
            pytest.skip("quest fixture not present")
        text = fixture.read_text()
        results = parse_lab_text(text)
        names = {r.raw_test_name.upper() for r in results}
        assert "GLUCOSE" in names
        assert "CREATININE" in names
        assert "HDL CHOLESTEROL" in names
        assert "LDL-CHOLESTEROL" in names
        assert len(results) >= 10


class TestCsvPattern:
    """Pattern 4: 'Name,value,unit,low,high'."""

    def test_basic_csv(self):
        result = parse_lab_line("Vitamin D,28.4,ng/mL,30,100")
        assert result == ParsedLabResult(
            raw_test_name="Vitamin D",
            value=28.4,
            unit="ng/mL",
            reference_range_low=30.0,
            reference_range_high=100.0,
            raw_line="Vitamin D,28.4,ng/mL,30,100",
        )

    def test_csv_with_empty_unit_field(self):
        result = parse_lab_line("Folate,9.1,,2.7,17.0")
        assert result is not None
        assert result.unit is None
        assert result.value == 9.1


class TestNonMatchingLines:
    def test_empty_line_returns_none(self):
        assert parse_lab_line("") is None

    def test_whitespace_only_line_returns_none(self):
        assert parse_lab_line("   ") is None

    def test_prose_header_line_returns_none(self):
        assert parse_lab_line("This is just a header line with no numbers") is None

    def test_patient_name_line_returns_none(self):
        assert parse_lab_line("Patient Name: Jane Doe") is None

    def test_separator_dashes_returns_none(self):
        assert parse_lab_line("-----------------------") is None

    def test_lab_name_header_without_values_returns_none(self):
        assert parse_lab_line("Quest Diagnostics Laboratory Report") is None


class TestParseLabText:
    def test_multi_line_report_skips_headers_and_blank_lines(self):
        text = (
            "LAB REPORT - Quest Diagnostics\n"
            "Patient: John Doe\n"
            "DOB: 01/01/1980\n"
            "\n"
            "CRP    8.20  mg/L   (0.00-3.00)\n"
            "Glucose   95  mg/dL  H  70-99\n"
            "\n"
            "End of Report"
        )
        results = parse_lab_text(text)
        assert len(results) == 2
        assert results[0].raw_test_name == "CRP"
        assert results[0].value == 8.2
        assert results[1].raw_test_name == "Glucose"
        assert results[1].value == 95.0

    def test_empty_text_returns_empty_list(self):
        assert parse_lab_text("") == []

    def test_mixed_format_report(self):
        text = (
            "CRP    8.20  mg/L   (0.00-3.00)\n"
            "Homocysteine | 12.5 | umol/L | 5-15\n"
            "Vitamin D,28.4,ng/mL,30,100\n"
            "Glucose   95  mg/dL  H  70-99\n"
        )
        results = parse_lab_text(text)
        names = [r.raw_test_name for r in results]
        assert names == ["CRP", "Homocysteine", "Vitamin D", "Glucose"]


class TestParseLabFile:
    def test_txt_file_is_decoded_and_parsed(self):
        file_bytes = b"CRP    8.20  mg/L   (0.00-3.00)\nGlucose   95  mg/dL  H  70-99\n"
        results = parse_lab_file(file_bytes, "report.txt")
        assert len(results) == 2

    def test_csv_file_is_decoded_and_parsed(self):
        file_bytes = b"Vitamin D,28.4,ng/mL,30,100\n"
        results = parse_lab_file(file_bytes, "report.csv")
        assert len(results) == 1
        assert results[0].raw_test_name == "Vitamin D"

    def test_filename_case_insensitive_dispatch_for_pdf(self, monkeypatch):
        import app.pipeline.lab_parser as lab_parser_module

        monkeypatch.setattr(
            lab_parser_module, "extract_text_from_pdf", lambda file_bytes: "CRP    8.20  mg/L   (0.00-3.00)\n"
        )
        results = parse_lab_file(b"fake-pdf-bytes", "REPORT.PDF")
        assert len(results) == 1
        assert results[0].raw_test_name == "CRP"

    def test_non_utf8_bytes_are_replaced_not_raised(self):
        file_bytes = b"CRP    8.20  mg/L   (0.00-3.00)\n\xff\xfe garbage bytes\n"
        # Should not raise a UnicodeDecodeError; invalid bytes get replaced.
        results = parse_lab_file(file_bytes, "report.txt")
        assert any(r.raw_test_name == "CRP" for r in results)
