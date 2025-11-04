"""
Langfuse API client for trace fetching.

This module provides async wrapper around the Langfuse SDK for fetching traces
and prompts from the Langfuse observability platform.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from langfuse import Langfuse

from ..core.interfaces import TraceProvider
from ..core.models import Trace, TraceRun, RunType
from ..utils.async_helpers import run_in_executor
from ..utils.config import config

logger = logging.getLogger(__name__)


class LangfuseClient(TraceProvider):
    """Langfuse API client (async wrapper around sync SDK)."""

    def __init__(self):
        """Initialize Langfuse client with credentials from config."""
        if not config.langfuse_public_key or not config.langfuse_secret_key:
            raise ValueError(
                "Langfuse requires public_key and secret_key. "
                "Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY environment variables."
            )

        self.client = Langfuse(
            public_key=config.langfuse_public_key,
            secret_key=config.langfuse_secret_key,
            host=config.langfuse_host,
        )

    async def fetch_trace(self, trace_id: str) -> Trace:
        """
        Fetch trace from Langfuse API.

        Note: Langfuse SDK v3 provides BOTH sync and async APIs (VERIFIED 2025-10-31):
        - Sync API with executor: self.client.api.trace.get(trace_id) wrapped in run_in_executor
        - Native async API (RECOMMENDED): self.client.async_api.trace.get(trace_id)

        The async_api provides better performance and is the recommended approach for
        production use. The sync + executor approach is shown below for compatibility
        with existing sync SDK usage patterns.

        Args:
            trace_id: The ID of the trace to fetch

        Returns:
            Trace object with parsed runs

        Raises:
            Exception: If trace cannot be fetched or parsed
        """
        # Option 1: Sync API with executor (compatibility approach)
        trace_data = await run_in_executor(lambda: self.client.api.trace.get(trace_id))

        # Option 2 (RECOMMENDED for production): Native async API
        # trace_data = await self.client.async_api.trace.get(trace_id)

        # Parse Langfuse trace → our Trace model
        return self._parse_langfuse_trace(trace_data)

    async def fetch_failed_traces(
        self, project: str, start_time: datetime, end_time: datetime, limit: int = 100
    ) -> List[Trace]:
        """
        Fetch traces that contain failures within a time range.

        Note: This is a placeholder implementation for TraceProvider interface.
        Langfuse API filtering capabilities should be implemented based on API docs.

        Args:
            project: Project ID to filter traces
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum number of traces to return

        Returns:
            List of failed traces
        """
        # TODO: Implement using Langfuse API query capabilities
        logger.warning(
            "fetch_failed_traces not yet implemented for Langfuse",
            project=project,
            start_time=start_time,
            end_time=end_time,
            limit=limit,
        )
        return []

    async def fetch_trace_hierarchy(self, trace_id: str) -> Dict[str, Any]:
        """
        Fetch the complete hierarchy of a trace.

        Args:
            trace_id: The ID of the trace

        Returns:
            Dictionary containing hierarchical trace data
        """
        trace = await self.fetch_trace(trace_id)
        return {
            "trace_id": trace.trace_id,
            "project_name": trace.project_name,
            "runs": [
                {
                    "id": run.id,
                    "name": run.name,
                    "run_type": run.run_type.value,
                    "parent_run_id": run.parent_run_id,
                    "dotted_order": run.dotted_order,
                }
                for run in trace.runs
            ],
        }

    async def fetch_prompt(
        self, name: str, version: Optional[int] = None, label: Optional[str] = None
    ) -> Dict:
        """
        Fetch managed prompt from Langfuse prompt registry.

        Note: get_prompt() is the recommended v3 API (not api.prompt.get())
        Provides client-side caching, automatic retries, and fallbacks

        Args:
            name: Prompt name
            version: Specific version number (optional)
            label: Label to fetch (e.g., "production", "staging") (optional)

        Returns:
            Prompt data from Langfuse
        """
        prompt_data = await run_in_executor(
            self.client.get_prompt, name, version=version, label=label or "production"
        )
        return prompt_data

    def _parse_langfuse_trace(self, data: Dict) -> Trace:
        """
        Parse Langfuse API response → Trace.

        Args:
            data: Raw trace data from Langfuse API

        Returns:
            Parsed Trace object

        Raises:
            ValueError: If required fields are missing
        """
        runs = []
        trace_id = data["id"]

        # Langfuse uses "observations" (SPAN, GENERATION, EVENT)
        for idx, obs in enumerate(data.get("observations", [])):
            # Validate required fields exist
            if not all(k in obs for k in ["id", "name", "type"]):
                logger.warning(
                    "Skipping malformed observation",
                    observation_id=obs.get("id", "unknown"),
                    missing_fields=[k for k in ["id", "name", "type"] if k not in obs],
                )
                continue

            run = TraceRun(
                id=obs["id"],
                name=obs["name"],
                run_type=self._map_observation_type(obs["type"]),
                start_time=self._parse_iso_timestamp(obs["startTime"]),
                end_time=self._parse_iso_timestamp(obs.get("endTime")),
                parent_run_id=obs.get("parentObservationId"),
                inputs=obs.get("input", {}),
                outputs=obs.get("output", {}),
                error=obs.get("statusMessage") if obs.get("level") == "ERROR" else None,
                trace_id=trace_id,
                dotted_order=f"{idx:04d}",  # Temporary - will be rebuilt by hierarchy
                metadata={
                    "model": obs.get("model"),
                    "usage": obs.get("usage", {}),
                    "langfuse_metadata": obs.get("metadata", {}),
                    "promptName": obs.get("metadata", {}).get("promptName"),
                    "promptVersion": obs.get("metadata", {}).get("promptVersion"),
                },
            )
            runs.append(run)

        # Build hierarchy and assign proper dotted_order
        runs = self._build_langfuse_hierarchy(runs)

        return Trace(
            trace_id=trace_id,
            project_name=data.get("projectId", "unknown"),
            runs=runs,
            start_time=min(run.start_time for run in runs) if runs else datetime.now(),
            end_time=(
                max((run.end_time for run in runs if run.end_time), default=None)
                if runs
                else None
            ),
            metadata={"format": "langfuse", "source": "api"},
        )

    def _build_langfuse_hierarchy(self, runs: List[TraceRun]) -> List[TraceRun]:
        """
        Build hierarchy from parentObservationId and assign dotted_order.

        Args:
            runs: List of TraceRun objects

        Returns:
            List of TraceRun objects with updated dotted_order reflecting hierarchy
        """
        # Build parent-child map
        children_map = {}
        root_runs = []

        for run in runs:
            if run.parent_run_id:
                children_map.setdefault(run.parent_run_id, []).append(run)
            else:
                root_runs.append(run)

        # Assign dotted_order via DFS
        def assign_order(run: TraceRun, order: str):
            run.dotted_order = order
            children = children_map.get(run.id, [])
            children.sort(key=lambda x: x.start_time)  # Deterministic ordering
            for idx, child in enumerate(children):
                child_order = f"{order}.{idx:04d}" if order else f"{idx:04d}"
                assign_order(child, child_order)

        # Process all roots
        for idx, root in enumerate(root_runs):
            assign_order(root, f"{idx:04d}")

        return runs

    def _map_observation_type(self, obs_type: str) -> RunType:
        """
        Map Langfuse observation type to RunType.

        Args:
            obs_type: Langfuse observation type (UPPERCASE)

        Returns:
            Corresponding RunType enum value
        """
        mapping = {
            "GENERATION": RunType.LLM,
            "SPAN": RunType.CHAIN,
            "EVENT": RunType.TOOL,
            "TOOL": RunType.TOOL,
            "RETRIEVER": RunType.RETRIEVER,
            "EMBEDDING": RunType.EMBEDDING,
            "AGENT": RunType.CHAIN,
            "CHAIN": RunType.CHAIN,
            "EVALUATOR": RunType.CHAIN,
            "GUARDRAIL": RunType.CHAIN,
        }
        return mapping.get(obs_type, RunType.CHAIN)

    def _parse_iso_timestamp(self, ts_str: Optional[str]) -> Optional[datetime]:
        """
        Parse ISO 8601 timestamp string.

        Args:
            ts_str: ISO 8601 timestamp string (may be None)

        Returns:
            Parsed datetime object or None
        """
        if not ts_str:
            return None
        return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
