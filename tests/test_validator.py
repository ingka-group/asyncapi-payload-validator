"""
Copyright (c) 2026 Ingka Holding B.V.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root
# Use the new CLI entry point from the package
CLI_MODULE = 'asyncapi_payload_validator.cli'
# All test data (spec + payloads) now resides under tests/test-files/
DATA_DIR = Path(__file__).resolve().parent / 'test-files'
SPEC = DATA_DIR / 'asyncapi-2.6-spec.yaml'
MESSAGE_ID = 'testMessage'
VERBOSE = os.environ.get('VALIDATOR_TEST_VERBOSE', '').lower() in ('1','true','yes','on')

def run_validator(payload: str) -> subprocess.CompletedProcess:
    """Run the validator via the package CLI module on a payload file and return the completed process."""
    payload_path = DATA_DIR / payload
    cmd = [sys.executable, '-m', CLI_MODULE, str(payload_path), str(SPEC), '--message-id', MESSAGE_ID]
    # Use UTF-8 encoding to handle special characters on Windows
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if VERBOSE:
        _print_summary(payload, proc)
    return proc

CATEGORY_PATTERNS = [
    ("Extra Attributes", "Attributes in JSON but not in YAML:"),
    ("Type Mismatches", "Attributes with type mismatches:"),
    ("Missing Required", "Required attributes in YAML but missing in JSON:"),
    ("Length Violations", "Length violations:"),
    ("Pattern Violations", "Pattern violations:"),
    ("Enum Violations", "Enum violations:"),
    ("Numeric Violations", "Numeric violations:"),
    ("Composition Violations", "Composition (oneOf/anyOf/allOf) violations:"),
]

def _extract_fail_categories(stdout: str):
    lines = stdout.splitlines()
    fail = []
    for cat, marker in CATEGORY_PATTERNS:
        for i,l in enumerate(lines):
            if marker in l:
                # Look ahead until blank line or end for a 'None'
                block = []
                for j in range(i+1, len(lines)):
                    if not lines[j].strip():
                        break
                    block.append(lines[j])
                joined = "\n".join(block)
                if 'None' not in joined:
                    fail.append(cat)
                break
    return fail

def _print_summary(payload: str, proc: subprocess.CompletedProcess):
    fail_cats = _extract_fail_categories(proc.stdout)
    status = 'PASS' if proc.returncode == 0 else 'FAIL'
    print(f"[validator-summary] payload={payload} status={status} exit={proc.returncode} fail_categories={fail_cats}")

def assert_pass(proc: subprocess.CompletedProcess):
    stdout = proc.stdout or ""
    assert proc.returncode == 0, f"Expected PASS (exit 0) but got {proc.returncode}\nSTDOUT:\n{stdout}\nSTDERR:\n{proc.stderr}"
    assert 'RESULT: PASS' in stdout, f"PASS marker missing in stdout.\n{stdout}"

def assert_fail(proc: subprocess.CompletedProcess):
    stdout = proc.stdout or ""
    assert proc.returncode != 0, f"Expected FAIL (non-zero) but got 0\nSTDOUT:\n{stdout}"
    assert 'RESULT: FAIL' in stdout, f"FAIL marker missing in stdout.\n{stdout}"

def test_valid_v1():
    proc = run_validator('payload-valid-v1.json')
    assert_pass(proc)

def test_valid_v2():
    proc = run_validator('payload-valid-v2.json')
    assert_pass(proc)

def test_extra_and_missing_fails():
    proc = run_validator('payload-extra-and-missing.json')
    assert_fail(proc)
    # Evidence of extra attribute detection
    assert 'container.unexpected' in proc.stdout
    assert 'ghost' in proc.stdout
    # Because branch-specific required fields are not listed under Missing Required (by design),
    # ensure composition logic flagged the variant mismatch.
    assert 'oneOf expects exactly 1 match' in proc.stdout or 'expects exactly 1 match' in proc.stdout

def test_pattern_violations_fail():
    proc = run_validator('payload-pattern-violations.json')
    assert_fail(proc)
    # Look for pattern mismatch phrases
    assert 'does not match pattern' in proc.stdout
    assert 'ID-' in proc.stdout  # id pattern issue

def test_numeric_violations_fail():
    proc = run_validator('payload-numeric-violations.json')
    assert_fail(proc)
    # amount below minimum and count not multipleOf 5
    assert 'amount' in proc.stdout
    assert 'count' in proc.stdout
    # multipleOf or minimum related wording
    assert ('multipleOf' in proc.stdout) or ('minimum' in proc.stdout)

def test_length_violations_fail():
    proc = run_validator('payload-length-violations.json')
    assert_fail(proc)
    # Current validator surfaces note length issue; array item length not yet implemented.
    assert 'TooLongNote' in proc.stdout
    # Ensure length violations section is not 'None'
    assert 'String length violations' in proc.stdout

def test_required_missing_fail():
    proc = run_validator('payload-required-missing.json')
    assert_fail(proc)
    # id should appear in the Missing Required section (line with just the path)
    required_section_start = proc.stdout.find('Required attributes in YAML but missing in JSON:')
    assert required_section_start != -1
    after = proc.stdout[required_section_start:required_section_start+200]
    assert ' id' in after or '⚠️  id' in after or 'id\n' in after

def test_enum_violations_fail():
    proc = run_validator('payload-enum-violations.json')
    assert_fail(proc)
    # variant, container.type, and meta.sharedValue all invalid
    assert 'variant' in proc.stdout
    assert 'container.type' in proc.stdout
    assert 'meta.sharedValue' in proc.stdout or 'sharedValue' in proc.stdout

def test_type_mismatches_fail():
    proc = run_validator('payload-type-mismatches.json')
    assert_fail(proc)
    # Look for type mismatch markers for several fields
    for key in ['id', 'amount', 'count', 'note']:
        assert key.split('.')[-1] in proc.stdout

def test_additional_properties_false_valid_pass():
    """Object with additionalProperties:false and only declared keys should pass."""
    proc = run_validator('payload-strict-valid.json')
    assert_pass(proc)
    # Ensure no extra attribute flagged for strictObj
    assert 'strictObj.notAllowed' not in proc.stdout

def test_additional_properties_false_extra_fails():
    """Extra key under additionalProperties:false object must be reported as Extra Attribute."""
    proc = run_validator('payload-strict-extra.json')
    assert_fail(proc)
    # Look for the path or at least the offending key
    assert 'strictObj.notAllowed' in proc.stdout or 'notAllowed' in proc.stdout
    # Confirm it's categorized as an Extra Attribute section (i.e., section not None)
    extra_section_start = proc.stdout.find('Attributes in JSON but not in YAML:')
    assert extra_section_start != -1, 'Extra Attributes section missing'
    after = proc.stdout[extra_section_start:extra_section_start+300]
    assert ('notAllowed' in after) or ('strictObj.notAllowed' in after)
