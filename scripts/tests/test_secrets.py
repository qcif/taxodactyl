"""Unit tests for src.utils.secrets."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from src.utils.secrets import (
    AzureVaultBackend, LocalVaultBackend, NullVaultBackend, Vault,
)

SECRET_KEY = 'test-secret-key'
EMAIL = 'user@example.com'


def _make_local_backend(storage_dir: Path, secret_key=SECRET_KEY):
    with patch.dict(os.environ, {'SECRET_KEY': secret_key}):
        return LocalVaultBackend(storage_dir)


class TestLocalVaultBackend(unittest.TestCase):

    def setUp(self):
        self._tmpdir = TemporaryDirectory()
        self.storage_dir = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_get_returns_none_when_no_file(self):
        backend = _make_local_backend(self.storage_dir)
        self.assertIsNone(backend.get('MY_KEY', EMAIL))

    def test_put_and_get_roundtrip(self):
        backend = _make_local_backend(self.storage_dir)
        backend.put('MY_KEY', EMAIL, 'secret-value')
        self.assertEqual(backend.get('MY_KEY', EMAIL), 'secret-value')

    def test_get_returns_none_for_unknown_secret(self):
        backend = _make_local_backend(self.storage_dir)
        backend.put('MY_KEY', EMAIL, 'secret-value')
        self.assertIsNone(backend.get('OTHER_KEY', EMAIL))

    def test_get_returns_none_for_unknown_user(self):
        backend = _make_local_backend(self.storage_dir)
        backend.put('MY_KEY', EMAIL, 'secret-value')
        self.assertIsNone(backend.get('MY_KEY', 'other@example.com'))

    def test_put_overwrites_existing_value(self):
        backend = _make_local_backend(self.storage_dir)
        backend.put('MY_KEY', EMAIL, 'first')
        backend.put('MY_KEY', EMAIL, 'second')
        self.assertEqual(backend.get('MY_KEY', EMAIL), 'second')

    def test_multiple_secrets_coexist(self):
        backend = _make_local_backend(self.storage_dir)
        backend.put('KEY_A', EMAIL, 'value-a')
        backend.put('KEY_B', EMAIL, 'value-b')
        self.assertEqual(backend.get('KEY_A', EMAIL), 'value-a')
        self.assertEqual(backend.get('KEY_B', EMAIL), 'value-b')

    def test_multiple_users_coexist(self):
        backend = _make_local_backend(self.storage_dir)
        backend.put('MY_KEY', 'alice@example.com', 'alice-secret')
        backend.put('MY_KEY', 'bob@example.com', 'bob-secret')
        self.assertEqual(
            backend.get('MY_KEY', 'alice@example.com'), 'alice-secret')
        self.assertEqual(
            backend.get('MY_KEY', 'bob@example.com'), 'bob-secret')

    def test_file_is_encrypted(self):
        backend = _make_local_backend(self.storage_dir)
        backend.put('MY_KEY', EMAIL, 'plaintext-value')
        raw = backend._path.read_bytes()
        self.assertNotIn(b'plaintext-value', raw)

    def test_wrong_key_returns_none(self):
        backend_write = _make_local_backend(
            self.storage_dir, secret_key='key-a')
        backend_write.put('MY_KEY', EMAIL, 'value')
        backend_read = _make_local_backend(
            self.storage_dir, secret_key='key-b')
        self.assertIsNone(backend_read.get('MY_KEY', EMAIL))

    def test_cipher_is_none_without_secret_key(self):
        env = {k: v for k, v in os.environ.items() if k != 'SECRET_KEY'}
        with patch.dict(os.environ, env, clear=True):
            backend = LocalVaultBackend(self.storage_dir)
        self.assertIsNone(backend._cipher)

    def test_put_is_noop_without_secret_key(self):
        env = {k: v for k, v in os.environ.items() if k != 'SECRET_KEY'}
        with patch.dict(os.environ, env, clear=True):
            backend = LocalVaultBackend(self.storage_dir)
        backend.put('MY_KEY', EMAIL, 'value')
        self.assertFalse(backend._path.exists())

    def test_get_returns_none_without_secret_key(self):
        env = {k: v for k, v in os.environ.items() if k != 'SECRET_KEY'}
        with patch.dict(os.environ, env, clear=True):
            backend = LocalVaultBackend(self.storage_dir)
        self.assertIsNone(backend.get('MY_KEY', EMAIL))

    def test_corrupt_file_returns_none(self):
        backend = _make_local_backend(self.storage_dir)
        backend._path.write_bytes(b'not-valid-encrypted-data')
        self.assertIsNone(backend.get('MY_KEY', EMAIL))


class TestAzureVaultBackendKeyFormat(unittest.TestCase):

    def test_key_is_alphanumeric_and_hyphens_only(self):
        key = AzureVaultBackend._key('NCBI_API_KEY', 'user@example.com')
        self.assertRegex(key, r'^[a-zA-Z0-9-]+$')

    def test_key_excludes_colon(self):
        self.assertNotIn(':', AzureVaultBackend._key('K', 'u@e.com'))

    def test_key_excludes_at_sign(self):
        self.assertNotIn('@', AzureVaultBackend._key('K', 'u@e.com'))

    def test_key_excludes_dot(self):
        self.assertNotIn('.', AzureVaultBackend._key('K', 'u@e.com'))

    def test_key_excludes_underscore(self):
        self.assertNotIn('_', AzureVaultBackend._key('MY_KEY', EMAIL))


class TestAzureVaultBackendOperations(unittest.TestCase):

    def _make_backend(self):
        mock_client = MagicMock()
        with patch('azure.identity.DefaultAzureCredential'), \
             patch('azure.keyvault.secrets.SecretClient',
                   return_value=mock_client):
            backend = AzureVaultBackend('https://myvault.vault.azure.net/')
        backend._client = mock_client
        return backend, mock_client

    def test_get_returns_secret_value(self):
        backend, client = self._make_backend()
        client.get_secret.return_value.value = 'my-api-key'
        self.assertEqual(backend.get('NCBI_API_KEY', EMAIL), 'my-api-key')

    def test_get_returns_none_on_exception(self):
        backend, client = self._make_backend()
        client.get_secret.side_effect = Exception('not found')
        self.assertIsNone(backend.get('NCBI_API_KEY', EMAIL))

    def test_put_calls_set_secret(self):
        backend, client = self._make_backend()
        backend.put('NCBI_API_KEY', EMAIL, 'my-api-key')
        client.set_secret.assert_called_once()

    def test_put_uses_sanitized_key(self):
        backend, client = self._make_backend()
        backend.put('NCBI_API_KEY', EMAIL, 'value')
        key_used = client.set_secret.call_args[0][0]
        self.assertRegex(key_used, r'^[a-zA-Z0-9-]+$')

    def test_put_swallows_exception(self):
        backend, client = self._make_backend()
        client.set_secret.side_effect = Exception('vault error')
        backend.put('NCBI_API_KEY', EMAIL, 'value')  # must not raise


class TestNullVaultBackend(unittest.TestCase):

    def test_get_returns_none(self):
        self.assertIsNone(NullVaultBackend().get('MY_KEY', EMAIL))

    def test_put_is_noop(self):
        NullVaultBackend().put('MY_KEY', EMAIL, 'value')  # must not raise


class TestVault(unittest.TestCase):

    def _make_local_config(self, storage_dir: Path):
        config = MagicMock()
        config.azure_key_vault_enabled = False
        config.user_secrets_dir = storage_dir
        return config

    def _make_azure_config(self):
        config = MagicMock()
        config.azure_key_vault_enabled = True
        config.azure_key_vault_url = 'https://myvault.vault.azure.net/'
        return config

    def test_selects_local_backend_when_not_azure(self):
        with TemporaryDirectory() as d:
            vault = Vault(self._make_local_config(Path(d)))
            self.assertIsInstance(vault._backend, LocalVaultBackend)

    def test_selects_azure_backend_when_azure(self):
        with patch('azure.identity.DefaultAzureCredential'), \
             patch('azure.keyvault.secrets.SecretClient'):
            vault = Vault(self._make_azure_config())
        self.assertIsInstance(vault._backend, AzureVaultBackend)

    def test_falls_back_to_null_backend_on_init_failure(self):
        config = MagicMock()
        config.azure_key_vault_enabled = True
        config.azure_key_vault_url = 'https://myvault.vault.azure.net/'
        with patch('azure.identity.DefaultAzureCredential',
                   side_effect=Exception('no credentials')):
            vault = Vault(config)
        self.assertIsInstance(vault._backend, NullVaultBackend)

    def test_null_backend_on_init_failure_does_not_raise(self):
        config = MagicMock()
        config.azure_key_vault_enabled = True
        config.azure_key_vault_url = 'https://myvault.vault.azure.net/'
        with patch('azure.identity.DefaultAzureCredential',
                   side_effect=Exception('no credentials')):
            vault = Vault(config)
        self.assertIsNone(vault.get('MY_KEY', EMAIL))
        vault.put('MY_KEY', EMAIL, 'value')  # must not raise

    def test_get_delegates_to_backend(self):
        with TemporaryDirectory() as d:
            with patch.dict(os.environ, {'SECRET_KEY': SECRET_KEY}):
                vault = Vault(self._make_local_config(Path(d)))
            vault.put('MY_KEY', EMAIL, 'stored-value')
            self.assertEqual(vault.get('MY_KEY', EMAIL), 'stored-value')

    def test_put_and_get_roundtrip(self):
        with TemporaryDirectory() as d:
            with patch.dict(os.environ, {'SECRET_KEY': SECRET_KEY}):
                vault = Vault(self._make_local_config(Path(d)))
            vault.put('MY_KEY', EMAIL, 'hello')
            self.assertEqual(vault.get('MY_KEY', EMAIL), 'hello')

    def test_get_returns_none_on_backend_error(self):
        with TemporaryDirectory() as d:
            vault = Vault(self._make_local_config(Path(d)))
            vault._backend = MagicMock(get=MagicMock(side_effect=Exception))
            self.assertIsNone(vault.get('MY_KEY', EMAIL))

    def test_put_swallows_backend_error(self):
        with TemporaryDirectory() as d:
            vault = Vault(self._make_local_config(Path(d)))
            vault._backend = MagicMock(put=MagicMock(side_effect=Exception))
            vault.put('MY_KEY', EMAIL, 'value')  # must not raise


if __name__ == '__main__':
    unittest.main()
