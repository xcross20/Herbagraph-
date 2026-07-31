"""LLM-assisted lab parsing fallback tests."""

import json
from unittest.mock import patch

import pytest

from app.pipeline.lab_parser import parse_lab_file_with_llm_fallback
from app.pipeline.llm_lab_parser import parse_lab_text_with_llm, parse_llm_response
from app.schemas.pipeline import ParsedLabResult

pytestmark = pytest.mark.unit


def test_parse_llm_response_maps_rows():
    payload = {
        "results": [
            {
                "raw_test_name": "GLUCOSE",
                "value": 95,
                "unit": "mg/dL",
                "reference_range_low": 70,
                "reference_range_high": 99,
            },
            {
                "raw_test_name": "HELICOBACTER PYLORI, UREA BREATH TEST",
                "value": 1,
                "unit": "DETECTED",
                "reference_range_low": 0,
                "reference_range_high": 0,
                "qualitative_result": "DETECTED",
                "expected_result": "NOT DETECTED",
            },
        ]
    }
    rows = parse_llm_response(json.dumps(payload))
    assert len(rows) == 2
    assert rows[0].raw_test_name == "GLUCOSE"
    assert rows[1].qualitative_result == "DETECTED"


@patch("app.pipeline.llm_lab_parser.sync_chat_json_with_fallback")
def test_parse_lab_text_with_llm(mock_chat):
    mock_chat.return_value = (
        json.dumps(
            {
                "results": [
                    {
                        "raw_test_name": "CRP",
                        "value": 4.2,
                        "unit": "mg/L",
                        "reference_range_low": 0,
                        "reference_range_high": 3,
                    }
                ]
            }
        ),
        None,
    )

    rows = parse_lab_text_with_llm("Patient: [REDACTED]\nCRP result 4.2 mg/L (0-3)")
    assert len(rows) == 1
    assert rows[0].raw_test_name == "CRP"
    mock_chat.assert_called_once()


@patch("app.pipeline.llm_lab_parser.parse_lab_text_with_llm")
def test_parse_lab_file_with_llm_fallback_invokes_llm_when_regex_empty(mock_llm):
    mock_llm.return_value = [
        ParsedLabResult(
            raw_test_name="Glucose",
            value=102.0,
            unit="mg/dL",
            reference_range_low=70.0,
            reference_range_high=99.0,
        )
    ]
    messy = b"Some Lab Corp Report\nGlucose level was 102 mg/dL on 01/15/2026\nRef 70-99\n"
    rows = parse_lab_file_with_llm_fallback(messy, "report.txt")
    assert len(rows) == 1
    assert rows[0].raw_test_name == "Glucose"
    mock_llm.assert_called_once()


def test_parse_lab_file_with_llm_fallback_skips_llm_when_regex_succeeds():
    file_bytes = b"CRP    8.20  mg/L   (0.00-3.00)\n"
    with patch("app.pipeline.llm_lab_parser.parse_lab_text_with_llm") as mock_llm:
        rows = parse_lab_file_with_llm_fallback(file_bytes, "report.txt")
        assert len(rows) == 1
        assert rows[0].raw_test_name == "CRP"
        mock_llm.assert_not_called()