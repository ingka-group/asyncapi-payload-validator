"""
Copyright (c) 2026 Ingka Holding B.V.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

"""Test basic package imports and functionality."""

import pytest
from pathlib import Path


def test_package_import():
    """Test that the package can be imported."""
    import asyncapi_payload_validator
    assert asyncapi_payload_validator.__version__ == "1.0.0"


def test_validator_module_import():
    """Test that validator module can be imported."""
    from asyncapi_payload_validator import validator
    assert hasattr(validator, 'main')
    assert hasattr(validator, 'get_all_json_paths')
    assert hasattr(validator, 'get_all_yaml_paths')


def test_cli_module_import():
    """Test that CLI module can be imported."""
    from asyncapi_payload_validator import cli
    assert hasattr(cli, 'cli')


def test_get_json_paths():
    """Test JSON path extraction."""
    from asyncapi_payload_validator.validator import get_all_json_paths
    
    sample = {
        "userId": "123",
        "email": "test@example.com",
        "metadata": {
            "source": "web"
        }
    }
    
    paths, types = get_all_json_paths(sample)
    
    assert "userId" in paths
    assert "email" in paths
    assert "metadata" in paths
    assert "metadata.source" in paths
    assert types["userId"] == "str"
    assert types["metadata"] == "dict"


def test_resolve_ref():
    """Test $ref resolution."""
    from asyncapi_payload_validator.validator import resolve_ref
    
    schema = {
        "components": {
            "schemas": {
                "User": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"}
                    }
                }
            }
        }
    }
    
    ref_schema = {"$ref": "#/components/schemas/User"}
    resolved = resolve_ref(ref_schema, schema, set())
    
    assert resolved["type"] == "object"
    assert "properties" in resolved


def test_check_enum_violations():
    """Test enum validation."""
    from asyncapi_payload_validator.validator import check_enum_violations
    
    payload = {"status": "invalid"}
    enum_map = {"status": ["active", "inactive", "pending"]}
    
    violations = check_enum_violations(payload, enum_map)
    assert len(violations) == 1
    assert "status" in violations[0]
    
    # Valid enum
    payload_valid = {"status": "active"}
    violations_valid = check_enum_violations(payload_valid, enum_map)
    assert len(violations_valid) == 0


def test_check_pattern_violations():
    """Test pattern validation."""
    from asyncapi_payload_validator.validator import check_pattern_violations
    
    payload = {"email": "invalid-email"}
    pattern_map = {"email": r"^[\w\.-]+@[\w\.-]+\.\w+$"}
    
    violations = check_pattern_violations(payload, pattern_map)
    assert len(violations) == 1
    assert "email" in violations[0]
    
    # Valid pattern
    payload_valid = {"email": "test@example.com"}
    violations_valid = check_pattern_violations(payload_valid, pattern_map)
    assert len(violations_valid) == 0


def test_check_numeric_violations():
    """Test numeric constraint validation."""
    from asyncapi_payload_validator.validator import check_numeric_violations
    
    payload = {"age": 150}
    numeric_map = {"age": {"minimum": 0, "maximum": 120}}
    
    violations = check_numeric_violations(payload, numeric_map)
    assert len(violations) == 1
    assert "age" in violations[0]
    assert "maximum" in violations[0]
    
    # Valid number
    payload_valid = {"age": 30}
    violations_valid = check_numeric_violations(payload_valid, numeric_map)
    assert len(violations_valid) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
