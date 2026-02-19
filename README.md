# AsyncAPI Payload Validator

[![PyPI version](https://badge.fury.io/py/asyncapi-payload-validator.svg)](https://badge.fury.io/py/asyncapi-payload-validator)
[![Python Support](https://img.shields.io/pypi/pyversions/asyncapi-payload-validator.svg)](https://pypi.org/project/asyncapi-payload-validator/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A comprehensive Python tool for validating JSON message payloads against AsyncAPI specifications. Performs detailed JSON schema validation including type checking, constraints, patterns, enums, and composition rules.

## Features

✅ **Comprehensive Validation**
- Type checking with lenient coercion (string numbers, booleans)
- Required field validation
- String constraints (minLength, maxLength, pattern)
- Numeric constraints (minimum, maximum, multipleOf)
- Enum validation
- Composition rules (oneOf, anyOf, allOf)
- Additional properties handling

✅ **Developer-Friendly**
- Detailed HTML reports with line-by-line source highlighting
- Clear error messages with path resolution
- Supports AsyncAPI 2.x and 3.x specifications
- Works with both YAML and JSON spec files

✅ **Flexible Usage**
- Command-line tool for CI/CD integration
- Python library for programmatic use
- GitHub Actions integration ready

## Installation

### From PyPI (Recommended)

```bash
pip install asyncapi-payload-validator
```

### From Source

```bash
git clone https://github.com/ingka-group/asyncapi-payload-validator.git
cd  asyncapi-payload-validator
pip install .
```

### For Development

```bash
pip install -e ".[dev]"
```

## Quick Start

### Command Line

```bash
# Basic validation
asyncapi-validate payload.json asyncapi-spec.yaml

# Generate HTML report
asyncapi-validate payload.json asyncapi-spec.yaml --html-report report.html

# Validate specific message by ID
asyncapi-validate payload.json asyncapi-spec.yaml --message-id UserSignedUp
```

### Jinja2 Template Support

The validator supports Jinja2 templates in JSON payloads, enabling validation of template files before rendering with production data.

#### Structural Validation (No Context)
Validate template structure without rendering - checks that required keys are present:

```bash
# Validate template structure only
asyncapi-validate event-template.json asyncapi-spec.yaml --render-jinja2
```

**Template example** (`event-template.json`):
```json
{
  "eventId": "{{event_id}}",
  "timestamp": "{{timestamp}}",
  "userData": {{user_data}},
  "metadata": {
    "source": "{{source_system}}",
    "version": "1.0"
  }
}
```

**Note:** Objects and arrays are automatically serialized with `| tojson` filter - no need to add it manually!

**What's validated:**
- ✅ Required keys are present in template
- ✅ JSON structure is valid
- ✅ No extra attributes
- ⏭️ Types, patterns, enums, numeric constraints **skipped** (can't validate template variables)

#### Full Validation (With Context)
Render template with context and perform complete validation:

```bash
# Validate rendered template
asyncapi-validate event-template.json asyncapi-spec.yaml \
  --render-jinja2 \
  --jinja2-context context.json
```

**Context file** (`context.json`):
```json
{
  "event_id": "evt-12345",
  "timestamp": "2024-01-15T10:30:00Z",
  "user_data": {
    "userId": "user-789",
    "email": "user@example.com"
  },
  "source_system": "api-gateway"
}
```

**What's validated:**
- ✅ All structural checks (keys, structure)
- ✅ Type validation (rendered values)
- ✅ Pattern validation (regex matches)
- ✅ Enum validation
- ✅ Numeric constraints
- ✅ All other AsyncAPI schema rules

### Example Output

#### ✅ Passing Validation

When your payload matches the AsyncAPI schema perfectly:

```
➕ Attributes in JSON but not in YAML:
    ✔  None

❌ Attributes with type mismatches:
    ✔  None

🚫 Required attributes in YAML but missing in JSON:
    ✔  None

↔️  String length violations (minLength/maxLength):
    ✔  None

#️⃣  Pattern violations:
    ✔  None

✅ Enum violations:
    ✔  None

🔢 Numeric constraint violations:
    ✔  None

🧩 Composition (oneOf/anyOf/allOf) violations:
    ✔  None

✅ RESULT: PASS
```

**Exit code**: `0` (success)

---

#### ❌ Failing Validation

When violations are detected:

```
➕ Attributes in JSON but not in YAML:
    ⚠️  metadata.extraField: attribute not declared
    ⚠️  unknownProperty: attribute not declared

❌ Attributes with type mismatches:
    ✖️  userId: expected string, got number
    ✖️  isActive: expected boolean, got string

🚫 Required attributes in YAML but missing in JSON:
    ⚠️  email: required but missing
    ⚠️  eventType: required but missing

↔️  String length violations (minLength/maxLength):
    ✖️  username: length 2 violates minLength 3

#️⃣  Pattern violations:
    ✖️  email: value 'invalid-email' does not match pattern ^[\w\.-]+@[\w\.-]+\.\w+$
    ✖️  phoneNumber: value 'abc123' does not match pattern ^\+?[1-9]\d{1,14}$

✅ Enum violations:
    ✖️  status: value 'pending' not in enum [active, inactive, suspended]
    ✖️  role: value 'superadmin' not in enum [user, admin, guest]

🔢 Numeric constraint violations:
    ✖️  age: value 5 is below minimum 18
    ✖️  count: value 7 is not a multiple of 5
    ✖️  price: value 10001 exceeds maximum 10000

🧩 Composition (oneOf/anyOf/allOf) violations:
    ✖️  contactInfo: oneOf expects exactly 1 match, got 0 matches

❌ RESULT: FAIL
```

**Exit code**: `1` (failure)

---

#### 📄 HTML Report Generated

When using `--html-report`:

```
➕ Attributes in JSON but not in YAML:
    ⚠️  metadata.extraField: attribute not declared

❌ Attributes with type mismatches:
    ✖️  userId: expected string, got number

🚫 Required attributes in YAML but missing in JSON:
    ⚠️  email: required but missing

... (additional violations) ...

📄 HTML report written to report.html

❌ RESULT: FAIL
```

The HTML report includes:
- 📊 Visual summary with violation counts
- 🔍 Line-by-line code context from both payload and spec
- 🎨 Syntax-highlighted source code snippets
- 📱 Responsive design for easy viewing

---

### Python Library (Programmatic Usage)

The simplest way to use the validator programmatically is with the `validate_payload()` function:

```python
import json
import yaml
from pathlib import Path
from asyncapi_payload_validator import validate_payload

# Load your payload and spec
payload = json.loads(Path('payload.json').read_text())
spec = yaml.safe_load(Path('asyncapi.yaml').read_text())

# Validate!
result = validate_payload(payload, spec)

# Check if valid
if result['valid']:
    print("✅ Validation passed!")
else:
    print(f"❌ Validation failed with {result['summary']['total_violations']} violation(s)")
    
    # Show summary
    for category, count in result['summary'].items():
        if count > 0 and category != 'total_violations':
            print(f"  • {category}: {count}")
    
    # Show detailed violations
    for category, violations in result['violations'].items():
        if violations:
            print(f"\n{category}:")
            for violation in violations:
                print(f"  - {violation}")
```

**Output:**
```
❌ Validation failed with 5 violation(s)
  • extra_attributes: 1
  • type_mismatches: 1
  • missing_required: 2
  • pattern_violations: 1

extra_attributes:
  - metadata.extraField

type_mismatches:
  - userId: expected string, got number

missing_required:
  - email
  - eventType

pattern_violations:
  - email: value 'invalid-email' does not match pattern ^[\w\.-]+@[\w\.-]+\.\w+$
```

### Validate Specific Message

```python
from asyncapi_payload_validator import validate_payload

# Validate against a specific message ID
result = validate_payload(
    payload_data=payload,
    asyncapi_spec=spec,
    message_id='UserSignedUp'  # Specify which message schema to use
)
```

### Return Value Structure

```python
{
    'valid': False,  # True if no violations
    'violations': {
        'extra_attributes': ['metadata.extraField'],
        'type_mismatches': ['userId: expected string, got number'],
        'missing_required': ['email', 'eventType'],
        'length_violations': [],
        'pattern_violations': ['email: value ...'],
        'enum_violations': [],
        'numeric_violations': [],
        'composition_violations': []
    },
    'summary': {
        'extra_attributes': 1,
        'type_mismatches': 1,
        'missing_required': 2,
        'length_violations': 0,
        'pattern_violations': 1,
        'enum_violations': 0,
        'numeric_violations': 0,
        'composition_violations': 0,
        'total_violations': 5
    }
}
```

### Jinja2 Template Validation (Python API)

#### Structural Validation (No Context)
```python
from jinja2 import Template
import json
from asyncapi_payload_validator import validate_payload

# Load template (without rendering)
template_text = Path('event-template.json').read_text()

# For structural validation, replace Jinja2 variables with null
import re
cleaned_json = re.sub(r'{{\s*[^}]+\s*}}', 'null', template_text)
template_payload = json.loads(cleaned_json)

# Validate structure only
result = validate_payload(template_payload, spec)

# Note: This validates keys exist, but skips value type/pattern checks
# Best for CI/CD template linting before context is available
```

#### Full Validation (With Context)
```python
from jinja2 import Template
import json
import re
from asyncapi_payload_validator import validate_payload

# Load template and context
template_text = Path('event-template.json').read_text()
context = json.loads(Path('context.json').read_text())

# Auto-add | tojson filter for object/array variables
for var_name, var_value in context.items():
    if isinstance(var_value, (dict, list)):
        pattern = r'\{\{\s*' + re.escape(var_name) + r'\s*(?!\|)\}\}'
        replacement = '{{' + var_name + ' | tojson}}'
        template_text = re.sub(pattern, replacement, template_text)

# Render template
template = Template(template_text)
rendered_json = template.render(**context)
payload = json.loads(rendered_json)

# Validate rendered payload
result = validate_payload(payload, spec)

if result['valid']:
    print("✅ Template renders to valid payload!")
else:
    print(f"❌ Rendered payload has {result['summary']['total_violations']} violation(s)")
```

### Advanced: CLI-Style Usage

If you prefer using the CLI behavior programmatically:

```python
from asyncapi_payload_validator.validator import main
import sys

# Set arguments
sys.argv = [
    'validator',
    'payload.json',
    'asyncapi-spec.yaml',
    '--html-report',
    'validation-report.html'
]

# Run validation (exits with code 0 or 1)
main()
```

### Advanced: Individual Validation Functions

For fine-grained control, import specific validation functions:

```python
import json
import yaml
from pathlib import Path
from asyncapi_payload_validator.validator import (
    get_all_json_paths,
    get_all_yaml_paths,
    get_required_yaml_paths,
    check_enum_violations,
    check_numeric_violations,
    check_pattern_violations,
)

# Load your payload and spec
payload = json.loads(Path('payload.json').read_text())
spec = yaml.safe_load(Path('asyncapi.yaml').read_text())

# Get paths and types
json_paths, json_types = get_all_json_paths(payload)
yaml_paths, yaml_types = get_all_yaml_paths(spec)
required_paths = get_required_yaml_paths(spec)

# Check specific violations
enum_violations = check_enum_violations(payload, {"status": ["active", "inactive"]})
pattern_violations = check_pattern_violations(payload, {"email": r"^[\w\.-]+@[\w\.-]+\.\w+$"})

print(f"Extra fields: {json_paths - yaml_paths}")
print(f"Missing required: {required_paths - json_paths}")
```

## Usage Examples

### CI/CD Integration

#### GitHub Actions

```yaml
name: Validate AsyncAPI Payloads

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install validator
        run: pip install asyncapi-payload-validator
      
      - name: Validate payload
        run: |
          asyncapi-validate \
            tests/fixtures/payload.json \
            asyncapi-spec.yaml \
            --html-report validation-report.html
      
      - name: Upload report
        if: failure()
        uses: actions/upload-artifact@v3
        with:
          name: validation-report
          path: validation-report.html
```

#### GitLab CI

```yaml
validate-payloads:
  image: python:3.11
  script:
    - pip install asyncapi-payload-validator
    - asyncapi-validate payload.json asyncapi.yaml --html-report report.html
  artifacts:
    when: always
    paths:
      - report.html
```

### Validation Rules

The validator checks:

1. **Extra Attributes**: Fields in payload not declared in schema
2. **Type Mismatches**: Incorrect data types (with lenient coercion)
3. **Missing Required**: Required fields absent from payload
4. **Length Violations**: String length constraints (minLength/maxLength)
5. **Pattern Violations**: Regex pattern mismatches
6. **Enum Violations**: Values not in allowed enum list
7. **Numeric Violations**: Number constraint violations (min/max/multipleOf)
8. **Composition Violations**: oneOf/anyOf/allOf rule failures

### Real-World Example

#### ❌ Failing Payload

```json
{
  "eventType": "OrderPlaced",
  "orderId": 12345,
  "customerEmail": "not-an-email",
  "amount": 5,
  "status": "pending",
  "extraField": "should not be here"
}
```

#### ✅ Expected Schema

```yaml
payload:
  type: object
  required:
    - eventType
    - orderId
    - customerEmail
    - amount
    - currency
  properties:
    eventType:
      type: string
      enum: [OrderPlaced, OrderCancelled]
    orderId:
      type: string
      pattern: '^ORD-\d{6}$'
    customerEmail:
      type: string
      format: email
    amount:
      type: number
      minimum: 10
      maximum: 10000
    currency:
      type: string
      enum: [USD, EUR, GBP]
    status:
      type: string
      enum: [confirmed, processing]
```

#### 🔍 Validation Results

```
➕ Attributes in JSON but not in YAML:
    ⚠️  extraField: attribute not declared

❌ Attributes with type mismatches:
    ✖️  orderId: expected string, got number

🚫 Required attributes in YAML but missing in JSON:
    ⚠️  currency: required but missing

↔️  String length violations (minLength/maxLength):
    ✔  None

#️⃣  Pattern violations:
    ✖️  orderId: value '12345' does not match pattern '^ORD-\d{6}$'
    ✖️  customerEmail: value 'not-an-email' does not match email format

✅ Enum violations:
    ✖️  status: value 'pending' not in enum [confirmed, processing]

🔢 Numeric constraint violations:
    ✖️  amount: value 5 is below minimum 10

🧩 Composition (oneOf/anyOf/allOf) violations:
    ✔  None

❌ RESULT: FAIL
```

#### ✅ Corrected Payload

```json
{
  "eventType": "OrderPlaced",
  "orderId": "ORD-123456",
  "customerEmail": "customer@example.com",
  "amount": 99.99,
  "currency": "USD",
  "status": "confirmed"
}
```

**Validation Result**: `✅ RESULT: PASS`

---

### Understanding the Output

The validator uses clear icons to categorize findings:

| Icon | Category | Severity | Description |
|------|----------|----------|-------------|
| ➕ | Extra Attributes | WARN | Fields in your payload not defined in schema |
| ❌ | Type Mismatches | ERROR | Wrong data types (e.g., number instead of string) |
| 🚫 | Missing Required | ERROR | Required fields not present in payload |
| ↔️ | Length Violations | WARN | String too short/long (minLength/maxLength) |
| #️⃣ | Pattern Violations | ERROR | String doesn't match regex pattern |
| ✅ | Enum Violations | ERROR | Value not in allowed list |
| 🔢 | Numeric Violations | ERROR | Number constraints violated (min/max/multipleOf) |
| 🧩 | Composition Violations | ERROR | oneOf/anyOf/allOf rules not satisfied |

**Status Indicators:**
- `✔ None` - No violations in this category (green check)
- `⚠️` - Warning-level violation
- `✖️` - Error-level violation

---

---

### Quick Comparison: Pass vs Fail

| Aspect | ✅ Passing Example | ❌ Failing Example |
|--------|-------------------|-------------------|
| **Output** | All categories show `✔ None` | Categories show `⚠️` or `✖️` violations |
| **Exit Code** | `0` | `1` |
| **Console** | `✅ RESULT: PASS` in green | `❌ RESULT: FAIL` in red |
| **HTML Report** | Optional with `--html-report` | Optional with `--html-report` |
| **CI/CD** | Pipeline continues ✓ | Pipeline fails ✗ |

---

### Example Payload

```json
{
  "eventType": "UserSignedUp",
  "userId": "12345",
  "email": "user@example.com",
  "metadata": {
    "source": "mobile-app",
    "version": "2.1.0"
  }
}
```

### Example AsyncAPI Spec

```yaml
asyncapi: 2.6.0
info:
  title: User Events API
  version: 1.0.0

channels:
  user/signedup:
    subscribe:
      message:
        messageId: UserSignedUp
        payload:
          type: object
          required:
            - eventType
            - userId
            - email
          properties:
            eventType:
              type: string
              enum: [UserSignedUp, UserDeleted]
            userId:
              type: string
              pattern: '^\d+$'
            email:
              type: string
              format: email
            metadata:
              type: object
              additionalProperties: true
```

## HTML Report Features

The generated HTML report includes:

- ✅ **Summary Dashboard**: Pass/fail status with violation counts
- 🔍 **Detailed Findings**: Each violation with:
  - Severity level (ERROR/WARN)
  - Attribute path
  - Expected vs actual values
  - Line numbers in both payload and spec
  - Source code context (2 lines before/after)
- 📊 **Categorized Results**: Grouped by violation type
- 🎨 **Syntax Highlighting**: Easy-to-read code snippets
- 📱 **Responsive Design**: Works on desktop and mobile

## Advanced Features

### Message ID Selection

When your AsyncAPI spec has multiple message types:

```bash
asyncapi-validate payload.json spec.yaml --message-id UserSignedUp
```

This validates only against the `UserSignedUp` message schema.

### Lenient Type Coercion

The validator is lenient with type mismatches:

- `"42"` (string) → accepted for `integer` type
- `"3.14"` (string) → accepted for `number` type
- `"true"` (string) → accepted for `boolean` type
- `[true]` (single-element array) → unwrapped for `boolean`

### Composition Handling

Supports all JSON Schema composition keywords:

```yaml
oneOf:  # Exactly one schema must match
  - properties:
      type: { const: "email" }
      address: { type: string, format: email }
  - properties:
      type: { const: "phone" }
      number: { type: string, pattern: '^\+?[1-9]\d{1,14}$' }

anyOf:  # At least one schema must match
  - required: [email]
  - required: [phone]

allOf:  # All schemas must match (merge properties)
  - properties:
      id: { type: string }
  - required: [id]
```

## Exit Codes

- `0`: Validation **passed** (no violations)
- `1`: Validation **failed** (violations found)
- `2`: Error (invalid arguments, file not found, etc.)
- `130`: Cancelled by user (Ctrl+C)

## Troubleshooting

### "ModuleNotFoundError: No module named 'asyncapi_payload_validator'"

Make sure you installed the package:
```bash
pip install asyncapi-payload-validator
```

### "FileNotFoundError: [Errno 2] No such file or directory"

Check file paths are correct:
```bash
ls -la payload.json asyncapi.yaml
```

### "Invalid YAML/JSON syntax"

Validate your files separately:
```bash
python -m json.tool payload.json
python -c "import yaml; yaml.safe_load(open('asyncapi.yaml'))"
```

### HTML Report Not Generated

Ensure Jinja2 is installed:
```bash
pip install Jinja2>=3.0
```

## Development

### Running Tests

**Note**: Due to a known issue with pytest's output capture mechanism on Windows (affects Python 3.10+), tests must be run in WSL or Linux environments for full compatibility.

#### On Linux/WSL (Recommended)
```bash
pytest tests/
pytest --cov=asyncapi_payload_validator --cov-report=html
```

### Code Formatting

```bash
black asyncapi_payload_validator/
flake8 asyncapi_payload_validator/
mypy asyncapi_payload_validator/
```

### Building Package

```bash
python -m build
twine check dist/*
```

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENCE.md) file for details.

## Acknowledgments

- Inspired by [AsyncAPI Initiative](https://www.asyncapi.com/)
- Uses [PyYAML](https://pyyaml.org/) and [Jinja2](https://jinja.palletsprojects.com/)

## Links

- **PyPI**: https://pypi.org/project/asyncapi-payload-validator/
- **GitHub**: https://github.com/ingka-group/asyncapi-payload-validator
- **Issues**: https://github.com/ingka-group/asyncapi-payload-validator/issues
- **AsyncAPI Spec**: https://v2.asyncapi.com/docs/reference/specification/v2.6.0

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

---
