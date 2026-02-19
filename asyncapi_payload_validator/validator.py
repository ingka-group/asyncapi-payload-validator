"""
Copyright (c) 2026 Ingka Holding B.V.

This source code is licensed under the MIT license found in the
LICENSE file in the root directory of this source tree.
"""

from __future__ import annotations

"""Contract validation helper: compare a sample JSON payload against an AsyncAPI / JSON Schema.

This script performs a structural cross-check between a concrete JSON payload and
an AsyncAPI specification (YAML file) containing JSON Schema fragments. It
reports:

    * Extra attributes: present in JSON but not declared in the schema (with
        allowance for objects that declare `additionalProperties` — treated as
        wildcards so their dynamic keys are not flagged).
    * Missing required attributes: declared as required in the schema but absent
        from the JSON payload.
    * Type mismatches: differing primitive/collection types (with lenient
        coercions: numeric strings accepted for number/integer; 'true'/'false'
        strings accepted for boolean; union types honored).
    * String length violations: minLength / maxLength failures.
    * Regex pattern violations: JSON string values that fail the schema's
        `pattern` expressions.

Resolution of `$ref` pointers complies with in-document JSON Pointer fragments.
Recursive / cyclic references are guarded against with a visited set.

Exit codes:
    0 -> PASS (no findings)
    1 -> FAIL (one or more findings)

Usage:
    python json_vs_yaml_attributes.py <sample_json_path> <asyncapi_yaml_path>

NOTE: This script implements a focused subset of JSON Schema validation:
            - Presence / required
            - Types (with lenient coercions)
            - String length & pattern
            - Enum
            - Numeric minimum, maximum, multipleOf
            - Compositions: oneOf / anyOf / allOf (shallow, per-property)
        Deep, exhaustive JSON Schema features (dependencies, complex nested
        composition interactions, format semantics beyond simple handling) are
        intentionally out of scope but can be added incrementally.
"""

import sys
import yaml
import json
import re
import os
import html as _html
from datetime import datetime
try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    _JINJA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _JINJA_AVAILABLE = False
from pathlib import Path
from typing import Any, Dict, Set, Tuple, List
from decimal import Decimal, InvalidOperation

# ------------------------------------------------------------
# Unified icon mapping (used for CLI, HTML summary, and table rows)
# ------------------------------------------------------------
ICONS: Dict[str, str] = {
    'Extra Attributes': '➕',
    'Type Mismatches': '❌',
    'Missing Required': '🚫',
    'Length Violations': '↔️',
    'Pattern Violations': '#️⃣',
    'Enum Violations': '✅',
    'Numeric Violations': '🔢',
    'Composition Violations': '🧩',
}

# Simple green check for CLI "None" lines (distinct from the boxed green check ✅ and heavy check ✔️)
def _supports_color() -> bool:
    try:
        return sys.stdout.isatty() and os.environ.get('NO_COLOR') is None
    except Exception:
        return False

GREEN_CHECK = "\x1b[32m✔\x1b[0m" if _supports_color() else "✔"  # plain heavy check colored green when terminal supports it
YELLOW_CROSS = "\x1b[33m✗\x1b[0m" if _supports_color() else "✗"  # yellow cross for violations (replaces generic ✖️)

def resolve_ref(schema: Any, full_root: Dict[str, Any], visited: Set[str]) -> Any:
    """Resolve an internal `$ref` to its target schema object.

    Supports chained references (a referenced object that itself contains a
    `$ref`). Non-internal (external) references are returned unchanged.

    Args:
        schema: Schema (possibly a dict with a `$ref`).
        full_root: Entire AsyncAPI document loaded as a Python object.
        visited: Set of reference strings already resolved in the current
            resolution path (guards against cycles).
    Returns:
        The resolved schema object (dict / list / primitive) or the original
        `schema` if resolution fails or would recurse infinitely.
    """
    if not isinstance(schema, dict) or '$ref' not in schema:
        return schema
    ref_path = schema['$ref']
    # Normalize by stripping whitespace/newlines (handles broken wrapped refs)
    ref_path_clean = ''.join(ref_path.split())
    if ref_path_clean != ref_path:
        ref_path = ref_path_clean
    # Only handle internal document references
    if not ref_path.startswith('#/'):
        return schema
    if ref_path in visited:
        return schema
    visited.add(ref_path)
    parts = ref_path.lstrip('#/').split('/')
    target = full_root
    for part in parts:
        if isinstance(target, dict):
            target = target.get(part)
        else:
            return schema  # unresolved
    # Resolve chains of refs
    if isinstance(target, dict) and '$ref' in target:
        return resolve_ref(target, full_root, visited)
    return target

# ------------------------------------------------------------
# Line mapping helpers (approximate path->line correlation)
# ------------------------------------------------------------

def _normalize_key(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    return raw

def build_yaml_line_map(yaml_text: str) -> Dict[str, int]:
    """Approximate mapping of dot paths -> line numbers in YAML spec.

    Heuristic: Uses indentation (assumes 2-space) to build a stack of keys.
    Only tracks mapping for keys that look like schema property names.
    Composition keywords are traversed but not added as path segments.
    The mapping stores the *first* occurrence of a path.
    """
    lines = yaml_text.splitlines()
    path_stack: List[str] = []
    line_map: Dict[str, int] = {}
    comp_keys = {"properties", "items", "components", "schemas", "messages"}
    for idx, line in enumerate(lines):
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        m = re.match(r'^(\s*)([^:#\n]+):', line)
        if not m:
            continue
        indent, key = m.groups()
        depth = len(indent) // 2  # assume 2-space indent
        key = _normalize_key(key)
        # Adjust stack to current depth
        while len(path_stack) > depth:
            path_stack.pop()
        # Push key (avoid adding structural non-property markers to path depth except channel templates)
        path_stack.append(key)
        # Build candidate dot path from leaf-subsequence starting after known schema roots
        # Simplistic: join everything, then later consumers match by suffix.
        dot_path = '.'.join([p for p in path_stack if p not in ('components','schemas','messages','payload','properties','items')])
        # Record for property-like keys (skip empty or structural)
        if dot_path and key not in comp_keys and key not in ('type','enum','required','oneOf','anyOf','allOf','minLength','maxLength','pattern'):
            line_map.setdefault(dot_path, idx + 1)
    return line_map

def build_json_schema_line_map(json_text: str) -> Dict[str, int]:
    """Approximate mapping of dot paths -> line numbers in a JSON AsyncAPI / schema document.

    Mirrors the intent of build_yaml_line_map but adapted to JSON syntax. We build a
    stack of keys using indentation heuristics (assuming 2 spaces per level, but
    tolerating other multiples) and filter out structural schema container keys so
    that produced dot paths resemble those produced from the payload schema traversal.

    This remains heuristic and is meant only for oriented navigation in the
    HTML report. It intentionally ignores non-property keyword keys (type, enum, etc.).
    """
    lines = json_text.splitlines()
    stack: List[str] = []
    line_map: Dict[str, int] = {}
    structural = {'components','schemas','messages','payload','properties','$defs','items'}
    skip_leaf = {'type','enum','required','oneOf','anyOf','allOf','minLength','maxLength','pattern',
                 'description','title','format','minimum','maximum','multipleOf','additionalProperties',
                 '$ref'}
    for idx, line in enumerate(lines):
        m = re.match(r'^(\s*)"([^"\\]+)"\s*:', line)
        if not m:
            continue
        indent, key = m.groups()
        depth = len(indent) // 2 if len(indent) else 0
        while len(stack) > depth:
            stack.pop()
        stack.append(key)
        if key in skip_leaf:
            continue
        filtered = [p for p in stack if p not in structural]
        if not filtered:
            continue
        dot_path = '.'.join(filtered)
        if dot_path:
            line_map.setdefault(dot_path, idx + 1)
            # Also register just the last segment to improve suffix lookups (if unique)
            last_seg = filtered[-1]
            line_map.setdefault(last_seg, idx + 1)
    return line_map

def build_json_line_map(json_text: str) -> Dict[str, int]:
    """Approximate mapping of dot paths -> line numbers in JSON payload.

    Array indices are ignored to mirror path semantics used in validators.
    """
    lines = json_text.splitlines()
    stack: List[str] = []
    line_map: Dict[str, int] = {}
    for idx, line in enumerate(lines):
        stripped = line.strip()
        # Adjust stack on closing braces/brackets by counting '}' occurrences
        close_count = line.count('}')
        # naive pop for each '}' *before* processing a new key on same line
        for _ in range(close_count):
            if stack:
                stack.pop()
        m = re.match(r'^(\s*)"([^"\\]+)"\s*:', line)
        if not m:
            continue
        indent = m.group(1)
        key = m.group(2)
        depth = len(indent) // 2
        # Ensure stack length aligns (best-effort; JSON may use 2-space or 4-space indent)
        while len(stack) > depth:
            stack.pop()
        stack.append(key)
        dot_path = '.'.join(stack)
        line_map.setdefault(dot_path, idx + 1)
    return line_map

def extract_path_from_message(message: str) -> str:
    """Best-effort extraction of the leading path before first colon.
    Falls back to empty string if no colon pattern found."""
    parts = message.split(':', 1)
    if len(parts) < 2:
        return message.strip()
    return parts[0].strip()

def get_length_constraints(
    schema: Any,
    prefix: str = "",
    full_root: Dict[str, Any] | None = None,
    visited: Set[str] | None = None,
) -> Dict[str, Dict[str, int]]:
    """Collect `minLength` / `maxLength` constraints for string properties.

    Descends through `properties` and `items` while resolving `$ref` values.

    Args:
        schema: Current schema node (object / array / primitive dict).
        prefix: Dot-path built so far.
        full_root: Full AsyncAPI document (used for `$ref` resolution).
        visited: Reference guard set reused inside recursion.
    Returns:
        Mapping of attribute path -> { 'minLength': int|None, 'maxLength': int|None }.
    """
    if full_root is None:
        full_root = schema
    if visited is None:
        visited = set()
    schema = resolve_ref(schema, full_root, visited) if isinstance(schema, dict) and '$ref' in schema else schema
    constraints = dict()
    if isinstance(schema, dict):
        # Traverse composition keywords (merge view)
        for comp_kw in ('allOf', 'anyOf', 'oneOf'):
            if comp_kw in schema and isinstance(schema[comp_kw], list):
                for subschema in schema[comp_kw]:
                    constraints.update(get_length_constraints(subschema, prefix, full_root, visited))
        if 'properties' in schema:
            for k, v in schema['properties'].items():
                v = resolve_ref(v, full_root, visited) if isinstance(v, dict) and '$ref' in v else v
                new_prefix = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict) and v.get('type') == 'string':
                    min_len = v.get('minLength')
                    max_len = v.get('maxLength')
                    if min_len is not None or max_len is not None:
                        constraints[new_prefix] = {'minLength': min_len, 'maxLength': max_len}
                constraints.update(get_length_constraints(v, new_prefix, full_root, visited))
        if schema.get('type') == 'array' and 'items' in schema:
            constraints.update(get_length_constraints(schema['items'], prefix, full_root, visited))
    return constraints

