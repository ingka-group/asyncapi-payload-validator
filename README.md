# AsyncAPI Payload Validator

[![PyPI version](https://badge.fury.io/py/asyncapi-payload-validator.svg)](https://badge.fury.io/py/asyncapi-payload-validator)
[![Python Support](https://img.shields.io/pypi/pyversions/asyncapi-payload-validator.svg)](https://pypi.org/project/asyncapi-payload-validator/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python tool for validating JSON message payloads against AsyncAPI specifications. Performs detailed JSON Schema validation including type checking, constraints, patterns, enums, and composition rules.

## Features

- **Comprehensive validation** - types, required fields, string length, patterns, enums, numeric constraints, oneOf/anyOf/allOf
- **Lenient type coercion** - string numbers and booleans accepted where appropriate
- **AsyncAPI 2.x and 3.x** - supports both specification versions
- **HTML reports** - detailed reports with line-by-line source highlighting
- **Jinja2 templates** - validate template structure before rendering
- **CI/CD ready** - exit codes, GitHub Actions and GitLab CI examples

## Installation

```bash
pip install asyncapi-payload-validator
```

<details>
<summary>Install from source</summary>

```bash
git clone https://github.com/ingka-group/asyncapi-payload-validator.git
cd asyncapi-payload-validator
pip install .
```

For development: `pip install -e ".[dev]"`
</details>

## Quick Start

### Command Line

```bash
# Basic validation
asyncapi-validate payload.json asyncapi-spec.yaml

# Generate HTML report
asyncapi-validate payload.json asyncapi-spec.yaml --html-report report.html

# Validate specific message by ID
asyncapi-validate payload.json asyncapi-spec.yaml --message-id UserSignedUp

# Validate Jinja2 template structure
asyncapi-validate template.json spec.yaml --render-jinja2

# Validate rendered template with context
asyncapi-validate template.json spec.yaml --render-jinja2 --jinja2-context context.json
```

### Python Library

```python
import json, yaml
from pathlib import Path
from asyncapi_payload_validator import validate_payload

payload = json.loads(Path('payload.json').read_text())
spec = yaml.safe_load(Path('asyncapi.yaml').read_text())

result = validate_payload(payload, spec)

if result['valid']:
    print("Validation passed!")
else:
    print(f"{result['summary']['total_violations']} violation(s)")
    for category, violations in result['violations'].items():
        for v in violations:
            print(f"  - {v}")
```

See [Python API Reference](docs/python-api.md) for the full API, return value structure, and advanced usage.

## Validation Rules

| Category | Description |
|----------|-------------|
| Extra Attributes | Fields in payload not declared in schema |
| Type Mismatches | Incorrect data types (with lenient coercion) |
| Missing Required | Required fields absent from payload |
| Length Violations | String minLength/maxLength constraints |
| Pattern Violations | Regex pattern mismatches |
| Enum Violations | Values not in allowed enum list |
| Numeric Violations | min/max/multipleOf constraints |
| Composition Violations | oneOf/anyOf/allOf rule failures |

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Validation passed |
| `1` | Validation failed (violations found) |
| `2` | Error (invalid arguments, file not found) |
| `130` | Cancelled by user (Ctrl+C) |

## Documentation

| Guide | Description |
|-------|-------------|
| [Examples and Output](docs/examples.md) | Output format, real-world examples, icon reference |
| [Python API](docs/python-api.md) | Programmatic usage, return structure, individual functions |
| [CI/CD Integration](docs/ci-cd.md) | GitHub Actions, GitLab CI examples |
| [Advanced Features](docs/advanced.md) | Jinja2 templates, type coercion, composition, troubleshooting |

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT - see [LICENCE.md](LICENCE.md) for details.

## Links

- **PyPI**: https://pypi.org/project/asyncapi-payload-validator/
- **GitHub**: https://github.com/ingka-group/asyncapi-payload-validator
- **Issues**: https://github.com/ingka-group/asyncapi-payload-validator/issues
- **AsyncAPI Spec**: https://v2.asyncapi.com/docs/reference/specification/v2.6.0
- **Changelog**: [CHANGELOG.md](CHANGELOG.md)
