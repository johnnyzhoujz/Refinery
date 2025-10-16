# Hypothesis Pack Schema

**Status**: ✅ Production-ready (v1.0.0)

This directory contains the complete Hypothesis Pack v1 schema specification, examples, and validation tools.

## Contents

- `hypothesis-pack-v1.yaml` - JSON Schema definition (draft-07 compliant)
- `examples/` - Example hypothesis packs demonstrating various use cases
- `schema-design.md` - Comprehensive design document (root directory)

## Quick Start

### Validate Schema and Examples

```bash
# Install dependencies
pip install jsonschema pyyaml

# Run validation
python scripts/validate_schema.py
```

### Using the Schema

```python
from refinery.schemas.hypothesis_pack_v1 import HypothesisPack

# Load and validate
pack = HypothesisPack.from_yaml("hypothesis.yaml")

# Access data
print(f"Trace: {pack.metadata.trace_id}")
print(f"Findings: {len(pack.findings)}")
print(f"Hypotheses: {len(pack.hypotheses)}")
```

## Validation Status

✅ Schema validated against JSON Schema draft-07
✅ All required fields defined
✅ Enum values consistent
✅ All examples pass validation