def get_pattern_constraints(
    schema: Any,
    prefix: str = "",
    full_root: Dict[str, Any] | None = None,
    visited: Set[str] | None = None,
) -> Dict[str, str]:
    """Collect regex `pattern` constraints for string properties.

    Args:
        schema: Schema node under inspection.
        prefix: Current dot-path.
        full_root: Full document for `$ref` resolution.
        visited: Guard set for `$ref` recursion.
    Returns:
        Mapping of attribute path -> raw regex pattern string.
    """
    if full_root is None:
        full_root = schema
    if visited is None:
        visited = set()
    if isinstance(schema, dict) and '$ref' in schema:
        schema = resolve_ref(schema, full_root, visited)
    patterns = {}
    if isinstance(schema, dict):
        for comp_kw in ('allOf', 'anyOf', 'oneOf'):
            if comp_kw in schema and isinstance(schema[comp_kw], list):
                for subschema in schema[comp_kw]:
                    patterns.update(get_pattern_constraints(subschema, prefix, full_root, visited))
        if 'properties' in schema:
            for k, v in schema['properties'].items():
                v_resolved = resolve_ref(v, full_root, visited) if isinstance(v, dict) and '$ref' in v else v
                new_prefix = f"{prefix}.{k}" if prefix else k
                if isinstance(v_resolved, dict) and v_resolved.get('type') == 'string' and 'pattern' in v_resolved:
                    raw_pat = str(v_resolved['pattern']).strip()
                    # Avoid surrounding whitespace; store raw pattern
                    patterns[new_prefix] = raw_pat
                # Recurse
                patterns.update(get_pattern_constraints(v_resolved, new_prefix, full_root, visited))
        if schema.get('type') == 'array' and 'items' in schema:
            patterns.update(get_pattern_constraints(schema['items'], prefix, full_root, visited))
    return patterns

def get_json_values_by_path(json_obj: Any, path: str) -> List[Any]:
    """Retrieve all concrete JSON values for a dot-separated path.

    Array navigation is implicit: if a segment encounters a list, each dict
    element is probed for the remaining path.

    Args:
        json_obj: Root JSON object (dict / list) representing the payload.
        path: Dot-delimited attribute path (e.g. "data.syncConsignment.consignment").
    Returns:
        List of matching values (possibly empty if path not present).
    """
    parts = path.split('.')
    values = [json_obj]
    for part in parts:
        next_values = []
        for val in values:
            if isinstance(val, dict) and part in val:
                next_values.append(val[part])
            elif isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and part in item:
                        next_values.append(item[part])
        values = next_values
    return values

def check_length_violations(json_obj: Any, length_constraints: Dict[str, Dict[str, int]]) -> List[str]:
    """Validate string value lengths against collected length constraints.

    Args:
        json_obj: Root JSON payload.
        length_constraints: Mapping produced by `get_length_constraints`.
    Returns:
        List of violation messages (empty if none).
    """
    violations = []
    for path, constraint in length_constraints.items():
        values = get_json_values_by_path(json_obj, path)
        for value in values:
            if isinstance(value, str):
                min_len = constraint.get('minLength')
                max_len = constraint.get('maxLength')
                if min_len is not None and len(value) < min_len:
                    violations.append(f"{path}: value '{value}' length {len(value)} < minLength {min_len}")
                if max_len is not None and len(value) > max_len:
                    violations.append(f"{path}: value '{value}' length {len(value)} > maxLength {max_len}")
    return violations

def print_length_violations(violations: List[str]) -> None:
    """Pretty-print minLength/maxLength violations list."""
    print(f"\n{ICONS['Length Violations']}  String length violations (minLength/maxLength):")
    if violations:
        for v in violations:
            print(f"    {YELLOW_CROSS}  {v}")
    else:
        print(f"    {GREEN_CHECK}  None")

def check_pattern_violations(json_obj: Any, pattern_constraints: Dict[str, str]) -> List[str]:
    """Check regex pattern compliance.

    Treats ints / floats / bools as coercible (converted to str) *only* to
    allow positive matching for patterns expecting digits or simple tokens.

    Args:
        json_obj: Root JSON payload.
        pattern_constraints: Mapping of attribute paths to regex patterns.
    Returns:
        List of violation strings.
    """
    violations = []
    for path, pattern_text in pattern_constraints.items():
        try:
            regex = re.compile(pattern_text)
        except re.error as e:
            violations.append(f"{path}: invalid regex '{pattern_text}' ({e})")
            continue
        values = get_json_values_by_path(json_obj, path)
        for v in values:
            # Only evaluate strings; skip nulls; attempt to coerce ints to str
            if v is None:
                continue
            if not isinstance(v, str):
                # If numeric or bool, coerce to str for match (allows patterns that accept digits)
                if isinstance(v, (int, float, bool)):
                    v_test = str(v)
                else:
                    # Non-string and not coercible simple scalar: violation
                    violations.append(f"{path}: value type {type(v).__name__} not string for pattern '{pattern_text}'")
                    continue
            else:
                v_test = v
            if not regex.fullmatch(v_test):
                violations.append(f"{path}: value '{v_test}' does not match pattern '{pattern_text}'")
    return violations

def print_pattern_violations(violations: List[str]) -> None:
    """Pretty-print pattern violations."""
    print(f"\n{ICONS['Pattern Violations']}  Pattern violations:")
    if violations:
        for v in violations:
            print(f"    {YELLOW_CROSS}  {v}")
    else:
        print(f"    {GREEN_CHECK}  None")

# ------------------------------------------------------------
# Additional constraint collection & validation (enum / numeric / compositions)
# ------------------------------------------------------------

def collect_additional_constraints(
    schema: Any,
    prefix: str = "",
    full_root: Dict[str, Any] | None = None,
    visited: Set[str] | None = None,
) -> Tuple[Dict[str, List[Any]], Dict[str, Dict[str, Any]], Dict[str, Dict[str, List[Any]]]]:
    """Traverse schema collecting enum, numeric limits, and composition clauses.

    Returns:
        (enum_map, numeric_map, composition_map)
        enum_map: path -> list(enum values)
        numeric_map: path -> {minimum, maximum, multipleOf}
        composition_map: path -> {'oneOf': [...], 'anyOf': [...], 'allOf': [...]} (lists of subschema dicts)
    """
    if full_root is None:
        full_root = schema
    if visited is None:
        visited = set()
    if isinstance(schema, dict) and '$ref' in schema:
        schema = resolve_ref(schema, full_root, visited)

    enum_map: Dict[str, List[Any]] = {}
    numeric_map: Dict[str, Dict[str, Any]] = {}
    composition_map: Dict[str, Dict[str, List[Any]]] = {}

    def recurse(node: Any, path: str, local_visited: Set[str]):
        """Recursive walker over the schema tree accumulating constraint metadata.

        Parameters:
            node: Current schema fragment (may contain properties / items / enum / numeric keys / compositions / $ref).
            path: Dot-qualified path accumulated so far representing the location of this node relative to the root payload schema.
            local_visited: Reference guard set used while resolving nested $ref chains inside this descent branch (prevents infinite recursion on cycles).

        Side Effects:
            Mutates the closure-captured dictionaries: enum_map, numeric_map, composition_map.
        """
        if isinstance(node, dict) and '$ref' in node:
            node = resolve_ref(node, full_root, local_visited)
        if not isinstance(node, dict):
            return

        # Traverse composition keywords BEFORE collecting to ensure enums in composed branches are seen.
        for comp_kw in ('allOf', 'anyOf', 'oneOf'):
            if comp_kw in node and isinstance(node[comp_kw], list):
                for subschema in node[comp_kw]:
                    recurse(subschema, path, local_visited)

        # Collect enum (merge enums coming from distinct variant branches at same path)
        if 'enum' in node and path:
            existing = enum_map.get(path)
            new_vals = node['enum']
            if isinstance(new_vals, list):
                if existing is None:
                    enum_map[path] = list(new_vals)
                else:
                    # Merge while preserving original order preference
                    for v in new_vals:
                        if v not in existing:
                            existing.append(v)

        # Numeric constraints
        numeric_keys = {k for k in ('minimum', 'maximum', 'multipleOf') if k in node}
        if numeric_keys and path:
            numeric_map[path] = {k: node.get(k) for k in ('minimum', 'maximum', 'multipleOf') if k in node}

        # Composition (shallow)
        comp_present = False
        comp_entry: Dict[str, List[Any]] = {}
        for comp_key in ('oneOf', 'anyOf', 'allOf'):
            if comp_key in node and isinstance(node[comp_key], list) and path:
                comp_entry[comp_key] = node[comp_key]
                comp_present = True
        if comp_present:
            composition_map[path] = comp_entry

        # Dive into properties
        if 'properties' in node and isinstance(node['properties'], dict):
            for prop, sub in node['properties'].items():
                new_path = f"{path}.{prop}" if path else prop
                recurse(sub, new_path, local_visited)

        # Array items
        if node.get('type') == 'array' and 'items' in node:
            # Items share the same path (no index appended)
            recurse(node['items'], path, local_visited)

    recurse(schema, prefix, visited)
    return enum_map, numeric_map, composition_map


