#!/usr/bin/env python3
"""Test Config singleton behavior and YAML-based configuration."""

import argparse
import os
import tempfile
import unittest
import yaml
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from src.utils.config import Config  # noqa: E402

CUSTOM_TEMP_ROOT = '/tmp/test_root_dir/'
ENV_VARS_TO_CLEAR = [
    'OUTPUT_DIR',
    'INPUT_FASTA_FILEPATH',
    'INPUT_METADATA_CSV_FILEPATH',
    'ALLOWED_LOCI_FILE',
    'MIN_NT',
    'MIN_IDENTITY',
]


class TestConfigSingleton(unittest.TestCase):
    """Test Config singleton pattern behavior."""

    def setUp(self):
        """Reset singleton state before each test."""
        # Clear singleton instance
        Config._instance = None
        Config._initialized = False

        # Clear any environment variables that might affect tests
        self.original_env = {}
        for var in ENV_VARS_TO_CLEAR:
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
        original_value = config1.blast_max_target_seqs
        new_value = 5000
        config1.blast_max_target_seqs = new_value

        # Verify config2 sees the change
        self.assertEqual(config2.blast_max_target_seqs, new_value)
        self.assertNotEqual(config2.blast_max_target_seqs, original_value)

    def test_singleton_shared_nested_attributes(self):
        """Test that nested attribute changes are shared across instances."""
        config1 = Config()
        config2 = Config()

        # Modify nested attribute through config1
        original_value = config1.criteria.alignment_min_identity
        new_value = 0.99
        config1.criteria.alignment_min_identity = new_value

        # Verify config2 sees the change
        self.assertEqual(config2.criteria.alignment_min_identity, new_value)
        self.assertNotEqual(
            config2.criteria.alignment_min_identity,
            original_value
        )

    def test_initialization_only_once(self):
        """Test that __init__ is only called once despite instances."""
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


