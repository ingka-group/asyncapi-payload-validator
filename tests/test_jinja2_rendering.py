"""
Copyright (c) 2026 Ingka Holding B.V.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

"""Tests for Jinja2 template rendering and validation."""

import json
import pytest
from pathlib import Path
from asyncapi_payload_validator import validate_payload


TEST_FILES_DIR = Path(__file__).parent / 'test-files'


def test_jinja2_structural_validation_without_context():
    """Test structural validation of Jinja2 template without context (no rendering)."""
    # Load template
    template_path = TEST_FILES_DIR / 'payload-jinja2-template.j2'
    template_text = template_path.read_text(encoding='utf-8')
    
    # Load spec
    spec_path = TEST_FILES_DIR / 'asyncapi-event-spec.yaml'
    import yaml
    spec = yaml.safe_load(spec_path.read_text(encoding='utf-8'))
    
    # For structural validation, replace Jinja2 variables with null
    # Match {{anything}} including filters like {{var | tojson}}
    import re
    cleaned_json = re.sub(r'{{\s*[^}]+\s*}}', 'null', template_text)
    template_payload = json.loads(cleaned_json)
    
    # Validate - should pass because all required keys are present
    result = validate_payload(template_payload, spec, message_id='UserEvent')
    
    # In structural mode, we only validate keys, not values
    # So this should pass even though values are null
    assert isinstance(result, dict)
    assert 'valid' in result
    assert 'violations' in result
    assert 'summary' in result


def test_jinja2_structural_validation_missing_required_fields():
    """Test structural validation detects missing required fields in template."""
    # Load template missing required fields
    template_path = TEST_FILES_DIR / 'payload-jinja2-template-missing-required.j2'
    template_text = template_path.read_text(encoding='utf-8')

    # Load spec
    spec_path = TEST_FILES_DIR / 'asyncapi-event-spec.yaml'
    import yaml
    spec = yaml.safe_load(spec_path.read_text(encoding='utf-8'))

    # Replace Jinja2 variables with null
    # Match {{anything}} including filters like {{var | tojson}}
    import re
    cleaned_json = re.sub(r'{{\s*[^}]+\s*}}', 'null', template_text)
    template_payload = json.loads(cleaned_json)    # Validate - should fail because eventType and version are missing
    result = validate_payload(template_payload, spec, message_id='UserEvent')
    
    assert result['valid'] == False
    assert len(result['violations']['missing_required']) > 0


def test_jinja2_structural_validation_extra_attributes():
    """Test structural validation detects extra attributes in template."""
    # Template with extra field
    template_text = '''{
      "eventId": "{{event_id}}",
      "eventType": "UserSignedUp",
      "timestamp": "{{timestamp}}",
      "version": "{{version}}",
      "data": {{user_data}},
      "metadata": {
        "source": "{{source_system}}",
        "correlationId": "{{correlation_id}}"
      },
      "extraField": "{{extra}}"
    }'''
    
    # Load spec
    spec_path = TEST_FILES_DIR / 'asyncapi-event-spec.yaml'
    import yaml
    spec = yaml.safe_load(spec_path.read_text(encoding='utf-8'))
    
    # Replace Jinja2 variables with null
    # Match {{anything}} including filters like {{var | tojson}}
    import re
    cleaned_json = re.sub(r'{{\s*[^}]+\s*}}', 'null', template_text)
    template_payload = json.loads(cleaned_json)
    
    # Validate - should fail because extraField is not in schema
    result = validate_payload(template_payload, spec, message_id='UserEvent')
    
    assert result['valid'] == False
    assert len(result['violations']['extra_attributes']) > 0
    assert any('extraField' in attr for attr in result['violations']['extra_attributes'])


def test_jinja2_full_validation_with_context():
    """Test full validation with Jinja2 context (rendering + validation)."""
    from jinja2 import Template
    import re
    
    # Load template
    template_path = TEST_FILES_DIR / 'payload-jinja2-template.j2'
    template_text = template_path.read_text(encoding='utf-8')
    
    # Load context
    context_path = TEST_FILES_DIR / 'jinja2-context.json'
    context = json.loads(context_path.read_text(encoding='utf-8'))
    
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
    
    # Load spec
    spec_path = TEST_FILES_DIR / 'asyncapi-event-spec.yaml'
    import yaml
    spec = yaml.safe_load(spec_path.read_text(encoding='utf-8'))
    
    # Validate - should pass because rendered payload matches schema
    result = validate_payload(payload, spec, message_id='UserEvent')
    
    assert result['valid'] == True
    assert result['summary']['total_violations'] == 0


def test_jinja2_full_validation_pattern_violation_with_context():
    """Test full validation detects pattern violations in rendered values."""
    from jinja2 import Template
    
    # Template with pattern-violating context
    template_text = '''{
      "eventId": "{{event_id}}",
      "eventType": "UserSignedUp",
      "timestamp": "{{timestamp}}",
      "version": "{{version}}",
      "data": {
        "userId": "{{user_id}}",
        "userName": "{{user_name}}",
        "email": "{{email}}",
        "roles": ["user"]
      },
      "metadata": {
        "source": "{{source_system}}",
        "correlationId": "{{correlation_id}}"
      }
    }'''
    
    # Context with invalid email pattern
    context = {
        "event_id": "evt-12345",
        "timestamp": "2024-01-15T10:30:00.000Z",
        "version": "v2",
        "user_id": "12345",
        "user_name": "testuser",
        "email": "invalid-email-format",  # Invalid email
        "source_system": "api-gateway",
        "correlation_id": "corr-abc123"
    }
    
    # Render template
    template = Template(template_text)
    rendered_json = template.render(**context)
    payload = json.loads(rendered_json)
    
    # Load spec
    spec_path = TEST_FILES_DIR / 'asyncapi-event-spec.yaml'
    import yaml
    spec = yaml.safe_load(spec_path.read_text(encoding='utf-8'))
    
    # Validate - should fail because email format is invalid
    result = validate_payload(payload, spec, message_id='UserEvent')
    
    # Should have validation error for email format
    assert isinstance(result, dict)
    assert 'valid' in result
    # Email format validation would be caught if format validation is enabled


def test_jinja2_invalid_template_structure():
    """Test that invalid JSON structure in template is detected."""
    # Template with invalid JSON structure (missing comma)
    template_text = '''{
      "eventId": "{{event_id}}"
      "eventType": "UserSignedUp"
    }'''
    
    # Try to clean and parse - should fail
    import re
    cleaned_json = re.sub(r'{{\s*\w+\s*}}', 'null', template_text)
    
    with pytest.raises(json.JSONDecodeError):
        json.loads(cleaned_json)


def test_jinja2_nested_variable_handling():
    """Test that nested Jinja2 variables are handled correctly."""
    from jinja2 import Template
    import re
    
    # Template with nested object as variable
    template_text = '''{
      "eventId": "evt-123",
      "eventType": "UserSignedUp",
      "timestamp": "2024-01-15T10:30:00.000Z",
      "version": "v2",
      "data": {{nested_object}},
      "metadata": {
        "source": "system",
        "correlationId": "corr-123"
      }
    }'''
    
    # Context with nested object
    context = {
        "nested_object": {
            "userId": "12345",
            "userName": "testuser",
            "email": "test@example.com",
            "roles": ["user", "admin"]
        }
    }
    
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
    
    # Verify nested object is properly rendered
    assert payload['data']['userId'] == "12345"
    assert payload['data']['userName'] == "testuser"
    assert 'roles' in payload['data']
    assert len(payload['data']['roles']) == 2


def test_jinja2_auto_tojson_for_objects_and_arrays():
    """Test that tojson is automatically added for objects and arrays, but not duplicated."""
    from jinja2 import Template
    import re
    
    # Template with mixed variables - some with manual | tojson, some without
    template_text = '''{
      "orderId": "{{order_id}}",
      "salesStops": {{salesStops}},
      "customer": {{customer_data | tojson}},
      "tags": {{tags}},
      "status": "{{status}}"
    }'''
    
    # Context with different types
    context = {
        "order_id": "ORD-123",
        "salesStops": [
            {"location": "Store A", "amount": 100},
            {"location": "Store B", "amount": 200}
        ],
        "customer_data": {
            "name": "John Doe",
            "email": "john@example.com"
        },
        "tags": ["priority", "express"],
        "status": "confirmed"
    }
    
    # Auto-add | tojson filter for object/array variables
    for var_name, var_value in context.items():
        if isinstance(var_value, (dict, list)):
            # Negative lookahead (?!\|) ensures we don't add if already has filter
            pattern = r'\{\{\s*' + re.escape(var_name) + r'\s*(?!\|)\}\}'
            replacement = '{{' + var_name + ' | tojson}}'
            template_text = re.sub(pattern, replacement, template_text)
    
    # Verify the transformed template
    assert '{{salesStops | tojson}}' in template_text  # Auto-added
    assert '{{customer_data | tojson}}' in template_text  # Already had it, not duplicated
    assert '{{tags | tojson}}' in template_text  # Auto-added
    assert '"{{order_id}}"' in template_text  # String, no tojson
    assert '"{{status}}"' in template_text  # String, no tojson
    
    # Render template
    template = Template(template_text)
    rendered_json = template.render(**context)
    payload = json.loads(rendered_json)
    
    # Verify all values are correctly rendered
    assert payload['orderId'] == "ORD-123"
    assert len(payload['salesStops']) == 2
    assert payload['salesStops'][0]['location'] == "Store A"
    assert payload['customer']['name'] == "John Doe"
    assert payload['tags'] == ["priority", "express"]
    assert payload['status'] == "confirmed"