def check_enum_violations(json_obj: Any, enum_map: Dict[str, List[Any]]) -> List[str]:
    """Validate payload values against enumerated allowed sets.

    For each path recorded in enum_map, all concrete values at that path in the JSON
    sample are compared to the allowed list. Numeric coercion of string values is
    attempted when the enumeration consists solely of numeric primitives, allowing
    strings like "42" to satisfy enum [42].

    Parameters:
        json_obj: Parsed JSON payload object.
        enum_map: Mapping path -> list of permissible literal values (as extracted from schema).

    Returns:
        A list of readable violation messages; empty if all encountered values are in-range.
    """
    violations: List[str] = []
    for path, allowed in enum_map.items():
        values = get_json_values_by_path(json_obj, path)
        if not values:
            continue
        # Pre-compute coercion hints
        all_allowed_numbers = all(isinstance(a, (int, float)) for a in allowed)
        allowed_set = set(allowed)
        for v in values:
            candidate = v
            # Lenient numeric string coercion
            if isinstance(v, str) and all_allowed_numbers:
                try:
                    if '.' in v:
                        candidate = float(v)
                    else:
                        candidate = int(v)
                except ValueError:
                    pass
            if candidate not in allowed_set:
                violations.append(f"{path}: value '{v}' not in enum {allowed}")
    return violations


def check_numeric_violations(json_obj: Any, numeric_map: Dict[str, Dict[str, Any]]) -> List[str]:
    """Check numeric constraints (minimum / maximum / multipleOf) for each path.

    Numeric values are leniently coerced from strings using Decimal for precision. If a
    value cannot be coerced to a number it is reported as a violation. Bounds are
    inclusive. For multipleOf, exact integral division in Decimal space is required.

    Parameters:
        json_obj: Parsed JSON payload object.
        numeric_map: Mapping path -> constraint dict with any of 'minimum', 'maximum', 'multipleOf'.

    Returns:
        List of violation message strings (empty if all numeric constraints satisfied).
    """
    violations: List[str] = []
    for path, constraints in numeric_map.items():
        values = get_json_values_by_path(json_obj, path)
        if not values:
            continue
        for raw in values:
            # Attempt numeric coercion (int/float or numeric string)
            try:
                if isinstance(raw, str):
                    num = Decimal(raw)
                elif isinstance(raw, (int, float)):
                    num = Decimal(str(raw))
                else:
                    violations.append(f"{path}: non-numeric value '{raw}' for numeric constraint")
                    continue
            except (InvalidOperation, ValueError):
                violations.append(f"{path}: value '{raw}' not coercible to number")
                continue
            if 'minimum' in constraints:
                if num < Decimal(str(constraints['minimum'])):
                    violations.append(f"{path}: {raw} < minimum {constraints['minimum']}")
            if 'maximum' in constraints:
                if num > Decimal(str(constraints['maximum'])):
                    violations.append(f"{path}: {raw} > maximum {constraints['maximum']}")
            if 'multipleOf' in constraints:
                try:
                    base = Decimal(str(constraints['multipleOf']))
                    if base != 0:
                        quotient = num / base
                        # Check closeness to integer within tolerance
                        if quotient != quotient.to_integral_value():
                            violations.append(f"{path}: {raw} not a multipleOf {constraints['multipleOf']}")
                except (InvalidOperation, ValueError):
                    violations.append(f"{path}: invalid multipleOf '{constraints['multipleOf']}'")
    return violations


def _satisfies_simple(schema: Any, value: Any, full_root: Dict[str, Any], visited: Set[str]) -> bool:
    """Lightweight schema satisfaction check for composition evaluation.

    Supports: type, enum, pattern, minimum, maximum, multipleOf (with lenient coercions).
    Does NOT recursively evaluate nested object properties (keeps it shallow).
    """
    if isinstance(schema, dict) and '$ref' in schema:
        schema = resolve_ref(schema, full_root, visited)
    if not isinstance(schema, dict):
        return True
    # Honor required keys (shallow) so that oneOf/anyOf/allOf match counting is meaningful.
    # If schema specifies required keys and value is an object missing any of them, schema does not match.
    if 'required' in schema and isinstance(value, dict):
        req = schema.get('required')
        if isinstance(req, list):
            for k in req:
                # Only treat as missing if the key is not present (case sensitive per JSON Schema spec)
                if k not in value:
                    return False
    # Type check (lenient similar to main logic)
    expected = schema.get('type')
    candidates: List[str]
    if expected is None:
        candidates = []
    elif isinstance(expected, list):
        candidates = expected
    else:
        candidates = [expected]
    def is_type_ok(cand: str, val: Any) -> bool:
        if cand == 'string':
            return isinstance(val, str)
        if cand == 'integer':
            if isinstance(val, int): return True
            if isinstance(val, str) and re.fullmatch(r'^-?\d+$', val): return True
            return False
        if cand == 'number':
            if isinstance(val, (int, float)): return True
            if isinstance(val, str) and re.fullmatch(r'^-?\d+(?:\.\d+)?$', val): return True
            return False
        if cand == 'boolean':
            if isinstance(val, bool): return True
            if isinstance(val, str) and val.lower() in ('true','false'): return True
            return False
        if cand == 'null':
            return val is None
        if cand == 'object':
            return isinstance(val, dict)
        if cand == 'array':
            return isinstance(val, list)
        return True
    if candidates:
        if not any(is_type_ok(c, value) for c in candidates):
            return False
    # Enum
    if 'enum' in schema:
        if value not in schema['enum']:
            # Try numeric coercion
            if isinstance(value, str):
                try:
                    coerced = int(value) if value.isdigit() else float(value)
                    if coerced not in schema['enum']:
                        return False
                except Exception:
                    return False
            else:
                return False
    # Pattern (only for string or coercible)
    if 'pattern' in schema and isinstance(value, str):
        if not re.fullmatch(str(schema['pattern']).strip(), value):
            return False
    # Numeric constraints
    if any(k in schema for k in ('minimum','maximum','multipleOf')):
        try:
            num = Decimal(str(value))
        except Exception:
            return False
        if 'minimum' in schema and num < Decimal(str(schema['minimum'])):
            return False
        if 'maximum' in schema and num > Decimal(str(schema['maximum'])):
            return False
        if 'multipleOf' in schema:
            base = Decimal(str(schema['multipleOf']))
            if base != 0 and (num / base) != (num / base).to_integral_value():
                return False
    return True


def check_composition_violations(
    json_obj: Any,
    composition_map: Dict[str, Dict[str, List[Any]]],
    full_root: Dict[str, Any]
) -> List[str]:
    """Evaluate shallow composition clauses (oneOf / anyOf / allOf) over collected paths.

    For each path associated with composition lists, every value instance from the JSON
    payload is checked against each subschema using the lightweight '_satisfies_simple'
    predicate. Match counts are then validated against the composition operator rules:
        * oneOf: exactly one subschema must match
        * anyOf: at least one subschema must match
        * allOf: all subschemas must match

    Note: This is a shallow check; nested property requirements inside subschemas are
    not recursively validated beyond required/type/enum/pattern/numeric—keeping
    evaluation performant while still surfacing common composition misuses.

    Parameters:
        json_obj: Parsed JSON payload.
        composition_map: Mapping path -> {'oneOf'|'anyOf'|'allOf': [subschema dicts...]}
        full_root: Full AsyncAPI / schema document for resolving internal $refs.

    Returns:
        List of violation messages describing mismatched composition cardinalities.
    """
    violations: List[str] = []
    for path, comps in composition_map.items():
        values = get_json_values_by_path(json_obj, path)
        if not values:
            continue
        for val in values:
            for comp_kind, schemas in comps.items():
                matches = 0
                for s in schemas:
                    if _satisfies_simple(s, val, full_root, set()):
                        matches += 1
                if comp_kind == 'oneOf':
                    if matches != 1:
                        violations.append(f"{path}: oneOf expects exactly 1 match, got {matches}")
                elif comp_kind == 'anyOf':
                    if matches < 1:
                        violations.append(f"{path}: anyOf expects >=1 match, got 0")
                elif comp_kind == 'allOf':
                    if matches != len(schemas):
                        violations.append(f"{path}: allOf expects {len(schemas)} matches, got {matches}")
    return violations


def print_enum_violations(violations: List[str]) -> None:
    print(f"\n{ICONS['Enum Violations']} Enum violations:")
    if violations:
        for v in violations:
            print(f"    {YELLOW_CROSS}  {v}")
    else:
        print(f"    {GREEN_CHECK}  None")


def print_numeric_violations(violations: List[str]) -> None:
    print(f"\n{ICONS['Numeric Violations']} Numeric constraint violations:")
    if violations:
        for v in violations:
            print(f"    {YELLOW_CROSS}  {v}")
    else:
        print(f"    {GREEN_CHECK}  None")


def print_composition_violations(violations: List[str]) -> None:
    print(f"\n{ICONS['Composition Violations']} Composition (oneOf/anyOf/allOf) violations:")
    if violations:
        for v in violations:
            print(f"    {YELLOW_CROSS}  {v}")
    else:
        print(f"    {GREEN_CHECK}  None")

def extract_schema_from_envelope(yaml_obj: Any) -> Any:
    """Extract underlying AsyncAPI spec from potential wrapper/envelope.

    Some pipeline tools wrap the raw spec inside known keys (payload / AsyncSpec / specData).
    Returns the deepest found nested spec, otherwise the original object.
    """
    # Try to traverse known envelope structure
    keys = ["payload", "AsyncSpec", "specData"]
    obj = yaml_obj
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            obj = obj[k]
        else:
            return yaml_obj  # fallback: return as-is
    return obj

