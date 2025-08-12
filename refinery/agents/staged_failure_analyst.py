"""
Staged failure analyst using Vector Store + File Search with Interactive Responses API.

This implements the 4-stage analysis approach:
1. Trace Analysis (Interactive) - Heavy retrieval and analysis
2. Gap Analysis (Interactive) - Compare actual vs expected  
3. Diagnosis (Interactive) - Root cause with evidence
4. Synthesis (Interactive) - Executive summary and recommendations
"""

import json
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

import openai
from ..core.interfaces import FailureAnalyst
from ..core.models import (
    Trace, TraceAnalysis, GapAnalysis, Diagnosis,
    DomainExpertExpectation, FailureType, Confidence
)
from ..utils.config import config
from ..integrations.vector_store_manager import VectorStoreManager
from ..integrations import responses_client
from ..integrations.responses_request_builder import (
    build_responses_body, build_responses_body_no_tools
)
from .staged_schemas import (
    TRACE_ANALYSIS_SCHEMA, GAP_ANALYSIS_SCHEMA, 
    DIAGNOSIS_SCHEMA, SYNTHESIS_SCHEMA
)
from ..prompts.system_prompts import (
    FAILURE_ANALYST_SYSTEM_PROMPT_V3,
    STAGE1_TRACE_ANALYSIS_PROMPT,
    STAGE2_GAP_ANALYSIS_PROMPT,
    STAGE3_DIAGNOSIS_PROMPT,
    STAGE4_SYNTHESIS_PROMPT
)

logger = logging.getLogger(__name__)


