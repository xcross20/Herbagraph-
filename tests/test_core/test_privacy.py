import pytest

from app.config import settings
from app.core.privacy import (
    EncryptionError,
    decrypt_bytes,
    decrypt_str,
    deidentify_payload,
    deidentify_text,
    encrypt_bytes,
    encrypt_str,
)

pytestmark = pytest.mark.unit


class TestDeidentifyTextRedaction:
    def test_patient_name_label_is_redacted(self):
        result = deidentify_text("Patient: John Smith presented with fatigue.")
        assert "John Smith" not in result
        assert "[REDACTED]" in result

    def test_name_label_is_redacted(self):
        result = deidentify_text("Name: Jane Q. Doe\nCRP was elevated.")
        assert "Jane" not in result
        assert "Doe" not in result

    def test_email_is_redacted(self):
        result = deidentify_text("Contact the patient at john.smith@example.com for follow-up.")
        assert "john.smith@example.com" not in result
        assert "[REDACTED]" in result

    def test_ssn_is_redacted(self):
        result = deidentify_text("SSN on file: 123-45-6789.")
        assert "123-45-6789" not in result

    def test_phone_number_is_redacted(self):
        result = deidentify_text("Call the patient back at (555) 123-4567 tomorrow.")
        assert "(555) 123-4567" not in result

    def test_plain_phone_number_is_redacted(self):
        result = deidentify_text("Reach at 555-123-4567 anytime.")
        assert "555-123-4567" not in result

    def test_mrn_is_redacted(self):
        result = deidentify_text("MRN: 4455667 shows history of hypertension.")
        assert "4455667" not in result

    def test_patient_id_is_redacted(self):
        result = deidentify_text("Patient ID: A1234B on record.")
        assert "A1234B" not in result

    def test_slash_date_is_redacted(self):
        result = deidentify_text("Collected on 01/15/1980 in the morning.")
        assert "01/15/1980" not in result

    def test_long_form_date_is_redacted(self):
        result = deidentify_text("Visit occurred on January 15, 1980 per chart notes.")
        assert "January 15, 1980" not in result

    def test_address_is_redacted(self):
        result = deidentify_text("Lives at 123 Main Street according to intake form.")
        assert "123 Main Street" not in result

    def test_zip_code_is_redacted(self):
        result = deidentify_text("Mailing zip 90210 on file.")
        assert "90210" not in result

    def test_empty_string_returns_empty(self):
        assert deidentify_text("") == ""

    def test_none_like_falsy_input_returned_as_is(self):
        assert deidentify_text(None) is None

    def test_clinical_content_with_parenthesized_range_is_preserved(self):
        line = "CRP    8.20  mg/L   (0.00-3.00)"
        assert deidentify_text(line) == line

    def test_clinical_content_with_plain_range_is_preserved(self):
        line = "Glucose   95  mg/dL  H  70-99"
        assert deidentify_text(line) == line

    def test_full_report_redacts_pii_but_keeps_lab_values(self):
        text = (
            "Patient: John Smith\n"
            "Email: john.smith@example.com\n"
            "SSN: 123-45-6789\n"
            "Phone: (555) 123-4567\n"
            "Address: 123 Main Street\n"
            "Zip: 90210\n"
            "\n"
            "CRP    8.20  mg/L   (0.00-3.00)\n"
            "Glucose   95  mg/dL  H  70-99\n"
        )
        result = deidentify_text(text)
        assert "John Smith" not in result
        assert "john.smith@example.com" not in result
        assert "123-45-6789" not in result
        assert "(555) 123-4567" not in result
        assert "123 Main Street" not in result
        assert "90210" not in result
        assert "CRP" in result
        assert "8.20" in result
        assert "Glucose" in result
        assert "95" in result


class TestDeidentifyPayload:
    def test_recurses_through_nested_dict(self):
        payload = {
            "notes": "Patient: John Smith has elevated CRP",
            "nested": {"contact": "john.smith@example.com"},
        }
        result = deidentify_payload(payload)
        assert "John Smith" not in result["notes"]
        assert "john.smith@example.com" not in result["nested"]["contact"]

    def test_recurses_through_lists(self):
        payload = {"lines": ["SSN: 123-45-6789", "CRP 8.20 mg/L"]}
        result = deidentify_payload(payload)
        assert "123-45-6789" not in result["lines"][0]
        assert result["lines"][1] == "CRP 8.20 mg/L"

    def test_non_string_leaf_values_are_left_untouched(self):
        payload = {"value": 8.2, "flag": True, "nothing": None}
        result = deidentify_payload(payload)
        assert result == payload

    def test_respects_deidentify_before_llm_flag_disabled(self, monkeypatch):
        monkeypatch.setattr(settings, "deidentify_before_llm", False)
        payload = {"notes": "Patient: John Smith"}
        result = deidentify_payload(payload)
        assert result == payload
        assert result["notes"] == "Patient: John Smith"

    def test_respects_deidentify_before_llm_flag_enabled(self, monkeypatch):
        monkeypatch.setattr(settings, "deidentify_before_llm", True)
        payload = {"notes": "Patient: John Smith"}
        result = deidentify_payload(payload)
        assert "John Smith" not in result["notes"]


class TestEncryptDecryptBytes:
    def test_roundtrip_returns_original_bytes(self):
        original = b"raw lab report file contents \x00\x01\x02"
        token = encrypt_bytes(original)
        assert token != original
        assert decrypt_bytes(token) == original

    def test_encrypting_same_bytes_twice_gives_different_tokens(self):
        original = b"same content"
        token_a = encrypt_bytes(original)
        token_b = encrypt_bytes(original)
        assert token_a != token_b

    def test_decrypting_garbage_raises_encryption_error(self):
        with pytest.raises(EncryptionError):
            decrypt_bytes(b"not-a-valid-fernet-token")

    def test_decrypting_tampered_token_raises_encryption_error(self):
        token = bytearray(encrypt_bytes(b"some payload"))
        token[-1] ^= 0xFF
        with pytest.raises(EncryptionError):
            decrypt_bytes(bytes(token))


class TestEncryptDecryptStr:
    def test_roundtrip_returns_original_string(self):
        original = "some clinical free text with unicode café"
        token = encrypt_str(original)
        assert token != original
        assert decrypt_str(token) == original

    def test_empty_string_roundtrip(self):
        token = encrypt_str("")
        assert decrypt_str(token) == ""

    def test_decrypting_garbage_string_raises_encryption_error(self):
        with pytest.raises(EncryptionError):
            decrypt_str("clearly-not-encrypted")


class TestMissingEncryptionKey:
    def test_encrypt_bytes_raises_when_key_missing(self, monkeypatch):
        monkeypatch.setattr(settings, "encryption_key", "")
        with pytest.raises(EncryptionError):
            encrypt_bytes(b"data")

    def test_decrypt_bytes_raises_when_key_missing(self, monkeypatch):
        monkeypatch.setattr(settings, "encryption_key", "")
        with pytest.raises(EncryptionError):
            decrypt_bytes(b"anything")

    def test_key_restored_after_test_allows_encryption_again(self):
        # Sanity check that monkeypatch reverted encryption_key from the prior tests.
        token = encrypt_bytes(b"works again")
        assert decrypt_bytes(token) == b"works again"