def print_extra_attrs(
    json_attrs: Set[str],
    yaml_attrs: Set[str],
    wildcard_prefixes: Set[str] | None = None,
) -> List[str]:
    """Report attributes present in JSON that are not declared in the schema.

    Args:
        json_attrs: All discovered JSON attribute paths.
        yaml_attrs: All discovered YAML schema attribute paths.
        wildcard_prefixes: Attribute path prefixes that allow arbitrary nested keys
            (derived from schemas with `additionalProperties`). Paths under
            these prefixes are suppressed from the "extra" reporting.
    Returns:
        Sorted list of "extra" attribute paths printed to stdout.
    """
    if wildcard_prefixes is None:
        wildcard_prefixes = set()
    raw_extra = json_attrs - yaml_attrs
    filtered = []
    for attr in raw_extra:
        skip = False
        for wp in wildcard_prefixes:
            if attr == wp or attr.startswith(wp + '.'):
                skip = True
                break
        if not skip:
            filtered.append(attr)
    extra_attrs = sorted(filtered)
    print(f"\n{ICONS['Extra Attributes']} Attributes in JSON but not in YAML:")
    if extra_attrs:
        for attr in extra_attrs:
            print(f"    ⚠️  {attr}")
    else:
        print(f"    {GREEN_CHECK}  None")
    return extra_attrs

def get_type_mismatches(
    json_types: Dict[str, str],
    yaml_types: Dict[str, Any],
    sample_json: Any,
) -> List[str]:
    r"""Compare JSON runtime value types with schema-declared types (lenient).

    Leniencies:
        * integer: accepts Python int OR string matching ``^-?\d+$``
        * number: accepts Python int/float OR numeric string ``^-?\d+(?:\.\d+)?$``
        * boolean: accepts bool, case-insensitive 'true'/'false', or single-element list thereof
        * union list: satisfied if any declared member type accepts the value
        * null: accepts JSON null (Python None)

    Args:
        json_types: Mapping attribute path -> Python inferred type name (str/int/...)
        yaml_types: Mapping attribute path -> schema type (string or list for unions)
        sample_json: Root JSON object to fetch concrete values for coercion checks
    Returns:
        List of mismatch description strings.
    """
    type_mismatches = []
    py_to_jsonschema = {
        'str': 'string',
        'int': 'integer',
        'float': 'number',
        'bool': 'boolean',
        'list': 'array',
        'dict': 'object',
        'NoneType': 'null'
    }
    int_re = re.compile(r'^-?\d+$')
    num_re = re.compile(r'^-?\d+(?:\.\d+)?$')

    def value_matches(decl, value):
        # Normalize declaration to list
        if isinstance(decl, list):
            decl_list = decl
        else:
            decl_list = [decl]
        v_type = type(value).__name__
        v_json = py_to_jsonschema.get(v_type, v_type)
        # Helper: attempt boolean coercion from string
        def is_coercible_boolean(v):
            if isinstance(v, bool):
                return True
            if isinstance(v, str) and v.lower() in ("true", "false"):
                return True
            return False
        # If value is a single-element list, unwrap for coercion attempts
        unwrapped = value
        if isinstance(value, list) and len(value) == 1:
            unwrapped = value[0]
        for target in decl_list:
            if target == v_json:
                return True
            if target == 'integer':
                if isinstance(value, int):
                    return True
                if isinstance(value, str) and int_re.match(value):
                    return True
            if target == 'number':
                if isinstance(value, (int, float)):
                    return True
                if isinstance(value, str) and num_re.match(value):
                    return True
            if target == 'boolean':
                # Direct bool
                if isinstance(value, bool):
                    return True
                # String or single-element list containing boolean-like string
                if is_coercible_boolean(value) or is_coercible_boolean(unwrapped):
                    return True
            if target == 'null' and value is None:
                return True
        return False

    for path, py_type in json_types.items():
        if path not in yaml_types:
            continue
        decl = yaml_types[path]
        # Quick structural accept if identical scalar type
        mapped = py_to_jsonschema.get(py_type, py_type)
        if not isinstance(decl, list) and decl == mapped:
            continue
        values = get_json_values_by_path(sample_json, path)
        if not values:
            # Could not fetch concrete values; fall back to label diff
            if decl != mapped:
                type_mismatches.append(f"{path}: JSON type '{mapped}' != YAML type '{decl}' (no values)")
            continue
        if not all(value_matches(decl, v) for v in values):
            # Capture sample (first up to 3 values)
            show = values[:3]
            type_mismatches.append(f"{path}: values {show} not compatible with YAML type '{decl}'")
    return type_mismatches

def print_type_mismatches(type_mismatches: List[str]) -> None:
    print(f"\n{ICONS['Type Mismatches']} Attributes with type mismatches:")
    if type_mismatches:
        for mismatch in type_mismatches:
            # Use the unified yellow cross for mismatch entries
            print(f"    {YELLOW_CROSS}  {mismatch}")
    else:
        print(f"    {GREEN_CHECK}  None")

def print_required_missing(required_yaml_attrs: Set[str], json_attrs: Set[str]) -> List[str]:
    """Print and return required attribute paths absent in JSON."""
    required_missing = sorted(required_yaml_attrs - json_attrs)
    print(f"\n{ICONS['Missing Required']} Required attributes in YAML but missing in JSON:")
    if required_missing:
        for attr in required_missing:
            print(f"    ⚠️  {attr}")
    else:
        print(f"    {GREEN_CHECK}  None")
    return required_missing

def get_required_yaml_paths(
    schema: Any,
    prefix: str = "",
    full_root: Dict[str, Any] | None = None,
    visited: Set[str] | None = None,
) -> Set[str]:
    """Collect required attribute paths (recursive over properties & arrays).

    Args:
        schema: Current schema node.
        prefix: Accumulated dot path.
        full_root: Full document root for resolving references.
        visited: `$ref` guard set.
    Returns:
        Set of fully-qualified required attribute paths.
    """
    if full_root is None:
        full_root = schema
    if visited is None:
        visited = set()
    if isinstance(schema, dict) and '$ref' in schema:
        schema = resolve_ref(schema, full_root, visited)
    required_paths = set()
    if isinstance(schema, dict):
        # allOf: merge required sets (spec semantics). anyOf/oneOf: traverse but do NOT mark their branch-required keys globally.
        if 'allOf' in schema and isinstance(schema['allOf'], list):
            for subschema in schema['allOf']:
                required_paths.update(get_required_yaml_paths(subschema, prefix, full_root, visited))
        for comp_kw in ('anyOf', 'oneOf'):
            if comp_kw in schema and isinstance(schema[comp_kw], list):
                for subschema in schema[comp_kw]:
                    # Traverse children to discover deeper required keys, but do not add this level's conditional requirements.
                    required_paths.update(get_required_yaml_paths(subschema, prefix, full_root, visited))
        if 'properties' in schema:
            required = schema.get('required', [])
            for k, v in schema['properties'].items():
                new_prefix = f"{prefix}.{k}" if prefix else k
                if k in required:
                    required_paths.add(new_prefix)
                required_paths.update(get_required_yaml_paths(v, new_prefix, full_root, visited))
        if schema.get('type') == 'array' and 'items' in schema:
            required_paths.update(get_required_yaml_paths(schema['items'], prefix, full_root, visited))
    return required_paths

def refine_oneof_required(
    sample_json: Any,
    root_schema: Any,
    required_paths: Set[str],
    full_root: Dict[str, Any],
) -> Set[str]:
    """Refine required paths so that oneOf branch-specific required keys from *inactive* branches
    are not reported as globally missing.

    Heuristic approach:
      * Walk the schema looking for objects with a oneOf.
      * For each oneOf branch, resolve $ref and attempt a lightweight match against the sample
        at that location using single-value enum/const properties present in the sample.
      * If exactly one branch matches, treat only that branch's own immediate required keys
        as active; remove the immediate required keys of the non-selected branches from the
        overall required_paths set (fully-qualified path form).

    Notes / Limitations:
      * We intentionally keep deeper nested required keys already gathered because they will
        only have been discovered if traversing that branch (harmless). The primary false
        positives stem from the *immediate* required list of sibling variant objects.
      * If 0 or >1 branches match (ambiguous), we skip refinement for that oneOf site.
      * This is a heuristic – it does not execute full JSON Schema validation for branch
        selection – but is usually sufficient when variants are distinguished via an
        enum/const discriminator-like field (common pattern: { "type": "A" } vs { "type": "B" }).
    """
    if not isinstance(required_paths, set):  # defensive
        required_paths = set(required_paths)

    def _resolve(node: Any, seen: Set[str] | None = None) -> Any:
        if not isinstance(node, dict):
            return node
        if '$ref' in node:
            return resolve_ref(node, full_root, seen or set())
        return node

    def _collect_branch_required(schema_node: Dict[str, Any]) -> Set[str]:
        req = set()
        if not isinstance(schema_node, dict):
            return req
        required_local = schema_node.get('required') or []
        props = schema_node.get('properties') if isinstance(schema_node.get('properties'), dict) else {}
        for k in required_local:
            if k in props:  # Only include if property exists (defensive)
                req.add(k)
        return req

    def _match_branch(schema_node: Dict[str, Any], sample_node: Any) -> bool:
        if not isinstance(schema_node, dict) or not isinstance(sample_node, dict):
            return False
        props = schema_node.get('properties') if isinstance(schema_node.get('properties'), dict) else {}
        score = 0
        for prop_name, prop_schema in props.items():
            prop_schema = _resolve(prop_schema)
            if not isinstance(prop_schema, dict):
                continue
            # Single-value enum or const acts as discriminator hint
            enum_vals = prop_schema.get('enum') if isinstance(prop_schema.get('enum'), list) else None
            if enum_vals and len(enum_vals) == 1:
                if sample_node.get(prop_name) == enum_vals[0]:
                    score += 1
                else:
                    return False  # Mismatch on discriminator eliminates branch
        # Consider a branch a match if it passed all discriminator checks (>=1) OR there were none (score==0) but structure matches basic type
        return score > 0

    def _walk(schema_node: Any, sample_node: Any, base_path: str = "") -> None:
        schema_node = _resolve(schema_node)
        if not isinstance(schema_node, dict):
            return
        # Dive into properties first so nested oneOfs handled
        if 'properties' in schema_node and isinstance(schema_node['properties'], dict):
            for prop, sub in schema_node['properties'].items():
                new_path = f"{base_path}.{prop}" if base_path else prop
                sub_sample = sample_node.get(prop) if isinstance(sample_node, dict) else None
                _walk(sub, sub_sample, new_path)
        # Now handle oneOf at this node
        if 'oneOf' in schema_node and isinstance(schema_node['oneOf'], list) and isinstance(sample_node, dict):
            branches = [ _resolve(b) for b in schema_node['oneOf'] ]
            matches = []
            branch_required_map: list[Set[str]] = []
            for idx, b in enumerate(branches):
                b = _resolve(b)
                branch_required = _collect_branch_required(b)
                branch_required_map.append(branch_required)
                if _match_branch(b, sample_node):
                    matches.append(idx)
            if len(matches) == 1:  # single active branch
                active = matches[0]
                # Collect remove set: required of every non-active branch at this base path
                to_remove: Set[str] = set()
                for idx, reqset in enumerate(branch_required_map):
                    if idx == active:
                        continue
                    for field in reqset:
                        fq = f"{base_path}.{field}" if base_path else field
                        to_remove.add(fq)
                if to_remove:
                    required_paths.difference_update(to_remove)
        # allOf/anyOf recursion (for completeness)
        for kw in ('allOf', 'anyOf'):
            if kw in schema_node and isinstance(schema_node[kw], list):
                for subs in schema_node[kw]:
                    _walk(subs, sample_node, base_path)

    try:
        _walk(root_schema, sample_json, "")
    except Exception:
        # Fail-safe: don't break validation if heuristic errors
        return required_paths
    return required_paths

