"""
Implementation of the FailureAnalyst interface for analyzing AI agent failures.

This module provides advanced analysis capabilities for understanding why AI agents fail,
using chain-of-thought reasoning and structured outputs.
"""

import json
import asyncio
import tempfile
import logging
from pathlib import Path
from typing import Any, Dict
from datetime import datetime
from jinja2 import Template

import openai
from ..core.interfaces import FailureAnalyst
from ..core.models import (
    Trace, TraceAnalysis, GapAnalysis, Diagnosis,
    DomainExpertExpectation, FailureType, Confidence
)
from ..utils.config import config
from .holistic_templates import HOLISTIC_ANALYSIS_SCHEMA
from ..prompts.system_prompts import FAILURE_ANALYST_SYSTEM_PROMPT, HOLISTIC_ANALYSIS_TEMPLATE

logger = logging.getLogger(__name__)


class AdvancedFailureAnalyst(FailureAnalyst):
    """Holistic batch-based implementation of FailureAnalyst using OpenAI Files + Batch APIs."""
    
    def __init__(self):
        # Use OpenAI client directly for batch processing
        if not config.openai_api_key:
            raise ValueError("OpenAI API key is required for batch analysis")
        self.client = openai.Client(api_key=config.openai_api_key)
        self._cached_holistic_result = None  # Cache result for subsequent calls
        
    async def _holistic_batch_analysis(
        self,
        trace: Trace,
        expectation: DomainExpertExpectation,
        prompt_contents: dict = None,
        eval_contents: dict = None
    ) -> Dict[str, Any]:
        """Perform single holistic batch analysis covering all 3 sections."""
        logger.info("Starting holistic batch analysis", 
                   trace_id=trace.trace_id, 
                   runs_count=len(trace.runs))
        
        # Step 1: Prepare comprehensive trace data (NO file upload needed)
        trace_data = self._prepare_comprehensive_trace_data(
            trace, expectation, prompt_contents, eval_contents
        )
        
        # Step 2: Submit single batch request with holistic prompt + inline data
        batch_id = await self._submit_holistic_batch(trace_data, expectation, trace.trace_id)
        
        # Step 3: Poll for completion and parse result
        result = await self._poll_batch_completion(batch_id)
        
        # Step 4: Cache result for subsequent method calls
        self._cached_holistic_result = result
        
        return result
        
    async def analyze_trace(
        self, 
        trace: Trace,
        expectation: DomainExpertExpectation,
        prompt_contents: dict = None,
        eval_contents: dict = None
    ) -> TraceAnalysis:
        """Single holistic batch analysis - this method triggers the full analysis."""
        logger.info("Starting holistic batch analysis", trace_id=trace.trace_id)
        
        # Perform single holistic analysis via batch
        holistic_result = await self._holistic_batch_analysis(
            trace, expectation, prompt_contents, eval_contents
        )
        
        # Extract trace_analysis section
        trace_analysis_data = holistic_result["trace_analysis"]
        
        return TraceAnalysis(
            trace_id=trace.trace_id,
            execution_flow=trace_analysis_data.get("execution_summary", ""),
            context_at_each_step={"summary": trace_analysis_data.get("execution_summary", "")},
            data_transformations=[],
            error_propagation_path=trace_analysis_data.get("key_issues", []),
            identified_issues=trace_analysis_data.get("key_issues", [])
        )
    
    async def compare_to_expected(
        self,
        analysis: TraceAnalysis,
        expectation: DomainExpertExpectation,
        prompt_contents: dict = None,
        eval_contents: dict = None
    ) -> GapAnalysis:
        """Return cached gap analysis from holistic batch result."""
        logger.info("Returning cached gap analysis", trace_id=analysis.trace_id)
        
        # Gap analysis was already computed in holistic batch
        # This method just returns the cached result
        gap_analysis_data = self._cached_holistic_result["gap_analysis"]
        
        return GapAnalysis(
            behavioral_differences=gap_analysis_data["behavioral_differences"],
            missing_context=gap_analysis_data["missing_context"],
            incorrect_assumptions=[],  # Simplified schema doesn't include this
            suggested_focus_areas=gap_analysis_data.get("behavioral_differences", [])  # Use behavioral_differences as focus areas
        )
    
    async def diagnose_failure(
        self,
        trace_analysis: TraceAnalysis,
        gap_analysis: GapAnalysis,
        prompt_contents: dict = None,
        eval_contents: dict = None
    ) -> Diagnosis:
        """Return cached diagnosis from holistic batch result."""
        logger.info("Returning cached diagnosis", trace_id=trace_analysis.trace_id)
        
        # Diagnosis was already computed in holistic batch
        # This method just returns the cached result
        diagnosis_data = self._cached_holistic_result["diagnosis"]
        
        # Print the executive summary for visibility
        print("\n" + "="*80)
        print("HOLISTIC BATCH ANALYSIS COMPLETE:")
        print("="*80)
        print("Executive Summary:", self._cached_holistic_result["executive_summary"])
        print("="*80)
        
        return Diagnosis(
            failure_type=FailureType.CONTEXT_ISSUE,  # Default for simplified schema
            root_cause=diagnosis_data["root_cause"],
            evidence=[diagnosis_data.get("root_cause", "")],
            affected_components=[],
            confidence=Confidence(diagnosis_data["confidence"]),
            detailed_analysis=diagnosis_data.get("root_cause", "")
        )
    
    def _prepare_comprehensive_trace_data(
        self,
        trace: Trace,
        expectation: DomainExpertExpectation,
        prompt_contents: dict = None,
        eval_contents: dict = None
    ) -> str:
        """Prepare comprehensive trace data as formatted text for inline use."""
        
        # Build comprehensive trace data as readable text
        trace_text = f"""
=== TRACE ANALYSIS DATA ===

TRACE METADATA:
- Trace ID: {trace.trace_id}
- Project: {trace.project_name}
- Total Runs: {len(trace.runs)}
- Start Time: {trace.start_time.isoformat()}
- End Time: {trace.end_time.isoformat() if trace.end_time else "N/A"}
- Duration: {trace.duration_ms}ms

EXPECTATION:
- Description: {expectation.description}
- Business Context: {expectation.business_context or "N/A"}
- Specific Issues: {expectation.specific_issues or "None specified"}
- Expected Output: {expectation.expected_output or "N/A"}

EXECUTION RUNS ({len(trace.runs)} total):
"""
        
        # Add run details (up to 50 runs max)
        for i, run in enumerate(trace.runs[:50]):
            trace_text += f"""
--- Run {i+1}: {run.name} (ID: {run.id}) ---
Type: {run.run_type.value}
Order: {run.dotted_order}
Duration: {run.duration_ms}ms
Parent: {run.parent_run_id or "None"}

INPUTS:
{json.dumps(run.inputs, indent=2)}

OUTPUTS:  
{json.dumps(run.outputs, indent=2)}

ERROR: {run.error or "None"}

"""
        
        # Add agent files if provided
        if prompt_contents:
            trace_text += "\nAGENT PROMPT FILES:\n"
            for file_path, content in prompt_contents.items():
                trace_text += f"\n--- {file_path} ---\n{content[:1000]}{'...[truncated]' if len(content) > 1000 else ''}\n"
        
        if eval_contents:
            trace_text += "\nAGENT EVALUATION FILES:\n"
            for file_path, content in eval_contents.items():
                trace_text += f"\n--- {file_path} ---\n{content[:1000]}{'...[truncated]' if len(content) > 1000 else ''}\n"
        
        trace_text += "\n=== END TRACE DATA ===\n"
        
        logger.info("Prepared trace data for inline analysis", 
                   text_length=len(trace_text), 
                   runs_included=min(len(trace.runs), 20))
        
        return trace_text
    
    async def _submit_holistic_batch(self, trace_data: str, expectation: DomainExpertExpectation, trace_id: str = None) -> str:
        """Submit single holistic batch analysis request with inline trace data."""
        
        # Build combined prompt with trace data
        combined_prompt = self._build_holistic_prompt(expectation) + "\n\n" + trace_data
        
        # Create holistic analysis request using correct Responses API format
        analysis_request = {
            "model": "gpt-4o",
            "input": [
                {
                    "type": "message",
                    "role": "system",
                    "content": FAILURE_ANALYST_SYSTEM_PROMPT
                },
                {
                    "type": "message", 
                    "role": "user",
                    "content": combined_prompt
                }
            ],
            "max_output_tokens": 2000,  # Reduced to allow 88K input tokens
            "temperature": 0.1,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "holistic_analysis",
                    "strict": True,
                    "schema": HOLISTIC_ANALYSIS_SCHEMA
                }
            }
        }
        
        # Create batch request
        batch_request = {
            "custom_id": f"holistic_analysis_{trace_id or 'unknown'}_{int(datetime.now().timestamp())}",
            "method": "POST",
            "url": "/v1/responses", 
            "body": analysis_request
        }
        
        # Write and upload batch file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(json.dumps(batch_request) + '\n')
            batch_file_path = f.name
            
        try:
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
            
            logger.info("Holistic batch submitted", 
                       batch_id=batch_response.id,
                       input_file_id=batch_file_response.id)
            
            return batch_response.id
            
        finally:
            Path(batch_file_path).unlink(missing_ok=True)
            
    def _build_holistic_prompt(self, expectation: DomainExpertExpectation) -> str:
        """Build holistic analysis prompt using Jinja2 template."""
        template = Template(HOLISTIC_ANALYSIS_TEMPLATE)
        
        return template.render(
            expected_behavior=expectation.description,
            business_context=expectation.business_context,
            specific_issues=expectation.specific_issues
        )
        
    async def _poll_batch_completion(self, batch_id: str) -> Dict[str, Any]:
        """Poll batch job until completion and parse results."""
        logger.info("Polling batch completion", batch_id=batch_id)
        
        while True:
            batch_status = self.client.batches.retrieve(batch_id)
            status = batch_status.status
            
            logger.info("Batch status check", batch_id=batch_id, status=status)
            
            if status == "completed":
                # Re-fetch batch object to get populated output_file_id (2025 gotcha!)
                fresh_batch = self.client.batches.retrieve(batch_id)
                
                # Check request counts first
                successful_count = getattr(fresh_batch.request_counts, 'completed', 0)
                failed_count = getattr(fresh_batch.request_counts, 'failed', 0)
                
                logger.info("Batch completion stats", 
                           successful=successful_count, 
                           failed=failed_count)
                
                if successful_count > 0 and fresh_batch.output_file_id:
                    return await self._download_batch_results(fresh_batch.output_file_id)
                elif failed_count > 0 and fresh_batch.error_file_id:
                    # All requests failed - download error file instead
                    error_content = self.client.files.content(fresh_batch.error_file_id)
                    error_text = error_content.read().decode('utf-8')
                    logger.error("Batch failed - full error details: " + error_text)
                    raise RuntimeError(f"All batch requests failed. Error: {error_text}")
                else:
                    raise RuntimeError(f"Batch completed but no output or error file: {batch_id}")
                    
            elif status == "failed":
                error_details = batch_status.errors
                raise RuntimeError(f"Batch failed: {batch_id}, errors: {error_details}")
                
            elif status in ["cancelled", "expired"]:
                raise RuntimeError(f"Batch {status}: {batch_id}")
                
            # Wait before next poll
            await asyncio.sleep(30)  # 30 second intervals
            
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
        
        # Extract analysis from first result
        result = results[0]
        
        if result.get("error"):
            raise RuntimeError(f"Analysis failed: {result['error']}")
        
        response_body = result["response"]["body"]
        
        # Extract JSON analysis from response
        output_items = response_body.get("output", [])
        for item in output_items:
            if item.get("type") == "message" and item.get("role") == "assistant":
                content_items = item.get("content", [])
                for content in content_items:
                    if content.get("type") == "output_text":
                        analysis_text = content.get("text", "")
                        # Parse JSON from analysis text
                        return json.loads(analysis_text)
        
        raise RuntimeError("Could not extract analysis from batch results")
        
    async def _cleanup_file(self, file_id: str) -> None:
        """Delete uploaded file after analysis."""
        try:
            self.client.files.delete(file_id)
            logger.info("File cleaned up", file_id=file_id)
        except Exception as e:
            logger.warning("Failed to cleanup file", file_id=file_id, error=str(e))