class TestConfigYAMLLoading(unittest.TestCase):
    """Test Config YAML configuration loading."""

    def setUp(self):
        """Reset singleton state and create test directories."""
        # Clear singleton instance
        Config._instance = None
        Config._initialized = False

        # Create temporary directories for testing
        self.temp_dir = Path(tempfile.mkdtemp())
        self.test_config = self.temp_dir / 'test_config.yml'

        # Create test YAML config
        test_config_data = {
            'blast_max_target_seqs': 3000,
            'bold_database': 'COX1_SPECIES',
            'criteria': {
                'alignment_min_identity': 0.98,
                'alignment_min_nt': 400,
                'max_candidates_for_analysis': 5
            },
            'inputs': {
                'fasta_max_sequences': 200,
                'fasta_min_length_nt': 50,
                'fasta_max_length_nt': 2500
            },
            'temp_root': str(CUSTOM_TEMP_ROOT),
        }

        with open(self.test_config, 'w') as f:
            yaml.dump(test_config_data, f)

    def tearDown(self):
        """Clean up test files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_yaml_config_loading(self):
        """Test loading configuration from YAML file."""
        # Mock sys.argv to include our test config
        with patch('sys.argv', ['test_script', '-c', str(self.test_config)]):
            config = Config()

            # Verify simple attributes loaded from YAML
            self.assertEqual(config.blast_max_target_seqs, 3000)
            self.assertEqual(config.bold_database, 'COX1_SPECIES')

            # Verify nested attributes loaded from YAML
            self.assertEqual(config.criteria.alignment_min_identity, 0.98)
            self.assertEqual(config.criteria.alignment_min_nt, 400)
            self.assertEqual(config.criteria.max_candidates_for_analysis, 5)

            # Verify input attributes loaded from YAML
            self.assertEqual(config.inputs.fasta_max_sequences, 200)
            self.assertEqual(config.inputs.fasta_min_length_nt, 50)
            self.assertEqual(config.inputs.fasta_max_length_nt, 2500)

            # Verify custom temp root has been set
            self.assertEqual(
                config.tempdir,
                Path(CUSTOM_TEMP_ROOT) / 'biosecurity',
            )

    def test_default_config_values(self):
        """Test that default configuration values are loaded correctly."""
        # Test with no custom config file (uses defaults)
        with patch('sys.argv', ['test_script']):
            config = Config()

            # Verify default values from schema
            self.assertEqual(config.blast_max_target_seqs, 2000)
            self.assertEqual(config.bold_database, 'COX1_SPECIES_PUBLIC')

            # Verify nested default values
            self.assertEqual(config.criteria.alignment_min_identity, 0.935)
            self.assertEqual(config.criteria.alignment_min_nt, 300)
            self.assertEqual(config.criteria.max_candidates_for_analysis, 3)

            # Verify input default values
            self.assertEqual(config.inputs.fasta_max_sequences, 150)
            self.assertEqual(config.inputs.fasta_min_length_nt, 20)
            self.assertEqual(config.inputs.fasta_max_length_nt, 3000)

    def test_cascading_config_loading(self):
        """Test loading multiple config files with cascading override."""
        # Create a second config file with different values
        override_config = self.temp_dir / 'override_config.yml'
        override_data = {
            'blast_max_target_seqs': 4000,  # Override first config
            'criteria': {
                'alignment_min_identity': 0.99  # Override nested value
            }
        }

        with open(override_config, 'w') as f:
            yaml.dump(override_data, f)

        # Test cascading with both configs
        with patch('sys.argv', ['test_script', '-c', str(self.test_config),
                                '-c', str(override_config)]):
            config = Config()

            # Verify override took precedence
            self.assertEqual(config.blast_max_target_seqs, 4000)
            self.assertEqual(config.criteria.alignment_min_identity, 0.99)

            # Verify non-overridden values from first config remain
            self.assertEqual(config.bold_database, 'COX1_SPECIES')
            self.assertEqual(config.criteria.alignment_min_nt, 400)

    def test_config_shared_across_instances(self):
        """Test that configuration is shared across singleton instances."""
        with patch('sys.argv', ['test_script', '-c', str(self.test_config)]):
            config1 = Config()
            config2 = Config()

            # Verify they're the same instance
            self.assertIs(config1, config2)

            # Verify config values are shared
            self.assertEqual(
                config1.blast_max_target_seqs,
                config2.blast_max_target_seqs
            )
            self.assertEqual(
                config1.criteria.alignment_min_identity,
                config2.criteria.alignment_min_identity
            )

            # Modify attribute through config1
            config1.blast_max_target_seqs = 5000

            # Verify config2 sees the change
            self.assertEqual(config2.blast_max_target_seqs, 5000)

    def test_invalid_yaml_config_handling(self):
        """Test that invalid YAML configuration is handled gracefully."""
        # Create invalid YAML file
        invalid_config = self.temp_dir / 'invalid_config.yml'
        invalid_config.write_text('invalid: yaml: content: [')

        # Should exit with error
        with patch('sys.argv', ['test_script', '-c', str(invalid_config)]):
            with self.assertRaises(SystemExit):
                Config()

    def test_nonexistent_config_file_handling(self):
        """Test that non-existent config files are handled gracefully."""
        nonexistent_config = self.temp_dir / 'nonexistent.yml'

        # Should not fail, just use defaults
        with patch('sys.argv', ['test_script', '-c', str(nonexistent_config)]):
            config = Config()

            # Should have default values
            self.assertEqual(config.blast_max_target_seqs, 2000)
            self.assertEqual(config.criteria.alignment_min_identity, 0.935)

            # Verify default temp root
            self.assertEqual(
                config.tempdir,
                Path(tempfile.gettempdir()) / config.temp_dir_name,
            )

    def test_pydantic_validation(self):
        """Test that Pydantic validation works correctly."""
        # Create config with invalid data types
        invalid_config = self.temp_dir / 'invalid_types.yml'
        invalid_data = {
            'blast_max_target_seqs': 'not_a_number',  # Should be int
            'criteria': {
                'alignment_min_identity': 'not_a_float'  # Should be float
            }
        }

        with open(invalid_config, 'w') as f:
            yaml.dump(invalid_data, f)

        # Should exit with validation error
        with patch('sys.argv', ['test_script', '-c', str(invalid_config)]):
            with self.assertRaises(SystemExit):
                Config()

    def test_multiple_config_instances_behavior(self):
        """Test behavior when creating multiple Config instances."""
        # Test that multiple instances work correctly with different patches
        with patch('sys.argv', ['test_script', '-c', str(self.test_config)]):
            config1 = Config()
            original_value = config1.blast_max_target_seqs

        # Reset singleton for second test
        Config._instance = None
        Config._initialized = False

        with patch('sys.argv', ['test_script']):  # No config file
            config2 = Config()
            default_value = config2.blast_max_target_seqs

        # Verify different values were loaded
        self.assertNotEqual(original_value, default_value)
        self.assertEqual(original_value, 3000)  # From our test config
        self.assertEqual(default_value, 2000)   # Default value


class TestConfigCLIArgumentUpdate(unittest.TestCase):
    """Test that CLI arguments can be passed to Config for updates."""

    def setUp(self):
        """Reset singleton state before each test."""
        # Clear singleton instance
        Config._instance = None
        Config._initialized = False

        # Clear any environment variables that might affect tests
        self.original_env = {}
        for var in ENV_VARS_TO_CLEAR:
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

    def test_config_update_from_cli_args(self):
        """Test config can be updated from CLI arguments using method."""
        # Initialize config with defaults
        with patch('sys.argv', ['test_script']):
            config = Config()

            # Store original values to verify they change
            original_blast_max = config.blast_max_target_seqs
            original_min_identity = config.criteria.alignment_min_identity
            original_min_nt = config.criteria.alignment_min_nt

            # Create CLI args that should override config values
            cli_args = argparse.Namespace(
                blast_max_target_seqs=5000,
                min_identity=0.99,
                min_alignment_length=500,
                bold_database='COX1_SPECIES_PUBLIC',
                db_cov_target_min_a=10,
                gbif_max_occurrence_records=1000
            )

            # This should work but currently fails because update_from_args
            # doesn't exist. Test will fail until we implement this method
            self.assertTrue(hasattr(config, 'update_from_args'),
                            "Config should have an update_from_args method")

            # Update config from CLI args
            config.update_from_args(cli_args)

            # Verify that config values were updated
            self.assertEqual(config.blast_max_target_seqs, 5000)
            self.assertEqual(config.criteria.alignment_min_identity, 0.99)
            self.assertEqual(config.criteria.alignment_min_nt, 500)
            self.assertEqual(config.bold_database, 'COX1_SPECIES_PUBLIC')
            self.assertEqual(config.criteria.db_cov_target_min_a, 10)
            self.assertEqual(config.gbif_max_occurrence_records, 1000)

            # Verify original values were different (proving update worked)
            self.assertNotEqual(original_blast_max, 5000)
            self.assertNotEqual(original_min_identity, 0.99)
            self.assertNotEqual(original_min_nt, 500)

    def test_config_update_ignores_none_values(self):
        """Test that update_from_args ignores None values from CLI args."""
        with patch('sys.argv', ['test_script']):
            config = Config()
            original_blast_max = config.blast_max_target_seqs

            # CLI args with some None values (not specified by user)
            cli_args = argparse.Namespace(
                blast_max_target_seqs=None,  # Should be ignored
                min_identity=0.95,          # Should be applied
                some_nonexistent_arg=None   # Should be ignored safely
            )

            config.update_from_args(cli_args)

            # blast_max_target_seqs should remain unchanged
            self.assertEqual(config.blast_max_target_seqs, original_blast_max)
            # min_identity should be updated
            self.assertEqual(config.criteria.alignment_min_identity, 0.95)

    def test_config_update_handles_missing_attributes(self):
        """Test update_from_args handles CLI args that don't map to config."""
        with patch('sys.argv', ['test_script']):
            config = Config()

            # CLI args with non-existent config mappings
            cli_args = Namespace(
                nonexistent_arg=123,
                another_fake_arg='test'
            )

            # Should not raise an exception
            config.update_from_args(cli_args)

    def test_all_cli_args_propagate_to_config(self):
        """Test that all CLI_ARGS properly update their config attributes."""
        from src.utils.config.mappings import (
            CLI_ARGS,
            IntMapping,
            FloatMapping,
            BoolMapping,
            PathMapping,
            ListMapping,
            UppercaseListMapping,
            StringMapping,
        )

        with patch('sys.argv', ['test_script']):
            config = Config()

            # Create test values for each CLI argument based on its type
            cli_args_dict = {}
            for attr_name, mapping in CLI_ARGS.items():
                # Convert CLI name (hyphenated) to argparse name (underscored)
                arg_name = mapping.cli_name.replace('-', '_')

                # Generate appropriate test value based on mapping type
                if isinstance(mapping, IntMapping):
                    test_value = 9999
                elif isinstance(mapping, FloatMapping):
                    test_value = 0.9876
                elif isinstance(mapping, BoolMapping):
                    test_value = True
                elif isinstance(mapping, PathMapping):
                    # Use a temporary path that won't be created
                    test_value = Path('/tmp/test_cli_args_path')
                elif isinstance(mapping, UppercaseListMapping):
                    test_value = 'ACCEPTED,DOUBTFUL'
                elif isinstance(mapping, ListMapping):
                    test_value = 'item1,item2,item3'
                elif isinstance(mapping, StringMapping):
                    test_value = 'test_string_value'
                else:
                    # Fallback for any unknown mapping types
                    test_value = 'test_value'

                cli_args_dict[arg_name] = test_value

            # Create argparse Namespace from the dictionary
            cli_args = Namespace(**cli_args_dict)

            # Update config from CLI args
            config.update_from_args(cli_args)

            # Verify each CLI argument properly updated its config attribute
            for attr_name, mapping in CLI_ARGS.items():
                arg_name = mapping.cli_name.replace('-', '_')
                expected_value = cli_args_dict[arg_name]

                # Get the actual value from config
                if mapping.namespace:
                    namespace_obj = getattr(config, mapping.namespace)
                    actual_value = getattr(namespace_obj, mapping.name)
                else:
                    actual_value = getattr(config, mapping.name)

                # Cast expected value through the mapping's cast method
                expected_casted = mapping.cast(expected_value)

                namespace_prefix = (
                    f"{mapping.namespace}." if mapping.namespace else ""
                )
                error_msg = (
                    f"CLI arg '--{mapping.cli_name}' (attr: {attr_name}) "
                    f"did not properly update config.{namespace_prefix}"
                    f"{mapping.name}. "
                    f"Expected {expected_casted}, got {actual_value}"
                )
                self.assertEqual(
                    actual_value,
                    expected_casted,
                    error_msg
                )


