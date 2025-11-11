# FHIR mustSupport Element Analyzer

A Python tool for extracting and analyzing mustSupport elements from FHIR Implementation Guide packages, with instance usage analysis capabilities.

## Overview

This tool analyzes FHIR Structure Definitions to extract all elements marked with `mustSupport: true` and optionally analyzes FHIR instances to count how frequently these elements are actually populated in practice.

## Features

- **Extract mustSupport elements** from FHIR packages (npm format)
- **Extension support** - properly handles and displays extension names (e.g., `extension:statusReason`)
- **Cardinality information** - shows min..max constraints for each element
- **Instance analysis** - counts how many times each mustSupport element is populated across FHIR bundle instances
- **TSV output** - generates tab-separated files for easy analysis in spreadsheet applications

## Requirements

- Python 3.7+
- FHIR packages in npm format (stored in `~/.fhir/packages/`)

## Installation

1. Clone or download this repository
2. Ensure your FHIR packages are available in the standard FHIR package cache (`~/.fhir/packages/`)
3. Create an `instances` folder in the project directory if you want to analyze instance usage

## Configuration

The tool uses a configuration file at `config/config.json`:

```json
{
  "init": [
    {
      "mode": "dirty",
      "endpoint": "https://tx.dev.hl7.org.au/fhir"
    }
  ],
  "fhir-package-cache": "/Users/username/.fhir/packages",
  "instances-directory": "",
  "packages": [
    {
      "name": "hl7.fhir.au.ereq",
      "version": "1.0.0-ballot",
      "title": "AU eRequesting Implementation Guide"
    }
  ]
}
```

### Configuration Options

- **`init`**: Initialization settings
  - `mode`: Either "clean" (removes and re-copies packages) or "dirty" (uses existing local packages)
  - `endpoint`: FHIR terminology server endpoint
- **`fhir-package-cache`**: Path to your local FHIR package cache (typically `~/.fhir/packages/`)
- **`instances-directory`**: Path to folder containing FHIR instance files for analysis
  - Leave empty (`""`) to use the default `instances/` folder in the project directory
  - Set to an absolute or relative path to use a custom location (e.g., `"/path/to/test-data"`)
- **`packages`**: Array of FHIR packages to analyze
  - `name`: Package identifier
  - `version`: Package version
  - `title`: Descriptive title

## Usage

### Basic Usage

```bash
python main.py
```

This will:
1. Load FHIR packages specified in the configuration
2. Extract all mustSupport elements from Structure Definitions
3. If an `instances/` folder exists, analyze FHIR bundles for element usage
4. Generate a TSV report with the results

### Instance Analysis

To analyze how frequently mustSupport elements are used:

**Option 1: Using the default instances folder**
1. Create an `instances/` folder in the project directory
2. Place FHIR Bundle JSON files in this folder
3. Run the tool - it will automatically analyze these instances

**Option 2: Using a custom instances directory**
1. Set the `instances-directory` path in `config/config.json`
2. Place FHIR Bundle JSON files in that directory
3. Run the tool - it will analyze instances from the configured location

The tool will:
- Parse each JSON file as a FHIR Bundle
- Extract all resources from bundle entries
- Check each mustSupport element against matching resources
- Count how many times each element is populated

## Output

The tool generates a TSV file with the following columns:

| Column | Description |
|--------|-------------|
| Resource Type | The FHIR resource type (e.g., ServiceRequest, Patient) |
| Profile Name | The title of the Structure Definition profile |
| Element | The FHIR element path, including extension names where applicable |
| Cardinality | The min..max cardinality constraints (e.g., 0..1, 1..*, 0..*) |
| Use Count | Number of times the element was found populated in instance files |

### Example Output

```
Resource Type	Profile Name	Element	Cardinality	Use Count
ServiceRequest	AU eRequesting Diagnostic Request	ServiceRequest.identifier	0..1	4
ServiceRequest	AU eRequesting Diagnostic Request	ServiceRequest.extension:statusReason	0..1	0
Patient	AU Core Patient	Patient.name	1..*	2
```

## Extension Handling

The tool properly handles FHIR extensions:

- **Named extensions**: Displayed as `ResourceType.extension:extensionName`
- **Slice detection**: Uses the `sliceName` attribute from Structure Definitions
- **URL matching**: Falls back to URL-based matching for extension identification

## File Structure

```
ms-find/
├── main.py              # Main script
├── getter.py            # FHIR package retrieval utilities
├── utils.py             # Utility functions
├── config/
│   └── config.json      # Configuration file
├── instances/           # Optional: FHIR bundle instances for analysis
│   ├── bundle1.json
│   └── bundle2.json
└── README.md
```

## Logging

The tool generates detailed logs in the configured output directory under `logs/`. Log files include:
- Package loading information
- Structure Definition processing details
- Instance analysis results
- Error messages and warnings

## Error Handling

The tool includes robust error handling for:
- Missing or invalid FHIR packages
- Malformed JSON files
- Missing configuration files
- File system permission issues

## Examples

### Analyzing AU eRequesting Implementation Guide

1. Ensure `hl7.fhir.au.ereq` package is installed in `~/.fhir/packages/`
2. Update `config/config.json` with the package name
3. Run `python main.py`

### With Instance Analysis

1. Create `instances/` folder
2. Add FHIR Bundle JSON files
3. Run `python main.py`
4. Review the Use Count column in the output TSV

## Troubleshooting

**Package not found errors:**
- Verify FHIR packages are in `~/.fhir/packages/`
- Check package names in configuration match exactly

**No instances analyzed:**
- Ensure `instances/` folder exists
- Verify JSON files are valid FHIR Bundles
- Check log files for parsing errors

**Empty output:**
- Verify Structure Definitions contain mustSupport elements
- Check that differential or snapshot sections exist in the profiles

## Contributing

This tool is designed for FHIR Implementation Guide analysis. Contributions welcome for:
- Additional output formats
- Enhanced element path parsing
- Performance improvements
- Additional FHIR version support

## License

[Add your license information here]
