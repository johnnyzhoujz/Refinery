#!/usr/bin/env python3
"""
Validate Hypothesis Pack v1 schema and examples.

This script validates:
1. The JSON Schema file itself is valid
2. All example hypothesis packs validate against the schema
3. The schema follows JSON Schema draft-07 specification

Usage:
    python scripts/validate_schema.py
"""

import sys
from pathlib import Path

import yaml

# Try to import jsonschema, provide helpful error if missing
try:
    from jsonschema import Draft7Validator, ValidationError, validate
    from jsonschema.exceptions import SchemaError
except ImportError:
    print("Error: jsonschema library not installed")
    print("Install with: pip install jsonschema")
    sys.exit(1)


def validate_json_schema(schema_path: Path) -> tuple[bool, str]:
    """
    Validate that the schema file itself is a valid JSON Schema draft-07.

    Returns:
        (is_valid, message): Tuple of validation result and message
    """
    try:
        with open(schema_path) as f:
            schema = yaml.safe_load(f)

        # Check that it's a valid draft-07 schema
        Draft7Validator.check_schema(schema)

        return True, "✓ Schema file is valid JSON Schema draft-07"

    except SchemaError as e:
        return False, f"✗ Schema validation error: {e.message}"

    except Exception as e:
        return False, f"✗ Error loading schema: {e}"


def validate_example(example_path: Path, schema: dict) -> tuple[bool, str]:
    """
    Validate an example hypothesis pack against the schema.

    Returns:
        (is_valid, message): Tuple of validation result and message
    """
    try:
        with open(example_path) as f:
            data = yaml.safe_load(f)

        # Validate against schema
        validate(instance=data, schema=schema)

        return True, f"✓ {example_path.name} is valid"

    except ValidationError as e:
        error_path = " -> ".join(str(p) for p in e.path) if e.path else "root"
        return (
            False,
            f"✗ {example_path.name} validation error at {error_path}: {e.message}",
        )

    except Exception as e:
        return False, f"✗ Error loading {example_path.name}: {e}"


def check_required_fields(schema: dict) -> tuple[bool, str]:
    """
    Check that schema defines all expected required fields.
    """
    required_root_fields = [
        "$schema",
        "version",
        "metadata",
        "findings",
        "hypotheses",
        "reproducibility",
    ]

    if "required" not in schema:
        return False, "✗ Schema missing 'required' field at root level"

    missing = set(required_root_fields) - set(schema["required"])
    if missing:
        return False, f"✗ Schema missing required fields: {missing}"

    return True, "✓ All required root fields are defined"


def check_enum_consistency(schema: dict) -> tuple[bool, list[str]]:
    """
    Check that enum values are consistent and properly defined.
    """
    issues = []

    # Check confidence enum
    hypothesis_props = (
        schema.get("properties", {})
        .get("hypotheses", {})
        .get("items", {})
        .get("properties", {})
    )
    confidence_enum = hypothesis_props.get("confidence", {}).get("enum", [])
    expected_confidence = ["high", "medium", "low"]

    if set(confidence_enum) != set(expected_confidence):
        issues.append(
            f"Confidence enum mismatch: {confidence_enum} != {expected_confidence}"
        )

    # Check finding type enum
    finding_props = (
        schema.get("properties", {})
        .get("findings", {})
        .get("items", {})
        .get("properties", {})
    )
    finding_type_enum = finding_props.get("type", {}).get("enum", [])
    expected_types = ["gap", "error", "inefficiency"]

    if set(finding_type_enum) != set(expected_types):
        issues.append(
            f"Finding type enum mismatch: {finding_type_enum} != {expected_types}"
        )

    if not issues:
        return True, ["✓ Enum values are consistent"]
    else:
        return False, [f"✗ {issue}" for issue in issues]


def main():
    """Main validation function."""
    print("=" * 60)
    print("Hypothesis Pack v1 Schema Validation")
    print("=" * 60)
    print()

    # Paths
    root_dir = Path(__file__).parent.parent
    schema_path = root_dir / "schema" / "hypothesis-pack-v1.yaml"
    examples_dir = root_dir / "schema" / "examples"

    # Track results
    all_passed = True

    # 1. Validate schema file itself
    print("1. Validating JSON Schema file...")
    is_valid, message = validate_json_schema(schema_path)
    print(f"   {message}")
    if not is_valid:
        all_passed = False
    print()

    # Load schema for subsequent validations
    try:
        with open(schema_path) as f:
            schema = yaml.safe_load(f)
    except Exception as e:
        print(f"✗ Failed to load schema: {e}")
        sys.exit(1)

    # 2. Check required fields
    print("2. Checking required fields...")
    is_valid, message = check_required_fields(schema)
    print(f"   {message}")
    if not is_valid:
        all_passed = False
    print()

    # 3. Check enum consistency
    print("3. Checking enum consistency...")
    is_valid, messages = check_enum_consistency(schema)
    for message in messages:
        print(f"   {message}")
    if not is_valid:
        all_passed = False
    print()

    # 4. Validate examples
    print("4. Validating example hypothesis packs...")

    example_files = sorted(examples_dir.glob("*.yaml"))
    if not example_files:
        print("   ⚠ No example files found")
        all_passed = False
    else:
        for example_path in example_files:
            if example_path.name == "README.md":
                continue

            is_valid, message = validate_example(example_path, schema)
            print(f"   {message}")
            if not is_valid:
                all_passed = False

    print()
    print("=" * 60)

    if all_passed:
        print("✓ All validations passed!")
        print()
        print("Schema is production-ready:")
        print("- JSON Schema draft-07 compliant")
        print("- All required fields defined")
        print("- Enum values consistent")
        print("- All examples validate successfully")
        return 0
    else:
        print("✗ Some validations failed")
        print()
        print("Please fix the issues above before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
