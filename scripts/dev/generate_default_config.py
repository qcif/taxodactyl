#!/usr/bin/env python3
"""Generate default.yml config file from Pydantic models.

This script creates the default configuration YAML file based on the
Pydantic models defined in config_schema.py. This ensures that any
changes to the configuration schema are automatically reflected in
the default config file.
"""

import sys
from pathlib import Path

import yaml

# Add src to path to import modules
SCRIPTS_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_ROOT))

from src.utils.config.schema import ConfigSchema  # noqa: E402


def generate_default_config():
    """Generate default configuration YAML from Pydantic schema."""
    # Create default instance to get all default values
    config = ConfigSchema()

    # Get the scripts directory to calculate relative paths from
    scripts_dir = SCRIPTS_ROOT

    # Fields that should be relative to the scripts directory
    RELATIVE_PATH_FIELDS = (
        'allowed_loci_file',
        'flag_details_csv_path',
        'placeholder_img_path',
    )

    # Convert to dict, excluding computed fields and converting Path objects
    config_dict = {}

    for field_name, _ in ConfigSchema.model_fields.items():
        value = getattr(config, field_name)

        # Convert Path objects to strings for YAML serialization
        if isinstance(value, Path):
            if field_name in RELATIVE_PATH_FIELDS:
                # Convert to relative path from scripts directory
                try:
                    relative_path = value.relative_to(scripts_dir)
                    relative_str = str(relative_path)
                    # Remove redundant 'scripts/' prefix if present
                    if relative_str.startswith('scripts/'):
                        relative_str = relative_str[8:]  # len('scripts/') = 8
                    config_dict[field_name] = relative_str
                except ValueError:
                    # If can't make relative, use absolute path
                    config_dict[field_name] = str(value)
            else:
                config_dict[field_name] = str(value)
        elif hasattr(value, 'model_dump'):
            # Handle nested Pydantic models
            nested_dict = {}
            for nested_field_name, _ in (
                value.__class__.model_fields.items()
            ):
                nested_value = getattr(value, nested_field_name)
                if isinstance(nested_value, Path):
                    nested_dict[nested_field_name] = str(nested_value)
                else:
                    nested_dict[nested_field_name] = nested_value
            config_dict[field_name] = nested_dict
        else:
            config_dict[field_name] = value

    return config_dict


def write_yaml_config(config_dict: dict, output_path: Path):
    """Write configuration dictionary to YAML file."""
    with open(output_path, 'w') as f:
        yaml.safe_dump(
            config_dict,
            f,
            default_flow_style=False,
            sort_keys=False,
            indent=2,
            width=80
        )


def main():
    """Main function to generate default config."""
    # Define paths
    script_dir = Path(__file__).parent
    config_dir = script_dir.parent / 'config'
    output_path = config_dir / 'default.yml'

    # Ensure config directory exists
    config_dir.mkdir(exist_ok=True)

    print("Generating default configuration from Pydantic models...")

    try:
        # Generate config dict from schema
        config_dict = generate_default_config()

        # Write to YAML file
        write_yaml_config(config_dict, output_path)

        print(f"Default configuration written to: {output_path}")

    except Exception as e:
        print(f"Error generating default config: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
