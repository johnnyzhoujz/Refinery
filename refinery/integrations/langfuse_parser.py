"""
Langfuse file parser for trace exports.

This module provides standalone parsing functions for Langfuse JSON trace exports.
It extracts the core parsing logic used by LangfuseClient for API responses,
making it reusable for file-based workflows.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from ..core.models import Trace, TraceRun, RunType

logger = logging.getLogger(__name__)


def parse_langfuse_trace(data: Dict) -> Trace:
    """
    Parse Langfuse JSON export format to Trace.

    Langfuse exports contain:
    - id: trace ID
    - projectId: project name
    - observations: array of observations (GENERATION, SPAN, EVENT, etc.)

    Args:
        data: Langfuse trace JSON data (from API or file export)

    Returns:
        Parsed Trace object

    Raises:
        ValueError: If required fields are missing or data is malformed
    """
    if "id" not in data:
        raise ValueError("Langfuse trace missing required field: id")

    runs = []
    trace_id = data["id"]

    # Langfuse uses "observations" (SPAN, GENERATION, EVENT)
    for idx, obs in enumerate(data.get("observations", [])):
        # Validate required fields exist
        if not all(k in obs for k in ["id", "name", "type"]):
            missing = [k for k in ["id", "name", "type"] if k not in obs]
            logger.warning(
                f"Skipping malformed observation {obs.get('id', 'unknown')}: missing fields {missing}"
            )
            continue

        run = TraceRun(
            id=obs["id"],
            name=obs["name"],
            run_type=_map_observation_type(obs["type"]),
            start_time=_parse_iso_timestamp(obs["startTime"]),
            end_time=_parse_iso_timestamp(obs.get("endTime")),
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
                "promptName": obs.get("metadata", {}).get("promptName") if isinstance(obs.get("metadata"), dict) else None,
                "promptVersion": obs.get("metadata", {}).get("promptVersion") if isinstance(obs.get("metadata"), dict) else None,
            },
        )
        runs.append(run)

    # Build hierarchy and assign proper dotted_order
    runs = _build_hierarchy(runs)

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
        metadata={"format": "langfuse", "source": "file"},
    )


def _build_hierarchy(runs: List[TraceRun]) -> List[TraceRun]:
    """
    Build parent-child hierarchy from parentObservationId and assign dotted_order.

    Uses depth-first traversal to assign hierarchical dotted_order strings.
    Children are sorted by start_time for deterministic ordering.

    Validates parent IDs and promotes orphaned runs to roots if their parent
    doesn't exist (handles missing parents and circular references).

    Args:
        runs: List of TraceRun objects with parent_run_id set

    Returns:
        Same list with dotted_order updated to reflect hierarchy
    """
    # Build set of valid run IDs and ID->run mapping for validation
    valid_run_ids = {run.id for run in runs}
    runs_dict = {run.id: run for run in runs}

    # Detect cycles using DFS
    def has_cycle_from(run_id: str, visiting: set, visited: set) -> bool:
        """Check if following parent chain from run_id leads to a cycle."""
        if run_id in visiting:
            return True  # Cycle detected
        if run_id in visited:
            return False  # Already checked, no cycle

        visiting.add(run_id)
        run = runs_dict.get(run_id)
        if run and run.parent_run_id and run.parent_run_id in runs_dict:
            if has_cycle_from(run.parent_run_id, visiting, visited):
                visiting.discard(run_id)
                return True

        visiting.discard(run_id)
        visited.add(run_id)
        return False

    # Check for cycles and collect runs involved in cycles
    visited = set()
    runs_in_cycles = set()

    for run in runs:
        if run.id not in visited and run.parent_run_id:
            visiting = set()
            if has_cycle_from(run.id, visiting, visited):
                # Mark this run and all in its parent chain as cycle members
                current = run.id
                while current and current not in runs_in_cycles:
                    runs_in_cycles.add(current)
                    current_run = runs_dict.get(current)
                    if current_run and current_run.parent_run_id in runs_dict:
                        current = current_run.parent_run_id
                    else:
                        break

    # Validate and fix parent IDs
    for run in runs:
        if run.id in runs_in_cycles:
            # Part of a cycle - promote to root
            logger.warning(
                f"Observation {run.id} is part of circular parent chain, promoting to root"
            )
            run.parent_run_id = None
        elif run.parent_run_id and run.parent_run_id not in valid_run_ids:
            # Parent doesn't exist - promote to root
            logger.warning(
                f"Observation {run.id} references non-existent parent {run.parent_run_id}, "
                f"promoting to root"
            )
            run.parent_run_id = None
        elif run.parent_run_id == run.id:
            # Self-referential parent (edge case)
            logger.warning(f"Observation {run.id} references itself as parent, promoting to root")
            run.parent_run_id = None

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


def _map_observation_type(obs_type: str) -> RunType:
    """
    Map Langfuse observation type to RunType.

    Langfuse uses UPPERCASE observation types (GENERATION, SPAN, EVENT, etc.).

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


def _parse_iso_timestamp(ts_str: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO 8601 timestamp string.

    Handles timezone designator 'Z' by converting to '+00:00' format.

    Args:
        ts_str: ISO 8601 timestamp string (may be None)

    Returns:
        Parsed datetime object or None if input is None

    Raises:
        ValueError: If timestamp format is invalid
    """
    if not ts_str:
        return None
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