class TestConfigPathResolution(unittest.TestCase):
    """Test that relative paths in config files are resolved correctly."""

    def setUp(self):
        """Create temporary directory and reset singleton state."""
        # Reset singleton instance
        Config._instance = None
        Config._initialized = False

        # Create temporary directory for test files
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_relative_path_resolution_in_config(self):
        """Test that relative paths in YAML config are resolved correctly."""
        # Create temp config with relative paths
        temp_config = self.temp_dir / 'relative_paths.yml'
        config_data = {
            'allowed_loci_file': 'config/loci.json',
            'flag_details_csv_path': 'config/flags.csv',
        }

        with open(temp_config, 'w') as f:
            yaml.dump(config_data, f)

        # Test with relative paths in config
        with patch('sys.argv', ['test_script', '-c', str(temp_config)]):
            config = Config()

            # Paths should be absolute and point to correct location
            self.assertTrue(config.allowed_loci_file.is_absolute())
            self.assertTrue(config.flag_details_csv_path.is_absolute())

            # Should exist (assuming test runs from correct directory)
            self.assertTrue(config.allowed_loci_file.exists())
            self.assertTrue(config.flag_details_csv_path.exists())

            # Should contain 'scripts/config' in the path
            self.assertIn('scripts/config', str(config.allowed_loci_file))
            self.assertIn('scripts/config', str(config.flag_details_csv_path))

    def test_absolute_path_passthrough_in_config(self):
        """Test that absolute paths in YAML config are left unchanged."""
        # Create temp config with absolute paths
        temp_config = self.temp_dir / 'absolute_paths.yml'
        abs_loci_path = self.temp_dir / 'custom_loci.json'
        abs_flags_path = self.temp_dir / 'custom_flags.csv'

        # Create dummy files
        abs_loci_path.write_text('[]')
        abs_flags_path.write_text('id,name\n')

        config_data = {
            'allowed_loci_file': str(abs_loci_path),
            'flag_details_csv_path': str(abs_flags_path),
        }

        with open(temp_config, 'w') as f:
            yaml.dump(config_data, f)

        # Test with absolute paths in config
        with patch('sys.argv', ['test_script', '-c', str(temp_config)]):
            config = Config()

            # Should maintain the exact absolute paths specified
            self.assertEqual(config.allowed_loci_file, abs_loci_path)
            self.assertEqual(config.flag_details_csv_path, abs_flags_path)


if __name__ == '__main__':
    unittest.main()
