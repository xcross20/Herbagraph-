import uuid

import pytest

from app.config import settings
from app.core.file_storage import (
    ALLOWED_EXTENSIONS,
    delete_lab_file,
    load_lab_file,
    save_lab_file,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _use_tmp_upload_dir(tmp_path, monkeypatch):
    """Point settings.upload_dir at a per-test temp directory so nothing touches real disk state."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    return tmp_path


class TestAllowedExtensions:
    def test_contains_expected_extensions(self):
        assert ALLOWED_EXTENSIONS == {".pdf", ".txt", ".csv", ".png", ".jpg", ".jpeg"}

    def test_docx_not_allowed(self):
        assert ".docx" not in ALLOWED_EXTENSIONS

    def test_exe_not_allowed(self):
        assert ".exe" not in ALLOWED_EXTENSIONS


class TestSaveAndLoadLabFile:
    def test_roundtrip_produces_original_bytes(self):
        original = b"raw lab report bytes \x00\x01\x02"
        token = save_lab_file(original, uuid.uuid4(), "report.pdf")
        assert load_lab_file(token) == original

    def test_roundtrip_with_text_file(self):
        original = b"CRP 8.20 mg/L (0.00-3.00)"
        token = save_lab_file(original, uuid.uuid4(), "report.txt")
        assert load_lab_file(token) == original

    def test_encrypted_path_token_is_not_the_plain_path(self, tmp_path):
        lab_report_id = uuid.uuid4()
        token = save_lab_file(b"contents", lab_report_id, "report.csv")
        expected_plain_path = str(tmp_path / f"{lab_report_id}.csv.enc")
        assert token != expected_plain_path
        assert str(tmp_path) not in token
        assert str(lab_report_id) not in token

    def test_file_is_written_to_disk_encrypted(self, tmp_path):
        lab_report_id = uuid.uuid4()
        original = b"plaintext lab content"
        save_lab_file(original, lab_report_id, "report.pdf")
        on_disk_path = tmp_path / f"{lab_report_id}.pdf.enc"
        assert on_disk_path.exists()
        raw_disk_bytes = on_disk_path.read_bytes()
        assert raw_disk_bytes != original

    def test_creates_upload_dir_if_missing(self, tmp_path, monkeypatch):
        nested_dir = tmp_path / "nested" / "uploads"
        monkeypatch.setattr(settings, "upload_dir", str(nested_dir))
        assert not nested_dir.exists()
        save_lab_file(b"data", uuid.uuid4(), "report.png")
        assert nested_dir.exists()

    def test_extension_is_preserved_lowercased(self, tmp_path):
        lab_report_id = uuid.uuid4()
        save_lab_file(b"data", lab_report_id, "REPORT.PDF")
        assert (tmp_path / f"{lab_report_id}.pdf.enc").exists()

    def test_different_saves_produce_different_tokens(self):
        token_a = save_lab_file(b"same content", uuid.uuid4(), "a.pdf")
        token_b = save_lab_file(b"same content", uuid.uuid4(), "b.pdf")
        assert token_a != token_b


class TestDeleteLabFile:
    def test_delete_removes_the_file(self, tmp_path):
        lab_report_id = uuid.uuid4()
        token = save_lab_file(b"to be deleted", lab_report_id, "report.jpg")
        on_disk_path = tmp_path / f"{lab_report_id}.jpg.enc"
        assert on_disk_path.exists()

        delete_lab_file(token)
        assert not on_disk_path.exists()

    def test_delete_is_idempotent_when_file_already_gone(self):
        token = save_lab_file(b"data", uuid.uuid4(), "report.jpeg")
        delete_lab_file(token)
        # Deleting again should not raise even though the file is already gone.
        delete_lab_file(token)

    def test_load_after_delete_raises(self):
        token = save_lab_file(b"data", uuid.uuid4(), "report.txt")
        delete_lab_file(token)
        with pytest.raises(FileNotFoundError):
            load_lab_file(token)
