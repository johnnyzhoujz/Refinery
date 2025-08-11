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
                    inputs = {k: str(v)[:4000] + "..." if len(str(v)) > 4000 else v 
                             for k, v in inputs.items()}
                
                if isinstance(outputs, dict):
                    outputs = {k: str(v)[:4000] + "..." if len(str(v)) > 4000 else v 
                              for k, v in outputs.items()}
                elif isinstance(outputs, str) and len(outputs) > 4000:
                    outputs = outputs[:4000] + "..."
                
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
            if len(trace_runs) > 50:
                logger.warning("Large trace detected, limiting to key runs", 
                             total_runs=len(trace_runs))
                # Keep root runs, failed runs, and recent runs
                important_runs = []
                failed_runs = [r for r in trace_runs if r.error]
                root_runs = [r for r in trace_runs if not r.parent_run_id]
                
                # Add failed runs (highest priority)
                important_runs.extend(failed_runs[:10])
                
                # Add root runs  
                for run in root_runs[:5]:
                    if run not in important_runs:
                        important_runs.append(run)
                
                # Fill remaining with most recent runs
                remaining_slots = 50 - len(important_runs)
                for run in reversed(trace_runs[-remaining_slots:]):
                    if run not in important_runs:
                        important_runs.append(run)
                
                trace_runs = important_runs[:50]
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
    
    def extract_prompts_from_trace(self, trace: Trace) -> Dict[str, Any]:
        """Extract all prompts, templates, and model configs from a trace.
        
        Returns a dictionary with:
        - system_prompts: List of system prompts found
        - user_prompts: List of user message templates
        - prompt_templates: Any prompt templates with variables
        - model_configs: Model configuration details
        - eval_examples: Input/output pairs that could be test cases
        """
        extracted = {
            "system_prompts": [],
            "user_prompts": [],
            "prompt_templates": [],
            "model_configs": [],
            "eval_examples": [],
            "agent_metadata": {}
        }
        
        for run in trace.runs:
            # Extract from LLM runs (most likely to have prompts)
            if run.run_type == RunType.LLM:
                inputs = run.inputs or {}
                
                # Look for prompts in common locations
                # Handle different prompt formats from various frameworks
                
                # OpenAI format
                if "messages" in inputs:
                    messages = inputs["messages"]
                    if isinstance(messages, list):
                        for msg in messages:
                            if isinstance(msg, dict):
                                role = msg.get("role", "")
                                content = msg.get("content", "")
                                
                                if role == "system" and content:
                                    extracted["system_prompts"].append({
                                        "content": content,
                                        "run_id": run.id,
                                        "run_name": run.name,
                                        "timestamp": run.start_time.isoformat()
                                    })
                                elif role == "user" and content:
                                    extracted["user_prompts"].append({
                                        "content": content,
                                        "run_id": run.id,
                                        "run_name": run.name,
                                        "timestamp": run.start_time.isoformat(),
                                        "has_variables": self._detect_template_variables(content)
                                    })
                
                # Anthropic format
                if "prompt" in inputs:
                    prompt = inputs["prompt"]
                    if isinstance(prompt, str) and prompt:
                        extracted["user_prompts"].append({
                            "content": prompt,
                            "run_id": run.id,
                            "run_name": run.name,
                            "timestamp": run.start_time.isoformat(),
                            "has_variables": self._detect_template_variables(prompt)
                        })
                
                # Extract model configuration
                model_config = {}
                for key in ["model", "model_name", "temperature", "max_tokens", "top_p", "frequency_penalty"]:
                    if key in inputs:
                        model_config[key] = inputs[key]
                
                if model_config:
                    model_config["run_id"] = run.id
                    model_config["run_name"] = run.name
                    extracted["model_configs"].append(model_config)
            
            # Extract from Chain/Agent runs (might have templates)
            elif run.run_type in [RunType.CHAIN, RunType.TOOL]:
                inputs = run.inputs or {}
                outputs = run.outputs or {}
                
                # Look for template-like content
                for key, value in inputs.items():
                    if isinstance(value, str) and (
                        "prompt" in key.lower() or 
                        "template" in key.lower() or
                        "instruction" in key.lower() or
                        len(value) > 50  # Likely a prompt if it's long text
                    ):
                        if self._detect_template_variables(value):
                            extracted["prompt_templates"].append({
                                "content": value,
                                "key": key,
                                "run_id": run.id,
                                "run_name": run.name,
                                "variables": self._extract_template_variables(value)
                            })
                
                # Collect input/output pairs for potential test cases
                if inputs and outputs and not run.error:
                    extracted["eval_examples"].append({
                        "inputs": inputs,
                        "outputs": outputs,
                        "run_id": run.id,
                        "run_name": run.name,
                        "run_type": run.run_type.value
                    })
        
        # Extract agent metadata
        root_runs = [r for r in trace.runs if not r.parent_run_id]
        if root_runs:
            extracted["agent_metadata"] = {
                "agent_name": root_runs[0].name,
                "project_name": trace.project_name,
                "trace_id": trace.trace_id,
                "total_runs": len(trace.runs),
                "failed_runs": len([r for r in trace.runs if r.error]),
                "duration_ms": trace.duration_ms
            }
        
        # Deduplicate prompts
        extracted["system_prompts"] = self._deduplicate_prompts(extracted["system_prompts"])
        extracted["user_prompts"] = self._deduplicate_prompts(extracted["user_prompts"])
        
        return extracted
    
    def _detect_template_variables(self, text: str) -> bool:
        """Check if text contains template variables."""
        import re
        patterns = [
            r'\{[^}]+\}',  # {variable}
            r'\{\{[^}]+\}\}',  # {{variable}}
            r'\$\{[^}]+\}',  # ${variable}
        ]
        return any(re.search(pattern, text) for pattern in patterns)
    
    def _extract_template_variables(self, text: str) -> List[str]:
        """Extract variable names from template text."""
        import re
        variables = set()
        
        # Extract {variable} style
        variables.update(re.findall(r'\{([^}]+)\}', text))
        # Extract {{variable}} style
        variables.update(re.findall(r'\{\{([^}]+)\}\}', text))
        # Extract ${variable} style
        variables.update(re.findall(r'\$\{([^}]+)\}', text))
        
        return list(variables)
    
    def _deduplicate_prompts(self, prompts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate prompts, keeping the first occurrence."""
        seen = set()
        unique = []
        
        for prompt in prompts:
            content = prompt.get("content", "")
            if content and content not in seen:
                seen.add(content)
                unique.append(prompt)
        
        return unique


async def create_langsmith_client() -> SimpleLangSmithClient:
    """Create and return a configured LangSmith client."""
    return SimpleLangSmithClient()