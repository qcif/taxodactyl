import json
import shutil
import tempfile
import unittest
from pathlib import Path

from src.utils.flags import FLAGS, Flag


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
