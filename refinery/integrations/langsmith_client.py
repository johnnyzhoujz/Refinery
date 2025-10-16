"""
LangSmith integration for fetching traces and runs.

This module implements the TraceProvider interface to integrate with LangSmith's
API for fetching trace data, parsing runs, and building trace hierarchies.
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog
from langsmith import Client
from pydantic import BaseModel

from ..core.interfaces import TraceProvider
from ..core.models import RunType, Trace, TraceRun
from ..utils.config import config

logger = structlog.get_logger(__name__)


class LangSmithRun(BaseModel):
    """LangSmith API run data model."""

    id: str
    name: str
    run_type: str
    inputs: Dict[str, Any]
    outputs: Optional[Dict[str, Any]] = None
    start_time: str
    end_time: Optional[str] = None
    error: Optional[str] = None
    parent_run_id: Optional[str] = None
    trace_id: str
    dotted_order: str
    session_id: Optional[str] = None
    extra: Dict[str, Any] = {}


class LangSmithQueryRequest(BaseModel):
    """Request model for LangSmith runs query API."""

    filter: Optional[str] = None
    trace_filter: Optional[str] = None
    tree_filter: Optional[str] = None
    is_root: Optional[bool] = None
    data_source_type: Optional[str] = None
    select: List[str] = []
    order: str = "desc"
    offset: int = 0
    limit: int = 100


class RateLimitHandler:
    """Handles rate limiting with exponential backoff."""

    def __init__(self, max_retries: int = 5, base_delay: float = 1.0):
        self.max_retries = max_retries
        self.base_delay = base_delay

    async def execute_with_backoff(self, func, *args, **kwargs):
        """Execute function with exponential backoff on rate limits."""
        for attempt in range(self.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limited
                    if attempt < self.max_retries:
                        delay = self.base_delay * (2**attempt)
                        logger.warning(
                            "Rate limited, retrying",
                            attempt=attempt + 1,
                            delay=delay,
                            status_code=e.response.status_code,
                        )
                        await asyncio.sleep(delay)
                        continue
                raise
            except Exception as e:
                if attempt < self.max_retries:
                    delay = self.base_delay * (2**attempt)
                    logger.warning(
                        "Request failed, retrying",
                        attempt=attempt + 1,
                        delay=delay,
                        error=str(e),
                    )
                    await asyncio.sleep(delay)
                    continue
                raise


class CacheManager:
    """Manages 15-minute cache for LangSmith responses."""

    def __init__(self, ttl_seconds: int = 900):  # 15 minutes
        self.ttl_seconds = ttl_seconds
        self._cache: Dict[str, Tuple[Any, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get cached value if not expired."""
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                return value
            else:
                del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        """Cache value with current timestamp."""
        self._cache[key] = (value, time.time())

    def clear_expired(self) -> None:
        """Remove expired entries from cache."""
        current_time = time.time()
        expired_keys = [
            key
            for key, (_, timestamp) in self._cache.items()
            if current_time - timestamp >= self.ttl_seconds
        ]
        for key in expired_keys:
            del self._cache[key]


