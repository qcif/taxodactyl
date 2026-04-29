"""Secret storage backends for persisting user-provided credentials.

Supports local encrypted file storage and Azure Key Vault.
Backend is selected based on the AZURE_BACKEND environment variable.
"""

import base64
import hashlib
import json
import logging
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from src.utils.config import Config

logger = logging.getLogger(__name__)
config = Config()

AZURE_BACKEND_ENV = 'AZURE_BACKEND'
SECRET_KEY_ENV = 'SECRET_KEY'
SECRETS_FILENAME = 'secrets.enc'


class VaultBackend(ABC):

    @abstractmethod
    def get(self, secret_name: str, user_email: str) -> str | None:
        ...

    @abstractmethod
    def put(self, secret_name: str, user_email: str, value: str) -> None:
        ...


class LocalVaultBackend(VaultBackend):
    """Encrypted JSON file storage backend."""

    def __init__(self, storage_dir: Path):
        self._path = storage_dir / SECRETS_FILENAME
        self._cipher = self._init_cipher()

    def _init_cipher(self) -> Fernet | None:
        key = os.environ.get(SECRET_KEY_ENV)
        if not key:
            logger.warning(
                f"Env var {SECRET_KEY_ENV!r} not set; "
                "local secrets will not be persisted."
            )
            return None
        key_bytes = base64.urlsafe_b64encode(
            hashlib.sha256(key.encode()).digest()
        )
        return Fernet(key_bytes)

    def _read(self) -> dict:
        if self._cipher is None or not self._path.exists():
            return {}
        try:
            data = self._cipher.decrypt(self._path.read_bytes())
            return json.loads(data)
        except (InvalidToken, json.JSONDecodeError, OSError):
            logger.warning("Failed to read local secrets file; ignoring.")
            return {}

    def _write(self, data: dict) -> None:
        if self._cipher is None:
            return
        try:
            self._path.write_bytes(
                self._cipher.encrypt(json.dumps(data).encode())
            )
        except OSError as e:
            logger.warning(f"Failed to write local secrets file: {e}")

    def get(self, secret_name: str, user_email: str) -> str | None:
        return self._read().get(f"{secret_name}:{user_email}")

    def put(self, secret_name: str, user_email: str, value: str) -> None:
        data = self._read()
        data[f"{secret_name}:{user_email}"] = value
        self._write(data)


class AzureVaultBackend(VaultBackend):
    """Azure Key Vault backend."""

    def __init__(self, kv_url: str):
        from azure.identity import DefaultAzureCredential
        from azure.keyvault.secrets import SecretClient
        credential = DefaultAzureCredential()
        self._client = SecretClient(vault_url=kv_url, credential=credential)

    @staticmethod
    def _key(secret_name: str, user_email: str) -> str:
        raw = f"{secret_name}-{user_email}"
        return re.sub(r'[^a-zA-Z0-9-]', '-', raw)

    def get(self, secret_name: str, user_email: str) -> str | None:
        key = self._key(secret_name, user_email)
        try:
            val = self._client.get_secret(key).value
            logger.debug(f"Azure Key Vault: retrieved secret {key!r}:"
                         f" {val[:4]}*****")
            return val
        except Exception as e:
            logger.debug(f"Azure Key Vault: secret {key!r} not found: {e}")
            return None

    def put(self, secret_name: str, user_email: str, value: str) -> None:
        key = self._key(secret_name, user_email)
        try:
            self._client.set_secret(key, value)
            logger.debug(f"Azure Key Vault: set secret {key!r}")
        except Exception as e:
            logger.warning(f"Azure Key Vault: failed to set {key!r}: {e}")


_vault: VaultBackend | None = None


def _create_backend() -> VaultBackend:
    if config.is_azure:
        return AzureVaultBackend(config.azure_key_vault_url)
    return LocalVaultBackend(config.user_tempdir)


def _get_vault() -> VaultBackend:
    global _vault
    if _vault is None:
        _vault = _create_backend()
    return _vault


def get(secret_name: str, user_email: str) -> str | None:
    """Retrieve a secret from the vault."""
    try:
        return _get_vault().get(secret_name, user_email)
    except Exception as e:
        logger.warning(f"Vault get failed: {e}")
        return None


def put(secret_name: str, user_email: str, value: str) -> None:
    """Store a secret in the vault."""
    try:
        _get_vault().put(secret_name, user_email, value)
    except Exception as e:
        logger.warning(f"Vault put failed: {e}")