class StagedFailureAnalyst(FailureAnalyst):
    """
    Staged implementation using Vector Store + File Search with Interactive Responses API.
    
    All 4 stages use Interactive Responses API for reliable, fast analysis.
    """
    
    def __init__(self, model: str = "gpt-4o"):
        if not config.openai_api_key:
            raise ValueError("OpenAI API key is required for staged analysis")
        
        self.model = model
        self.client = openai.Client(api_key=config.openai_api_key)
        self.vector_store_manager = VectorStoreManager()
        
        # Initialize responses client
        responses_client.init_client(config.openai_api_key)
        
        # Cache results between stages
        self._vector_store_id: Optional[str] = None
        self._stage1_result: Optional[Dict] = None
        self._stage2_result: Optional[Dict] = None
        self._stage3_result: Optional[Dict] = None
        self._stage4_result: Optional[Dict] = None

    async def analyze_trace(
        self, 
        trace: Trace,
        expectation: DomainExpertExpectation,
        prompt_contents: dict = None,
        eval_contents: dict = None
    ) -> TraceAnalysis:
        """Run Stage 1: Trace Analysis using Interactive Responses API."""
        
        logger.info(f"Starting staged trace analysis for trace {trace.trace_id}")
        
        # Create vector store with all files
        self._vector_store_id = await self.vector_store_manager.create_analysis_vector_store(
            trace, expectation, prompt_contents or {}, eval_contents or {}
        )
        
        # Run Stage 1 interactively
        self._stage1_result = await self._run_stage1_interactive()
        
        # Convert to TraceAnalysis format for backward compatibility
        return self._convert_stage1_to_trace_analysis(trace.trace_id)
    
    async def compare_to_expected(
        self,
        analysis: TraceAnalysis,
        expectation: DomainExpertExpectation,
        prompt_contents: dict = None,
        eval_contents: dict = None
    ) -> GapAnalysis:
        """Run Stage 2: Gap Analysis using Interactive Responses API."""
        
        if not self._stage1_result:
            raise ValueError("Stage 1 must complete before Stage 2")
        
        logger.info(f"Starting Stage 2: Gap Analysis for trace {analysis.trace_id}")
        
        self._stage2_result = await self._run_stage2_interactive()
        
        # Convert to GapAnalysis format
        return self._convert_stage2_to_gap_analysis()
    
    async def diagnose_failure(
        self,
        trace_analysis: TraceAnalysis,
        gap_analysis: GapAnalysis,
        prompt_contents: dict = None,
        eval_contents: dict = None
    ) -> Diagnosis:
        """Run Stage 3: Diagnosis and Stage 4: Synthesis using Interactive Responses API."""
        
        if not self._stage2_result:
            raise ValueError("Stage 2 must complete before Stage 3")
        
        logger.info(f"Starting Stage 3: Diagnosis for trace {trace_analysis.trace_id}")
        
        self._stage3_result = await self._run_stage3_interactive()
        
        # Run Stage 4: Synthesis
        self._stage4_result = await self._run_stage4_interactive()
        
        # Print executive summary
        if self._stage4_result and "summary" in self._stage4_result:
            print("\n" + "="*80)
            print("STAGED ANALYSIS COMPLETE:")
            print("="*80)
            print("Executive Summary:", self._stage4_result["summary"]["executive_summary"])
            print("="*80)
        
        # Convert to Diagnosis format
        return self._convert_stage3_to_diagnosis()
    
    async def _run_stage1_interactive(self) -> Dict[str, Any]:
        """Run Stage 1: Trace Analysis interactively using Responses API."""
        
        logger.info("Running Stage 1: Trace Analysis (Interactive)")
        
        # Build request body with V3 system prompt (V2 + file search)
        body = build_responses_body(
            model=self.model,
            vector_store_id=self._vector_store_id,
            system_text=FAILURE_ANALYST_SYSTEM_PROMPT_V3,
            user_text=STAGE1_TRACE_ANALYSIS_PROMPT,
            json_schema_obj=TRACE_ANALYSIS_SCHEMA,
            max_num_results=8,
            max_output_tokens=2000,
            temperature=0.2
        )
        
        # Send request and parse response
        result = await responses_client.create_with_retry(body)
        
        logger.info("Completed Stage 1: Trace Analysis")
        return result
    
    async def _run_stage2_interactive(self) -> Dict[str, Any]:
        """Run Stage 2: Gap Analysis interactively using Responses API."""
        
        logger.info("Running Stage 2: Gap Analysis (Interactive)")
        
        # Format Stage 2 prompt with Stage 1 results
        user_prompt = STAGE2_GAP_ANALYSIS_PROMPT.format(
            stage1_json=json.dumps(self._stage1_result, indent=2)
        )
        
        # Build request body with V3 system prompt
        body = build_responses_body(
            model=self.model,
            vector_store_id=self._vector_store_id,
            system_text=FAILURE_ANALYST_SYSTEM_PROMPT_V3,
            user_text=user_prompt,
            json_schema_obj=GAP_ANALYSIS_SCHEMA,
            max_num_results=8,
            max_output_tokens=2000,
            temperature=0.2
        )
        
        # Send request and parse response
        result = await responses_client.create_with_retry(body)
        
        logger.info("Completed Stage 2: Gap Analysis")
        return result
    
    async def _run_stage3_interactive(self) -> Dict[str, Any]:
        """Run Stage 3: Diagnosis interactively using Responses API."""
        
        logger.info("Running Stage 3: Diagnosis (Interactive)")
        
        # Format Stage 3 prompt with previous results
        user_prompt = STAGE3_DIAGNOSIS_PROMPT.format(
            stage1_json=json.dumps(self._stage1_result, indent=2),
            stage2_json=json.dumps(self._stage2_result, indent=2)
        )
        
        # Build request body with V3 system prompt
        body = build_responses_body(
            model=self.model,
            vector_store_id=self._vector_store_id,
            system_text=FAILURE_ANALYST_SYSTEM_PROMPT_V3,
            user_text=user_prompt,
            json_schema_obj=DIAGNOSIS_SCHEMA,
            max_num_results=8,
            max_output_tokens=2500,
            temperature=0.2
        )
        
        # Send request and parse response
        result = await responses_client.create_with_retry(body)
        
        logger.info("Completed Stage 3: Diagnosis")
        return result
    
    async def _run_stage4_interactive(self) -> Dict[str, Any]:
        """Run Stage 4: Synthesis interactively using Responses API."""
        
        logger.info("Running Stage 4: Synthesis (Interactive)")
        
        # Stage 4 doesn't need file search - use simplified system prompt
        synthesis_system_prompt = "Use the provided JSON artifacts to synthesize findings. Output valid JSON per the given schema; no prose."
        
        # Format Stage 4 prompt with all previous results
        user_prompt = STAGE4_SYNTHESIS_PROMPT.format(
            stage1_json=json.dumps(self._stage1_result, indent=2),
            stage2_json=json.dumps(self._stage2_result, indent=2),
            stage3_json=json.dumps(self._stage3_result, indent=2)
        )
        
        # Build request body without file_search tool
        body = build_responses_body_no_tools(
            model=self.model,
            system_text=synthesis_system_prompt,
            user_text=user_prompt,
            json_schema_obj=SYNTHESIS_SCHEMA,
            max_output_tokens=2000,
            temperature=0.2
        )
        
        # Send request and parse response
        result = await responses_client.create_with_retry(body)
        
        logger.info("Completed Stage 4: Synthesis")
        return result
    
    def _convert_stage1_to_trace_analysis(self, trace_id: str) -> TraceAnalysis:
        """Convert Stage 1 result to TraceAnalysis format."""
        
        if not self._stage1_result:
            raise ValueError("Stage 1 result not available")
        
        # Extract execution summary from timeline
        timeline = self._stage1_result.get("timeline", [])
        execution_summary = f"Analyzed {len(timeline)} runs in execution trace"
        
        # Extract issues from events
        events = self._stage1_result.get("events", [])
        issues = []
        for event in events:
            if event.get("impact") in ["critical", "high"]:
                issues.append(event.get("description", "Unknown issue"))
        
        return TraceAnalysis(
            trace_id=trace_id,
            execution_flow=execution_summary,
            context_at_each_step={"timeline": timeline, "events": events},
            data_transformations=[],
            error_propagation_path=issues,
            identified_issues=issues
        )
    
    def _convert_stage2_to_gap_analysis(self) -> GapAnalysis:
        """Convert Stage 2 result to GapAnalysis format."""
        
        if not self._stage2_result:
            raise ValueError("Stage 2 result not available")
        
        gaps = self._stage2_result.get("gaps", [])
        
        behavioral_differences = []
        missing_context = []
        
        for gap in gaps:
            status = gap.get("status", "")
            if status in ["missing", "incorrect"]:
                diff = f"{gap.get('expectation_clause', 'Unknown')}: {gap.get('actual_behavior', 'Unknown')}"
                behavioral_differences.append(diff)
            if status == "missing":
                missing_context.append(gap.get("expectation_clause", "Unknown"))
        
        return GapAnalysis(
            behavioral_differences=behavioral_differences,
            missing_context=missing_context,
            incorrect_assumptions=[],
            suggested_focus_areas=behavioral_differences[:5]  # Top 5
        )
    
    def _convert_stage3_to_diagnosis(self) -> Diagnosis:
        """Convert Stage 3 result to Diagnosis format."""
        
        if not self._stage3_result:
            raise ValueError("Stage 3 result not available")
        
        causes = self._stage3_result.get("causes", [])
        confidence_data = self._stage3_result.get("confidence", {})
        
        # Get primary cause
        primary_cause = causes[0] if causes else {"hypothesis": "Unknown failure", "category": "unknown"}
        
        # Map category to failure type
        category_map = {
            "prompt_engineering": FailureType.PROMPT_ISSUE,
            "data_quality": FailureType.CONTEXT_ISSUE,
            "model_limitation": FailureType.MODEL_LIMITATION,
            "evaluation_design": FailureType.CONTEXT_ISSUE,
            "system_integration": FailureType.ORCHESTRATION_ISSUE
        }
        
        failure_type = category_map.get(
            primary_cause.get("category", "unknown"), 
            FailureType.CONTEXT_ISSUE
        )
        
        # Map confidence
        confidence_str = confidence_data.get("overall", "medium")
        confidence_map = {
            "very_high": Confidence.HIGH,
            "high": Confidence.HIGH, 
            "medium": Confidence.MEDIUM,
            "low": Confidence.LOW,
            "very_low": Confidence.LOW
        }
        confidence = confidence_map.get(confidence_str, Confidence.MEDIUM)
        
        # Extract evidence from causes
        evidence = []
        for cause in causes[:3]:  # Top 3 causes as evidence
            evidence.append(cause.get("hypothesis", "Unknown"))
        
        return Diagnosis(
            failure_type=failure_type,
            root_cause=primary_cause.get("hypothesis", "Unknown root cause"),
            evidence=evidence,
            affected_components=[],
            confidence=confidence,
            detailed_analysis=primary_cause.get("hypothesis", "Unknown root cause")
        )
    
    def __del__(self):
        """Cleanup vector store on destruction."""
        if hasattr(self, '_vector_store_id') and self._vector_store_id:
            try:
                self.vector_store_manager.cleanup_vector_store(self._vector_store_id)
            except Exception as e:
                logger.warning(f"Failed to cleanup vector store: {str(e)}")