class LangSmithClient(TraceProvider):
    """
    LangSmith integration client implementing TraceProvider interface.

    Uses the official LangSmith Python SDK for API interactions.
    """

    def __init__(self):
        """Initialize LangSmith client with configuration."""
        if not config.langsmith_api_key:
            raise ValueError("LangSmith API key is required")

        self.client = Client(
            api_key=config.langsmith_api_key, api_url=config.langsmith_api_url
        )
        self.cache = CacheManager(ttl_seconds=config.cache_ttl)

        logger.info("LangSmith client initialized", base_url=config.langsmith_api_url)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.client.aclose()

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
        except ValueError as e:
            logger.warning(
                "Failed to parse datetime", iso_string=iso_string, error=str(e)
            )
            return datetime.now(timezone.utc)

    def _convert_langsmith_run_to_trace_run(self, run_data: LangSmithRun) -> TraceRun:
        """Convert LangSmith run data to internal TraceRun model."""
        start_time = self._parse_datetime(run_data.start_time)
        end_time = None
        if run_data.end_time:
            end_time = self._parse_datetime(run_data.end_time)

        return TraceRun(
            id=run_data.id,
            name=run_data.name,
            run_type=self._map_run_type(run_data.run_type),
            inputs=run_data.inputs or {},
            outputs=run_data.outputs,
            start_time=start_time,
            end_time=end_time,
            error=run_data.error,
            parent_run_id=run_data.parent_run_id,
            trace_id=run_data.trace_id,
            dotted_order=run_data.dotted_order,
            metadata={"session_id": run_data.session_id, "extra": run_data.extra},
        )

    async def _make_request(
        self, method: str, endpoint: str, **kwargs
    ) -> Dict[str, Any]:
        """Make HTTP request with rate limiting and error handling."""
        url = urljoin(self.base_url, endpoint)

        async def _request():
            response = await self.client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()

        return await self.rate_limiter.execute_with_backoff(_request)

    async def _fetch_runs_by_query(
        self, query_request: LangSmithQueryRequest
    ) -> List[LangSmithRun]:
        """Fetch runs using LangSmith query API."""
        cache_key = f"query_{hash(str(query_request.dict()))}"
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.debug("Cache hit for runs query", cache_key=cache_key)
            return [LangSmithRun(**run) for run in cached_result]

        try:
            response = await self._make_request(
                "POST", "/runs/query", json=query_request.dict(exclude_none=True)
            )

            runs_data = response.get("runs", [])
            self.cache.set(cache_key, runs_data)

            return [LangSmithRun(**run) for run in runs_data]

        except Exception as e:
            logger.error(
                "Failed to fetch runs", error=str(e), query=query_request.dict()
            )
            raise

    async def fetch_trace(self, trace_id: str) -> Trace:
        """
        Fetch a single trace by ID.

        Args:
            trace_id: The trace ID to fetch

        Returns:
            Trace: Complete trace data with all runs

        Raises:
            ValueError: If trace_id is invalid
            httpx.HTTPStatusError: If API request fails
        """
        if not trace_id:
            raise ValueError("trace_id cannot be empty")

        cache_key = f"trace_{trace_id}"
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.debug("Cache hit for trace", trace_id=trace_id)
            return cached_result

        logger.info("Fetching trace", trace_id=trace_id)

        # Query all runs for this trace
        query_request = LangSmithQueryRequest(
            trace_filter=f'eq(trace_id, "{trace_id}")',
            select=[
                "id",
                "name",
                "run_type",
                "inputs",
                "outputs",
                "start_time",
                "end_time",
                "error",
                "parent_run_id",
                "trace_id",
                "dotted_order",
                "session_id",
                "extra",
            ],
            order="asc",  # Order by creation to build hierarchy properly
            limit=1000,  # Large limit to get all runs in trace
        )

        langsmith_runs = await self._fetch_runs_by_query(query_request)

        if not langsmith_runs:
            raise ValueError(f"No runs found for trace {trace_id}")

        # Convert to internal TraceRun objects
        runs = [self._convert_langsmith_run_to_trace_run(run) for run in langsmith_runs]

        # Sort runs by dotted_order to maintain hierarchy
        runs.sort(key=lambda x: x.dotted_order)

        # Extract trace metadata
        first_run = runs[0]
        start_time = min(run.start_time for run in runs)
        end_time = None
        if all(run.end_time for run in runs):
            end_time = max(run.end_time for run in runs if run.end_time)

        # Get project name from first run's session_id or use default
        project_name = first_run.metadata.get("session_id", "unknown")

        trace = Trace(
            trace_id=trace_id,
            project_name=project_name,
            runs=runs,
            start_time=start_time,
            end_time=end_time,
            metadata={"total_runs": len(runs)},
        )

        self.cache.set(cache_key, trace)
        logger.info(
            "Successfully fetched trace", trace_id=trace_id, run_count=len(runs)
        )

        return trace

    async def fetch_failed_traces(
        self, project: str, start_time: datetime, end_time: datetime, limit: int = 100
    ) -> List[Trace]:
        """
        Fetch traces that contain failures within a time range.

        Args:
            project: Project name to filter by
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum number of traces to return

        Returns:
            List[Trace]: List of traces containing failures
        """
        cache_key = (
            f"failed_{project}_{start_time.isoformat()}_{end_time.isoformat()}_{limit}"
        )
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.debug("Cache hit for failed traces", project=project)
            return cached_result

        logger.info(
            "Fetching failed traces",
            project=project,
            start_time=start_time,
            end_time=end_time,
        )

        # Build time range filter
        start_iso = start_time.isoformat()
        end_iso = end_time.isoformat()

        # Query for failed runs (runs with errors)
        query_request = LangSmithQueryRequest(
            filter=f'and(gte(start_time, "{start_iso}"), lte(start_time, "{end_iso}"), exists(error))',
            trace_filter=(
                f'eq(session_name, "{project}")' if project != "unknown" else None
            ),
            select=["trace_id"],
            limit=limit * 5,  # Get more runs to ensure we get enough unique traces
        )

        failed_runs = await self._fetch_runs_by_query(query_request)

        # Extract unique trace IDs
        trace_ids = list(set(run.trace_id for run in failed_runs))[:limit]

        # Fetch complete traces
        traces = []
        for trace_id in trace_ids:
            try:
                trace = await self.fetch_trace(trace_id)
                # Verify trace actually has failures
                if trace.get_failed_runs():
                    traces.append(trace)
            except Exception as e:
                logger.warning("Failed to fetch trace", trace_id=trace_id, error=str(e))
                continue

        self.cache.set(cache_key, traces)
        logger.info(
            "Successfully fetched failed traces", project=project, count=len(traces)
        )

        return traces

    async def fetch_trace_hierarchy(self, trace_id: str) -> Dict[str, Any]:
        """
        Fetch the complete hierarchy of a trace.

        Args:
            trace_id: The trace ID to fetch hierarchy for

        Returns:
            Dict[str, Any]: Hierarchical representation of the trace
        """
        cache_key = f"hierarchy_{trace_id}"
        cached_result = self.cache.get(cache_key)
        if cached_result is not None:
            logger.debug("Cache hit for trace hierarchy", trace_id=trace_id)
            return cached_result

        logger.info("Building trace hierarchy", trace_id=trace_id)

        # Fetch the complete trace
        trace = await self.fetch_trace(trace_id)

        # Build hierarchy using dotted_order
        hierarchy = {
            "trace_id": trace_id,
            "project_name": trace.project_name,
            "start_time": trace.start_time.isoformat(),
            "end_time": trace.end_time.isoformat() if trace.end_time else None,
            "total_runs": len(trace.runs),
            "failed_runs": len(trace.get_failed_runs()),
            "runs": [],
        }

        # Create a mapping of run_id to run data for building parent-child relationships
        {run.id: run for run in trace.runs}

        # Build hierarchical structure
        def build_run_node(run: TraceRun) -> Dict[str, Any]:
            return {
                "id": run.id,
                "name": run.name,
                "run_type": run.run_type.value,
                "dotted_order": run.dotted_order,
                "start_time": run.start_time.isoformat(),
                "end_time": run.end_time.isoformat() if run.end_time else None,
                "duration_ms": run.duration_ms,
                "is_failed": run.is_failed,
                "error": run.error,
                "inputs": run.inputs,
                "outputs": run.outputs,
                "children": [],
            }

        # Create nodes for all runs
        run_nodes = {run.id: build_run_node(run) for run in trace.runs}

        # Build parent-child relationships
        root_nodes = []
        for run in trace.runs:
            node = run_nodes[run.id]
            if run.parent_run_id and run.parent_run_id in run_nodes:
                parent_node = run_nodes[run.parent_run_id]
                parent_node["children"].append(node)
            else:
                root_nodes.append(node)

        # Sort children by dotted_order for consistent ordering
        def sort_children(node):
            node["children"].sort(key=lambda x: x["dotted_order"])
            for child in node["children"]:
                sort_children(child)

        for root in root_nodes:
            sort_children(root)

        hierarchy["runs"] = root_nodes

        self.cache.set(cache_key, hierarchy)
        logger.info(
            "Successfully built trace hierarchy",
            trace_id=trace_id,
            root_runs=len(root_nodes),
        )

        return hierarchy

    async def health_check(self) -> bool:
        """Check if LangSmith API is accessible."""
        try:
            # Make a simple query to test connectivity
            query_request = LangSmithQueryRequest(limit=1)
            await self._fetch_runs_by_query(query_request)
            return True
        except Exception as e:
            logger.error("LangSmith health check failed", error=str(e))
            return False

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self.cache._cache.clear()
        logger.info("Cache cleared")


# Factory function for creating LangSmith client
async def create_langsmith_client() -> LangSmithClient:
    """Create and return a configured LangSmith client."""
    client = LangSmithClient()

    # Verify connectivity
    if not await client.health_check():
        logger.warning("LangSmith API health check failed")

    return client
