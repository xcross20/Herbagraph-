"""Background task dispatch with production-friendly HTTP errors."""

from __future__ import annotations

from celery import Celery
from fastapi import HTTPException, status

from app.core.privacy import EncryptionError


def save_encrypted_lab_file(save_fn, *args, **kwargs) -> str:
    """Wrap save_lab_file; map missing ENCRYPTION_KEY to 503."""
    try:
        return save_fn(*args, **kwargs)
    except EncryptionError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "File encryption is not configured. Set ENCRYPTION_KEY on Railway web and worker services. "
                "Generate one with: python scripts/generate_encryption_key.py"
            ),
        ) from exc


def dispatch_celery_task(task, *args, **kwargs):
    """Enqueue a Celery task; map broker/worker issues to 503."""
    try:
        return task.delay(*args, **kwargs)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"Background worker unavailable ({type(exc).__name__}). "
                "Add a Redis service, set REDIS_URL on web + worker, and deploy the Celery worker."
            ),
        ) from exc


def redis_reachable(celery_app: Celery, timeout: float = 2.0) -> bool:
    try:
        with celery_app.connection_or_acquire() as conn:
            conn.ensure_connection(max_retries=1, timeout=timeout)
        return True
    except Exception:
        return False