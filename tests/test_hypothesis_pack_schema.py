"""
Golden test for Hypothesis Pack schema validation.

This test ensures that CLI output produces valid hypothesis packs
that pass schema validation.
"""

import json
from pathlib import Path

import pytest
import yaml

from refinery.core.models import (
    ChangeType,
    Confidence,
    Diagnosis,
    FailureType,
    FileChange,
    Hypothesis,
)
from refinery.schemas.hypothesis_pack_v1 import (
    HypothesisPack,
    create_hypothesis_pack,
)


@pytest.fixture
def sample_diagnosis():
    """Create a sample diagnosis for testing."""
    return Diagnosis(
        failure_type=FailureType.PROMPT_ISSUE,
        root_cause="Intent classifier lacks billing category",
        evidence=[
            "User query: 'cancel subscription' → classified as 'general_inquiry'",
            "Expected: 'billing_inquiry'",
        ],
        affected_components=["IntentClassifier"],
        confidence=Confidence.HIGH,
        detailed_analysis="The classifier lacks training data for billing queries.",
    )


@pytest.fixture
def sample_hypothesis():
    """Create a sample hypothesis for testing."""
    return Hypothesis(
        id="hyp-001",
        description="Add billing intent to classifier",
        rationale="Adding few-shot examples will improve classification.",
        confidence=Confidence.HIGH,
        risks=["May increase token usage"],
        proposed_changes=[
            FileChange(
                file_path="prompts/intent_classifier/system.txt",
                original_content="Classify into: [general_inquiry, technical_support]",
                new_content="Classify into: [general_inquiry, technical_support, billing_inquiry]",
                change_type=ChangeType.PROMPT_MODIFICATION,
                description="Add billing intent category",
            )
        ],
        example_before="User: 'cancel subscription' → 'general_inquiry'",
        example_after="User: 'cancel subscription' → 'billing_inquiry'",
    )


@pytest.fixture
def json_schema():
    """Load the JSON Schema definition."""
    schema_path = Path(__file__).parent.parent / "schema" / "hypothesis-pack-v1.yaml"
    with open(schema_path) as f:
        return yaml.safe_load(f)


def test_create_hypothesis_pack_from_dataclasses(sample_diagnosis, sample_hypothesis):
    """Test creating a hypothesis pack from existing dataclasses."""
    pack = create_hypothesis_pack(
        trace_id="test-trace-001",
        project="test-project",
        diagnosis=sample_diagnosis,
        hypotheses_list=[sample_hypothesis],
    )

    assert pack.metadata.trace_id == "test-trace-001"
    assert pack.metadata.project == "test-project"
    assert len(pack.findings) == 1
    assert len(pack.hypotheses) == 1
    assert pack.hypotheses[0].id == "hyp-001"
    assert len(pack.hypotheses[0].proposed_changes) == 1


def test_hypothesis_pack_yaml_serialization(sample_diagnosis, sample_hypothesis):
    """Test YAML serialization/deserialization."""
    pack = create_hypothesis_pack(
        trace_id="test-trace-001",
        project="test-project",
        diagnosis=sample_diagnosis,
        hypotheses_list=[sample_hypothesis],
    )

    # Serialize to YAML
    yaml_str = pack.to_yaml()
    assert "$schema" in yaml_str
    assert "hypothesis-pack" in yaml_str
    assert "hyp-001" in yaml_str

    # Deserialize back
    pack2 = HypothesisPack.from_yaml(yaml_str)
    assert pack2.metadata.trace_id == pack.metadata.trace_id
    assert pack2.hypotheses[0].id == pack.hypotheses[0].id


def test_hypothesis_pack_json_serialization(sample_diagnosis, sample_hypothesis):
    """Test JSON serialization/deserialization."""
    pack = create_hypothesis_pack(
        trace_id="test-trace-001",
        project="test-project",
        diagnosis=sample_diagnosis,
        hypotheses_list=[sample_hypothesis],
    )

    # Serialize to JSON
    json_str = pack.to_json()
    data = json.loads(json_str)
    assert data["$schema"] == "https://raw.githubusercontent.com/johnnyzhoujz/Refinery/v0.1.0/schema/hypothesis-pack-v1.yaml"
    assert data["version"] == "1.0.0"

    # Deserialize back
    pack2 = HypothesisPack.from_json(json_str)
    assert pack2.metadata.trace_id == pack.metadata.trace_id


