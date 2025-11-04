"""
Local file trace provider with multi-format support.

Provides TraceProvider interface for loading traces from local JSON files.
Supports multiple trace formats with automatic format detection:
- Langfuse JSON exports
- OTLP JSON traces (from any backend: Grafana Tempo, Honeycomb, Datadog, etc.)
- LangSmith JSON exports (if applicable)
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import structlog

from ..core.models import Trace
from ..core.interfaces import TraceProvider
from .otlp_parser import parse_otlp_trace
from .langfuse_parser import parse_langfuse_trace

logger = structlog.get_logger(__name__)


class LocalFileTraceProvider(TraceProvider):
    """
    Trace provider for loading traces from local files with automatic format detection.

    Supports:
    - Langfuse JSON exports (detects "observations" array)
    - OTLP JSON traces (detects "resourceSpans" array)
    """

    def __init__(self, file_path: str):
        """
        Initialize local file trace provider.

        Args:
            file_path: Path to JSON trace file (Langfuse or OTLP format)

        Raises:
            FileNotFoundError: If file doesn't exist
        """
        self.file_path = Path(file_path)
        if not self.file_path.exists():
            raise FileNotFoundError(f"Trace file not found: {file_path}")
        if not self.file_path.is_file():
            raise FileNotFoundError(f"Path is not a file: {file_path}")

        self._trace_cache: Optional[Trace] = None

    def _detect_format(self, data: dict) -> str:
        """
        Detect trace format from JSON structure.

        Detection priority:
        1. Langfuse format: has "observations" array (id validated by parser)
        2. OTLP format: has "resourceSpans" array

        Args:
            data: Parsed JSON data

        Returns:
            Format string: "langfuse" or "otlp"

        Raises:
            ValueError: If format cannot be determined
        """
        # Check for Langfuse format (observations array indicates Langfuse)
        # Note: 'id' field is validated by parser, not format detection
        if "observations" in data:
            return "langfuse"

        # Check for OTLP format (resourceSpans array)
        if "resourceSpans" in data:
            return "otlp"

        raise ValueError(
            "Unknown trace format. Expected either:\n"
            "  - Langfuse format (with 'observations' array)\n"
            "  - OTLP format (with 'resourceSpans' field)"
        )

    async def fetch_trace(self, trace_id: Optional[str] = None) -> Trace:
        """
        Load trace from local file with automatic format detection.

        Supports Langfuse and OTLP JSON formats. Format is automatically detected
        based on JSON structure.

        Args:
            trace_id: Optional trace ID (not used, file contains single trace)

        Returns:
            Parsed Trace object

        Raises:
            ValueError: If file format is invalid or cannot be determined
        """
        # Return cached trace if available
        if self._trace_cache:
            return self._trace_cache

        logger.info("Loading trace from file", file_path=str(self.file_path))

        # Load JSON file
        try:
            with open(self.file_path, "r") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in trace file: {e}")
        except Exception as e:
            raise ValueError(f"Failed to read trace file: {e}")

        # Detect format
        try:
            format_type = self._detect_format(data)
        except ValueError as e:
            raise ValueError(f"Cannot determine trace format: {e}")

        logger.info("Detected trace format", format=format_type, file_path=str(self.file_path))

        # Parse based on detected format
        effective_trace_id = trace_id or self.file_path.stem

        try:
            if format_type == "langfuse":
                trace = parse_langfuse_trace(data)
            elif format_type == "otlp":
                trace = parse_otlp_trace(data, effective_trace_id)
            else:
                raise ValueError(f"Unsupported format: {format_type}")
        except Exception as e:
            raise ValueError(f"Failed to parse {format_type} trace: {e}")

        # Cache the trace
        self._trace_cache = trace

        logger.info(
            "Successfully loaded trace",
            format=format_type,
            trace_id=trace.trace_id,
            num_runs=len(trace.runs),
            file_path=str(self.file_path),
        )

        return trace

    async def fetch_failed_traces(
        self, project: str, start_time: datetime, end_time: datetime, limit: int = 100
    ) -> List[Trace]:
        """
        Fetch failed traces (not applicable for file-based providers).

        Args:
            project: Project name
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum number of traces

        Raises:
            NotImplementedError: File-based providers cannot query for failed traces
        """
        raise NotImplementedError(
            "LocalFileTraceProvider does not support fetch_failed_traces. "
            "This method is only applicable for API-based providers (LangSmith, Langfuse)."
        )

    async def fetch_trace_hierarchy(self, trace_id: str) -> Dict[str, Any]:
        """
        Fetch trace hierarchy (not applicable for file-based providers).

        Args:
            trace_id: Trace ID

        Raises:
            NotImplementedError: File-based providers cannot fetch additional hierarchy
        """
        raise NotImplementedError(
            "LocalFileTraceProvider does not support fetch_trace_hierarchy. "
            "This method is only applicable for API-based providers (LangSmith, Langfuse)."
        )

    def __repr__(self) -> str:
        return f"LocalFileTraceProvider(file_path='{self.file_path}')"
