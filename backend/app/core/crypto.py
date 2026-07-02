"""RSA key management for encrypting the login password in transit.

Because the PoC runs over plain HTTP, the login password is protected with an
application-level RSA envelope: the frontend fetches the public key, encrypts
the password with RSA-OAEP (SHA-256) and sends the base64 ciphertext. The
backend decrypts it here with the in-memory private key.

Keys are generated once per process; restarting the backend rotates them, and
the frontend always fetches a fresh public key immediately before each login.
"""

from __future__ import annotations

import base64
from functools import lru_cache

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.exceptions.base import UnauthorizedError


class PasswordCipher:
    """Holds a process-local RSA keypair used to decrypt login passwords."""

    def __init__(self, key_size: int = 2048) -> None:
        self._private_key = rsa.generate_private_key(
            public_exponent=65537, key_size=key_size
        )

    def public_key_pem(self) -> str:
        """Return the PEM (SubjectPublicKeyInfo) public key for the frontend."""

        pem = self._private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return pem.decode("utf-8")

    def decrypt(self, ciphertext_b64: str) -> str:
        """Decrypt a base64 RSA-OAEP(SHA-256) ciphertext into a plaintext string."""

        try:
            ciphertext = base64.b64decode(ciphertext_b64)
            plaintext = self._private_key.decrypt(
                ciphertext,
                padding.OAEP(
                    mgf=padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                ),
            )
            return plaintext.decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - any failure means bad credentials
            raise UnauthorizedError("Could not decrypt credentials") from exc


@lru_cache
def get_password_cipher() -> PasswordCipher:
    """Return the process-wide password cipher singleton."""

    return PasswordCipher()
