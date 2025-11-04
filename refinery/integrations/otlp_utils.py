"""
OTLP (OpenTelemetry Protocol) parsing utilities.

Provides utilities for parsing OTLP trace data including timestamps,
attributes, and building hierarchical span structures.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Union

from ..core.models import TraceRun


def parse_otlp_timestamp(value: Union[str, int]) -> datetime:
    """
    Parse OTLP timestamp (nanoseconds since epoch).

    OTLP timestamps are represented as nanoseconds since Unix epoch.
    This function converts them to timezone-aware datetime objects in UTC.

    Args:
        value: Timestamp as string or int (nanoseconds since epoch)

    Returns:
        Timezone-aware datetime in UTC

    Example:
        >>> ts = parse_otlp_timestamp(1609459200000000000)
        >>> print(ts)
        2021-01-01 00:00:00+00:00
    """
    if isinstance(value, str):
        value = int(value)
    return datetime.fromtimestamp(value / 1e9, tz=timezone.utc)


def flatten_otlp_attributes(attributes: List[Dict]) -> Dict[str, Any]:
    """
    Flatten OTLP attribute array to dict.

    OTLP attributes are represented as an array of objects with 'key' and 'value'
    fields, where 'value' is itself a nested object containing the actual value
    under fields like 'stringValue', 'intValue', 'doubleValue', 'boolValue', etc.

    This function flattens this structure to a simple key-value dict.

    Args:
        attributes: List of OTLP attribute objects with 'key' and 'value' fields

    Returns:
        Flat dictionary mapping attribute keys to their values

    Example:
        >>> attrs = [
        ...     {"key": "name", "value": {"stringValue": "test"}},
        ...     {"key": "count", "value": {"intValue": 42}}
        ... ]
        >>> result = flatten_otlp_attributes(attrs)
        >>> print(result)
        {'name': 'test', 'count': 42}
    """
    result = {}
    for attr in attributes:
        key = attr.get("key")
        value_obj = attr.get("value", {})
        # Handle stringValue, intValue, doubleValue, boolValue, etc.
        # The value is stored under one of these type-specific keys
        value = next(iter(value_obj.values())) if value_obj else None
        result[key] = value
    return result


def build_hierarchy(spans: List[TraceRun]) -> List[TraceRun]:
    """
    Build parent-child hierarchy from flat span list and assign dotted_order.

    This function takes a flat list of TraceRun objects (with parent_run_id set)
    and assigns each span a dotted_order field that represents its position in
    the trace hierarchy. The dotted_order uses zero-padded 4-digit numbers
    separated by dots (e.g., "0000", "0000.0001", "0000.0001.0000").

    The algorithm:
    1. Groups spans by parent_run_id to build a parent-child map
    2. Identifies root spans (those with no parent)
    3. Performs depth-first traversal to assign dotted_order
    4. Sorts children by start_time for deterministic ordering

    Args:
        spans: Flat list of TraceRun objects (with parent_run_id set)

    Returns:
        Same list with dotted_order set on all runs (modified in-place)

    Example:
        >>> spans = [
        ...     TraceRun(id="1", parent_run_id=None, ...),
        ...     TraceRun(id="2", parent_run_id="1", ...),
        ...     TraceRun(id="3", parent_run_id="1", ...)
        ... ]
        >>> build_hierarchy(spans)
        >>> # spans[0].dotted_order = "0000"
        >>> # spans[1].dotted_order = "0000.0000"
        >>> # spans[2].dotted_order = "0000.0001"
    """
    # Build parent-child map
    children_map: Dict[str, List[TraceRun]] = {}
    root_spans: List[TraceRun] = []

    for span in spans:
        if span.parent_run_id:
            children_map.setdefault(span.parent_run_id, []).append(span)
        else:
            root_spans.append(span)

    # Assign dotted_order via depth-first traversal
    def assign_order(span: TraceRun, order: str) -> None:
        """Recursively assign dotted_order to span and its children."""
        span.dotted_order = order
        children = children_map.get(span.id, [])
        # Sort children by start_time for deterministic ordering
        children.sort(key=lambda x: x.start_time)
        for idx, child in enumerate(children):
            child_order = f"{order}.{idx:04d}" if order else f"{idx:04d}"
            assign_order(child, child_order)

    # Process all root spans
    root_spans.sort(key=lambda x: x.start_time)
    for idx, root in enumerate(root_spans):
        assign_order(root, f"{idx:04d}")

    return spans
