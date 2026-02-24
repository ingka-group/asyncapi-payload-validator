# Python API Reference

Use the validator as a Python library for programmatic validation.

## Basic Usage

```python
import json
import yaml
from pathlib import Path
from asyncapi_payload_validator import validate_payload

# Load your payload and spec
payload = json.loads(Path('payload.json').read_text())
spec = yaml.safe_load(Path('asyncapi.yaml').read_text())

# Validate
result = validate_payload(payload, spec)

if result['valid']:
    print("✅ Validation passed!")
else:
    print(f"❌ {result['summary']['total_violations']} violation(s)")
    
    for category, count in result['summary'].items():
        if count > 0 and category != 'total_violations':
            print(f"  • {category}: {count}")
    
    for category, violations in result['violations'].items():
        if violations:
            print(f"\n{category}:")
            for violation in violations:
                print(f"  - {violation}")
```

## Validate Specific Message

```python
result = validate_payload(
    payload_data=payload,
    asyncapi_spec=spec,
    message_id='UserSignedUp'
)
```

## Return Value Structure

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

## Jinja2 Template Validation

### Structural Validation (No Context)

```python
from jinja2 import Template
import json
import re
from pathlib import Path
from asyncapi_payload_validator import validate_payload

template_text = Path('event-template.json').read_text()

# Replace Jinja2 variables with null for structural checks
cleaned_json = re.sub(r'{{\s*[^}]+\s*}}', 'null', template_text)
template_payload = json.loads(cleaned_json)

result = validate_payload(template_payload, spec)
# Validates keys exist, skips value type/pattern checks
```

### Full Validation (With Context)

```python
from jinja2 import Template
import json
import re
from pathlib import Path
from asyncapi_payload_validator import validate_payload

template_text = Path('event-template.json').read_text()
context = json.loads(Path('context.json').read_text())

# Auto-add | tojson filter for object/array variables
for var_name, var_value in context.items():
    if isinstance(var_value, (dict, list)):
        pattern = r'\{\{\s*' + re.escape(var_name) + r'\s*(?!\|)\}\}'
        replacement = '{{' + var_name + ' | tojson}}'
        template_text = re.sub(pattern, replacement, template_text)

template = Template(template_text)
rendered_json = template.render(**context)
payload = json.loads(rendered_json)

result = validate_payload(payload, spec)
```

## Advanced: CLI-Style Usage

```python
from asyncapi_payload_validator.validator import main
import sys

sys.argv = [
    'validator',
    'payload.json',
    'asyncapi-spec.yaml',
    '--html-report',
    'validation-report.html'
]

main()  # Exits with code 0 or 1
```

## Advanced: Individual Validation Functions

For fine-grained control:

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

payload = json.loads(Path('payload.json').read_text())
spec = yaml.safe_load(Path('asyncapi.yaml').read_text())

json_paths, json_types = get_all_json_paths(payload)
yaml_paths, yaml_types = get_all_yaml_paths(spec)
required_paths = get_required_yaml_paths(spec)

enum_violations = check_enum_violations(payload, {"status": ["active", "inactive"]})
pattern_violations = check_pattern_violations(payload, {"email": r"^[\w\.-]+@[\w\.-]+\.\w+$"})

print(f"Extra fields: {json_paths - yaml_paths}")
print(f"Missing required: {required_paths - json_paths}")
```
