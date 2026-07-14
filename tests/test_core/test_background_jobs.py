import pytest
from fastapi import HTTPException

from app.core.background_jobs import save_encrypted_lab_file
from app.core.privacy import EncryptionError


def test_save_encrypted_lab_file_maps_encryption_error():
    def _boom(*_args, **_kwargs):
        raise EncryptionError("ENCRYPTION_KEY is not configured")

    with pytest.raises(HTTPException) as exc:
        save_encrypted_lab_file(_boom)
    assert exc.value.status_code == 503
    assert "ENCRYPTION_KEY" in exc.value.detail