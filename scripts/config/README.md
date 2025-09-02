# Configuration System

This directory contains YAML configuration files for the biosecurity workflow. The system supports cascading configurations, allowing you to compose settings from multiple files.

## Files

- **`default.yml`** - Default configuration with all standard settings
- **`base.yml`** - Example base configuration for typical analyses  
- **`high_confidence.yml`** - Stricter analysis criteria for high-confidence results
- **`lab_environment.yml`** - Lab-specific settings (facility info, database names)
- **`test.yml`** - Test configuration with custom values
- **`example_custom.yml`** - Example of comprehensive custom configuration

## Usage

### Single Configuration File
```bash
python p3_assign_taxonomy.py -c config/base.yml --query_dir data/query_001
```

### Cascading Configuration Files
```bash
# Base settings + high confidence criteria + lab environment
python p3_assign_taxonomy.py \
  -c config/base.yml \
  -c config/high_confidence.yml \
  -c config/lab_environment.yml \
  --query_dir data/query_001
```

## How Cascading Works

Configuration files are merged in order, with later files overriding earlier ones:

1. **base.yml** sets foundation settings
2. **high_confidence.yml** overrides analysis criteria for stricter validation  
3. **lab_environment.yml** overrides facility info and database settings

### Example Cascading Result

```yaml
# From base.yml
inputs:
  facility_name: "Default Lab"
  fasta_max_sequences: 150
criteria:
  alignment_min_identity: 0.935

# After high_confidence.yml override
criteria:
  alignment_min_identity: 0.95  # Overridden
inputs:
  fasta_max_sequences: 100      # Overridden

# After lab_environment.yml override  
inputs:
  facility_name: "Marine Biology Research Institute"  # Overridden
  fasta_max_sequences: 200                            # Overridden again
```

## Configuration Structure

All configurations follow the Pydantic schema with these main sections:

- **`inputs`** - Input file validation and metadata
- **`criteria`** - Analysis criteria and thresholds
- **`report`** - Report generation settings
- **Root level** - BLAST, BOLD, GBIF, and other tool settings

## Environment Variables

Sensitive data still uses environment variables:
- `USER_EMAIL` - User email for API access
- `NCBI_API_KEY` - NCBI API key
- `TAXONKIT_DATA` - TaxonKit database path

## Creating Custom Configurations

1. Start with `base.yml` as a foundation
2. Create specific override files for:
   - Environment settings (dev/test/prod)
   - Analysis type settings (high confidence, exploratory)
   - Lab-specific settings (facilities, databases)
3. Use cascading to compose the final configuration