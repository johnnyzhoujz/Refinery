"""
OTLP trace parser for OpenTelemetry traces.

This module provides parsing functionality for OTLP (OpenTelemetry Protocol) trace data
from various backends including Grafana Tempo, Honeycomb, Datadog, New Relic, Jaeger,
and custom OTLP collectors.

The parser follows the OTLP specification for trace data structure and supports
the official OpenTelemetry semantic conventions for GenAI operations.
"""

from typing import Any, Dict, Optional

from ..core.models import RunType, Trace, TraceRun
from .otlp_utils import build_hierarchy, flatten_otlp_attributes, parse_otlp_timestamp


def parse_otlp_trace(data: Dict, trace_id: str) -> Trace:
    """
    Parse OTLP JSON file to Trace.

    Supports traces exported from ANY OTLP backend:
    - Grafana Tempo
    - Honeycomb
    - Datadog
    - New Relic
    - Jaeger
    - Custom OTLP collectors

    The OTLP structure follows: resourceSpans[].scopeSpans[].spans[]

    Args:
        data: OTLP JSON data dictionary
        trace_id: Trace ID to assign to the trace

    Returns:
        Trace object with all spans parsed and hierarchically organized

    Raises:
        ValueError: If no spans found in OTLP trace

    Example:
        >>> with open("tempo_trace.json") as f:
        ...     data = json.load(f)
        >>> trace = parse_otlp_trace(data, "abc123")
        >>> print(f"Parsed {len(trace.runs)} spans")
    """
    runs = []

    # OTLP structure: resourceSpans[].scopeSpans[].spans[]
    for resource_span in data.get("resourceSpans", []):
        for scope_span in resource_span.get("scopeSpans", []):
            for span in scope_span.get("spans", []):
                run = _parse_span(span)
                runs.append(run)

    if not runs:
        raise ValueError(f"No spans found in OTLP trace: {trace_id}")

    # Build hierarchy and assign dotted_order
    runs_with_hierarchy = build_hierarchy(runs)

    # Extract service name from resource attributes
    project_name = _extract_service_name(data)

    return Trace(
        trace_id=trace_id,
        project_name=project_name,
        runs=runs_with_hierarchy,
        start_time=min(run.start_time for run in runs_with_hierarchy),
        end_time=max(
            (run.end_time for run in runs_with_hierarchy if run.end_time), default=None
        ),
        metadata={"format": "opentelemetry", "source": "file"},
    )


def _extract_service_name(data: Dict) -> str:
    """
    Extract service name from OTLP resource attributes.

    Looks for the "service.name" attribute in the resource section of the OTLP trace.
    This is a standard semantic convention in OpenTelemetry.

    Args:
        data: OTLP JSON data dictionary

    Returns:
        Service name or "unknown" if not found

    Example:
        >>> data = {
        ...     "resourceSpans": [{
        ...         "resource": {
        ...             "attributes": [
        ...                 {"key": "service.name", "value": {"stringValue": "my-app"}}
        ...             ]
        ...         }
        ...     }]
        ... }
        >>> _extract_service_name(data)
        'my-app'
    """
    for resource_span in data.get("resourceSpans", []):
        resource = resource_span.get("resource", {})
        attributes = flatten_otlp_attributes(resource.get("attributes", []))
        if "service.name" in attributes:
            return attributes["service.name"]
    return "unknown"


def _parse_span(span: Dict) -> TraceRun:
    """
    Parse OTLP span to TraceRun.

    Converts an OTLP span structure to our internal TraceRun model.
    Extracts inputs, outputs, errors, and metadata from the span.

    Args:
        span: OTLP span dictionary

    Returns:
        TraceRun object with all fields populated

    Example:
        >>> span = {
        ...     "spanId": "abc123",
        ...     "name": "llm.call",
        ...     "startTimeUnixNano": "1609459200000000000",
        ...     "endTimeUnixNano": "1609459205000000000",
        ...     "traceId": "trace-1",
        ...     "attributes": []
        ... }
        >>> run = _parse_span(span)
        >>> print(run.name)
        'llm.call'
    """
    attributes = flatten_otlp_attributes(span.get("attributes", []))

    return TraceRun(
        id=span["spanId"],
        name=span["name"],
        run_type=_infer_run_type(span, attributes),
        start_time=parse_otlp_timestamp(span["startTimeUnixNano"]),
        end_time=parse_otlp_timestamp(span["endTimeUnixNano"]),
        parent_run_id=span.get("parentSpanId"),
        inputs=_extract_inputs(span, attributes),
        outputs=_extract_outputs(span, attributes),
        error=_extract_error(span),
        trace_id=span["traceId"],
        dotted_order="",  # Will be set by build_hierarchy()
        metadata=attributes,  # Store all attributes for extraction
    )


