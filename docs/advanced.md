# Advanced Features

## Jinja2 Template Support

Validate Jinja2 template files before rendering with production data.

### Structural Validation (No Context)

Checks that required keys are present without rendering the template:

```bash
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

> Objects and arrays are automatically serialized with `| tojson` filter — no need to add it manually.

**What's validated:**
- ✅ Required keys are present in template
- ✅ JSON structure is valid
- ✅ No extra attributes
- ⏭️ Types, patterns, enums, numeric constraints **skipped** (can't validate template variables)

### Full Validation (With Context)

Render template with context and perform complete validation:

```bash
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

---

## Message ID Selection

When your AsyncAPI spec has multiple message types:

```bash
asyncapi-validate payload.json spec.yaml --message-id UserSignedUp
```

This validates only against the `UserSignedUp` message schema.

---

## Lenient Type Coercion

The validator is lenient with type mismatches common in real-world payloads:

| Input | Accepted as |
|-------|-------------|
| `"42"` (string) | `integer` |
| `"3.14"` (string) | `number` |
| `"true"` (string) | `boolean` |
| `[true]` (single-element array) | `boolean` |

---

## Composition Handling

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

---

## HTML Report Features

The generated HTML report includes:

- ✅ **Summary Dashboard**: Pass/fail status with violation counts
- 🔍 **Detailed Findings**: Each violation with severity, attribute path, expected vs actual values, line numbers, and source code context
- 📊 **Categorized Results**: Grouped by violation type
- 🎨 **Syntax Highlighting**: Easy-to-read code snippets
- 📱 **Responsive Design**: Works on desktop and mobile

---

## Validation Rules

The validator checks these categories:

1. **Extra Attributes** — Fields in payload not declared in schema
2. **Type Mismatches** — Incorrect data types (with lenient coercion)
3. **Missing Required** — Required fields absent from payload
4. **Length Violations** — String length constraints (minLength/maxLength)
5. **Pattern Violations** — Regex pattern mismatches
6. **Enum Violations** — Values not in allowed enum list
7. **Numeric Violations** — Number constraint violations (min/max/multipleOf)
8. **Composition Violations** — oneOf/anyOf/allOf rule failures

---

## Troubleshooting

### "ModuleNotFoundError: No module named 'asyncapi_payload_validator'"

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

---

## Development

### Running Tests

> **Note**: Due to a known issue with pytest's output capture mechanism on Windows (affects Python 3.10+), tests should be run in WSL or Linux environments for full compatibility.

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
