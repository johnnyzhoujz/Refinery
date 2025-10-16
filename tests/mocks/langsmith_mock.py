"""
Mock LangSmith client for testing without API calls.

This module provides a MockLangSmithClient that mimics the behavior of
the real LangSmithClient but uses fixed responses instead of making API calls.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from refinery.core.models import RunType, Trace, TraceRun


class MockLangSmithClient:
    """
    Mock LangSmith client for testing.

    Usage:
        mock_client = MockLangSmithClient(fixed_responses={
            "trace-123": {
                "trace_id": "trace-123",
                "project_name": "test-project",
                "runs": [...]
            }
        })

        trace = await mock_client.fetch_trace("trace-123")
    """

    def __init__(self, fixed_responses: Optional[Dict[str, Any]] = None):
        """
        Initialize mock client with optional fixed responses.

        Args:
            fixed_responses: Dict mapping trace_id to trace data
        """
        self.fixed_responses = fixed_responses or {}
        self.call_count = 0
        self.last_trace_id = None

    async def fetch_trace(self, trace_id: str) -> Trace:
        """
        Mock fetch_trace that returns fixed trace data.

        Args:
            trace_id: The trace ID to fetch

        Returns:
            Trace: Mocked trace data

        Raises:
            ValueError: If trace_id not in fixed_responses
        """
        self.call_count += 1
        self.last_trace_id = trace_id

        if trace_id not in self.fixed_responses:
            raise ValueError(f"Mock: No trace data found for trace_id: {trace_id}")

        trace_data = self.fixed_responses[trace_id]

        # Convert mock data to Trace object
        runs = [
            TraceRun(
                id=run["id"],
                name=run["name"],
                run_type=RunType(run["run_type"]),
                inputs=run.get("inputs", {}),
                outputs=run.get("outputs"),
                start_time=datetime.fromisoformat(
                    run["start_time"].replace("Z", "+00:00")
                ),
                end_time=(
                    datetime.fromisoformat(run["end_time"].replace("Z", "+00:00"))
                    if run.get("end_time")
                    else None
                ),
                error=run.get("error"),
                parent_run_id=run.get("parent_run_id"),
                trace_id=trace_id,
                dotted_order=run["dotted_order"],
                metadata=run.get("metadata", {}),
            )
            for run in trace_data["runs"]
        ]

        return Trace(
            trace_id=trace_id,
            project_name=trace_data.get("project_name", "test-project"),
            runs=runs,
            start_time=min(run.start_time for run in runs),
            end_time=(
                max(run.end_time for run in runs if run.end_time)
                if any(run.end_time for run in runs)
                else None
            ),
            metadata=trace_data.get("metadata", {"source": "mock"}),
        )

    async def fetch_failed_traces(
        self, project: str, start_time: datetime, end_time: datetime, limit: int = 100
    ) -> List[Trace]:
        """
        Mock fetch_failed_traces - returns all mocked traces with failures.

        Args:
            project: Project name (ignored in mock)
            start_time: Start time (ignored in mock)
            end_time: End time (ignored in mock)
            limit: Max traces to return

        Returns:
            List[Trace]: List of mocked failed traces
        """
        self.call_count += 1

        # Return all traces that have at least one failed run
        failed_traces = []
        for trace_id, trace_data in self.fixed_responses.items():
            trace = await self.fetch_trace(trace_id)
            if trace.get_failed_runs():
                failed_traces.append(trace)

        return failed_traces[:limit]

    async def fetch_trace_hierarchy(self, trace_id: str) -> Dict[str, Any]:
        """
        Mock fetch_trace_hierarchy - returns simplified hierarchy.

        Args:
            trace_id: The trace ID

        Returns:
            Dict: Mocked hierarchy data
        """
        self.call_count += 1
        self.last_trace_id = trace_id

        trace = await self.fetch_trace(trace_id)

        return {
            "trace_id": trace_id,
            "project_name": trace.project_name,
            "total_runs": len(trace.runs),
            "failed_runs": len(trace.get_failed_runs()),
            "runs": [
                {
                    "id": run.id,
                    "name": run.name,
                    "run_type": run.run_type.value,
                    "is_failed": run.is_failed,
                    "error": run.error,
                }
                for run in trace.runs
            ],
        }

    async def health_check(self) -> bool:
        """Mock health check - always returns True."""
        return True

    def clear_cache(self) -> None:
        """Mock cache clear - no-op."""
        pass

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass

    def extract_prompts_from_trace(self, trace: "Trace") -> Dict[str, Any]:
        """
        Mock extract_prompts_from_trace method.

        Returns a mock prompt extraction result with system prompts.
        """
        # Return mock prompt extraction with some system prompts
        system_prompts = []
        for i, run in enumerate(trace.runs):
            if run.run_type.value == "llm" and run.inputs:
                # Extract mock system prompt from inputs
                prompt_text = run.inputs.get("messages", [{}])[0].get(
                    "content", f"Mock system prompt {i}"
                )
                system_prompts.append({"run_name": run.name, "content": prompt_text})

        return {
            "system_prompts": system_prompts,
            "user_prompts": [],
            "assistant_prompts": [],
        }


def create_mock_trace_data() -> Dict[str, Any]:
    """
    Create a sample trace data structure for testing.

    Returns:
        Dict: Sample trace data with one failed run
    """
    return {
        "trace_id": "mock-trace-001",
        "project_name": "mock-project",
        "runs": [
            {
                "id": "run-001",
                "name": "RootChain",
                "run_type": "chain",
                "inputs": {"query": "test query"},
                "outputs": {"result": "test result"},
                "start_time": "2025-10-15T10:00:00.000Z",
                "end_time": "2025-10-15T10:00:10.000Z",
                "error": None,
                "parent_run_id": None,
                "dotted_order": "1",
                "metadata": {},
            },
            {
                "id": "run-002",
                "name": "FailedLLMCall",
                "run_type": "llm",
                "inputs": {"prompt": "test prompt"},
                "outputs": None,
                "start_time": "2025-10-15T10:00:01.000Z",
                "end_time": "2025-10-15T10:00:05.000Z",
                "error": "API rate limit exceeded",
                "parent_run_id": "run-001",
                "dotted_order": "1.1",
                "metadata": {},
            },
        ],
        "metadata": {"source": "mock"},
    }
