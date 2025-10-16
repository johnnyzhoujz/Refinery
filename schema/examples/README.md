# Hypothesis Pack v1 Examples

This directory contains example hypothesis packs demonstrating various use cases and edge cases.

## Examples

### 1. Simple Hypothesis Pack (`simple-hypothesis-pack.yaml`)

**Use Case**: Single finding, single hypothesis
**Scenario**: Intent classifier misclassifies billing query as general inquiry

This example demonstrates:
- Basic hypothesis pack structure
- Single diagnostic finding
- One hypothesis with a single proposed change
- Complete metadata and reproducibility sections

**Key Features**:
- Prompt modification change type
- Few-shot learning approach
- Before/after examples
- Generation metadata included

---

### 2. Complex Hypothesis Pack (`complex-hypothesis-pack.yaml`)

**Use Case**: Multiple findings, multiple ranked hypotheses
**Scenario**: Cascading failure across intent classification, retrieval, and orchestration

This example demonstrates:
- Multiple diagnostic findings with different severities
- Three ranked hypotheses addressing different aspects
- Multiple change types (prompt, config, orchestration)
- Cross-component impact analysis

**Key Features**:
- Prompt modification (hypothesis 1)
- Config change (hypothesis 2)
- Orchestration suggestion (hypothesis 3)
- Confidence ranking (high → medium → high)
- Risk assessment for each hypothesis

---

### 3. Diagnostic-Only Hypothesis Pack (`diagnostic-only-hypothesis-pack.yaml`)

**Use Case**: Edge case - infrastructure issue with no code fixes
**Scenario**: External API timeout (non-code problem)

This example demonstrates:
- Hypothesis with empty `proposed_changes` array
- Infrastructure/external service issues
- Diagnostic-only output (no actionable code changes)
- Minimal configuration

**Key Features**:
- Empty `proposed_changes: []`
- "Non-code fix required" in description
- Still provides before/after examples for validation
- Demonstrates schema flexibility

---

## Schema Validation

All examples validate against `schema/hypothesis-pack-v1.yaml`.

### Validate Examples

```bash
# Using Python jsonschema library
pip install pyyaml jsonschema

# Validate simple example
python -c "
import yaml
from jsonschema import validate

with open('schema/hypothesis-pack-v1.yaml') as f:
    schema = yaml.safe_load(f)

with open('schema/examples/simple-hypothesis-pack.yaml') as f:
    data = yaml.safe_load(f)

validate(instance=data, schema=schema)
print('✓ Simple example is valid')
"

# Validate all examples
for example in schema/examples/*.yaml; do
    echo "Validating $example..."
    python -c "
import yaml
from jsonschema import validate

with open('schema/hypothesis-pack-v1.yaml') as f:
    schema = yaml.safe_load(f)

with open('$example') as f:
    data = yaml.safe_load(f)

validate(instance=data, schema=schema)
print('✓ Valid')
"
done
```

### Using Pydantic Models

```python
from refinery.schemas.hypothesis_pack_v1 import HypothesisPack

# Load and validate
pack = HypothesisPack.from_yaml("schema/examples/simple-hypothesis-pack.yaml")

# Access data
print(f"Trace: {pack.metadata.trace_id}")
print(f"Findings: {len(pack.findings)}")
print(f"Hypotheses: {len(pack.hypotheses)}")

# Export to JSON
json_output = pack.to_json()
print(json_output)
```

---

## Common Patterns

### Pattern 1: Prompt Modification with Few-Shot Examples

See: `simple-hypothesis-pack.yaml`, `complex-hypothesis-pack.yaml` (hyp-001)

```yaml
proposed_changes:
  - file_path: "prompts/intent_classifier/system.txt"
    change_type: "prompt_modification"
    description: "Add billing_inquiry intent and few-shot examples"
    original_content: |
      [current prompt]
    new_content: |
      [updated prompt with examples]
    diff: |
      [unified diff]
```

### Pattern 2: Config Change for Knowledge Base

See: `complex-hypothesis-pack.yaml` (hyp-002)

```yaml
proposed_changes:
  - file_path: "config/knowledge_base/document_sources.yaml"
    change_type: "config_change"
    description: "Add billing policy documents to knowledge base"
    original_content: |
      [current config]
    new_content: |
      [updated config with new source]
```

### Pattern 3: Orchestration Suggestion

See: `complex-hypothesis-pack.yaml` (hyp-003)

```yaml
proposed_changes:
  - file_path: "orchestration/routing.yaml"
    change_type: "orchestration_suggestion"
    description: "Add billing_inquiry routing rule to BillingHandler"
    original_content: |
      [current routing]
    new_content: |
      [updated routing with new rule]
```

### Pattern 4: Diagnostic-Only (No Changes)

See: `diagnostic-only-hypothesis-pack.yaml`

```yaml
hypotheses:
  - id: "hyp-001"
    description: "Infrastructure issue (non-code fix)"
    rationale: "External service problem, not agent code"
    confidence: "high"
    risks: []
    proposed_changes: []  # Empty - no code changes needed
```

---

## Extending Examples

When adding new examples:

1. **Follow naming convention**: `{use-case}-hypothesis-pack.yaml`
2. **Validate against schema**: Ensure it passes JSON Schema validation
3. **Update this README**: Add description and key features
4. **Include metadata**: Complete all required fields
5. **Add to tests**: Include in golden test suite

---

## Schema Version

All examples use:
- **Schema Version**: v1.0.0
- **Schema URL**: https://refinery.ai/schemas/hypothesis-pack/v1

When the schema is updated to v1.1.0 or v2.0.0, examples will be versioned accordingly.
