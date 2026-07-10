"""Unit tests for :class:`AzureBlobCacheBackend`.

The Azure SDK is not exercised against a real storage account; instead
we inject a fake :class:`ContainerClient` that records calls and can be
pre-seeded with blobs. This lets us verify the backend's behaviour
against the minimal subset of the SDK surface that it touches:

- ``container_client.get_blob_client(name)``
- ``blob_client.download_blob()`` -> object with ``.properties`` and
  ``.readall()``
- ``blob_client.upload_blob(data, overwrite=..., metadata=...)``
- ``blob_client.delete_blob()``
"""

import pickle
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from azure.core.exceptions import (
    ResourceExistsError,
    ResourceNotFoundError,
)

from src.utils.cache import (
    CREATED_AT_METADATA_KEY,
    AzureBlobCacheBackend,
)


class FakeBlob:
    """In-memory representation of a single blob entry."""

    def __init__(self, data: bytes, metadata: dict, last_modified=None):
        self.data = data
        self.metadata = dict(metadata)
        self.last_modified = last_modified or datetime.now(timezone.utc)


class FakeDownloader:
    def __init__(self, blob: FakeBlob):
        self._blob = blob
        self.properties = SimpleNamespace(
            metadata=dict(blob.metadata),
            last_modified=blob.last_modified,
        )

    def readall(self) -> bytes:
        return self._blob.data


class FakeBlobClient:
    def __init__(self, container: 'FakeContainerClient', name: str):
        self._container = container
        self._name = name

    def download_blob(self):
        self._container.calls.append(('download', self._name))
        if self._name not in self._container.blobs:
            raise ResourceNotFoundError(f"Blob {self._name} not found")
        return FakeDownloader(self._container.blobs[self._name])

    def upload_blob(self, data, overwrite=False, metadata=None):
        self._container.calls.append(
            ('upload', self._name, overwrite, dict(metadata or {}))
        )
        if not overwrite and self._name in self._container.blobs:
            raise ResourceExistsError(f"Blob {self._name} already exists")
        self._container.blobs[self._name] = FakeBlob(
            data=bytes(data),
            metadata=metadata or {},
        )

    def delete_blob(self):
        self._container.calls.append(('delete', self._name))
        if self._name not in self._container.blobs:
            raise ResourceNotFoundError(f"Blob {self._name} not found")
        del self._container.blobs[self._name]


class FakeContainerClient:
    def __init__(self, raise_on_create: Exception | None = None):
        self.blobs: dict[str, FakeBlob] = {}
        self.calls: list = []
        self.create_container_calls = 0
        self._raise_on_create = raise_on_create

    def create_container(self):
        self.create_container_calls += 1
        if self._raise_on_create is not None:
            raise self._raise_on_create

    def get_blob_client(self, name: str) -> FakeBlobClient:
        return FakeBlobClient(self, name)


