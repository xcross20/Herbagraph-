import uuid

import pytest

from app.config import settings
from app.core.file_storage import (
    ALLOWED_EXTENSIONS,
    DB_STORAGE_PREFIX,
    LabFileSaveResult,
    delete_lab_file,
    load_lab_file,
    save_lab_file,
    uses_database_file_storage,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _use_tmp_upload_dir(tmp_path, monkeypatch):
    """Point settings.upload_dir at a per-test temp directory so nothing touches real disk state."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path))
    monkeypatch.delenv("RAILWAY_ENVIRONMENT", raising=False)
    monkeypatch.setattr(settings, "file_storage_backend", "disk")
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
        saved = save_lab_file(original, uuid.uuid4(), "report.pdf")
        assert load_lab_file(saved.encrypted_file_path) == original

    def test_roundtrip_with_text_file(self):
        original = b"CRP 8.20 mg/L (0.00-3.00)"
        saved = save_lab_file(original, uuid.uuid4(), "report.txt")
        assert load_lab_file(saved.encrypted_file_path) == original

    def test_encrypted_path_token_is_not_the_plain_path(self, tmp_path):
        lab_report_id = uuid.uuid4()
        saved = save_lab_file(b"contents", lab_report_id, "report.csv")
        expected_plain_path = str(tmp_path / f"{lab_report_id}.csv.enc")
        assert saved.encrypted_file_path != expected_plain_path
        assert str(tmp_path) not in saved.encrypted_file_path
        assert str(lab_report_id) not in saved.encrypted_file_path

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
        saved_a = save_lab_file(b"same content", uuid.uuid4(), "a.pdf")
        saved_b = save_lab_file(b"same content", uuid.uuid4(), "b.pdf")
        assert saved_a.encrypted_file_path != saved_b.encrypted_file_path


class TestDatabaseFileStorage:
    def test_database_backend_roundtrip_without_disk(self, monkeypatch):
        monkeypatch.setattr(settings, "file_storage_backend", "database")
        original = b"database-backed lab bytes"
        lab_report_id = uuid.uuid4()
        saved = save_lab_file(original, lab_report_id, "report.pdf")
        assert isinstance(saved, LabFileSaveResult)
        assert saved.encrypted_file_data is not None
        assert uses_database_file_storage()
        assert load_lab_file(saved.encrypted_file_path, saved.encrypted_file_data) == original

    def test_auto_backend_uses_database_on_railway(self, monkeypatch):
        monkeypatch.setattr(settings, "file_storage_backend", "auto")
        monkeypatch.setenv("RAILWAY_ENVIRONMENT", "production")
        assert uses_database_file_storage()


class TestDeleteLabFile:
    def test_delete_removes_the_file(self, tmp_path):
        lab_report_id = uuid.uuid4()
        saved = save_lab_file(b"to be deleted", lab_report_id, "report.jpg")
        on_disk_path = tmp_path / f"{lab_report_id}.jpg.enc"
        assert on_disk_path.exists()

        delete_lab_file(saved.encrypted_file_path)
        assert not on_disk_path.exists()

    def test_delete_is_idempotent_when_file_already_gone(self):
        saved = save_lab_file(b"data", uuid.uuid4(), "report.jpeg")
        delete_lab_file(saved.encrypted_file_path)
        delete_lab_file(saved.encrypted_file_path)

    def test_load_after_delete_raises(self):
        saved = save_lab_file(b"data", uuid.uuid4(), "report.txt")
        delete_lab_file(saved.encrypted_file_path)
        with pytest.raises(FileNotFoundError):
            load_lab_file(saved.encrypted_file_path)

    def test_delete_database_backend_is_noop(self, monkeypatch):
        monkeypatch.setattr(settings, "file_storage_backend", "database")
        saved = save_lab_file(b"data", uuid.uuid4(), "report.txt")
        delete_lab_file(saved.encrypted_file_path)
        assert load_lab_file(saved.encrypted_file_path, saved.encrypted_file_data) == b"data"