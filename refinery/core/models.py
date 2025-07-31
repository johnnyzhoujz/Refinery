"""
Shared data models and interfaces for Refinery.

These models define the common data structures used across all components
to ensure consistency and type safety.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field


class RunType(str, Enum):
    """Types of runs in a trace."""
    LLM = "llm"
    CHAIN = "chain"
    TOOL = "tool"
    RETRIEVER = "retriever"
    EMBEDDING = "embedding"
    PROMPT = "prompt"
    PARSER = "parser"


class FailureType(str, Enum):
    """Categories of AI agent failures."""
    PROMPT_ISSUE = "prompt_issue"
    CONTEXT_ISSUE = "context_issue"
    MODEL_LIMITATION = "model_limitation"
    ORCHESTRATION_ISSUE = "orchestration_issue"
    RETRIEVAL_ISSUE = "retrieval_issue"
    OUTPUT_PARSING_ISSUE = "output_parsing_issue"


class ChangeType(str, Enum):
    """Types of code changes."""
    PROMPT_MODIFICATION = "prompt_modification"
    EVAL_MODIFICATION = "eval_modification"
    CONFIG_CHANGE = "config_change"
    ORCHESTRATION_SUGGESTION = "orchestration_suggestion"


class Confidence(str, Enum):
    """Confidence levels for hypotheses."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class TraceRun:
    """Represents a single run (span) in a trace."""
    id: str
    name: str
    run_type: RunType
    inputs: Dict[str, Any]
    outputs: Optional[Dict[str, Any]]
    start_time: datetime
    end_time: Optional[datetime]
    error: Optional[str]
    parent_run_id: Optional[str]
    trace_id: str
    dotted_order: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> Optional[float]:
        """Calculate run duration in milliseconds."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return None
    
    @property
    def is_failed(self) -> bool:
        """Check if this run failed."""
        return self.error is not None


@dataclass
class Trace:
    """Complete trace of an AI agent execution."""
    trace_id: str
    project_name: str
    runs: List[TraceRun]
    start_time: datetime
    end_time: Optional[datetime]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def get_root_run(self) -> Optional[TraceRun]:
        """Get the root run of this trace."""
        for run in self.runs:
            if run.parent_run_id is None:
                return run
        return None
    
    def get_failed_runs(self) -> List[TraceRun]:
        """Get all failed runs in this trace."""
        return [run for run in self.runs if run.is_failed]


@dataclass
class DomainExpertExpectation:
    """What the domain expert expected to happen."""
    description: str
    expected_output: Optional[str] = None
    business_context: Optional[str] = None
    specific_issues: List[str] = field(default_factory=list)


@dataclass
class TraceAnalysis:
    """Structured analysis of a trace."""
    trace_id: str
    execution_flow: List[Dict[str, Any]]
    context_at_each_step: Dict[str, Any]
    data_transformations: List[Dict[str, Any]]
    error_propagation_path: Optional[List[str]] = None
    identified_issues: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class GapAnalysis:
    """Analysis of gaps between expected and actual behavior."""
    behavioral_differences: List[str]
    missing_context: List[str]
    incorrect_assumptions: List[str]
    suggested_focus_areas: List[str]


@dataclass
class Diagnosis:
    """Root cause diagnosis of a failure."""
    failure_type: FailureType
    root_cause: str
    evidence: List[str]
    affected_components: List[str]
    confidence: Confidence
    detailed_analysis: str


@dataclass
class FileChange:
    """Represents a change to a file."""
    file_path: str
    original_content: str
    new_content: str
    change_type: ChangeType
    description: str
    
    def get_diff(self) -> str:
        """Generate a diff of the changes."""
        # TODO: Implement proper diff generation
        return f"--- {self.file_path}\n+++ {self.file_path}\n..."


@dataclass
class Hypothesis:
    """A hypothesis for fixing an AI agent failure."""
    id: str
    description: str
    rationale: str
    proposed_changes: List[FileChange]
    confidence: Confidence
    risks: List[str]
    example_before: Optional[str] = None
    example_after: Optional[str] = None
    
    def get_risk_level(self) -> str:
        """Assess overall risk level of this hypothesis."""
        if len(self.risks) == 0:
            return "low"
        elif len(self.risks) <= 2:
            return "medium"
        else:
            return "high"


@dataclass
class ValidationResult:
    """Result of validating a change."""
    is_valid: bool
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ImpactReport:
    """Report on the potential impact of changes."""
    affected_files: List[str]
    potential_breaking_changes: List[str]
    suggested_tests: List[str]
    confidence: Confidence


class CodeContext(BaseModel):
    """Context about the codebase."""
    repository_path: str
    main_language: str = "python"
    framework: Optional[str] = None
    relevant_files: List[str] = Field(default_factory=list)
    dependencies: Dict[str, str] = Field(default_factory=dict)
    

class AnalysisRequest(BaseModel):
    """Request to analyze a failed trace."""
    trace: Trace
    expectation: DomainExpertExpectation
    code_context: Optional[CodeContext] = None
    previous_analyses: List[Diagnosis] = Field(default_factory=list)


class HypothesisRequest(BaseModel):
    """Request to generate hypotheses."""
    diagnosis: Diagnosis
    code_context: CodeContext
    constraints: List[str] = Field(default_factory=list)
    preferred_approach: Optional[str] = None