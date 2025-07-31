"""
Simple LangSmith integration using the official SDK.
"""

import structlog
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from langsmith import Client
from ..core.interfaces import TraceProvider
from ..core.models import Trace, TraceRun, RunType
from ..utils.config import config

logger = structlog.get_logger(__name__)


class SimpleLangSmithClient(TraceProvider):
    """Simple LangSmith client using the official SDK."""
    
    def __init__(self):
        """Initialize LangSmith client."""
        if not config.langsmith_api_key:
            raise ValueError("LangSmith API key is required")
            
        self.client = Client(
            api_key=config.langsmith_api_key,
            api_url=config.langsmith_api_url
        )
        
        logger.info("LangSmith client initialized")
    
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
    
    async def fetch_trace(self, trace_id: str) -> Trace:
        """Fetch a single trace by ID."""
        if not trace_id:
            raise ValueError("trace_id cannot be empty")
        
        logger.info("Fetching trace", trace_id=trace_id)
        
        try:
            # Use the official SDK to list runs for this trace
            runs = list(self.client.list_runs(trace_id=trace_id))
            
            if not runs:
                raise ValueError(f"No runs found for trace_id: {trace_id}")
            
            # Convert to internal format
            trace_runs = []
            trace_start_time = None
            trace_end_time = None
            project_name = "unknown"
            
            for run in runs:
                # Truncate large inputs/outputs to manage token usage
                inputs = run.inputs or {}
                outputs = run.outputs
                
                # Truncate large text fields
                if isinstance(inputs, dict):
                    inputs = {k: str(v)[:1000] + "..." if len(str(v)) > 1000 else v 
                             for k, v in inputs.items()}
                
                if isinstance(outputs, dict):
                    outputs = {k: str(v)[:1000] + "..." if len(str(v)) > 1000 else v 
                              for k, v in outputs.items()}
                elif isinstance(outputs, str) and len(outputs) > 1000:
                    outputs = outputs[:1000] + "..."
                
                # Convert SDK run to internal TraceRun
                trace_run = TraceRun(
                    id=str(run.id),
                    name=run.name or "unnamed",
                    run_type=self._map_run_type(run.run_type or "chain"),
                    inputs=inputs,
                    outputs=outputs,
                    start_time=run.start_time,
                    end_time=run.end_time,
                    error=run.error,
                    parent_run_id=str(run.parent_run_id) if run.parent_run_id else None,
                    trace_id=str(run.trace_id),
                    dotted_order=run.dotted_order or "",
                    metadata={}
                )
                
                trace_runs.append(trace_run)
                
                # Track overall trace timing
                if trace_start_time is None or run.start_time < trace_start_time:
                    trace_start_time = run.start_time
                if run.end_time and (trace_end_time is None or run.end_time > trace_end_time):
                    trace_end_time = run.end_time
                
                # Get project name from session
                if hasattr(run, 'session_name') and run.session_name:
                    project_name = run.session_name
            
            # Limit trace size for analysis (keep most important runs)
            if len(trace_runs) > 10:
                logger.warning("Large trace detected, limiting to key runs", 
                             total_runs=len(trace_runs))
                # Keep root runs, failed runs, and recent runs
                important_runs = []
                failed_runs = [r for r in trace_runs if r.error]
                root_runs = [r for r in trace_runs if not r.parent_run_id]
                
                # Add failed runs (highest priority)
                important_runs.extend(failed_runs[:5])
                
                # Add root runs  
                for run in root_runs[:3]:
                    if run not in important_runs:
                        important_runs.append(run)
                
                # Fill remaining with most recent runs
                remaining_slots = 10 - len(important_runs)
                for run in reversed(trace_runs[-remaining_slots:]):
                    if run not in important_runs:
                        important_runs.append(run)
                
                trace_runs = important_runs[:10]
                logger.info("Limited trace size", kept_runs=len(trace_runs))
            
            trace = Trace(
                trace_id=trace_id,
                project_name=project_name,
                runs=trace_runs,
                start_time=trace_start_time or datetime.now(timezone.utc),
                end_time=trace_end_time,
                metadata={}
            )
            
            logger.info("Trace fetched successfully", 
                       trace_id=trace_id, 
                       runs_count=len(trace_runs))
            
            return trace
            
        except Exception as e:
            logger.error("Failed to fetch trace", trace_id=trace_id, error=str(e))
            raise
    
    async def fetch_failed_traces(
        self, 
        project: str, 
        start_time: datetime,
        end_time: datetime,
        limit: int = 100
    ) -> List[Trace]:
        """Fetch traces that contain failures within a time range."""
        # This is a simplified implementation
        logger.info("Fetching failed traces", project=project, limit=limit)
        return []
    
    async def fetch_trace_hierarchy(self, trace_id: str) -> Dict[str, Any]:
        """Fetch the complete hierarchy of a trace."""
        trace = await self.fetch_trace(trace_id)
        
        return {
            "trace_id": trace_id,
            "project_name": trace.project_name,
            "start_time": trace.start_time.isoformat(),
            "end_time": trace.end_time.isoformat() if trace.end_time else None,
            "total_runs": len(trace.runs),
            "failed_runs": len(trace.get_failed_runs()),
            "runs": [
                {
                    "id": run.id,
                    "name": run.name,
                    "run_type": run.run_type.value,
                    "parent_id": run.parent_run_id,
                    "error": run.error
                }
                for run in trace.runs
            ]
        }


async def create_langsmith_client() -> SimpleLangSmithClient:
    """Create and return a configured LangSmith client."""
    return SimpleLangSmithClient()