def get_all_json_paths(json_obj: Any, prefix: str = "") -> Tuple[Set[str], Dict[str, str]]:
    """Discover every attribute path & its Python type within a JSON payload.

    Args:
        json_obj: Root JSON (dict/list/primitive) to traverse.
        prefix: Path accumulated so far.
    Returns:
        (paths, types) where:
          paths -> set of dot paths
          types -> mapping path -> Python type name
    """
    paths = set()
    types = dict()
    if isinstance(json_obj, dict):
        for k, v in json_obj.items():
            new_prefix = f"{prefix}.{k}" if prefix else k
            paths.add(new_prefix)
            types[new_prefix] = type(v).__name__
            sub_paths, sub_types = get_all_json_paths(v, new_prefix)
            paths.update(sub_paths)
            types.update(sub_types)
    elif isinstance(json_obj, list):
        for i, item in enumerate(json_obj):
            sub_paths, sub_types = get_all_json_paths(item, prefix)
            paths.update(sub_paths)
            types.update(sub_types)
    return paths, types

def get_all_yaml_paths(
    schema: Any,
    prefix: str = "",
    full_root: Dict[str, Any] | None = None,
    visited: Set[str] | None = None,
) -> Tuple[Set[str], Dict[str, Any]]:
    """Enumerate schema-declared attribute paths & their declared types.
      * Always fully resolve chained $ref entries before traversal.
      * Traverse composition keywords (allOf / anyOf / oneOf) by union-ing
        the collected properties under the same prefix path.
      * Traverse array `items` schemas (including $ref + compositions inside).
      * Default a property's type to 'object' if absent (common when nested
        via allOf fragments that only declare sub-properties).

    Returns:
        (paths, types) where types[path] is a JSON Schema type string or list.
    """
    if full_root is None:
        full_root = schema
    if visited is None:
        visited = set()

    # Fully resolve chained refs before proceeding.
    while isinstance(schema, dict) and '$ref' in schema:
        schema = resolve_ref(schema, full_root, visited)

    paths: Set[str] = set()
    types: Dict[str, Any] = {}

    if not isinstance(schema, dict):
        return paths, types

    # Handle composition keywords by traversing each branch; we do NOT short-circuit
    # because allOf merges, while oneOf/anyOf still signal potential properties.
    composed = False
    for comp_kw in ('allOf', 'anyOf', 'oneOf'):
        if comp_kw in schema and isinstance(schema[comp_kw], list):
            composed = True
            for subschema in schema[comp_kw]:
                sub_paths, sub_types = get_all_yaml_paths(subschema, prefix, full_root, visited)
                paths.update(sub_paths)
                # Do not overwrite an existing, more specific type with a generic one.
                for p, t in sub_types.items():
                    if p not in types:
                        types[p] = t
            # For allOf we continue (properties may exist alongside), for oneOf/anyOf it's
            # still valid to look at sibling properties, so we do not return early.
    # Continue with normal property/array descent regardless of composition presence.

    if 'properties' in schema and isinstance(schema['properties'], dict):
        for prop_name, prop_schema in schema['properties'].items():
            # Resolve prop-level refs fully
            prop_vis = set()  # fresh set per property to avoid cross-contamination
            while isinstance(prop_schema, dict) and '$ref' in prop_schema:
                prop_schema = resolve_ref(prop_schema, full_root, prop_vis)
            new_prefix = f"{prefix}.{prop_name}" if prefix else prop_name
            declared_type = 'object'
            if isinstance(prop_schema, dict) and 'type' in prop_schema:
                declared_type = prop_schema['type']
            types.setdefault(new_prefix, declared_type)
            paths.add(new_prefix)
            sub_paths, sub_types = get_all_yaml_paths(prop_schema, new_prefix, full_root, visited)
            paths.update(sub_paths)
            for p, t in sub_types.items():
                if p not in types:
                    types[p] = t

    # Array traversal: keep same prefix (no numeric index in paths)
    if schema.get('type') == 'array' and 'items' in schema:
        # Register the array itself (if we have a prefix)
        if prefix:
            types.setdefault(prefix, 'array')
            paths.add(prefix)
        sub_paths, sub_types = get_all_yaml_paths(schema['items'], prefix, full_root, visited)
        paths.update(sub_paths)
        for p, t in sub_types.items():
            if p not in types:
                types[p] = t

    return paths, types

def gather_additional_properties_prefixes(
    schema: Any,
    prefix: str = "",
    full_root: Dict[str, Any] | None = None,
    visited: Set[str] | None = None,
) -> Set[str]:
    """Collect attribute prefixes whose objects declare `additionalProperties`.

    These prefixes are treated as wildcards for unknown nested keys; any JSON
    attributes under them are not flagged as "extra" (schema intentionally
    permits arbitrary extension there).
    """
    if full_root is None:
        full_root = schema
    if visited is None:
        visited = set()
    if isinstance(schema, dict) and '$ref' in schema:
        schema = resolve_ref(schema, full_root, visited)
    prefixes = set()
    if isinstance(schema, dict):
        # Traverse compositions
        for comp_kw in ('allOf', 'anyOf', 'oneOf'):
            if comp_kw in schema and isinstance(schema[comp_kw], list):
                for subschema in schema[comp_kw]:
                    prefixes.update(gather_additional_properties_prefixes(subschema, prefix, full_root, visited))
        # NOTE: JSON Schema semantics:
        #   - additionalProperties omitted => unspecified (defaults to allowed, but we *do not* treat as wildcard here
        #     so that undefined keys can still be reported as extra unless user explicitly opts-in by setting it).
        #   - additionalProperties: false => disallow extras (MUST NOT be treated as wildcard) ✅
        #   - additionalProperties: true OR a schema object => allow arbitrary keys (treat as wildcard) ✅
        # Previous implementation incorrectly treated *any* presence (even false) as wildcard, suppressing
        # extra-attribute reporting. Fix: only add prefix when value is not strictly False.
        if 'additionalProperties' in schema and prefix:
            val = schema['additionalProperties']
            if val is not False:  # true or a schema (dict) means open extension point
                prefixes.add(prefix)
        if 'properties' in schema:
            for k, v in schema['properties'].items():
                new_prefix = f"{prefix}.{k}" if prefix else k
                prefixes.update(gather_additional_properties_prefixes(v, new_prefix, full_root, visited))
        if schema.get('type') == 'array' and 'items' in schema:
            prefixes.update(gather_additional_properties_prefixes(schema['items'], prefix, full_root, visited))
    return prefixes

def check_type_mismatches(json_types: Dict[str, str], yaml_types: Dict[str, Any]) -> None:
    """(Legacy) Print-only type mismatch function retained for compatibility.

    Prefer using `get_type_mismatches` for richer, coercion-aware diagnostics.
    """
    print("\nAttributes with type mismatches:")
    mismatch_found = False
    for attr in json_types:
        if attr in yaml_types:
            json_type = json_types[attr]
            yaml_type = yaml_types[attr]
            # Map Python types to JSON Schema types
            py_to_jsonschema = {
                'str': 'string',
                'int': 'integer',
                'float': 'number',
                'bool': 'boolean',
                'list': 'array',
                'dict': 'object',
                'NoneType': 'null'
            }
            mapped_json_type = py_to_jsonschema.get(json_type, json_type)
            if mapped_json_type != yaml_type:
                print(f"  {attr}: JSON type '{mapped_json_type}' != YAML type '{yaml_type}'")
                mismatch_found = True
    if not mismatch_found:
        print("  None")

