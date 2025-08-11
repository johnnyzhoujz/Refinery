"""
Batch-based trace analysis using OpenAI's Files and Batch APIs.

This module implements holistic trace analysis by:
1. Uploading full traces to Files API (bypassing truncation)
2. Using Batch API to avoid 30k TPM rate limits
3. Processing via Responses API with large context windows
"""

import json
import asyncio
import tempfile
import structlog
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

import openai
from ..core.models import Trace, TraceAnalysis, DomainExpertExpectation
from ..utils.config import config
from ..prompts.system_prompts import FAILURE_ANALYST_SYSTEM_PROMPT_V2

logger = structlog.get_logger(__name__)


class BatchTraceAnalyzer:
    """Holistic trace analysis using OpenAI Batch API."""
    
    def __init__(self):
        """Initialize with OpenAI client."""
        if not config.openai_api_key:
            raise ValueError("OpenAI API key is required for batch analysis")
        
        self.client = openai.Client(api_key=config.openai_api_key)
        logger.info("BatchTraceAnalyzer initialized")
    
    async def analyze_trace_holistic(
        self,
        trace: Trace,
        expectation: DomainExpertExpectation,
        prompt_contents: dict = None,
        eval_contents: dict = None,
        model: str = "gpt-4o"
    ) -> Dict[str, Any]:
        """
        Perform one-shot holistic analysis of entire trace using Batch API.
        
        Args:
            trace: Full trace data (no truncation)
            expectation: Domain expert's expected behavior
            prompt_contents: Agent prompt files
            eval_contents: Agent eval files  
            model: Model to use (default gpt-4o for large context)
            
        Returns:
            Dict with analysis results and metadata
        """
        logger.info("Starting holistic trace analysis", 
                   trace_id=trace.trace_id, 
                   runs_count=len(trace.runs))
        
        # Step 1: Upload trace as file
        trace_file_id = await self._upload_trace_file(trace, prompt_contents, eval_contents)
        
        # Step 2: Create batch analysis request
        batch_id = await self._submit_batch_analysis(
            trace_file_id, expectation, model
        )
        
        # Step 3: Poll for completion
        results = await self._poll_batch_completion(batch_id)
        
        # Step 4: Cleanup files (optional)
        await self._cleanup_file(trace_file_id)
        
        return results
    
    async def _upload_trace_file(
        self, 
        trace: Trace, 
        prompt_contents: dict = None,
        eval_contents: dict = None
    ) -> str:
        """Upload trace data to Files API."""
        
        # Prepare comprehensive trace data (NO truncation)
        trace_data = {
            "trace_metadata": {
                "trace_id": trace.trace_id,
                "project_name": trace.project_name,
                "total_runs": len(trace.runs),
                "start_time": trace.start_time.isoformat(),
                "end_time": trace.end_time.isoformat() if trace.end_time else None,
                "duration_ms": trace.duration_ms
            },
            "runs": [],
            "prompt_files": prompt_contents or {},
            "eval_files": eval_contents or {}
        }
        
        # Include ALL runs with FULL context
        for run in trace.runs:
            run_data = {
                "id": run.id,
                "name": run.name,
                "run_type": run.run_type.value,
                "inputs": run.inputs,  # Full inputs - no truncation
                "outputs": run.outputs,  # Full outputs - no truncation
                "error": run.error,
                "start_time": run.start_time.isoformat(),
                "end_time": run.end_time.isoformat() if run.end_time else None,
                "duration_ms": run.duration_ms,
                "parent_run_id": run.parent_run_id,
                "trace_id": run.trace_id,
                "dotted_order": run.dotted_order,
                "metadata": run.metadata
            }
            trace_data["runs"].append(run_data)
        
        # Write to temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(trace_data, f, indent=2, ensure_ascii=False)
            temp_path = f.name
        
        try:
            # Upload to Files API with purpose="user_data"
            with open(temp_path, 'rb') as f:
                file_response = self.client.files.create(
                    file=f,
                    purpose="user_data"
                )
            
            file_id = file_response.id
            logger.info("Trace uploaded to Files API", 
                       file_id=file_id, 
                       bytes=file_response.bytes)
            
            return file_id
            
        finally:
            # Cleanup temp file
            Path(temp_path).unlink(missing_ok=True)
    
    async def _submit_batch_analysis(
        self, 
        trace_file_id: str, 
        expectation: DomainExpertExpectation,
        model: str
    ) -> str:
        """Submit batch analysis request."""
        
        # Create analysis request for Responses API
        analysis_request = {
            "model": model,
            "instructions": FAILURE_ANALYST_SYSTEM_PROMPT_V2,
            "input": [
                {
                    "type": "text",
                    "text": f"""Analyze this complete agent trace for failure diagnosis.

**Expected Behavior:** {expectation.description}

**Business Context:** {expectation.business_context or 'Not provided'}

**Specific Issues to Check:** {expectation.specific_issues or 'General failure analysis'}

The complete trace data is attached as a file. Provide:

1. **Executive Summary** (2-3 sentences): What went wrong and why?

2. **Structured Analysis**:
```json
{{
  "failure_type": "context_issue|model_limitation|orchestration_issue|data_issue",
  "confidence": "HIGH|MEDIUM|LOW",
  "root_cause": "specific cause description",
  "evidence": ["evidence 1", "evidence 2", "..."],
  "affected_runs": ["run_id_1", "run_id_2"],
  "business_impact": "how this affects the user/business",
  "recommendations": [
    "specific actionable fix 1",
    "specific actionable fix 2"
  ]
}}
```

3. **Key Evidence Citations**: Reference specific run IDs and input/output content that support your diagnosis.
"""
                },
                {
                    "type": "file",
                    "file_id": trace_file_id
                }
            ],
            "max_output_tokens": 8000,  # Reasonable cap to stay within context
            "temperature": 0.1  # Low temperature for consistent analysis
        }
        
        # Create batch input file
        batch_request = {
            "custom_id": f"trace_analysis_{expectation.trace_id or 'unknown'}_{int(datetime.now().timestamp())}",
            "method": "POST", 
            "url": "/v1/responses",
            "body": analysis_request
        }
        
        # Write batch JSONL file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(json.dumps(batch_request) + '\n')
            batch_file_path = f.name
        
        try:
            # Upload batch file
            with open(batch_file_path, 'rb') as f:
                batch_file_response = self.client.files.create(
                    file=f,
                    purpose="batch"
                )
            
            # Create batch job
            batch_response = self.client.batches.create(
                input_file_id=batch_file_response.id,
                endpoint="/v1/responses",
                completion_window="24h"
            )
            
            batch_id = batch_response.id
            logger.info("Batch analysis submitted", 
                       batch_id=batch_id,
                       input_file_id=batch_file_response.id)
            
            return batch_id
            
        finally:
            # Cleanup temp file
            Path(batch_file_path).unlink(missing_ok=True)
    
    async def _poll_batch_completion(self, batch_id: str) -> Dict[str, Any]:
        """Poll batch job until completion and return results."""
        
        logger.info("Polling batch completion", batch_id=batch_id)
        
        while True:
            batch_status = self.client.batches.retrieve(batch_id)
            
            status = batch_status.status
            logger.info("Batch status check", batch_id=batch_id, status=status)
            
            if status == "completed":
                # Retrieve results
                output_file_id = batch_status.output_file_id
                if output_file_id:
                    results = await self._download_batch_results(output_file_id)
                    return {
                        "status": "completed",
                        "results": results,
                        "batch_metadata": {
                            "batch_id": batch_id,
                            "request_counts": batch_status.request_counts,
                            "completed_at": batch_status.completed_at
                        }
                    }
                else:
                    raise RuntimeError(f"Batch completed but no output file: {batch_id}")
                    
            elif status == "failed":
                error_details = batch_status.errors
                raise RuntimeError(f"Batch failed: {batch_id}, errors: {error_details}")
                
            elif status in ["cancelled", "expired"]:
                raise RuntimeError(f"Batch {status}: {batch_id}")
                
            # Wait before next poll (exponential backoff)
            await asyncio.sleep(30)  # 30 second intervals for batch polling
    
    async def _download_batch_results(self, output_file_id: str) -> Dict[str, Any]:
        """Download and parse batch results."""
        
        # Download results file
        file_content = self.client.files.content(output_file_id)
        content_text = file_content.read().decode('utf-8')
        
        # Parse JSONL results
        results = []
        for line in content_text.strip().split('\n'):
            if line.strip():
                result = json.loads(line)
                results.append(result)
        
        if not results:
            raise RuntimeError("No results found in batch output")
        
        # Extract the analysis from the first (and only) result
        result = results[0]
        
        if result.get("error"):
            raise RuntimeError(f"Analysis failed: {result['error']}")
        
        response_body = result["response"]["body"]
        
        # Extract the analysis text from the response
        output_items = response_body.get("output", [])
        analysis_text = ""
        
        for item in output_items:
            if item.get("type") == "message" and item.get("role") == "assistant":
                content_items = item.get("content", [])
                for content in content_items:
                    if content.get("type") == "output_text":
                        analysis_text += content.get("text", "")
        
        return {
            "analysis_text": analysis_text,
            "usage": response_body.get("usage", {}),
            "model": response_body.get("model"),
            "response_id": response_body.get("id")
        }
    
    async def _cleanup_file(self, file_id: str) -> None:
        """Delete uploaded file after analysis."""
        try:
            self.client.files.delete(file_id)
            logger.info("File cleaned up", file_id=file_id)
        except Exception as e:
            logger.warning("Failed to cleanup file", file_id=file_id, error=str(e))


async def create_batch_analyzer() -> BatchTraceAnalyzer:
    """Create and return a configured batch analyzer."""
    return BatchTraceAnalyzer()