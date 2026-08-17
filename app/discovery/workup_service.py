"""Prior workup as a first-class object."""

from __future__ import annotations

import re

from app.discovery.mutations import WorkupMutation
from app.models.enums import DiscoveryWorkupResult


def workup_from_text(text: str) -> list[WorkupMutation]:
    blob = (text or "").lower()
    rows: list[WorkupMutation] = []
    if re.search(r"\bemg\b|nerve conduction|\bncs\b", blob):
        result = DiscoveryWorkupResult.PATIENT_REPORTED_NORMAL if "normal" in blob else DiscoveryWorkupResult.UNKNOWN_RESULT
        rows.append(WorkupMutation(raw_test_name="EMG/NCS", result_summary="patient reported", result_state=result.value))
    if re.search(r"\bmri\b", blob):
        result = DiscoveryWorkupResult.PATIENT_REPORTED_NORMAL if "normal" in blob else DiscoveryWorkupResult.UNKNOWN_RESULT
        rows.append(WorkupMutation(raw_test_name="MRI", result_summary="patient reported", result_state=result.value))
    if re.search(r"ultrasound|sonogram", blob):
        result = DiscoveryWorkupResult.PATIENT_REPORTED_NORMAL if "normal" in blob else DiscoveryWorkupResult.UNKNOWN_RESULT
        rows.append(WorkupMutation(raw_test_name="Ultrasound", result_summary="patient reported", result_state=result.value))
    return rows


def result_state_from_recollection(result: str) -> str:
    blob = (result or "").lower()
    if "abnormal" in blob:
        return DiscoveryWorkupResult.PATIENT_REPORTED_ABNORMAL.value
    if "normal" in blob:
        return DiscoveryWorkupResult.PATIENT_REPORTED_NORMAL.value
    return DiscoveryWorkupResult.UNKNOWN_RESULT.value
