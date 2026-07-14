import os
import pathlib
import uuid
from dataclasses import dataclass

from app.config import settings
from app.core.privacy import decrypt_bytes, decrypt_str, encrypt_bytes, encrypt_str

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv", ".png", ".jpg", ".jpeg"}
DB_STORAGE_PREFIX = "db:"


@dataclass(frozen=True)
class LabFileSaveResult:
    encrypted_file_path: str
    encrypted_file_data: bytes | None = None


def uses_database_file_storage() -> bool:
    """Disk storage for local Docker; database on Railway (separate web + worker containers)."""
    backend = settings.file_storage_backend.lower()
    if backend == "auto":
        return bool(os.environ.get("RAILWAY_ENVIRONMENT"))
    return backend == "database"


def save_lab_file(file_bytes: bytes, lab_report_id: uuid.UUID, original_filename: str) -> LabFileSaveResult:
    """Encrypt and persist an uploaded lab file; return path token and optional DB blob."""
    if lab_report_id is None:
        raise ValueError("lab_report_id must be assigned before saving the uploaded file")

    encrypted_payload = encrypt_bytes(file_bytes)

    if uses_database_file_storage():
        token = encrypt_str(f"{DB_STORAGE_PREFIX}{lab_report_id}")
        return LabFileSaveResult(encrypted_file_path=token, encrypted_file_data=encrypted_payload)

    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = pathlib.Path(original_filename).suffix.lower()
    plain_path = os.path.join(settings.upload_dir, f"{lab_report_id}{ext}.enc")
    with open(plain_path, "wb") as f:
        f.write(encrypted_payload)
    return LabFileSaveResult(encrypted_file_path=encrypt_str(plain_path))


def load_lab_file(encrypted_path_token: str, encrypted_file_data: bytes | None = None) -> bytes:
    """Decrypt the path token and return original file bytes (disk or database backend)."""
    plain_ref = decrypt_str(encrypted_path_token)
    if plain_ref.startswith(DB_STORAGE_PREFIX):
        if not encrypted_file_data:
            raise FileNotFoundError(
                f"Lab file blob missing in database for {plain_ref.removeprefix(DB_STORAGE_PREFIX)}"
            )
        return decrypt_bytes(encrypted_file_data)

    with open(plain_ref, "rb") as f:
        return decrypt_bytes(f.read())


def delete_lab_file(encrypted_path_token: str) -> None:
    plain_ref = decrypt_str(encrypted_path_token)
    if plain_ref.startswith(DB_STORAGE_PREFIX):
        return
    if os.path.exists(plain_ref):
        os.remove(plain_ref)