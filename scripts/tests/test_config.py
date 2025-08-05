#!/usr/bin/env python3
"""Test Config singleton behavior and update_from_args method."""

import os
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import Config


class TestConfigSingleton(unittest.TestCase):
    """Test Config singleton pattern behavior."""

    def setUp(self):
        """Reset singleton state before each test."""
        # Clear singleton instance
        Config._instance = None
        Config._initialized = False
        
        # Clear any environment variables that might affect tests
        env_vars_to_clear = [
            'OUTPUT_DIR', 'INPUT_FASTA_FILEPATH', 'INPUT_METADATA_CSV_FILEPATH',
            'ALLOWED_LOCI_FILE', 'MIN_NT', 'MIN_IDENTITY'
        ]
        self.original_env = {}
        for var in env_vars_to_clear:
            self.original_env[var] = os.environ.get(var)
            if var in os.environ:
                del os.environ[var]

    def tearDown(self):
        """Restore environment variables after each test."""
        for var, value in self.original_env.items():
            if value is not None:
                os.environ[var] = value
            elif var in os.environ:
                del os.environ[var]

    def test_singleton_same_instance(self):
        """Test that Config() returns the same instance."""
        config1 = Config()
        config2 = Config()
        
        self.assertIs(config1, config2)
        self.assertEqual(id(config1), id(config2))

    def test_singleton_shared_attributes(self):
        """Test that attribute changes are shared across instances."""
        config1 = Config()
        config2 = Config()
        
        # Modify instance attribute through config1
        original_output_dir = config1.output_dir
        new_output_dir = Path('/tmp/test_output')
        config1.output_dir = new_output_dir
        
        # Verify config2 sees the change
        self.assertEqual(config2.output_dir, new_output_dir)
        self.assertNotEqual(config2.output_dir, original_output_dir)

    def test_singleton_shared_class_attributes(self):
        """Test that class attribute changes are shared across instances."""
        config1 = Config()
        config2 = Config()
        
        # Modify class attribute through config1
        original_value = config1.BLAST_MAX_TARGET_SEQS
        new_value = 5000
        config1.BLAST_MAX_TARGET_SEQS = new_value
        
        # Verify config2 sees the change
        self.assertEqual(config2.BLAST_MAX_TARGET_SEQS, new_value)
        self.assertNotEqual(config2.BLAST_MAX_TARGET_SEQS, original_value)

    def test_singleton_shared_nested_attributes(self):
        """Test that nested attribute changes are shared across instances."""
        config1 = Config()
        config2 = Config()
        
        # Modify nested attribute through config1
        original_value = config1.CRITERIA.ALIGNMENT_MIN_IDENTITY
        new_value = 0.99
        config1.CRITERIA.ALIGNMENT_MIN_IDENTITY = new_value
        
        # Verify config2 sees the change
        self.assertEqual(config2.CRITERIA.ALIGNMENT_MIN_IDENTITY, new_value)
        self.assertNotEqual(config2.CRITERIA.ALIGNMENT_MIN_IDENTITY, 
                           original_value)

    def test_initialization_only_once(self):
        """Test that __init__ is only called once despite multiple instances."""
        # We can't easily mock __init__ due to singleton pattern complexity
        # Instead, test that the _initialized flag works correctly
        config1 = Config()
        config2 = Config()
        config3 = Config()
        
        # All instances should be the same object
        self.assertIs(config1, config2)
        self.assertIs(config2, config3)
        
        # The _initialized flag should be True after first initialization
        self.assertTrue(Config._initialized)


