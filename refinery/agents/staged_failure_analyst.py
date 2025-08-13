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
import time
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
        """Run Stage 1: Trace Analysis using chunked approach for large traces."""
        
        logger.info(f"Starting staged trace analysis for trace {trace.trace_id}")
        
        # Determine if we need chunking based on trace size
        total_runs = len(trace.runs)
        chunked_config = config.chunked_analysis
        use_chunking = (total_runs > chunked_config.chunking_threshold and 
                       not chunked_config.disable_chunking)
        
        if use_chunking:
            num_groups = (total_runs + chunked_config.group_size_runs - 1) // chunked_config.group_size_runs
            logger.info(f"Large trace detected ({total_runs} runs > {chunked_config.chunking_threshold}), "
                       f"using chunked analysis with {num_groups} groups")
            
            # Create vector store with chunked files for large traces
            self._vector_store_id = await self.vector_store_manager.create_single_store_with_all_files(
                trace, expectation, prompt_contents or {}, eval_contents or {}, 
                group_size=chunked_config.group_size_runs
            )
            
            # Run chunked Stage 1
            self._stage1_result = await self._run_stage1_chunked(num_groups)
        else:
            logger.info(f"Small trace ({total_runs} runs <= {chunked_config.chunking_threshold}), "
                       f"using standard analysis")
            
            # Original single-call approach for small traces
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
    
    async def _run_stage1_chunked(self, num_groups: int) -> Dict[str, Any]:
        """
        Run Stage 1 in groups to avoid TPM limits.
        
        Args:
            num_groups: Number of groups to process
            
        Returns:
            Merged Stage 1 results from all groups
        """
        logger.info(f"Running Stage 1: Chunked Analysis with {num_groups} groups")
        
        partials = []  # consistent variable naming
        tokens_window = []  # list of (timestamp, total_tokens) for simple TPM tracking
        chunked_config = config.chunked_analysis
        
        for group_idx in range(num_groups):
            group_id = f"g{group_idx + 1:02d}"
            
            # User message with scope line
            user_message = f"""Scope: ONLY consider files whose *filename begins with* "{group_id}_". Ignore any file not matching this prefix.

{STAGE1_TRACE_ANALYSIS_PROMPT}"""
            
            # TPM budgeting - before call
            now_ts = time.time()
            tokens_window = [(ts, t) for ts, t in tokens_window if now_ts - ts < 60]
            tokens_in_60 = sum(t for _, t in tokens_window)
            est_next = 12000 if chunked_config.max_num_results_stage1 == 2 else 15000
            
            tpm_threshold = chunked_config.tpm_limit - chunked_config.tpm_buffer
            if tokens_in_60 + est_next > tpm_threshold:
                wait = 60 - (now_ts - min(ts for ts, _ in tokens_window))
                logger.info(f"TPM limit approaching, waiting {wait:.1f}s before group {group_idx + 1}")
                await asyncio.sleep(max(0, wait))
            
            # Build request body - spec-compliant format
            body = {
                "model": self.model,
                "tools": [
                    {
                        "type": "file_search",
                        "vector_store_ids": [self._vector_store_id],
                        "max_num_results": chunked_config.max_num_results_stage1  # e.g., 2
                    }
                ],
                "input": [
                    { "type": "message",
                      "role": "system",
                      "content": [ { "type": "input_text", "text": FAILURE_ANALYST_SYSTEM_PROMPT_V3 } ] },
                    { "type": "message", 
                      "role": "user",
                      "content": [ { "type": "input_text", "text": user_message } ] }
                ],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "stage1_output", 
                        "strict": True,
                        "schema": TRACE_ANALYSIS_SCHEMA     # root {"type":"object", ...}
                    }
                },
                "temperature": chunked_config.temperature,
                "max_output_tokens": chunked_config.max_output_tokens_stage1
            }
            
            # Make API call with retry logic
            try:
                for retry_attempt in range(2):  # 2 retries per group
                    try:
                        resp = await responses_client.create(body)
                        data, usage_total = responses_client.parse_json_and_usage(resp)
                        partials.append(data)
                        
                        # TPM budgeting - after call
                        ts_after = time.time()
                        actual = usage_total or est_next
                        tokens_window = [(ts, t) for ts, t in tokens_window if ts_after - ts < 60]
                        tokens_window.append((ts_after, actual))
                        
                        logger.info(f"Completed Stage 1 Group {group_idx + 1}/{num_groups}: "
                                  f"Found {len(data.get('timeline', []))} timeline items, "
                                  f"used {actual} tokens")
                        break  # Success, exit retry loop
                        
                    except Exception as e:
                        if retry_attempt == 0 and "rate" in str(e).lower():
                            logger.warning(f"Rate limit on group {group_idx + 1}, retrying in 30s")
                            await asyncio.sleep(30)
                        else:
                            raise
                            
            except Exception as e:
                logger.error(f"Failed Stage 1 Group {group_idx + 1}: {str(e)}")
                # POC level: continue with minimal placeholder
                partials.append({"timeline": [], "events": [], "evidence": []})
            
            # Sleep between groups to smooth TPM usage (except after last group)
            if group_idx < num_groups - 1:
                sleep_time = chunked_config.inter_group_sleep_s
                logger.info(f"Chunked analysis progress: {group_idx + 1}/{num_groups} groups completed, "
                          f"sleeping {sleep_time}s before next group...")
                await asyncio.sleep(sleep_time)
        
        # Merge partial results
        logger.info("Merging Stage 1 partial results...")
        merged_result = self._merge_stage1_results(partials)
        
        logger.info(f"Completed Stage 1 Chunked Analysis: "
                   f"Merged {len(merged_result.get('timeline', []))} total timeline items")
        return merged_result
    
    def _merge_stage1_results(self, partials: list[dict]) -> dict:
        """
        Merge partial Stage 1 results from chunked analysis.
        
        Args:
            partials: List of partial Stage 1 results from each group
            
        Returns:
            Merged Stage 1 result dictionary
        """
        logger.debug(f"Merging {len(partials)} partial Stage 1 results")
        
        merged = {"timeline": [], "events": [], "evidence": []}
        
        for group_idx, result in enumerate(partials):
            timeline = result.get("timeline", [])
            events = result.get("events", [])
            evidence = result.get("evidence", [])
            
            # Add merge metadata for sorting
            for idx, item in enumerate(timeline):
                item.setdefault("_merge_group_index", group_idx)
                item.setdefault("_merge_order", idx)
            
            for idx, item in enumerate(events):
                item.setdefault("_merge_group_index", group_idx)
                item.setdefault("_merge_order", idx)
                
            for idx, item in enumerate(evidence):
                if isinstance(item, dict):
                    item.setdefault("_merge_group_index", group_idx)
                    item.setdefault("_merge_order", idx)
            
            # Extend merged lists
            merged["timeline"].extend(timeline)
            merged["events"].extend(events)
            merged["evidence"].extend(evidence)
            
            logger.debug(f"Group {group_idx + 1}: Added {len(timeline)} timeline, "
                       f"{len(events)} events, {len(evidence)} evidence items")
        
        # Sort timeline by timestamp, then by (group_index, order) for deterministic ordering
        def sort_key(item):
            timestamp = item.get("timestamp")
            if timestamp:
                return timestamp
            else:
                # Fallback to group and order for items without timestamps
                return (item.get("_merge_group_index", 0), item.get("_merge_order", 0))
        
        merged["timeline"].sort(key=sort_key)
        
        # Sort events by severity/impact, then by group order
        def event_sort_key(item):
            impact_priority = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            impact = item.get("impact", "low")
            priority = impact_priority.get(impact, 3)
            return (priority, item.get("_merge_group_index", 0), item.get("_merge_order", 0))
        
        merged["events"].sort(key=event_sort_key)
        
        # Remove merge metadata from final result (optional - keeps result clean)
        for item in merged["timeline"]:
            item.pop("_merge_group_index", None)
            item.pop("_merge_order", None)
        
        for item in merged["events"]:
            item.pop("_merge_group_index", None)
            item.pop("_merge_order", None)
            
        for item in merged["evidence"]:
            if isinstance(item, dict):
                item.pop("_merge_group_index", None)
                item.pop("_merge_order", None)
        
        logger.info(f"Merge complete: {len(merged['timeline'])} timeline items, "
                   f"{len(merged['events'])} events, {len(merged['evidence'])} evidence items")
        
        return merged
    
    async def _run_stage2_interactive(self) -> Dict[str, Any]:
        """Run Stage 2: Gap Analysis with reduced retrieval for chunked compatibility."""
        
        logger.info("Running Stage 2: Gap Analysis (Interactive)")
        
        # Format Stage 2 prompt with Stage 1 results
        user_prompt = STAGE2_GAP_ANALYSIS_PROMPT.format(
            stage1_json=json.dumps(self._stage1_result, indent=2)
        )
        
        # Use chunked analysis configuration for consistent limits
        chunked_config = config.chunked_analysis
        
        # Build request body with V3 system prompt and reduced limits
        body = build_responses_body(
            model=self.model,
            vector_store_id=self._vector_store_id,
            system_text=FAILURE_ANALYST_SYSTEM_PROMPT_V3,
            user_text=user_prompt,
            json_schema_obj=GAP_ANALYSIS_SCHEMA,
            max_num_results=chunked_config.max_num_results_other,  # 3 instead of 8
            max_output_tokens=chunked_config.max_output_tokens_other,  # 1000 instead of 2000
            temperature=chunked_config.temperature  # 0.2
        )
        
        # Send request and parse response
        result = await responses_client.create_with_retry(body)
        
        logger.info("Completed Stage 2: Gap Analysis")
        return result
    
    async def _run_stage3_interactive(self) -> Dict[str, Any]:
        """Run Stage 3: Diagnosis with reduced retrieval for chunked compatibility."""
        
        logger.info("Running Stage 3: Diagnosis (Interactive)")
        
        # Format Stage 3 prompt with previous results
        user_prompt = STAGE3_DIAGNOSIS_PROMPT.format(
            stage1_json=json.dumps(self._stage1_result, indent=2),
            stage2_json=json.dumps(self._stage2_result, indent=2)
        )
        
        # Use chunked analysis configuration for consistent limits
        chunked_config = config.chunked_analysis
        
        # Build request body with V3 system prompt and reduced limits
        body = build_responses_body(
            model=self.model,
            vector_store_id=self._vector_store_id,
            system_text=FAILURE_ANALYST_SYSTEM_PROMPT_V3,
            user_text=user_prompt,
            json_schema_obj=DIAGNOSIS_SCHEMA,
            max_num_results=chunked_config.max_num_results_other,  # 3 instead of 8
            max_output_tokens=chunked_config.max_output_tokens_other + 200,  # 1200 instead of 2500
            temperature=chunked_config.temperature  # 0.2
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
        
        # Extract actual coverage data from Stage 1
        timeline = self._stage1_result.get("timeline", [])
        coverage = self._stage1_result.get("coverage", {})
        
        # Use actual runs analyzed from coverage, fallback to timeline length
        runs_analyzed = coverage.get("runs_analyzed", [])
        actual_runs_count = len(runs_analyzed) if runs_analyzed else len(timeline)
        
        execution_summary = f"Analyzed {actual_runs_count} runs in execution trace"
        
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
        
        # Preserve remediations from Stage 3
        remediations = self._stage3_result.get("remediations", [])
        
        # Preserve actions and findings from Stage 4
        next_actions = []
        top_findings = []
        if self._stage4_result:
            next_actions = self._stage4_result.get("actions_next", [])
            top_findings = self._stage4_result.get("top_findings", [])
        
        return Diagnosis(
            failure_type=failure_type,
            root_cause=primary_cause.get("hypothesis", "Unknown root cause"),
            evidence=evidence,
            affected_components=[],
            confidence=confidence,
            detailed_analysis=primary_cause.get("hypothesis", "Unknown root cause"),
            remediations=remediations,
            next_actions=next_actions,
            top_findings=top_findings
        )
    
    def __del__(self):
        """Cleanup vector store on destruction."""
        if hasattr(self, '_vector_store_id') and self._vector_store_id:
            try:
                self.vector_store_manager.cleanup_vector_store(self._vector_store_id)
            except Exception as e:
                logger.warning(f"Failed to cleanup vector store: {str(e)}")