def find_payload_schema(asyncapi: Dict[str, Any], preferred_message_id: str | None = None) -> Any:
    """Locate the payload schema to validate against.

    Supports both AsyncAPI 2.x and 3.x specifications.

    AsyncAPI 2.x structure:
        - channels.{channelName}.publish/subscribe.message
    
    AsyncAPI 3.x structure:
        - operations.{operationId}.messages (array of message refs)
        - channels.{channelId}.messages (direct message definitions)

    Selection strategy (first match wins unless a preferred message id is supplied):
        A. If a --message-id was provided, search all messages for matching messageId
        1. If exactly one component schema exists -> return it (legacy shortcut).
        2. Iterate channels/operations and return the first message payload found.
        3. Fallback: first payload under components.messages.
        4. Final fallback: entire document root.

    Args:
        asyncapi: Parsed AsyncAPI document.
        preferred_message_id: Optional explicit messageId to target.
    Returns:
        The chosen payload schema object (may still contain $ref to be resolved later).
    """
    if not isinstance(asyncapi, dict):
        return asyncapi

    # Detect AsyncAPI version
    asyncapi_version = asyncapi.get('asyncapi', '2.0.0')
    is_v3 = asyncapi_version.startswith('3.')

    def _resolve(obj: Any) -> Any:
        if isinstance(obj, dict) and '$ref' in obj:
            return resolve_ref(obj, asyncapi, set())
        return obj

    # Helper to extract payload from a message dict (already resolved)
    def _payload_from_message(msg_obj: Any) -> Any:
        if isinstance(msg_obj, dict) and 'payload' in msg_obj:
            return _resolve(msg_obj['payload'])
        return None

    # A. Explicit message id search
    if preferred_message_id:
        # AsyncAPI 3.x: Search operations first
        if is_v3:
            operations = asyncapi.get('operations') if isinstance(asyncapi.get('operations'), dict) else {}
            for op_val in operations.values():
                if not isinstance(op_val, dict):
                    continue
                # operations.{operationId}.messages is an array of message refs
                messages_list = op_val.get('messages', [])
                if not isinstance(messages_list, list):
                    messages_list = [messages_list]
                for msg_ref in messages_list:
                    m_res = _resolve(msg_ref)
                    if isinstance(m_res, dict) and m_res.get('messageId') == preferred_message_id:
                        p = _payload_from_message(m_res)
                        if p is not None:
                            return p
            
            # Also search channels.{channelId}.messages in AsyncAPI 3.x
            channels = asyncapi.get('channels') if isinstance(asyncapi.get('channels'), dict) else {}
            for ch_val in channels.values():
                if not isinstance(ch_val, dict):
                    continue
                ch_messages = ch_val.get('messages', {})
                if isinstance(ch_messages, dict):
                    for msg_ref in ch_messages.values():
                        m_res = _resolve(msg_ref)
                        if isinstance(m_res, dict) and m_res.get('messageId') == preferred_message_id:
                            p = _payload_from_message(m_res)
                            if p is not None:
                                return p
        
        # AsyncAPI 2.x: Search channels (publish/subscribe)
        else:
            channels = asyncapi.get('channels') if isinstance(asyncapi.get('channels'), dict) else {}
            for ch_val in channels.values():
                if not isinstance(ch_val, dict):
                    continue
                for op in ('publish', 'subscribe'):
                    op_obj = ch_val.get(op)
                    if not isinstance(op_obj, dict):
                        continue
                    msg = op_obj.get('message')
                    if isinstance(msg, list):
                        msgs_iter = msg
                    else:
                        msgs_iter = [msg]
                    for m in msgs_iter:
                        m_res = _resolve(m)
                        if isinstance(m_res, dict) and m_res.get('messageId') == preferred_message_id:
                            p = _payload_from_message(m_res)
                            if p is not None:
                                return p
        
        # Search components.messages (common to both 2.x and 3.x)
        comps = asyncapi.get('components') if isinstance(asyncapi.get('components'), dict) else {}
        messages = comps.get('messages') if isinstance(comps.get('messages'), dict) else {}
        for m in messages.values():
            m_res = _resolve(m)
            if isinstance(m_res, dict) and m_res.get('messageId') == preferred_message_id:
                p = _payload_from_message(m_res)
                if p is not None:
                    return p

    # 1. Single schema shortcut (unchanged behaviour)
    comps_full = asyncapi.get('components') if isinstance(asyncapi.get('components'), dict) else {}
    schemas_full = comps_full.get('schemas') if isinstance(comps_full.get('schemas'), dict) else {}
    if len(schemas_full) == 1:
        return next(iter(schemas_full.values()))

    # 2. First channel/operation message payload
    if is_v3:
        # AsyncAPI 3.x: Check operations first
        operations = asyncapi.get('operations') if isinstance(asyncapi.get('operations'), dict) else {}
        for op_val in operations.values():
            if not isinstance(op_val, dict):
                continue
            messages_list = op_val.get('messages', [])
            if not isinstance(messages_list, list):
                messages_list = [messages_list]
            for msg_ref in messages_list:
                m_res = _resolve(msg_ref)
                p = _payload_from_message(m_res)
                if p is not None:
                    return p
        
        # Then check channels.{channelId}.messages
        channels_full = asyncapi.get('channels') if isinstance(asyncapi.get('channels'), dict) else {}
        for ch_val in channels_full.values():
            if not isinstance(ch_val, dict):
                continue
            ch_messages = ch_val.get('messages', {})
            if isinstance(ch_messages, dict):
                for msg_ref in ch_messages.values():
                    m_res = _resolve(msg_ref)
                    p = _payload_from_message(m_res)
                    if p is not None:
                        return p
    else:
        # AsyncAPI 2.x: Check channels (publish/subscribe)
        channels_full = asyncapi.get('channels') if isinstance(asyncapi.get('channels'), dict) else {}
        for ch_val in channels_full.values():
            if not isinstance(ch_val, dict):
                continue
            for op in ('publish', 'subscribe'):
                op_obj = ch_val.get(op)
                if not isinstance(op_obj, dict) or 'message' not in op_obj:
                    continue
                msg = op_obj['message']
                msgs_iter = msg if isinstance(msg, list) else [msg]
                for m in msgs_iter:
                    m_res = _resolve(m)
                    p = _payload_from_message(m_res)
                    if p is not None:
                        return p

    # 3. First components.messages payload
    for m in (comps_full.get('messages') or {}).values():
        m_res = _resolve(m)
        p = _payload_from_message(m_res)
        if p is not None:
            return p

    # 4. Fallback root
    return asyncapi

def _normalize_object_schema(schema: Any) -> Any:
    """Heuristic normalization for loosely-specified object schemas.

    Some AsyncAPI/JSON Schema authoring styles omit an explicit `properties` block
    and instead place child keys (or $ref containers) directly under an
    object declaring `type: object`. This deviates from canonical JSON Schema
    but appears in real-world specs. To make validation resilient, detect this
    pattern and wrap those direct child keys into a synthesized `properties`.

    Only keys whose values are dicts (potential schemas) and not in the
    reserved keyword allow-list are moved. Existing `properties` are left
    untouched.
    """
    if not isinstance(schema, dict):
        return schema
    if schema.get('type') != 'object' or 'properties' in schema:
        return schema
    reserved = { 'type','required','description','title','enum','oneOf','anyOf','allOf',
                 '$id','$schema','additionalProperties','format','default','examples' }
    implicit_props = {}
    for k,v in list(schema.items()):
        if k in reserved:
            continue
        if isinstance(v, dict):
            implicit_props[k] = v
    if implicit_props:
        # Remove the implicit keys from top-level and create proper properties mapping
        for k in implicit_props:
            schema.pop(k, None)
        schema['properties'] = implicit_props
    return schema

def validate_payload(
    payload_data: Dict[str, Any],
    asyncapi_spec: Dict[str, Any],
    message_id: str = None
) -> Dict[str, Any]:
    """
    Validate a JSON payload against an AsyncAPI specification.
    
    This is the primary programmatic API for validation. It performs all validation
    checks (extra attributes, type mismatches, required fields, length/pattern/enum
    violations, numeric constraints, and composition rules) and returns structured results.
    
    Args:
        payload_data: The JSON payload to validate (as a Python dict).
        asyncapi_spec: The AsyncAPI specification (as a Python dict, loaded from YAML/JSON).
        message_id: Optional message ID to validate against. If None, auto-detects the schema.
    
    Returns:
        A dictionary with the following structure:
        {
            'valid': bool,  # True if no violations, False otherwise
            'violations': {
                'extra_attributes': List[str],      # Fields in payload not in schema
                'type_mismatches': List[str],        # Type errors
                'missing_required': List[str],       # Required fields missing
                'length_violations': List[str],      # String length violations
                'pattern_violations': List[str],     # Regex pattern mismatches
                'enum_violations': List[str],        # Invalid enum values
                'numeric_violations': List[str],     # Numeric constraint violations
                'composition_violations': List[str]  # oneOf/anyOf/allOf violations
            },
            'summary': {
                'extra_attributes': int,      # Count of violations
                'type_mismatches': int,
                'missing_required': int,
                'length_violations': int,
                'pattern_violations': int,
                'enum_violations': int,
                'numeric_violations': int,
                'composition_violations': int,
                'total_violations': int       # Total count across all categories
            }
        }
    
    Example:
        >>> import json, yaml
        >>> from pathlib import Path
        >>> from asyncapi_payload_validator import validate_payload
        >>> 
        >>> payload = json.loads(Path('payload.json').read_text())
        >>> spec = yaml.safe_load(Path('asyncapi.yaml').read_text())
        >>> 
        >>> result = validate_payload(payload, spec)
        >>> 
        >>> if result['valid']:
        ...     print("✅ Validation passed!")
        ... else:
        ...     print(f"❌ Found {result['summary']['total_violations']} violation(s)")
        ...     for category, violations in result['violations'].items():
        ...         if violations:
        ...             print(f"{category}: {violations}")
    """
    # Extract schema from AsyncAPI envelope
    schema = extract_schema_from_envelope(asyncapi_spec)
    
    # Find the specific message schema
    payload_schema = find_payload_schema(schema, message_id)
    
    # Normalize the schema (handle implicit properties)
    payload_schema = _normalize_object_schema(payload_schema)
    
    # Get all paths and types
    json_attrs, json_types = get_all_json_paths(payload_data)
    yaml_attrs, yaml_types = get_all_yaml_paths(payload_schema, full_root=schema)
    required_yaml_attrs = get_required_yaml_paths(payload_schema, full_root=schema)
    
    # Refine branch-specific required attributes (oneOf) to exclude inactive variant requirements
    try:
        required_yaml_attrs = refine_oneof_required(payload_data, payload_schema, required_yaml_attrs, schema)
    except Exception:
        pass  # Heuristic refinement failure should not abort validation
    
    # Gather constraints
    length_constraints = get_length_constraints(payload_schema, full_root=schema)
    pattern_constraints = get_pattern_constraints(payload_schema, full_root=schema)
    wildcard_prefixes = gather_additional_properties_prefixes(payload_schema, full_root=schema)
    enum_map, numeric_map, composition_map = collect_additional_constraints(payload_schema, full_root=schema)
    
    # Check for violations
    extra_attrs = list(json_attrs - yaml_attrs)
    # Filter out paths under additionalProperties: true objects
    extra_attrs = [attr for attr in extra_attrs 
                   if not any(attr.startswith(prefix + '.') or attr == prefix 
                             for prefix in wildcard_prefixes)]
    
    type_mismatches = get_type_mismatches(json_types, yaml_types, payload_data)
    required_missing = list(required_yaml_attrs - json_attrs)
    length_violations = check_length_violations(payload_data, length_constraints)
    pattern_violations = check_pattern_violations(payload_data, pattern_constraints)
    enum_violations = check_enum_violations(payload_data, enum_map)
    numeric_violations = check_numeric_violations(payload_data, numeric_map)
    composition_violations = check_composition_violations(payload_data, composition_map, schema)
    
    # Build results dictionary
    violations = {
        'extra_attributes': extra_attrs,
        'type_mismatches': type_mismatches,
        'missing_required': required_missing,
        'length_violations': length_violations,
        'pattern_violations': pattern_violations,
        'enum_violations': enum_violations,
        'numeric_violations': numeric_violations,
        'composition_violations': composition_violations,
    }
    
    # Calculate summary
    summary = {category: len(violations_list) for category, violations_list in violations.items()}
    summary['total_violations'] = sum(summary.values())
    
    # Determine if valid
    valid = summary['total_violations'] == 0
    
    return {
        'valid': valid,
        'violations': violations,
        'summary': summary
    }


