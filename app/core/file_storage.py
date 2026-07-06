import os
import pathlib
import uuid

from app.config import settings
from app.core.privacy import decrypt_bytes, decrypt_str, encrypt_bytes, encrypt_str

ALLOWED_EXTENSIONS = {".pdf", ".txt", ".csv", ".png", ".jpg", ".jpeg"}


def save_lab_file(file_bytes: bytes, lab_report_id: uuid.UUID, original_filename: str) -> str:
    """Encrypt and persist an uploaded lab file to disk; return the Fernet-encrypted path token."""
    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = pathlib.Path(original_filename).suffix.lower()
    plain_path = os.path.join(settings.upload_dir, f"{lab_report_id}{ext}.enc")
    with open(plain_path, "wb") as f:
        f.write(encrypt_bytes(file_bytes))
    return encrypt_str(plain_path)


def load_lab_file(encrypted_path_token: str) -> bytes:
    """Decrypt the path token, read the file from disk, and decrypt its contents."""
    plain_path = decrypt_str(encrypted_path_token)
    with open(plain_path, "rb") as f:
        return decrypt_bytes(f.read())


def delete_lab_file(encrypted_path_token: str) -> None:
    plain_path = decrypt_str(encrypted_path_token)
    if os.path.exists(plain_path):
        os.remove(plain_path)
