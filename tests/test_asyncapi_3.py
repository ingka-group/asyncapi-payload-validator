"""
Copyright (c) 2026 Ingka Holding B.V.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

"""Tests for AsyncAPI 3.0 support."""

import json
import yaml
import pytest
from pathlib import Path
from asyncapi_payload_validator import validate_payload
from asyncapi_payload_validator.validator import find_payload_schema


@pytest.fixture
def asyncapi_3_spec():
    """Load AsyncAPI 3.0 test spec."""
    spec_path = Path(__file__).parent / 'test-files' / 'asyncapi-3.0-spec.yaml'
    return yaml.safe_load(spec_path.read_text())


@pytest.fixture
def valid_payload_v3():
    """Load valid payload for AsyncAPI 3.0."""
    payload_path = Path(__file__).parent / 'test-files' / 'payload-asyncapi-3.0-valid.json'
    return json.loads(payload_path.read_text())


@pytest.fixture
def invalid_payload_v3():
    """Load invalid payload for AsyncAPI 3.0."""
    payload_path = Path(__file__).parent / 'test-files' / 'payload-asyncapi-3.0-invalid.json'
    return json.loads(payload_path.read_text())


def test_asyncapi_3_version_detection(asyncapi_3_spec):
    """Test that AsyncAPI 3.0 is correctly detected."""
    assert asyncapi_3_spec.get('asyncapi') == '3.0.0'


def test_asyncapi_3_find_payload_schema(asyncapi_3_spec):
    """Test finding payload schema in AsyncAPI 3.0 structure."""
    schema = find_payload_schema(asyncapi_3_spec, preferred_message_id='UserSignedUp')
    
    assert schema is not None
    assert isinstance(schema, dict)
    assert schema.get('type') == 'object'
    assert 'properties' in schema
    assert 'id' in schema['properties']
    assert 'email' in schema['properties']


def test_asyncapi_3_operations_structure(asyncapi_3_spec):
    """Test AsyncAPI 3.0 operations structure is correctly parsed."""
    assert 'operations' in asyncapi_3_spec
    assert 'sendUserEvent' in asyncapi_3_spec['operations']
    
    operation = asyncapi_3_spec['operations']['sendUserEvent']
    assert operation.get('action') == 'send'
    assert 'messages' in operation


def test_asyncapi_3_channels_structure(asyncapi_3_spec):
    """Test AsyncAPI 3.0 channels structure is correctly parsed."""
    assert 'channels' in asyncapi_3_spec
    assert 'userChannel' in asyncapi_3_spec['channels']
    
    channel = asyncapi_3_spec['channels']['userChannel']
    assert 'address' in channel
    assert 'messages' in channel


def test_asyncapi_3_valid_payload(valid_payload_v3, asyncapi_3_spec):
    """Test validation passes for valid AsyncAPI 3.0 payload."""
    result = validate_payload(valid_payload_v3, asyncapi_3_spec, message_id='UserSignedUp')
    
    assert result['valid'] is True
    assert result['summary']['total_violations'] == 0


def test_asyncapi_3_invalid_payload(invalid_payload_v3, asyncapi_3_spec):
    """Test validation detects violations in AsyncAPI 3.0 payload."""
    result = validate_payload(invalid_payload_v3, asyncapi_3_spec, message_id='UserSignedUp')
    
    assert result['valid'] is False
    assert result['summary']['total_violations'] >= 4  # We expect at least 4 violations
    
    # Should detect type mismatch (id should be string, not number)
    assert result['summary']['type_mismatches'] > 0
    
    # Should detect length violation (username too short)
    assert result['summary']['length_violations'] > 0
    
    # Should detect numeric violation (age below minimum 18)
    assert result['summary']['numeric_violations'] > 0
    
    # Should detect enum violation (status 'deleted' not in enum)
    assert result['summary']['enum_violations'] > 0


def test_asyncapi_3_without_message_id(valid_payload_v3, asyncapi_3_spec):
    """Test AsyncAPI 3.0 validation without specifying message_id."""
    result = validate_payload(valid_payload_v3, asyncapi_3_spec)
    
    assert result['valid'] is True
    assert result['summary']['total_violations'] == 0


def test_asyncapi_3_vs_2_compatibility():
    """Test that both AsyncAPI 2.x and 3.x work correctly."""
    # AsyncAPI 2.x spec
    v2_spec_path = Path(__file__).parent / 'test-files' / 'asyncapi-2.6-spec.yaml'
    v2_spec = yaml.safe_load(v2_spec_path.read_text())
    
    # AsyncAPI 3.x spec
    v3_spec_path = Path(__file__).parent / 'test-files' / 'asyncapi-3.0-spec.yaml'
    v3_spec = yaml.safe_load(v3_spec_path.read_text())
    
    # Both should be dictionaries
    assert isinstance(v2_spec, dict)
    assert isinstance(v3_spec, dict)
    
    # Both should have asyncapi version
    assert 'asyncapi' in v2_spec
    assert 'asyncapi' in v3_spec
    
    # Versions should be different
    assert not v2_spec['asyncapi'].startswith('3.')
    assert v3_spec['asyncapi'].startswith('3.')


def test_asyncapi_3_message_reference_resolution(asyncapi_3_spec):
    """Test that message references in AsyncAPI 3.0 are correctly resolved."""
    # The operations reference messages
    operation = asyncapi_3_spec['operations']['sendUserEvent']
    message_ref = operation['messages'][0]
    
    # Should be a reference
    assert isinstance(message_ref, dict)
    assert '$ref' in message_ref
    
    # Reference should point to components.messages
    assert message_ref['$ref'] == '#/components/messages/UserSignedUp'
    
    # The actual message should be in components
    assert 'components' in asyncapi_3_spec
    assert 'messages' in asyncapi_3_spec['components']
    assert 'UserSignedUp' in asyncapi_3_spec['components']['messages']


def test_asyncapi_3_payload_schema_validation(valid_payload_v3, asyncapi_3_spec):
    """Test specific schema validations in AsyncAPI 3.0."""
    result = validate_payload(valid_payload_v3, asyncapi_3_spec, message_id='UserSignedUp')
    
    # All required fields should be present
    assert result['summary']['missing_required'] == 0
    
    # No extra attributes
    assert result['summary']['extra_attributes'] == 0
    
    # All types match
    assert result['summary']['type_mismatches'] == 0
    
    # Pattern matches (id is numeric string, email is valid)
    assert result['summary']['pattern_violations'] == 0
    
    # Enum is valid
    assert result['summary']['enum_violations'] == 0
    
    # Numeric constraints met
    assert result['summary']['numeric_violations'] == 0
