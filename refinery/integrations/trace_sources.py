"""
Trace source abstraction for fetching traces from various sources.

This module provides a simplified interface for fetching traces, supporting:
- Local JSON files (for offline analysis, CI integration, security audit)
- LangSmith API (for live trace fetching)
"""

import json
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import structlog

from ..core.models import RunType, Trace, TraceRun
from ..integrations.langsmith_client import LangSmithClient

logger = structlog.get_logger(__name__)


class TraceSource(ABC):
    """Abstract base class for trace sources."""

    @abstractmethod
    async def fetch_trace(self) -> Trace:
        """Fetch trace from the source."""
        pass


class LocalFileSource(TraceSource):
    """Parse trace from local LangSmith JSON file."""

    def __init__(self, file_path: str):
        """
        Initialize local file source.

        Args:
            file_path: Path to LangSmith JSON trace file
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Trace file not found: {file_path}")

    def _parse_datetime(self, iso_string: str) -> datetime:
        """Parse ISO datetime string to datetime object."""
        try:
            # Handle different ISO formats
            if iso_string.endswith("Z"):
                return datetime.fromisoformat(iso_string[:-1]).replace(
                    tzinfo=timezone.utc
                )
            elif "+" in iso_string or iso_string.count("-") > 2:
                return datetime.fromisoformat(iso_string)
            else:
                return datetime.fromisoformat(iso_string).replace(tzinfo=timezone.utc)
        except (ValueError, AttributeError) as e:
            logger.warning(
                "Failed to parse datetime", iso_string=iso_string, error=str(e)
            )
            return datetime.now(timezone.utc)

    def _map_run_type(self, langsmith_type: str) -> RunType:
        """Map LangSmith run type to internal RunType enum."""
        type_mapping = {
            "llm": RunType.LLM,
            "chain": RunType.CHAIN,
            "tool": RunType.TOOL,
            "retriever": RunType.RETRIEVER,
            "embedding": RunType.EMBEDDING,
            "prompt": RunType.PROMPT,
            "parser": RunType.PARSER,
        }
        return type_mapping.get(langsmith_type.lower(), RunType.CHAIN)

    def _validate_trace_data(self, data: Dict[str, Any]) -> None:
        """Validate that JSON data has required LangSmith trace fields."""
        required_fields = ["trace_id", "runs"]

        for field in required_fields:
            if field not in data:
                raise ValueError(
                    f"Invalid trace file: missing required field '{field}'"
                )

        if not isinstance(data["runs"], list):
            raise ValueError("Invalid trace file: 'runs' must be a list")

        if len(data["runs"]) == 0:
            raise ValueError("Invalid trace file: 'runs' list is empty")

    def _parse_run(self, run_data: Dict[str, Any]) -> TraceRun:
        """Parse a single run from LangSmith JSON format."""
        start_time = self._parse_datetime(run_data.get("start_time", ""))
        end_time = None
        if run_data.get("end_time"):
            end_time = self._parse_datetime(run_data["end_time"])

        return TraceRun(
            id=run_data.get("id", ""),
            name=run_data.get("name", ""),
            run_type=self._map_run_type(run_data.get("run_type", "chain")),
            inputs=run_data.get("inputs", {}),
            outputs=run_data.get("outputs"),
            start_time=start_time,
            end_time=end_time,
            error=run_data.get("error"),
            parent_run_id=run_data.get("parent_run_id"),
            trace_id=run_data.get("trace_id", ""),
            dotted_order=run_data.get("dotted_order", ""),
            metadata={
                "session_id": run_data.get("session_id"),
                "extra": run_data.get("extra", {}),
            },
        )

    async def fetch_trace(self) -> Trace:
        """
        Parse trace from local JSON file.

        Returns:
            Trace: Parsed trace data

        Raises:
            FileNotFoundError: If trace file doesn't exist
            ValueError: If trace file has invalid format
            json.JSONDecodeError: If file is not valid JSON
        """
        logger.info("Loading trace from file", file_path=str(self.file_path))

        try:
            with open(self.file_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in trace file: {e}")

        # Validate trace data structure
        self._validate_trace_data(data)

        # Parse runs
        runs = [self._parse_run(run_data) for run_data in data["runs"]]

        # Sort runs by dotted_order to maintain hierarchy
        runs.sort(key=lambda x: x.dotted_order)

        # Extract trace metadata
        trace_id = data["trace_id"]
        project_name = data.get("project_name", data.get("session_id", "local"))

        # Calculate start and end times
        start_time = min(run.start_time for run in runs)
        end_time = None
        if all(run.end_time for run in runs):
            end_time = max(run.end_time for run in runs if run.end_time)

        trace = Trace(
            trace_id=trace_id,
            project_name=project_name,
            runs=runs,
            start_time=start_time,
            end_time=end_time,
            metadata={
                "total_runs": len(runs),
                "source": "local_file",
                "file_path": str(self.file_path),
            },
        )

        logger.info(
            "Successfully loaded trace from file",
            trace_id=trace_id,
            run_count=len(runs),
            file_path=str(self.file_path),
        )

        return trace


class LangSmithAPISource(TraceSource):
    """Fetch trace from LangSmith API."""

    def __init__(self, trace_id: str, project: str):
        """
        Initialize LangSmith API source.

        Args:
            trace_id: LangSmith trace ID
            project: LangSmith project name
        """
        self.trace_id = trace_id
        self.project = project
        self.client: LangSmithClient = None

    async def fetch_trace(self) -> Trace:
        """
        Fetch trace from LangSmith API.

        Returns:
            Trace: Fetched trace data

        Raises:
            ValueError: If trace_id is invalid or not found
            httpx.HTTPStatusError: If API request fails
        """
        logger.info(
            "Fetching trace from LangSmith API",
            trace_id=self.trace_id,
            project=self.project,
        )

        # Create LangSmith client
        self.client = LangSmithClient()

        # Fetch trace
        trace = await self.client.fetch_trace(self.trace_id)

        # Add source metadata
        trace.metadata["source"] = "langsmith_api"
        trace.metadata["project"] = self.project

        logger.info(
            "Successfully fetched trace from LangSmith API", trace_id=self.trace_id
        )

        return trace