class AzureBlobCacheBackendTests(unittest.TestCase):
    """Tests for :class:`AzureBlobCacheBackend` using a fake container."""

    def _make_backend(
        self,
        container: FakeContainerClient,
        timeout_hours: int = 24,
        blob_prefix: str = '',
    ) -> AzureBlobCacheBackend:
        backend = AzureBlobCacheBackend(
            container_name='test-container',
            timeout_hours=timeout_hours,
            connection_string='UseDevelopmentStorage=true',
            blob_prefix=blob_prefix,
        )
        # Short-circuit SDK initialization by injecting our fake.
        backend._container_client = container
        backend._container_ready = True
        return backend

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def test_requires_credentials(self):
        """Constructing without account_url or connection_string fails."""
        with self.assertRaises(ValueError):
            AzureBlobCacheBackend(
                container_name='c',
                timeout_hours=1,
            )

    # ------------------------------------------------------------------
    # put / get round-trip
    # ------------------------------------------------------------------

    def test_put_then_get_round_trip(self):
        """A value written via put() is readable via get()."""
        container = FakeContainerClient()
        backend = self._make_backend(container)

        payload = {
            'result': 'ok',
            'items': [1, 2, 3],
            'nested': {'k': 'v'},
        }
        backend.put('abc123', payload)

        self.assertIn('abc123', container.blobs)
        stored = container.blobs['abc123']
        self.assertIn(CREATED_AT_METADATA_KEY, stored.metadata)
        self.assertEqual(pickle.loads(stored.data), payload)

        # get() returns the same object.
        self.assertEqual(backend.get('abc123'), payload)

    def test_put_overwrites_existing_entry(self):
        """put() with an existing key overwrites (last writer wins)."""
        container = FakeContainerClient()
        backend = self._make_backend(container)

        backend.put('k', 'first')
        backend.put('k', 'second')

        self.assertEqual(backend.get('k'), 'second')
        # Every upload uses overwrite=True.
        uploads = [c for c in container.calls if c[0] == 'upload']
        self.assertEqual(len(uploads), 2)
        for call in uploads:
            self.assertTrue(call[2], f"upload not using overwrite: {call}")

    def test_put_stores_long_string_payload(self):
        """Large API-response-like strings survive the round trip."""
        container = FakeContainerClient()
        backend = self._make_backend(container)

        payload = 'x' * 200_000  # 200 KB
        backend.put('big', payload)

        self.assertEqual(backend.get('big'), payload)

    # ------------------------------------------------------------------
    # get() - misses and errors
    # ------------------------------------------------------------------

    def test_get_missing_key_returns_none(self):
        """A cache miss returns None."""
        container = FakeContainerClient()
        backend = self._make_backend(container)

        self.assertIsNone(backend.get('nope'))

    def test_get_swallows_unexpected_exceptions(self):
        """Unexpected errors from the SDK return None, not raise."""
        container = FakeContainerClient()
        backend = self._make_backend(container)

        def boom(*_args, **_kwargs):
            raise RuntimeError("network down")

        # Break get_blob_client for this one call.
        with patch.object(container, 'get_blob_client', side_effect=boom):
            self.assertIsNone(backend.get('any'))

    def test_get_unpickleable_blob_returns_none(self):
        """Corrupt pickle data returns None instead of propagating."""
        container = FakeContainerClient()
        backend = self._make_backend(container)

        container.blobs['bad'] = FakeBlob(
            data=b'not a valid pickle',
            metadata={
                CREATED_AT_METADATA_KEY: datetime.now().isoformat(),
            },
        )

        self.assertIsNone(backend.get('bad'))

    # ------------------------------------------------------------------
    # Expiry
    # ------------------------------------------------------------------

    def test_expired_entry_returns_none_and_is_deleted(self):
        """Blobs older than the TTL are returned as misses and deleted."""
        container = FakeContainerClient()
        backend = self._make_backend(container, timeout_hours=1)

        stale_time = (datetime.now() - timedelta(hours=2)).isoformat()
        container.blobs['old'] = FakeBlob(
            data=pickle.dumps('stale value'),
            metadata={CREATED_AT_METADATA_KEY: stale_time},
        )

        self.assertIsNone(backend.get('old'))
        # Backend best-effort deletes expired entries.
        self.assertNotIn('old', container.blobs)
        delete_calls = [c for c in container.calls if c[0] == 'delete']
        self.assertEqual(len(delete_calls), 1)

    def test_fresh_entry_is_returned(self):
        """Entries within the TTL window are returned normally."""
        container = FakeContainerClient()
        backend = self._make_backend(container, timeout_hours=24)

        fresh_time = (datetime.now() - timedelta(minutes=5)).isoformat()
        container.blobs['fresh'] = FakeBlob(
            data=pickle.dumps('hello'),
            metadata={CREATED_AT_METADATA_KEY: fresh_time},
        )

        self.assertEqual(backend.get('fresh'), 'hello')
        # No delete on fresh read.
        self.assertNotIn(
            'delete',
            {c[0] for c in container.calls},
        )

    def test_expiry_falls_back_to_last_modified(self):
        """When metadata is missing, blob last_modified drives expiry."""
        container = FakeContainerClient()
        backend = self._make_backend(container, timeout_hours=1)

        stale_last_modified = datetime.now(timezone.utc) - timedelta(
            hours=5
        )
        container.blobs['no-meta'] = FakeBlob(
            data=pickle.dumps('old'),
            metadata={},
            last_modified=stale_last_modified,
        )

        self.assertIsNone(backend.get('no-meta'))
        self.assertNotIn('no-meta', container.blobs)

    def test_invalid_created_at_metadata_uses_last_modified(self):
        """Garbage in the created_at metadata falls back to last_modified."""
        container = FakeContainerClient()
        backend = self._make_backend(container, timeout_hours=24)

        fresh_last_modified = datetime.now(timezone.utc) - timedelta(
            minutes=1
        )
        container.blobs['bad-meta'] = FakeBlob(
            data=pickle.dumps('value'),
            metadata={CREATED_AT_METADATA_KEY: 'not-a-timestamp'},
            last_modified=fresh_last_modified,
        )

        self.assertEqual(backend.get('bad-meta'), 'value')

    # ------------------------------------------------------------------
    # Blob naming
    # ------------------------------------------------------------------

    def test_blob_prefix_is_applied(self):
        """Cache entries are namespaced under the configured prefix."""
        container = FakeContainerClient()
        backend = self._make_backend(container, blob_prefix='cache/v1')

        backend.put('abc', 'value')
        self.assertIn('cache/v1/abc', container.blobs)
        self.assertNotIn('abc', container.blobs)

        self.assertEqual(backend.get('abc'), 'value')

    def test_blob_prefix_trailing_slash_is_stripped(self):
        """Trailing slashes in prefix don't cause double slashes."""
        container = FakeContainerClient()
        backend = self._make_backend(container, blob_prefix='cache/')

        backend.put('abc', 'value')
        self.assertIn('cache/abc', container.blobs)

    # ------------------------------------------------------------------
    # put() error handling
    # ------------------------------------------------------------------

    def test_put_swallows_upload_errors(self):
        """Upload failures are logged, not raised."""
        container = FakeContainerClient()
        backend = self._make_backend(container)

        def boom(*_args, **_kwargs):
            raise RuntimeError("storage throttled")

        with patch.object(
            FakeBlobClient, 'upload_blob', side_effect=boom
        ):
            # Should not raise.
            backend.put('k', 'v')

    # ------------------------------------------------------------------
    # Container bootstrap
    # ------------------------------------------------------------------

    def test_ensure_container_swallows_resource_exists(self):
        """Pre-existing containers don't cause errors on init."""
        container = FakeContainerClient(
            raise_on_create=ResourceExistsError("already exists")
        )
        backend = AzureBlobCacheBackend(
            container_name='c',
            timeout_hours=1,
            connection_string='UseDevelopmentStorage=true',
        )
        # Exercise _ensure_container directly with a fresh fake.
        backend._ensure_container(container)
        self.assertEqual(container.create_container_calls, 1)
        self.assertTrue(backend._container_ready)

    def test_ensure_container_swallows_permission_errors(self):
        """A RBAC error on create_container doesn't prevent use."""
        container = FakeContainerClient(
            raise_on_create=RuntimeError("AuthorizationFailure")
        )
        backend = AzureBlobCacheBackend(
            container_name='c',
            timeout_hours=1,
            connection_string='UseDevelopmentStorage=true',
        )
        backend._ensure_container(container)
        self.assertTrue(backend._container_ready)

    def test_container_client_is_cached(self):
        """Repeated backend calls reuse the same ContainerClient."""
        container = FakeContainerClient()
        backend = self._make_backend(container)

        # After the initial injection, _get_container_client() should
        # keep returning the same instance without reinitializing.
        self.assertIs(backend._get_container_client(), container)
        self.assertIs(backend._get_container_client(), container)


if __name__ == '__main__':
    unittest.main()