class TestConfigUpdateFromArgs(unittest.TestCase):
    """Test Config.update_from_args method."""

    def setUp(self):
        """Reset singleton state and create test directories."""
        # Clear singleton instance
        Config._instance = None
        Config._initialized = False
        
        # Create temporary directories for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_fasta = self.temp_dir / 'test.fasta'
        self.test_metadata = self.temp_dir / 'test.csv'
        self.test_loci = self.temp_dir / 'loci.json'
        
        # Create test files
        self.test_fasta.touch()
        self.test_metadata.touch()
        self.test_loci.write_text('{"COI": {"synonyms": ["COX1", "COI"]}}')

    def tearDown(self):
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_update_simple_attributes(self):
        """Test updating simple class attributes."""
        config = Config()
        
        # Test simple attribute updates
        args = Namespace(
            blast_max_target_seqs=3000,
            bold_database='COX1_SPECIES',
            nonexistent_arg=None
        )
        
        original_blast_max = config.BLAST_MAX_TARGET_SEQS
        original_bold_db = config.BOLD_DATABASE
        
        config.update_from_args(args)
        
        # Verify updates applied for known args
        self.assertEqual(config.BLAST_MAX_TARGET_SEQS, 3000)
        self.assertNotEqual(config.BLAST_MAX_TARGET_SEQS, original_blast_max)
        self.assertEqual(config.BOLD_DATABASE, 'COX1_SPECIES')
        self.assertNotEqual(config.BOLD_DATABASE, original_bold_db)
        
        # Verify unknown args are ignored (no error thrown)
        # This is expected behavior since we only process known mappings

    def test_update_nested_attributes(self):
        """Test updating nested attributes using dot notation."""
        config = Config()
        
        args = Namespace(
            min_identity=0.98,
            min_alignment_length=400,
            max_candidates_analysis=5
        )
        
        original_identity = config.CRITERIA.ALIGNMENT_MIN_IDENTITY
        original_length = config.CRITERIA.ALIGNMENT_MIN_NT
        original_candidates = config.CRITERIA.MAX_CANDIDATES_FOR_ANALYSIS
        
        config.update_from_args(args)
        
        # Verify nested updates applied
        self.assertEqual(config.CRITERIA.ALIGNMENT_MIN_IDENTITY, 0.98)
        self.assertNotEqual(config.CRITERIA.ALIGNMENT_MIN_IDENTITY, 
                           original_identity)
        self.assertEqual(config.CRITERIA.ALIGNMENT_MIN_NT, 400)
        self.assertNotEqual(config.CRITERIA.ALIGNMENT_MIN_NT, original_length)
        self.assertEqual(config.CRITERIA.MAX_CANDIDATES_FOR_ANALYSIS, 5)
        self.assertNotEqual(config.CRITERIA.MAX_CANDIDATES_FOR_ANALYSIS, 
                           original_candidates)

    def test_update_path_attributes(self):
        """Test updating Path attributes."""
        config = Config()
        
        args = Namespace(
            input_fasta=self.test_fasta,
            input_metadata=self.test_metadata,
            allowed_loci_file=self.test_loci
        )
        
        config.update_from_args(args)
        
        # Verify Path updates applied
        self.assertEqual(config.INPUTS.FASTA_FILEPATH, self.test_fasta)
        self.assertEqual(config.INPUTS.METADATA_PATH, self.test_metadata)
        self.assertEqual(config.ALLOWED_LOCI_FILE, self.test_loci)

    def test_update_shared_across_instances(self):
        """Test that updates are shared across singleton instances."""
        config1 = Config()
        config2 = Config()
        
        # Verify they're the same instance
        self.assertIs(config1, config2)
        
        args = Namespace(
            min_identity=0.97,
            blast_max_target_seqs=4000
        )
        
        # Update through config1
        config1.update_from_args(args)
        
        # Verify config2 sees the changes
        self.assertEqual(config2.CRITERIA.ALIGNMENT_MIN_IDENTITY, 0.97)
        self.assertEqual(config2.BLAST_MAX_TARGET_SEQS, 4000)
        
        # Verify they're still the same values
        self.assertEqual(config1.CRITERIA.ALIGNMENT_MIN_IDENTITY, 
                        config2.CRITERIA.ALIGNMENT_MIN_IDENTITY)
        self.assertEqual(config1.BLAST_MAX_TARGET_SEQS, 
                        config2.BLAST_MAX_TARGET_SEQS)

    def test_update_ignores_none_values(self):
        """Test that None values in args are ignored."""
        config = Config()
        
        original_identity = config.CRITERIA.ALIGNMENT_MIN_IDENTITY
        original_blast_max = config.BLAST_MAX_TARGET_SEQS
        
        args = Namespace(
            min_identity=None,
            blast_max_target_seqs=3500,
            nonexistent_arg=None
        )
        
        config.update_from_args(args)
        
        # Verify None value was ignored (no change)
        self.assertEqual(config.CRITERIA.ALIGNMENT_MIN_IDENTITY, 
                        original_identity)
        
        # Verify non-None value was applied
        self.assertEqual(config.BLAST_MAX_TARGET_SEQS, 3500)
        self.assertNotEqual(config.BLAST_MAX_TARGET_SEQS, original_blast_max)

    def test_update_unknown_args_ignored(self):
        """Test that unknown arguments are safely ignored."""
        config = Config()
        
        # Create args with unknown attributes
        args = Namespace(
            unknown_arg=42,
            another_unknown='test',
            min_identity=0.95  # This should be processed
        )
        
        original_identity = config.CRITERIA.ALIGNMENT_MIN_IDENTITY
        
        # Should not raise any errors
        config.update_from_args(args)
        
        # Known arg should be updated
        self.assertEqual(config.CRITERIA.ALIGNMENT_MIN_IDENTITY, 0.95)
        self.assertNotEqual(config.CRITERIA.ALIGNMENT_MIN_IDENTITY, 
                           original_identity)
        
        # Unknown args should not create attributes
        self.assertFalse(hasattr(config, 'unknown_arg'))
        self.assertFalse(hasattr(config, 'another_unknown'))

    def test_real_world_p0_validation_mapping(self):
        """Test with actual p0_validation.py arguments."""
        config = Config()
        
        args = Namespace(
            allowed_loci_file=self.test_loci,
            input_fasta=self.test_fasta,
            input_metadata=self.test_metadata,
            fasta_max_sequences=200,
            fasta_min_length=50,
            fasta_max_length=2500
        )
        
        config.update_from_args(args)
        
        # Verify all updates applied correctly
        self.assertEqual(config.ALLOWED_LOCI_FILE, self.test_loci)
        self.assertEqual(config.INPUTS.FASTA_FILEPATH, self.test_fasta)
        self.assertEqual(config.INPUTS.METADATA_PATH, self.test_metadata)
        self.assertEqual(config.INPUTS.FASTA_MAX_SEQUENCES, 200)
        self.assertEqual(config.INPUTS.FASTA_MIN_LENGTH_NT, 50)
        self.assertEqual(config.INPUTS.FASTA_MAX_LENGTH_NT, 2500)

    def test_real_world_p3_assign_taxonomy_mapping(self):
        """Test with actual p3_assign_taxonomy.py arguments."""
        config = Config()
        
        args = Namespace(
            min_alignment_length=350,
            min_query_coverage=0.9,
            min_identity=0.94,
            min_identity_strict=0.99,
            median_identity_warning_factor=0.96,
            max_candidates_analysis=4,
            phylogeny_min_sequences=25,
            phylogeny_max_per_species=35
        )
        
        config.update_from_args(args)
        
        # Verify all updates applied correctly
        self.assertEqual(config.CRITERIA.ALIGNMENT_MIN_NT, 350)
        self.assertEqual(config.CRITERIA.ALIGNMENT_MIN_Q_COVERAGE, 0.9)
        self.assertEqual(config.CRITERIA.ALIGNMENT_MIN_IDENTITY, 0.94)
        self.assertEqual(config.CRITERIA.ALIGNMENT_MIN_IDENTITY_STRICT, 0.99)
        self.assertEqual(config.CRITERIA.MEDIAN_IDENTITY_WARNING_FACTOR, 0.96)
        self.assertEqual(config.CRITERIA.MAX_CANDIDATES_FOR_ANALYSIS, 4)
        self.assertEqual(config.CRITERIA.PHYLOGENY_MIN_HIT_SEQUENCES, 25)
        self.assertEqual(config.CRITERIA.PHYLOGENY_MAX_HITS_PER_SPECIES, 35)


if __name__ == '__main__':
    unittest.main()