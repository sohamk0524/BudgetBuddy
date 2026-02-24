"""
Google Cloud Storage service for BudgetBuddy statement files.
Replaces the raw_file LargeBinary column from the SQLite schema.
"""

import os
from google.cloud import storage

BUCKET_NAME = os.environ.get('GCS_BUCKET', 'budgetbuddy-statements')


def _get_bucket():
    client = storage.Client()
    return client.bucket(BUCKET_NAME)


def upload_statement(user_id: int, filename: str, file_content: bytes) -> str:
    """
    Upload a statement file to GCS.

    Returns the GCS object path (e.g. 'statements/42/bank_statement.pdf').
    """
    gcs_path = f"statements/{user_id}/{filename}"
    bucket = _get_bucket()
    blob = bucket.blob(gcs_path)
    blob.upload_from_string(file_content)
    return gcs_path


def download_statement(gcs_path: str) -> bytes:
    """Download a statement file from GCS and return its bytes."""
    bucket = _get_bucket()
    blob = bucket.blob(gcs_path)
    return blob.download_as_bytes()


def delete_statement(gcs_path: str):
    """Delete a statement file from GCS."""
    bucket = _get_bucket()
    blob = bucket.blob(gcs_path)
    blob.delete()
