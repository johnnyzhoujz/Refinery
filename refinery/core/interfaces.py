"""
Abstract interfaces for Refinery components.

These interfaces define the contracts that each component must implement,
ensuring consistency and enabling easy testing and extension.
"""

from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime

from .models import (
    Trace, TraceRun, TraceAnalysis, GapAnalysis, 
    Diagnosis, Hypothesis, FileChange, ValidationResult,
    ImpactReport, DomainExpertExpectation, CodeContext
)


class TraceProvider(ABC):
    """Interface for fetching traces from observability platforms."""
    
    @abstractmethod
    async def fetch_trace(self, trace_id: str) -> Trace:
        """Fetch a single trace by ID."""
        pass
    
    @abstractmethod
    async def fetch_failed_traces(
        self, 
        project: str, 
        start_time: datetime,
        end_time: datetime,
        limit: int = 100
    ) -> List[Trace]:
        """Fetch traces that contain failures within a time range."""
        pass
    
    @abstractmethod
    async def fetch_trace_hierarchy(self, trace_id: str) -> Dict[str, Any]:
        """Fetch the complete hierarchy of a trace."""
        pass


class FailureAnalyst(ABC):
    """Interface for analyzing AI agent failures."""
    
    @abstractmethod
    async def analyze_trace(
        self, 
        trace: Trace,
        expectation: DomainExpertExpectation
    ) -> TraceAnalysis:
        """Analyze a trace and break down what happened."""
        pass
    
    @abstractmethod
    async def compare_to_expected(
        self,
        analysis: TraceAnalysis,
        expectation: DomainExpertExpectation
    ) -> GapAnalysis:
        """Compare actual behavior to expected behavior."""
        pass
    
    @abstractmethod
    async def diagnose_failure(
        self,
        trace_analysis: TraceAnalysis,
        gap_analysis: GapAnalysis
    ) -> Diagnosis:
        """Provide a root cause diagnosis."""
        pass


class HypothesisGenerator(ABC):
    """Interface for generating improvement hypotheses."""
    
    @abstractmethod
    async def search_best_practices(
        self,
        failure_type: str,
        model: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Search for relevant best practices."""
        pass
    
    @abstractmethod
    async def generate_hypotheses(
        self,
        diagnosis: Diagnosis,
        code_context: CodeContext,
        best_practices: List[Dict[str, Any]]
    ) -> List[Hypothesis]:
        """Generate hypotheses to fix the issue."""
        pass
    
    @abstractmethod
    async def rank_hypotheses(
        self,
        hypotheses: List[Hypothesis],
        context: Dict[str, Any]
    ) -> List[Hypothesis]:
        """Rank hypotheses by likelihood of success."""
        pass


class CodeManager(ABC):
    """Interface for managing code changes."""
    
    @abstractmethod
    async def analyze_codebase(self, path: str) -> CodeContext:
        """Analyze the codebase structure."""
        pass
    
    @abstractmethod
    async def get_related_files(self, file_path: str) -> List[str]:
        """Find files related to the target file."""
        pass
    
    @abstractmethod
    async def validate_change(self, change: FileChange) -> ValidationResult:
        """Validate a proposed change."""
        pass
    
    @abstractmethod
    async def analyze_impact(self, changes: List[FileChange]) -> ImpactReport:
        """Analyze the impact of proposed changes."""
        pass
    
    @abstractmethod
    async def apply_changes(
        self, 
        changes: List[FileChange],
        message: str
    ) -> Dict[str, Any]:
        """Apply changes with Git integration."""
        pass
    
    @abstractmethod
    async def rollback_changes(self, commit_id: str) -> bool:
        """Rollback changes to a previous state."""
        pass


class LLMProvider(ABC):
    """Interface for LLM interactions."""
    
    @abstractmethod
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Get a completion from the LLM."""
        pass
    
    @abstractmethod
    async def complete_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a completion with tool usage."""
        pass


class Cache(ABC):
    """Interface for caching."""
    
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        pass
    
    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 900) -> None:
        """Set a value in cache with TTL in seconds."""
        pass
    
    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete a value from cache."""
        pass