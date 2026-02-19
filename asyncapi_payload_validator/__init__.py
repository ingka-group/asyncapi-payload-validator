"""
Copyright (c) 2026 Ingka Holding B.V.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

"""AsyncAPI Payload Validator

A Python tool for validating JSON message payloads against AsyncAPI specifications.
Performs comprehensive JSON Schema validation including type checks, constraints,
patterns, enums, and composition rules.

Example:
    >>> import json, yaml
    >>> from pathlib import Path
    >>> from asyncapi_payload_validator import validate_payload
    >>> 
    >>> payload = json.loads(Path('payload.json').read_text())
    >>> spec = yaml.safe_load(Path('asyncapi.yaml').read_text())
    >>> 
    >>> result = validate_payload(payload, spec)
    >>> if result['valid']:
    ...     print("✅ Validation passed!")
    >>> else:
    ...     print(f"❌ Found {result['summary']['total_violations']} violations")
"""

__version__ = "1.0.0"
__license__ = "MIT"

# Import the main validation function
from asyncapi_payload_validator.validator import validate_payload

__all__ = [
    "__version__",
    "validate_payload",
]