def _render_html_report(context: Dict[str, Any], output_path: str) -> None:
    """Render an HTML report using Jinja2 template if available.

    Parameters:
        context: Data dictionary for the template.
        output_path: Target file path for the rendered HTML.
    """
    if not _JINJA_AVAILABLE:
        print("[WARN] Jinja2 not installed; skipping HTML report generation.")
        return
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    env = Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(['html', 'xml'])
    )
    try:
        template = env.get_template('validation_report.j2')
    except Exception as e:  # pragma: no cover
        print(f"[WARN] Could not load template: {e}")
        return
    html = template.render(**context)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n📄 HTML report written to {output_path}")


def main() -> None:
    """CLI entry point.

    Parses arguments, loads documents, performs extraction & validations, and
    prints a consolidated PASS/FAIL summary. Exits with code 1 upon any
    finding, else 0.
    """
    # Simple arg parsing supporting optional --html-report path, --message-id, and Jinja2 template rendering
    args = sys.argv[1:]
    html_report_path = None
    preferred_message_id = None
    render_jinja2 = False
    jinja2_context = None
    
    if '--html-report' in args:
        idx = args.index('--html-report')
        try:
            html_report_path = args[idx + 1]
            # Remove the flag and its value for positional processing
            del args[idx:idx + 2]
        except IndexError:
            print("Error: --html-report flag requires an output file path.")
            sys.exit(1)
    if '--message-id' in args:
        idx = args.index('--message-id')
        try:
            preferred_message_id = args[idx + 1]
            del args[idx:idx + 2]
        except IndexError:
            print("Error: --message-id flag requires a messageId value.")
            sys.exit(1)
    if '--render-jinja2' in args:
        render_jinja2 = True
        idx = args.index('--render-jinja2')
        del args[idx]
    if '--jinja2-context' in args:
        idx = args.index('--jinja2-context')
        try:
            context_file = args[idx + 1]
            del args[idx:idx + 2]
            # Load Jinja2 context from JSON file
            try:
                with open(context_file, 'r', encoding='utf-8') as f:
                    jinja2_context = json.load(f)
            except Exception as e:
                print(f"Error: Failed to load Jinja2 context from '{context_file}': {e}")
                sys.exit(1)
        except IndexError:
            print("Error: --jinja2-context flag requires a file path.")
            sys.exit(1)
    
    if len(args) != 2:
        print("Usage: python validator.py <sample_json> <asyncapi_yaml> [--html-report report.html] [--message-id <messageId>] [--render-jinja2] [--jinja2-context context.json]")
        sys.exit(1)
    json_path, yaml_path = args
    json_text = Path(json_path).read_text(encoding='utf-8')
    
    # Track if we're doing structural-only validation (template without context)
    structural_only_validation = False
    
    # Render Jinja2 template if requested
    if render_jinja2:
        if not _JINJA_AVAILABLE:
            print("[ERROR] Jinja2 is not installed. Cannot render templates.")
            sys.exit(1)
        
        # If no context provided for template, skip rendering and do structural validation only
        if not jinja2_context:
            structural_only_validation = True
            print("[INFO] No Jinja2 context provided. Skipping template rendering.")
            print("[INFO] Performing structural validation only - checking keys present in template.")
            print("[INFO] Value-based validations (types, patterns, enums, numeric constraints) will be skipped.")
            # Don't render - keep json_text as-is (the template with {{variables}})
            # We'll parse it as best-effort JSON, ignoring Jinja2 syntax
        else:
            # Render template with provided context
            try:
                from jinja2 import Template
                
                # Auto-add | tojson filter for object/array variables
                # This allows users to write {{variable}} without worrying about the filter
                template_text = json_text
                for var_name, var_value in jinja2_context.items():
                    if isinstance(var_value, (dict, list)):
                        # Find {{var_name}} that doesn't already have | tojson
                        # Use negative lookahead to avoid double-adding
                        pattern = r'\{\{\s*' + re.escape(var_name) + r'\s*(?!\|)\}\}'
                        replacement = '{{' + var_name + ' | tojson}}'
                        template_text = re.sub(pattern, replacement, template_text)
                
                template = Template(template_text)
                json_text = template.render(**jinja2_context)
                print(f"[INFO] Rendered JSON with Jinja2 template (context keys: {list(jinja2_context.keys())})")
            except Exception as e:
                print(f"[ERROR] Failed to render Jinja2 template: {e}")
                sys.exit(1)
    
    yaml_text = Path(yaml_path).read_text(encoding='utf-8')
    raw_yaml = yaml.safe_load(yaml_text)
    
    # Parse JSON - handle structural-only mode for templates
    jinja2_variable_paths = set()  # Track which paths are Jinja2 variables
    if structural_only_validation:
        # For structural validation, we need to extract keys from the template
        # First, identify which JSON paths are Jinja2 variables (will be replaced with runtime data)
        from jinja2 import Environment, meta
        env = Environment()
        try:
            ast = env.parse(json_text)
            variables = meta.find_undeclared_variables(ast)
            
            # Parse the template to find where each variable is used
            import json as json_module
            # Try to parse as-is to find variable locations
            lines = json_text.split('\n')
            for line_num, line in enumerate(lines):
                for var in variables:
                    # Check if this line has a variable as a value (not in a string)
                    if f'{{{{{var}}}}}' in line:
                        # Extract the key name from this line
                        match = re.search(r'"(\w+)"\s*:\s*\{\{' + re.escape(var) + r'\}\}', line)
                        if match:
                            key_name = match.group(1)
                            jinja2_variable_paths.add(key_name)
        except Exception as e:
            print(f"[WARN] Could not identify Jinja2 variable locations: {e}")
        
        # Strip Jinja2 variables and replace with valid JSON placeholders
        # Replace {{anything}} with null (matches simple vars and filters like {{var | tojson}})
        cleaned_json = re.sub(r'{{\s*[^}]+\s*}}', 'null', json_text)
        try:
            sample_json = json.loads(cleaned_json)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Template has invalid JSON structure (even after removing Jinja2 syntax): {e}")
            print("[INFO] Ensure your template has valid JSON structure with proper commas, braces, etc.")
            sys.exit(1)
    else:
        # Normal parsing of rendered JSON
        sample_json = json.loads(json_text)
    
    is_json_spec = yaml_path.lower().endswith('.json')
    asyncapi = extract_schema_from_envelope(raw_yaml)
    payload_schema = find_payload_schema(asyncapi, preferred_message_id)
    payload_schema = _normalize_object_schema(payload_schema)
    # Heuristic: if root schema (after normalization) has exactly one property name and
    # the sample JSON lacks that wrapper but contains fields that belong to the referenced schema,
    # auto-wrap to reduce false "extra" noise for authoring shorthand.
    def _maybe_wrap_root(sample_obj: Any, schema_obj: Any) -> Any:
        try:
            if isinstance(schema_obj, dict) and 'properties' in schema_obj:
                props = schema_obj['properties']
                if isinstance(props, dict) and len(props) == 1:
                    sole_key, sole_schema = next(iter(props.items()))
                    # If sample already has the sole key, nothing to do
                    if isinstance(sample_obj, dict) and sole_key not in sample_obj:
                        # If the sample's keys look like they belong to the nested schema (e.g., version/id present)
                        # and sole_schema ultimately resolves to an object with those properties, wrap.
                        nested = sole_schema
                        if isinstance(nested, dict) and '$ref' in nested:
                            nested = resolve_ref(nested, asyncapi, set())
                        if isinstance(nested, dict):
                            inner_props = nested.get('properties', {}) if isinstance(nested.get('properties'), dict) else {}
                            # Simple heuristic: at least one overlapping key
                            overlap = set(sample_obj.keys()) & set(inner_props.keys())
                            if overlap:
                                return {sole_key: sample_obj}
        except Exception:
            pass
        return sample_obj

    sample_json = _maybe_wrap_root(sample_json, payload_schema)
    json_attrs, json_types = get_all_json_paths(sample_json)
    # Collect YAML schema derived data (each call uses its own visited set)
    yaml_attrs, yaml_types = get_all_yaml_paths(payload_schema, full_root=asyncapi)
    required_yaml_attrs = get_required_yaml_paths(payload_schema, full_root=asyncapi)
    # Refine branch-specific required attributes (oneOf) so inactive variant requirements are excluded
    try:
        required_yaml_attrs = refine_oneof_required(sample_json, payload_schema, required_yaml_attrs, asyncapi)
    except Exception:
        pass  # heuristic refinement failure should not abort validation
    length_constraints = get_length_constraints(payload_schema, full_root=asyncapi)
    wildcard_prefixes = gather_additional_properties_prefixes(payload_schema, full_root=asyncapi)
    pattern_constraints = get_pattern_constraints(payload_schema, full_root=asyncapi)
    enum_map, numeric_map, composition_map = collect_additional_constraints(payload_schema, full_root=asyncapi)

    extra_attrs = print_extra_attrs(json_attrs, yaml_attrs, wildcard_prefixes)
    
    # Filter out required fields that are under Jinja2 variable paths (structural mode only)
    if structural_only_validation and jinja2_variable_paths:
        filtered_required = set()
        for req_path in required_yaml_attrs:
            # Check if this required path is nested under a Jinja2 variable
            is_under_jinja_var = False
            for jinja_var in jinja2_variable_paths:
                # Check if req_path starts with a path containing the jinja variable
                if f'.{jinja_var}.' in f'.{req_path}.':
                    is_under_jinja_var = True
                    break
            if not is_under_jinja_var:
                filtered_required.add(req_path)
        
        if len(required_yaml_attrs) > len(filtered_required):
            excluded_count = len(required_yaml_attrs) - len(filtered_required)
            print(f"[INFO] Excluded {excluded_count} required fields that are nested under Jinja2 variables")
        
        required_yaml_attrs = filtered_required
    
    required_missing = print_required_missing(required_yaml_attrs, json_attrs)
    
    # Skip value-based validations in structural mode (template without context)
    if structural_only_validation:
        type_mismatches = []
        length_violations = []
        pattern_violations = []
        enum_violations = []
        numeric_violations = []
        composition_violations = []
    else:
        type_mismatches = get_type_mismatches(json_types, yaml_types, sample_json)
        print_type_mismatches(type_mismatches)
        length_violations = check_length_violations(sample_json, length_constraints)
        print_length_violations(length_violations)
        pattern_violations = check_pattern_violations(sample_json, pattern_constraints)
        print_pattern_violations(pattern_violations)
        enum_violations = check_enum_violations(sample_json, enum_map)
        print_enum_violations(enum_violations)
        numeric_violations = check_numeric_violations(sample_json, numeric_map)
        print_numeric_violations(numeric_violations)
        composition_violations = check_composition_violations(sample_json, composition_map, asyncapi)
        print_composition_violations(composition_violations)

    # --- Build Jinja rows (new style only) ---
    counts = {
        'Extra Attributes': {'count': len(extra_attrs), 'fail': bool(extra_attrs)},
        'Type Mismatches': {'count': len(type_mismatches), 'fail': bool(type_mismatches)},
        'Missing Required': {'count': len(required_missing), 'fail': bool(required_missing)},
        'Length Violations': {'count': len(length_violations), 'fail': bool(length_violations)},
        'Pattern Violations': {'count': len(pattern_violations), 'fail': bool(pattern_violations)},
        'Enum Violations': {'count': len(enum_violations), 'fail': bool(enum_violations)},
        'Numeric Violations': {'count': len(numeric_violations), 'fail': bool(numeric_violations)},
        'Composition Violations': {'count': len(composition_violations), 'fail': bool(composition_violations)},
    }

    # Load spec lines (JSON first if provided/sibling) and payload lines for context extraction
    spec_json_lines: List[str] = []
    spec_yaml_lines: List[str] = []
    candidate_json_spec = ''
    spec_path_lower = yaml_path.lower()
    if spec_path_lower.endswith(('.yaml', '.yml')):
        base_no_ext = yaml_path.rsplit('.', 1)[0]
        cand = base_no_ext + '.json'
        if os.path.exists(cand):
            candidate_json_spec = cand
    elif spec_path_lower.endswith('.json'):
        candidate_json_spec = yaml_path

    if candidate_json_spec:
        try:
            with open(candidate_json_spec, 'r', encoding='utf-8') as sf:
                spec_json_lines = sf.readlines()
        except Exception:
            spec_json_lines = []

    try:
        with open(yaml_path, 'r', encoding='utf-8') as sf:
            original_lines = sf.readlines()
    except Exception:
        original_lines = []
    if spec_path_lower.endswith(('.yaml', '.yml')):
        spec_yaml_lines = original_lines
    else:
        spec_yaml_lines = []
    try:
        with open(json_path, 'r', encoding='utf-8') as pf:
            payload_lines_source = pf.readlines()
    except Exception:
        payload_lines_source = []

    def extract_path(msg: str) -> str:
        return msg.split(':', 1)[0].strip()

    def build_context_table(lines: List[str], key: str, is_json: bool, context: int = 2, truncate: int | None = None) -> str:
        if not lines or not key:
            return ''
        if is_json:
            pat = re.compile(r'"' + re.escape(key) + r'"\s*:')
        else:
            pat = re.compile(r'^\s*' + re.escape(key) + r'\s*:')
        target_index = None
        for idx, line in enumerate(lines):
            if pat.search(line):
                target_index = idx
                break
        if target_index is None:
            return ''
        start = max(0, target_index - context)
        end = min(len(lines), target_index + context + 1)
        snippet = lines[start:end]
        rows_html = []
        for offset, raw in enumerate(snippet, start=start):
            ln_no = offset + 1
            esc_line = _html.escape(raw.rstrip('\n'))
            if truncate and len(esc_line) > truncate:
                short = esc_line[:truncate] + '…'
                esc_line = f"<span title=\"{esc_line}\">{short}</span>"
            is_target = offset == target_index
            if is_json and truncate is None:
                # Payload table: no arrow column, highlight row
                highlight_cls = ' target-row' if is_target else ''
                rows_html.append(f"<tr class='{highlight_cls}'><td class='ln'>{ln_no}</td><td class='src'>{esc_line}</td></tr>")
            else:
                arrow = '➡' if is_target else ''
                rows_html.append(f"<tr><td class='ln'>{ln_no}</td><td class='mk'>{arrow}</td><td class='src'>{esc_line}</td></tr>")
        # Decide column layout: if payload style used, add class modifier
        table_class = 'snippet payload-snippet' if (is_json and truncate is None) else 'snippet'
        return f"<table class='{table_class}'>" + ''.join(rows_html) + "</table>"

    rows: List[Dict[str, Any]] = []
    def add_rows(category: str, issues: List[str]):
        icon_map = ICONS  # reuse unified mapping
        sev_map = {
            'Extra Attributes': 'WARN', 'Missing Required': 'ERROR', 'Type Mismatches': 'ERROR', 'Length Violations': 'WARN',
            'Pattern Violations': 'ERROR', 'Enum Violations': 'ERROR', 'Numeric Violations': 'ERROR', 'Composition Violations': 'ERROR'
        }
        for issue in issues:
            path = extract_path(issue)
            last_key = path.split('.')[-1]
            spec_table = ''
            if spec_json_lines:
                spec_table = build_context_table(spec_json_lines, last_key, is_json=True, truncate=100)
            if not spec_table and spec_yaml_lines:
                spec_table = build_context_table(spec_yaml_lines, last_key, is_json=False, truncate=100)
            payload_table = build_context_table(payload_lines_source, last_key, is_json=True)
            rows.append({
                'category': category,
                'category_icon': icon_map.get(category, ''),
                'severity': sev_map.get(category, 'INFO'),
                'path': path,
                'message': issue.split(':',1)[1].strip() if ':' in issue else issue,
                'spec_table': spec_table,
                'payload_table': payload_table,
            })

    add_rows('Extra Attributes', [f"{p}: attribute not declared" for p in extra_attrs])
    add_rows('Type Mismatches', type_mismatches)
    add_rows('Missing Required', [f"{p}: required but missing" for p in required_missing])
    add_rows('Length Violations', length_violations)
    add_rows('Pattern Violations', pattern_violations)
    add_rows('Enum Violations', enum_violations)
    add_rows('Numeric Violations', numeric_violations)
    add_rows('Composition Violations', composition_violations)
    rows.sort(key=lambda r: (r['category'], r['path']))

    spec_label = 'Schema (JSON excerpt)' if is_json_spec else 'Schema (YAML excerpt)'
    # --- Extract specification metadata (version/title) for HTML display ---
    spec_info = asyncapi.get('info') if isinstance(asyncapi, dict) else {}
    spec_version = spec_info.get('version') if isinstance(spec_info, dict) else None
    spec_title = spec_info.get('title') if isinstance(spec_info, dict) else None
    asyncapi_version = asyncapi.get('asyncapi') if isinstance(asyncapi, dict) else None
    # Only generate HTML report if --html-report flag was provided
    if html_report_path:
        context = {
            'generated_at': datetime.utcnow().isoformat(timespec='seconds') + 'Z',
            'summary': {'fail': bool(extra_attrs or type_mismatches or required_missing or length_violations or pattern_violations or enum_violations or numeric_violations or composition_violations)},
            'counts': counts,
            'rows': rows,
            'spec_label': spec_label,
            'icon_map': ICONS,
            'spec_version': spec_version,
            'spec_title': spec_title,
            'asyncapi_version': asyncapi_version,
        }
        _render_html_report(context, html_report_path)

    fail = bool(
        extra_attrs or type_mismatches or required_missing or length_violations or pattern_violations or
        enum_violations or numeric_violations or composition_violations
    )

    if fail:
        print("\n❌ RESULT: FAIL")
        sys.exit(1)
    else:
        print("\n✅ RESULT: PASS")
        sys.exit(0)

if __name__ == "__main__":
    main()
