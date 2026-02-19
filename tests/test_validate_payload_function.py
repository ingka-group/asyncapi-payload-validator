"""
Copyright (c) 2026 Ingka Holding B.V.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

"""Tests for the validate_payload() public API function."""

import json
import yaml
import pytest
from pathlib import Path
from asyncapi_payload_validator import validate_payload


# Fixtures for loading test data
@pytest.fixture
def asyncapi_spec():
    """Load the test AsyncAPI spec."""
    spec_path = Path(__file__).parent / 'test-files' / 'asyncapi-2.6-spec.yaml'
    return yaml.safe_load(spec_path.read_text())


@pytest.fixture
def valid_payload():
    """Load a valid test payload."""
    payload_path = Path(__file__).parent / 'test-files' / 'payload-valid-v1.json'
    return json.loads(payload_path.read_text())


@pytest.fixture
def invalid_payload():
    """Load an invalid test payload with type mismatches."""
    payload_path = Path(__file__).parent / 'test-files' / 'payload-type-mismatches.json'
    return json.loads(payload_path.read_text())


def test_validate_payload_with_valid_data(valid_payload, asyncapi_spec):
    """Test validate_payload returns valid=True for conforming payload."""
    result = validate_payload(valid_payload, asyncapi_spec, message_id='testMessage')
    
    assert result['valid'] is True
    assert result['summary']['total_violations'] == 0
    assert all(count == 0 for category, count in result['summary'].items() 
               if category != 'total_violations')


def test_validate_payload_with_invalid_data(invalid_payload, asyncapi_spec):
    """Test validate_payload detects violations in non-conforming payload."""
    result = validate_payload(invalid_payload, asyncapi_spec, message_id='testMessage')
    
    assert result['valid'] is False
    assert result['summary']['total_violations'] > 0
    assert result['summary']['type_mismatches'] > 0


def test_validate_payload_return_structure(valid_payload, asyncapi_spec):
    """Test validate_payload returns correct dictionary structure."""
    result = validate_payload(valid_payload, asyncapi_spec, message_id='testMessage')
    
    # Check top-level keys
    assert 'valid' in result
    assert 'violations' in result
    assert 'summary' in result
    
    # Check violations categories
    expected_categories = [
        'extra_attributes',
        'type_mismatches',
        'missing_required',
        'length_violations',
        'pattern_violations',
        'enum_violations',
        'numeric_violations',
        'composition_violations'
    ]
    
    for category in expected_categories:
        assert category in result['violations']
        assert isinstance(result['violations'][category], list)
        assert category in result['summary']
        assert isinstance(result['summary'][category], int)
    
    # Check total_violations in summary
    assert 'total_violations' in result['summary']
    assert result['summary']['total_violations'] == sum(
        count for category, count in result['summary'].items() 
        if category != 'total_violations'
    )


def test_validate_payload_with_enum_violations(asyncapi_spec):
    """Test validate_payload detects enum violations."""
    payload_path = Path(__file__).parent / 'test-files' / 'payload-enum-violations.json'
    payload = json.loads(payload_path.read_text())
    
    result = validate_payload(payload, asyncapi_spec, message_id='testMessage')
    
    assert result['valid'] is False
    assert result['summary']['enum_violations'] > 0
    assert len(result['violations']['enum_violations']) > 0


def test_validate_payload_with_missing_required(asyncapi_spec):
    """Test validate_payload detects missing required fields."""
    payload_path = Path(__file__).parent / 'test-files' / 'payload-required-missing.json'
    payload = json.loads(payload_path.read_text())
    
    result = validate_payload(payload, asyncapi_spec, message_id='testMessage')
    
    assert result['valid'] is False
    assert result['summary']['missing_required'] > 0
    assert len(result['violations']['missing_required']) > 0


def test_validate_payload_without_message_id(valid_payload, asyncapi_spec):
    """Test validate_payload works without specifying message_id."""
    result = validate_payload(valid_payload, asyncapi_spec)
    
    assert 'valid' in result
    assert 'violations' in result
    assert 'summary' in result


def test_validate_payload_types(valid_payload, asyncapi_spec):
    """Test validate_payload parameter and return types."""
    result = validate_payload(valid_payload, asyncapi_spec, message_id='testMessage')
    
    assert isinstance(result, dict)
    assert isinstance(result['valid'], bool)
    assert isinstance(result['violations'], dict)
    assert isinstance(result['summary'], dict)
