import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, timedelta

from src.utils.flags import FLAGS, Flag
from src.utils import cache


class TestUtils(unittest.TestCase):

    TEST_SPECIES = 'Test species'
    TEST_TARGET_TYPE = 'candidate'

    def setUp(self):
        self.query_dir = Path(tempfile.mkdtemp(prefix='query_001_'))

    def tearDown(self):
        shutil.rmtree(self.query_dir)

    def test_flags(self):
        Flag.write(self.query_dir, FLAGS.POSITIVE_ID, FLAGS.A)
        Flag.write(self.query_dir, FLAGS.TOI, FLAGS.B)
        for flag_id in (
            FLAGS.SOURCES,
            FLAGS.DB_COVERAGE_TARGET,
            FLAGS.DB_COVERAGE_RELATED,
            FLAGS.DB_COVERAGE_RELATED_COUNTRY,
        ):
            Flag.write(
                self.query_dir,
                flag_id,
                FLAGS.A,
                target=self.TEST_SPECIES,
                target_type=self.TEST_TARGET_TYPE,
            )
        flags = Flag.read(self.query_dir)
        flag_1 = flags[FLAGS.POSITIVE_ID]
        self.assertIsInstance(flag_1, Flag)
        self.assertEqual(flag_1.value, FLAGS.A)
        flag_2 = flags[FLAGS.TOI]
        self.assertIsInstance(flag_2, Flag)
        self.assertEqual(flag_2.value, FLAGS.B)
        flag_4 = flags[FLAGS.SOURCES][self.TEST_TARGET_TYPE][
            self.TEST_SPECIES]
        self.assertIsInstance(flag_4, Flag)
        self.assertEqual(flag_4.value, FLAGS.A)
        flags_json = Flag.read(self.query_dir, as_json=True)
        flag_4 = flags_json[FLAGS.SOURCES][self.TEST_TARGET_TYPE][
            self.TEST_SPECIES]
        self.assertIsInstance(flag_4, dict)
        self.assertEqual(flag_4['value'], FLAGS.A)

    def test_flag_json_storage(self):
        """Test that flags are properly stored in JSON format."""
        # Write multiple flags to the same flag_id file
        Flag.write(self.query_dir, FLAGS.DB_COVERAGE_TARGET, FLAGS.A,
                   target='species1', target_type='candidate')
        Flag.write(self.query_dir, FLAGS.DB_COVERAGE_TARGET, FLAGS.B,
                   target='species2', target_type='pmi')

        # Check that the file contains JSON with multiple flags
        flag_file = self.query_dir / f"{FLAGS.DB_COVERAGE_TARGET}.flag"
        self.assertTrue(flag_file.exists())

        with flag_file.open('r') as f:
            data = json.load(f)

        # Should be a list of flag dicts
        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 2)

        # Check first flag
        flag1 = data[0]
        self.assertEqual(flag1['flag_id'], FLAGS.DB_COVERAGE_TARGET)
        self.assertEqual(flag1['value'], FLAGS.A)
        self.assertEqual(flag1['target'], 'species1')
        self.assertEqual(flag1['target_type'], 'candidate')

        # Check second flag
        flag2 = data[1]
        self.assertEqual(flag2['flag_id'], FLAGS.DB_COVERAGE_TARGET)
        self.assertEqual(flag2['value'], FLAGS.B)
        self.assertEqual(flag2['target'], 'species2')
        self.assertEqual(flag2['target_type'], 'pmi')

    def test_flag_update_existing(self):
        """Test that updating an existing flag works correctly."""
        # Write initial flag
        Flag.write(self.query_dir, FLAGS.POSITIVE_ID, FLAGS.A,
                   target='species1', target_type='candidate')

        # Update the same flag
        Flag.write(self.query_dir, FLAGS.POSITIVE_ID, FLAGS.B,
                   target='species1', target_type='candidate')

        # Check that file still has only one flag with updated value
        flag_file = self.query_dir / f"{FLAGS.POSITIVE_ID}.flag"
        with flag_file.open('r') as f:
            data = json.load(f)

        self.assertIsInstance(data, list)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['value'], FLAGS.B)

    def test_flag_no_target(self):
        """Test flags without target/target_type."""
        Flag.write(self.query_dir, FLAGS.POSITIVE_ID, FLAGS.C)

        flag_file = self.query_dir / f"{FLAGS.POSITIVE_ID}.flag"
        with flag_file.open('r') as f:
            data = json.load(f)

        self.assertEqual(data[0]['flag_id'], FLAGS.POSITIVE_ID)
        self.assertEqual(data[0]['value'], FLAGS.C)
        self.assertIsNone(data[0]['target'])
        self.assertIsNone(data[0]['target_type'])


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