def test_hypothesis_pack_validates_against_json_schema(
    sample_diagnosis, sample_hypothesis, json_schema
):
    """Test that generated hypothesis packs validate against JSON Schema."""
    from jsonschema import ValidationError, validate

    pack = create_hypothesis_pack(
        trace_id="test-trace-001",
        project="test-project",
        diagnosis=sample_diagnosis,
        hypotheses_list=[sample_hypothesis],
    )

    # Convert to dict and validate
    data = pack.to_dict()

    try:
        validate(instance=data, schema=json_schema)
    except ValidationError as e:
        pytest.fail(f"Hypothesis pack failed schema validation: {e}")


def test_hypothesis_pack_with_empty_proposed_changes(sample_diagnosis):
    """Test edge case: hypothesis with no proposed changes (diagnostic-only)."""
    hypothesis = Hypothesis(
        id="hyp-001",
        description="Infrastructure issue (non-code fix)",
        rationale="External API timeout requires infrastructure investigation",
        confidence=Confidence.HIGH,
        risks=[],
        proposed_changes=[],  # Empty - diagnostic only
    )

    pack = create_hypothesis_pack(
        trace_id="test-trace-001",
        project="test-project",
        diagnosis=sample_diagnosis,
        hypotheses_list=[hypothesis],
    )

    assert len(pack.hypotheses[0].proposed_changes) == 0

    # Should still serialize/validate
    yaml_str = pack.to_yaml()
    pack2 = HypothesisPack.from_yaml(yaml_str)
    assert pack2.hypotheses[0].id == "hyp-001"


def test_hypothesis_pack_required_fields():
    """Test that required fields are enforced."""
    from pydantic import ValidationError

    # Missing required field should raise ValidationError
    with pytest.raises(ValidationError):
        HypothesisPack(
            schema_="https://refinery.ai/schemas/hypothesis-pack/v1",
            version="1.0.0",
            # Missing metadata, findings, hypotheses, reproducibility
        )


def test_hypothesis_pack_version_validation():
    """Test that version validation works."""
    from pydantic import ValidationError

    from refinery.schemas.hypothesis_pack_v1 import (
        Finding,
        FindingSeverity,
        FindingType,
        HypothesisPack,
        Hypothesis,
        Metadata,
        Reproducibility,
    )

    # v2.0.0 should fail (only v1.x.x supported)
    with pytest.raises(ValidationError, match="only supports v1"):
        HypothesisPack(
            schema_="https://refinery.ai/schemas/hypothesis-pack/v1",
            version="2.0.0",
            metadata=Metadata(
                trace_id="test",
                project="test",
                analyzed_at="2025-10-15T14:32:15Z",
                refinery_version="0.1.0",
                analysis_model="gpt-5-preview",
                hypothesis_model="gpt-5-preview",
                confidence_methodology="evidence-based-ranking",
            ),
            findings=[
                Finding(
                    type=FindingType.GAP,
                    description="Test finding",
                    evidence=["Evidence 1"],
                    severity=FindingSeverity.HIGH,
                )
            ],
            hypotheses=[
                Hypothesis(
                    id="hyp-001",
                    description="Test hypothesis",
                    rationale="Test rationale for the hypothesis",
                    confidence="high",
                    risks=[],
                    proposed_changes=[],
                )
            ],
            reproducibility=Reproducibility(
                diagnosis_hash="sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
            ),
        )


def test_hypothesis_id_pattern_validation():
    """Test that hypothesis ID pattern is enforced."""
    from pydantic import ValidationError

    from refinery.schemas.hypothesis_pack_v1 import Hypothesis

    # Invalid ID format should fail
    with pytest.raises(ValidationError):
        Hypothesis(
            id="invalid-id",  # Should be hyp-NNN
            description="Test hypothesis",
            rationale="Test rationale for the hypothesis",
            confidence="high",
            risks=[],
            proposed_changes=[],
        )


def test_file_path_pattern_validation():
    """Test that file_path pattern is enforced."""
    from pydantic import ValidationError

    from refinery.schemas.hypothesis_pack_v1 import ChangeType, ProposedChange

    # Invalid file path should fail (must start with allowed prefix)
    with pytest.raises(ValidationError):
        ProposedChange(
            file_path="invalid/path.txt",  # Should start with prompts|config|etc
            change_type=ChangeType.PROMPT_MODIFICATION,
            description="Test change",
            original_content="Original",
            new_content="New",
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