def _infer_run_type(span: Dict, attributes: Dict) -> RunType:
    """
    Infer run type from span kind and attributes.

    Uses OpenTelemetry semantic conventions to determine the type of operation:
    - LLM: If gen_ai.* attributes are present (GenAI semantic conventions)
    - TOOL: If span kind is SPAN_KIND_CLIENT (external API calls)
    - CHAIN: Default for orchestration logic

    Args:
        span: OTLP span dictionary
        attributes: Flattened attributes dictionary

    Returns:
        RunType enum value

    Example:
        >>> span = {"kind": "SPAN_KIND_INTERNAL"}
        >>> attrs = {"gen_ai.system": "anthropic"}
        >>> _infer_run_type(span, attrs)
        <RunType.LLM: 'llm'>
    """
    if any(k.startswith("gen_ai.") for k in attributes):
        return RunType.LLM
    if span.get("kind") == "SPAN_KIND_CLIENT":
        return RunType.TOOL
    return RunType.CHAIN


def _extract_inputs(span: Dict, attributes: Dict) -> Dict[str, Any]:
    """
    Extract input data from OTLP span.

    Follows OpenTelemetry GenAI semantic conventions with fallback support
    for vendor-specific patterns:
    1. PRIMARY: gen_ai.input.messages (official semantic convention)
    2. FALLBACK: gen_ai.prompt.* attributes (vendor-specific pattern)

    Args:
        span: OTLP span dictionary
        attributes: Flattened attributes dictionary

    Returns:
        Dictionary with extracted input data, or empty dict if nothing found

    Example:
        >>> attrs = {"gen_ai.input.messages": "[{\"role\": \"user\", \"content\": \"Hello\"}]"}
        >>> _extract_inputs({}, attrs)
        {'messages': '[{"role": "user", "content": "Hello"}]'}
    """
    inputs = {}

    # Try gen_ai.input.messages (official semantic convention)
    if "gen_ai.input.messages" in attributes:
        inputs["messages"] = attributes["gen_ai.input.messages"]

    # FALLBACK ONLY: Try gen_ai.prompt.* attributes (vendor-specific, not in official OTLP spec)
    # Official spec only defines gen_ai.input.messages - use that first
    prompt_attrs = {k: v for k, v in attributes.items() if k.startswith("gen_ai.prompt.")}
    if prompt_attrs:
        inputs["prompts"] = prompt_attrs

    return inputs if inputs else {}


def _extract_outputs(span: Dict, attributes: Dict) -> Dict[str, Any]:
    """
    Extract output data from OTLP span.

    Follows OpenTelemetry GenAI semantic conventions with fallback support
    for vendor-specific patterns:
    1. PRIMARY: gen_ai.output.messages (official semantic convention)
    2. FALLBACK: gen_ai.completion.* attributes (vendor-specific pattern)

    Args:
        span: OTLP span dictionary
        attributes: Flattened attributes dictionary

    Returns:
        Dictionary with extracted output data, or empty dict if nothing found

    Example:
        >>> attrs = {"gen_ai.output.messages": "[{\"role\": \"assistant\", \"content\": \"Hi!\"}]"}
        >>> _extract_outputs({}, attrs)
        {'messages': '[{"role": "assistant", "content": "Hi!"}]'}
    """
    outputs = {}

    # Try gen_ai.output.messages (official semantic convention)
    if "gen_ai.output.messages" in attributes:
        outputs["messages"] = attributes["gen_ai.output.messages"]

    # FALLBACK ONLY: Try gen_ai.completion.* attributes (vendor-specific, not in official OTLP spec)
    # Official spec only defines gen_ai.output.messages - use that first
    completion_attrs = {
        k: v for k, v in attributes.items() if k.startswith("gen_ai.completion.")
    }
    if completion_attrs:
        outputs["completions"] = completion_attrs

    return outputs if outputs else {}


def _extract_error(span: Dict) -> Optional[str]:
    """
    Extract error information from OTLP span status.

    Checks two sources for error information:
    1. status.code for ERROR status (STATUS_CODE_ERROR or code 2 per OTLP spec)
    2. events array for exception events with exception.message attribute

    Args:
        span: OTLP span dictionary

    Returns:
        Error message if found, None otherwise

    Example:
        >>> span = {"status": {"code": "STATUS_CODE_ERROR", "message": "API failed"}}
        >>> _extract_error(span)
        'API failed'

        >>> span = {
        ...     "events": [{
        ...         "name": "exception",
        ...         "attributes": [
        ...             {"key": "exception.message", "value": {"stringValue": "Timeout"}}
        ...         ]
        ...     }]
        ... }
        >>> _extract_error(span)
        'Timeout'
    """
    # Check for exception events first (more detailed error information)
    for event in span.get("events", []):
        if event.get("name") == "exception":
            # Extract exception message from event attributes
            event_attrs = flatten_otlp_attributes(event.get("attributes", []))
            if "exception.message" in event_attrs:
                return event_attrs["exception.message"]

    # Fallback to status code error
    status = span.get("status", {})
    if status.get("code") == "STATUS_CODE_ERROR" or status.get("code") == 2:
        # Return status message if available
        return status.get("message", "Unknown error")

    return None
