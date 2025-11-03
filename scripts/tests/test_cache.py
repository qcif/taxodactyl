import os
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta

from src.utils import cache


class TestCache(unittest.TestCase):

    def test_cache_set_and_get_with_tuple_key(self):
        """Test caching with tuple key."""
        cache_key = ('endpoint', 'db', True, {'param': 'value'})
        test_data = {
            'result': 'data',
            'items': [1, 2, 3],
            'nested': {'key': 'value'}
        }
        test_keyhash = cache.keyhash(cache_key)
        cache.put(test_keyhash, test_data)

        # Get cache
        retrieved = cache.get(test_keyhash)
        self.assertEqual(retrieved, test_data)

    def test_cache_get_nonexistent_key(self):
        """Test getting non-existent cache key returns None."""
        nonexistent_key = ('does', 'not', 'exist')
        keyhash = cache.keyhash(nonexistent_key)
        result = cache.get(keyhash)
        self.assertIsNone(result)

    def test_cache_with_different_key_types(self):
        """Test caching with different key types."""
        # String key
        string_key = "simple_string_key"
        string_data = "simple data"
        string_keyhash = cache.keyhash(string_key)
        cache.put(string_keyhash, string_data)
        self.assertEqual(cache.get(string_keyhash), string_data)

        # Integer key
        int_key = 12345
        int_data = {"number": 42}
        int_keyhash = cache.keyhash(int_key)
        cache.put(int_keyhash, int_data)
        self.assertEqual(cache.get(int_keyhash), int_data)

    def test_cache_overwrite_existing_key(self):
        """Test that setting a key twice overwrites the first value."""
        test_key = ('overwrite', 'test')
        first_data = "first value"
        second_data = "second value"

        test_keyhash = cache.keyhash(test_key)
        cache.put(test_keyhash, first_data)
        cache.put(test_keyhash, second_data)
        retrieved = cache.get(test_keyhash)
        self.assertEqual(retrieved, second_data)

    def test_cache_with_complex_data_types(self):
        """Test caching with complex data types."""
        cache_key = 'complex_data'
        complex_data = {
            'list': [1, 2, {'nested': 'dict'}],
            'tuple_in_list': [(1, 2), (3, 4)],
            'none_value': None,
            'boolean': True,
            'float': 3.14159
        }
        test_keyhash = cache.keyhash(cache_key)
        cache.put(test_keyhash, complex_data)
        retrieved = cache.get(test_keyhash)
        self.assertEqual(retrieved, complex_data)

    @patch('src.utils.cache.datetime')
    def test_cache_timeout_expired(self, mock_datetime):
        """Test that expired cache entries return None."""
        cache_key = 'timeout_test'
        test_data = "should be expired"

        # Mock datetime for setting cache (current time)
        set_time = datetime(2024, 1, 1, 12, 0, 0)
        mock_datetime.now.return_value = set_time
        mock_datetime.fromisoformat = datetime.fromisoformat

        test_keyhash = cache.keyhash(cache_key)
        cache.put(test_keyhash, test_data)

        # Mock datetime for getting cache (25 hours later, past 1 week default)
        get_time = set_time + timedelta(hours=169)  # Past 168 hour default
        mock_datetime.now.return_value = get_time

        # Get cache - should return None due to expiry
        retrieved = cache.get(test_keyhash)
        self.assertIsNone(retrieved)

    @patch.dict(os.environ, {'CACHE_TIMEOUT_HOURS': '999999'})
    def test_cache_timeout_not_expired(self):
        """Test that non-expired cache entries are returned."""
        cache_key = 'timeout_test_valid'
        test_data = "should not be expired"

        test_keyhash = cache.keyhash(cache_key)
        cache.put(test_keyhash, test_data)

        # Get cache - should return data due to very long timeout
        retrieved = cache.get(test_keyhash)
        self.assertEqual(retrieved, test_data)
