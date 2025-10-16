"""
Pydantic models for Hypothesis Pack v1 schema.

This module provides strongly-typed models with validation for the Hypothesis Pack
interchange format. Use these models to serialize/deserialize hypothesis packs
and validate against the JSON Schema.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import hashlib
import json
import yaml
from pydantic import BaseModel, Field, field_validator, model_validator


# Enums


class FindingType(str, Enum):
    """Type of diagnostic finding."""

    GAP = "gap"
    ERROR = "error"
    INEFFICIENCY = "inefficiency"


class FindingSeverity(str, Enum):
    """Severity level for findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConfidenceLevel(str, Enum):
    """Confidence level for hypotheses."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ChangeType(str, Enum):
    """Type of proposed change."""

    PROMPT_MODIFICATION = "prompt_modification"
    EVAL_MODIFICATION = "eval_modification"
    CONFIG_CHANGE = "config_change"
    ORCHESTRATION_SUGGESTION = "orchestration_suggestion"


class ConfidenceMethodology(str, Enum):
    """Methodology used to compute confidence scores."""

    EVIDENCE_BASED_RANKING = "evidence-based-ranking"
    LLM_SELF_ASSESSMENT = "llm-self-assessment"
    HYBRID = "hybrid"


# Models


class Metadata(BaseModel):
    """Metadata about the trace and analysis."""

    trace_id: str = Field(..., min_length=1, description="Trace identifier")
    project: str = Field(..., min_length=1, description="Project name")
    analyzed_at: datetime = Field(..., description="Analysis timestamp (ISO 8601)")
    refinery_version: str = Field(
        ..., pattern=r"^\d+\.\d+\.\d+.*$", description="Refinery version (semver)"
    )
    analysis_model: str = Field(
        ..., min_length=1, description="Model used for trace analysis"
    )
    hypothesis_model: str = Field(
        ..., min_length=1, description="Model used for hypothesis generation"
    )
    confidence_methodology: ConfidenceMethodology = Field(
        ..., description="Confidence scoring method"
    )
    total_analysis_time_ms: Optional[int] = Field(
        None, ge=0, description="Total analysis time in milliseconds"
    )


class Finding(BaseModel):
    """A diagnostic finding from trace analysis."""

    type: FindingType = Field(..., description="Category of finding")
    description: str = Field(
        ..., min_length=10, max_length=500, description="Finding summary"
    )
    evidence: List[str] = Field(..., min_length=1, description="Supporting evidence")
    severity: FindingSeverity = Field(..., description="Severity level")
    affected_components: Optional[List[str]] = Field(
        default_factory=list, description="Affected components"
    )

    @field_validator("evidence")
    @classmethod
    def evidence_must_not_be_empty(cls, v):
        if not v or len(v) == 0:
            raise ValueError("evidence array must contain at least one item")
        return v


class ProposedChange(BaseModel):
    """A proposed code/config change."""

    file_path: str = Field(
        ...,
        pattern=r"^(prompts|config|orchestration|tests|evals)/.*",
        description="File path (must start with allowed prefix)",
    )
    change_type: ChangeType = Field(..., description="Type of change")
    description: str = Field(
        ..., min_length=10, max_length=200, description="Change summary"
    )
    original_content: str = Field(..., description="Current content")
    new_content: str = Field(..., description="Proposed new content")
    diff: Optional[str] = Field(None, description="Unified diff (optional)")

    @model_validator(mode="after")
    def warn_if_contents_identical(self):
        """Warn if original and new content are identical."""
        if self.original_content == self.new_content:
            import warnings

            warnings.warn(
                f"original_content and new_content are identical for {self.file_path}"
            )
        return self


class GenerationMetadata(BaseModel):
    """Metadata about hypothesis generation."""

    model: Optional[str] = Field(None, description="Model used for generation")
    provider: Optional[str] = Field(None, description="LLM provider")
    max_tokens: Optional[int] = Field(None, ge=0, description="Max output tokens")
    reasoning_effort: Optional[str] = Field(
        None, description="Reasoning effort level"
    )
    diagnosis_hash: Optional[str] = Field(
        None, pattern=r"^sha256:[a-f0-9]{64}$", description="Diagnosis hash"
    )
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    schema_version: Optional[str] = Field(
        None, description="Internal schema version"
    )
    attempts: Optional[int] = Field(None, ge=1, description="Number of attempts")
    response_id: Optional[str] = Field(
        None, description="Provider response ID for debugging"
    )


class Hypothesis(BaseModel):
    """A ranked hypothesis for fixing the issue."""

    id: str = Field(
        ..., pattern=r"^hyp-\d{3}$", description="Hypothesis ID (format: hyp-NNN)"
    )
    description: str = Field(
        ..., min_length=10, max_length=200, description="Hypothesis summary"
    )
    rationale: str = Field(
        ..., min_length=20, max_length=1000, description="Why this fix should work"
    )
    confidence: ConfidenceLevel = Field(..., description="Confidence level")
    risks: List[str] = Field(default_factory=list, description="Potential risks")
    proposed_changes: List[ProposedChange] = Field(
        ...,
        min_length=0,
        description="Proposed changes (may be empty for diagnostic-only)",
    )
    example_before: Optional[str] = Field(
        None, max_length=500, description="Example of current behavior"
    )
    example_after: Optional[str] = Field(
        None, max_length=500, description="Example of expected behavior"
    )
    generation_metadata: Optional[GenerationMetadata] = Field(
        None, description="Generation metadata"
    )


class ModelParams(BaseModel):
    """Model hyperparameters for reproducibility."""

    temperature: Optional[float] = Field(
        None, ge=0.0, le=2.0, description="Sampling temperature"
    )
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Nucleus sampling")
    frequency_penalty: Optional[float] = Field(
        None, ge=-2.0, le=2.0, description="Frequency penalty"
    )
    presence_penalty: Optional[float] = Field(
        None, ge=-2.0, le=2.0, description="Presence penalty"
    )


class Reproducibility(BaseModel):
    """Reproducibility metadata."""

    seed: Optional[int] = Field(None, description="Random seed (nullable)")
    model_params: Optional[ModelParams] = Field(
        None, description="Model hyperparameters"
    )
    diagnosis_hash: str = Field(
        ..., pattern=r"^sha256:[a-f0-9]{64}$", description="Diagnosis hash (SHA-256)"
    )
    refinery_config: Optional[Dict[str, Any]] = Field(
        None, description="Refinery-specific config"
    )


class HypothesisPack(BaseModel):
    """Complete Hypothesis Pack v1 schema."""

    schema_: str = Field(..., alias="$schema", description="Schema identifier URL")
    version: str = Field(
        ..., pattern=r"^\d+\.\d+\.\d+$", description="Schema version (semver)"
    )
    metadata: Metadata = Field(..., description="Trace and analysis metadata")
    findings: List[Finding] = Field(..., description="Diagnostic findings")
    hypotheses: List[Hypothesis] = Field(..., description="Ranked hypotheses")
    reproducibility: Reproducibility = Field(..., description="Reproducibility metadata")

    model_config = {"populate_by_name": True}  # Allow both 'schema_' and '$schema'

    @field_validator("version")
    @classmethod
    def validate_version(cls, v):
        """Validate version is v1.x.x"""
        major = int(v.split(".")[0])
        if major != 1:
            raise ValueError(f"This model only supports v1.x.x schemas, got {v}")
        return v

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary with $schema alias."""
        # Use mode='json' to serialize datetime and other types properly
        return self.model_dump(by_alias=True, exclude_none=True, mode='json')

    def to_yaml(self) -> str:
        """Serialize to YAML string."""
        # Convert to JSON-compatible dict first (handles datetime, enums, etc.)
        json_str = self.to_json()
        data = json.loads(json_str)
        return yaml.dump(data, sort_keys=False, allow_unicode=True, default_flow_style=False)

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        data = self.to_dict()
        return json.dumps(data, indent=indent, ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HypothesisPack":
        """Deserialize from dictionary."""
        return cls.model_validate(data)

    @classmethod
    def from_yaml(cls, yaml_str: str) -> "HypothesisPack":
        """Deserialize from YAML string."""
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)

    @classmethod
    def from_json(cls, json_str: str) -> "HypothesisPack":
        """Deserialize from JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)


# Converter functions from existing dataclasses


def convert_diagnosis_to_findings(diagnosis) -> List[Finding]:
    """Convert Diagnosis dataclass to Finding models."""
    from ..core.models import Confidence as OldConfidence
    from ..core.models import FailureType as OldFailureType

    # Map failure types to finding types
    type_map = {
        OldFailureType.PROMPT_ISSUE: FindingType.GAP,
        OldFailureType.CONTEXT_ISSUE: FindingType.GAP,
        OldFailureType.MODEL_LIMITATION: FindingType.ERROR,
        OldFailureType.ORCHESTRATION_ISSUE: FindingType.ERROR,
        OldFailureType.RETRIEVAL_ISSUE: FindingType.ERROR,
        OldFailureType.OUTPUT_PARSING_ISSUE: FindingType.ERROR,
    }

    # Map confidence to severity
    severity_map = {
        OldConfidence.HIGH: FindingSeverity.CRITICAL,
        OldConfidence.MEDIUM: FindingSeverity.HIGH,
        OldConfidence.LOW: FindingSeverity.MEDIUM,
    }

    return [
        Finding(
            type=type_map.get(diagnosis.failure_type, FindingType.ERROR),
            description=diagnosis.root_cause,
            evidence=diagnosis.evidence,
            severity=severity_map.get(diagnosis.confidence, FindingSeverity.HIGH),
            affected_components=diagnosis.affected_components,
        )
    ]


def convert_hypotheses_to_schema(hypotheses_list) -> List[Hypothesis]:
    """Convert Hypothesis dataclasses to Hypothesis models."""
    result = []
    for hyp in hypotheses_list:
        # Convert proposed changes
        changes = [
            ProposedChange(
                file_path=fc.file_path,
                change_type=ChangeType(fc.change_type.value),
                description=fc.description,
                original_content=fc.original_content,
                new_content=fc.new_content,
                diff=getattr(fc, "diff", None),
            )
            for fc in hyp.proposed_changes
        ]

        # Convert generation metadata if present
        gen_meta = None
        if hasattr(hyp, "generation_metadata") and hyp.generation_metadata:
            gm = hyp.generation_metadata
            gen_meta = GenerationMetadata(
                model=gm.get("model"),
                provider=gm.get("provider"),
                max_tokens=gm.get("max_tokens"),
                reasoning_effort=gm.get("reasoning_effort"),
                diagnosis_hash=gm.get("diagnosis_hash"),
                created_at=gm.get("created_at"),
                schema_version=gm.get("schema_version"),
                attempts=gm.get("attempts"),
                response_id=gm.get("response_id"),
            )

        result.append(
            Hypothesis(
                id=hyp.id,
                description=hyp.description,
                rationale=hyp.rationale,
                confidence=ConfidenceLevel(hyp.confidence.value),
                risks=hyp.risks,
                proposed_changes=changes,
                example_before=hyp.example_before,
                example_after=hyp.example_after,
                generation_metadata=gen_meta,
            )
        )

    return result


def create_hypothesis_pack(
    trace_id: str,
    project: str,
    diagnosis,
    hypotheses_list: list,
    refinery_version: str = "0.1.0",
    analysis_model: str = "gpt-5-preview",
    hypothesis_model: str = "gpt-5-preview",
    total_analysis_time_ms: Optional[int] = None,
) -> HypothesisPack:
    """Create a HypothesisPack from existing dataclasses."""

    # Generate diagnosis hash
    diagnosis_str = (
        f"{diagnosis.root_cause}:{diagnosis.failure_type.value}:{diagnosis.confidence.value}"
    )
    diagnosis_hash = f"sha256:{hashlib.sha256(diagnosis_str.encode()).hexdigest()}"

    return HypothesisPack(
        schema_="https://raw.githubusercontent.com/johnnyzhoujz/Refinery/v0.1.0/schema/hypothesis-pack-v1.yaml",
        version="1.0.0",
        metadata=Metadata(
            trace_id=trace_id,
            project=project,
            analyzed_at=datetime.now(timezone.utc),
            refinery_version=refinery_version,
            analysis_model=analysis_model,
            hypothesis_model=hypothesis_model,
            confidence_methodology=ConfidenceMethodology.EVIDENCE_BASED_RANKING,
            total_analysis_time_ms=total_analysis_time_ms,
        ),
        findings=convert_diagnosis_to_findings(diagnosis),
        hypotheses=convert_hypotheses_to_schema(hypotheses_list),
        reproducibility=Reproducibility(
            seed=None,
            model_params=ModelParams(
                temperature=0.0,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0,
            ),
            diagnosis_hash=diagnosis_hash,
            refinery_config={
                "analysis_model": analysis_model,
                "hypothesis_model": hypothesis_model,
            },
        ),
    )
