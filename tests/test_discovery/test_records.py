"""Document intake classifies reports. Labs stay on the existing upload path."""

from app.discovery.records import classify_document, extract_record_findings


def test_classifies_lab_files_away_from_discovery():
    assert classify_document("results.csv", "") == "lab"
    assert classify_document("report.txt", "Analyte Value Reference Range") == "lab"
    assert classify_document("panel.pdf", "Collected at LabCorp on 1/1/2024") == "lab"
    assert classify_document("quest.txt", "Quest Diagnostics final report") == "lab"


def test_classifies_emg_and_extracts_reported_normal():
    text = "Needle EMG and nerve conduction studies were normal in both legs."
    assert classify_document("emg-report.txt", text) == "emg"
    names = {item.name: item.value for item in extract_record_findings("emg", text)}
    assert names["emg testing"] == "reported_normal"
    assert names["emg_report"] == "attached"


def test_classifies_radiology_from_impression():
    text = "MRI lumbar spine. Impression: no acute process."
    assert classify_document("spine.txt", text) == "radiology"
    rows = extract_record_findings("radiology", text)
    assert rows[0].name == "radiology report"
    assert "impression" in rows[0].value.lower()


def test_classifies_clinical_note():
    text = "Follow up in clinic next week for ongoing distal burning."
    assert classify_document("note.txt", text) == "note"
    rows = extract_record_findings("note", text)
    assert rows[0].name == "clinical note"


def test_lab_kind_does_not_extract_findings():
    assert extract_record_findings("lab", "B12 210 pg/mL Reference Range 200-900") == []


def test_document_outcomes_are_explicit():
    from app.discovery.records import classify_document_outcome

    lab = classify_document_outcome("quest.txt", "Quest Diagnostics final report")
    assert lab.outcome == "routed_to_lab_engine"
    mri = classify_document_outcome("scan.txt", "I had an MRI. My feet still burn.")
    assert mri.outcome == "ambiguous"
    ocr = classify_document_outcome("page.pdf", "scanned image ocr required")
    assert ocr.outcome == "needs_ocr"
    valid = classify_document_outcome(
        "emg.pdf",
        "%PDF-1.7 Needle EMG and nerve conduction studies were normal.",
    )
    assert valid.kind == "emg"
    assert valid.outcome == "accepted"
    assert valid.checksum
