"""
Encryption service for securely storing Plaid access tokens.
Uses Fernet symmetric encryption (AES-128-CBC with HMAC-SHA256).
"""

import os
from cryptography.fernet import Fernet, InvalidToken


def _get_fernet() -> Fernet:
    """
    Get a Fernet instance using the key from environment variable.

    Raises:
        ValueError: If FERNET_KEY is not set or invalid.
    """
    key = os.environ.get("FERNET_KEY")
    if not key:
        raise ValueError("FERNET_KEY environment variable is not set")

    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as e:
        raise ValueError(f"Invalid FERNET_KEY: {e}")


def encrypt_token(plaintext: str) -> bytes:
    """
    Encrypt a plaintext token using Fernet encryption.

    Args:
        plaintext: The access token to encrypt.

    Returns:
        The encrypted token as bytes (suitable for storing in LargeBinary column).

    Raises:
        ValueError: If encryption fails or FERNET_KEY is not configured.
    """
    if not plaintext:
        raise ValueError("Cannot encrypt empty token")

    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode())


def decrypt_token(ciphertext: bytes) -> str:
    """
    Decrypt an encrypted token.

    Args:
        ciphertext: The encrypted token bytes from database.

    Returns:
        The decrypted plaintext access token.

    Raises:
        ValueError: If decryption fails, token is invalid, or FERNET_KEY is not configured.
    """
    if not ciphertext:
        raise ValueError("Cannot decrypt empty ciphertext")

    fernet = _get_fernet()
    try:
        return fernet.decrypt(ciphertext).decode()
    except InvalidToken:
        raise ValueError("Invalid or corrupted token - decryption failed")


def generate_key() -> str:
    """
    Generate a new Fernet encryption key.

    Use this to generate a key for the FERNET_KEY environment variable:
        python -c "from services.encryption_service import generate_key; print(generate_key())"

    Returns:
        A URL-safe base64-encoded 32-byte key as a string.
    """
    return Fernet.generate_key().decode()
