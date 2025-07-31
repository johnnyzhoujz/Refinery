"""
Implementation of the FailureAnalyst interface for analyzing AI agent failures.

This module provides advanced analysis capabilities for understanding why AI agents fail,
using chain-of-thought reasoning and structured outputs.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from jinja2 import Template

from ..core.interfaces import FailureAnalyst
from ..core.models import (
    Trace, TraceRun, TraceAnalysis, GapAnalysis, Diagnosis,
    DomainExpertExpectation, FailureType, Confidence
)
from ..utils.llm_provider import get_llm_provider
from ..utils.config import config

logger = logging.getLogger(__name__)


class AdvancedFailureAnalyst(FailureAnalyst):
    """Advanced implementation of FailureAnalyst using LLM-powered analysis."""
    
    def __init__(self):
        self.llm = get_llm_provider(config)
        
    async def analyze_trace(
        self, 
        trace: Trace,
        expectation: DomainExpertExpectation
    ) -> TraceAnalysis:
        """Analyze a trace and break down what happened."""
        logger.info(f"Analyzing trace {trace.trace_id}")
        
        # Use the tool function to extract structured trace breakdown
        trace_breakdown = await self._extract_trace_breakdown(trace, expectation)
        
        return TraceAnalysis(
            trace_id=trace.trace_id,
            execution_flow=trace_breakdown["execution_flow"],
            context_at_each_step=trace_breakdown["context_at_each_step"],
            data_transformations=trace_breakdown["data_transformations"],
            error_propagation_path=trace_breakdown.get("error_propagation_path"),
            identified_issues=trace_breakdown.get("identified_issues", [])
        )
    
    async def compare_to_expected(
        self,
        analysis: TraceAnalysis,
        expectation: DomainExpertExpectation
    ) -> GapAnalysis:
        """Compare actual behavior to expected behavior."""
        logger.info(f"Comparing trace {analysis.trace_id} to expected behavior")
        
        # Use the tool function for gap analysis
        gap_analysis = await self._compare_to_expected_tool(analysis, expectation)
        
        return GapAnalysis(
            behavioral_differences=gap_analysis["behavioral_differences"],
            missing_context=gap_analysis["missing_context"],
            incorrect_assumptions=gap_analysis["incorrect_assumptions"],
            suggested_focus_areas=gap_analysis["suggested_focus_areas"]
        )
    
    async def diagnose_failure(
        self,
        trace_analysis: TraceAnalysis,
        gap_analysis: GapAnalysis
    ) -> Diagnosis:
        """Provide a root cause diagnosis."""
        logger.info(f"Diagnosing failure for trace {trace_analysis.trace_id}")
        
        prompt = self._build_diagnosis_prompt(trace_analysis, gap_analysis)
        
        # Print the exact prompt and system prompt used
        print("\n" + "="*80)
        print("DIAGNOSIS SYSTEM PROMPT:")
        print("="*80)
        print(DIAGNOSIS_SYSTEM_PROMPT)
        print("\n" + "="*80)
        print("DIAGNOSIS USER PROMPT:")
        print("="*80)
        print(prompt)
        print("="*80)
        
        diagnosis_response = await self.llm.complete(
            prompt=prompt,
            system_prompt=DIAGNOSIS_SYSTEM_PROMPT,
            temperature=0.2,  # Lower temperature for more consistent analysis
            max_tokens=2000
        )
        
        # Print the raw response
        print("\n" + "="*80)
        print("RAW DIAGNOSIS RESPONSE:")
        print("="*80)
        print(diagnosis_response)
        print("="*80)
        
        # Parse the structured response
        diagnosis_data = self._parse_diagnosis_response(diagnosis_response)
        
        return Diagnosis(
            failure_type=FailureType(diagnosis_data["failure_type"]),
            root_cause=diagnosis_data["root_cause"],
            evidence=diagnosis_data["evidence"],
            affected_components=diagnosis_data["affected_components"],
            confidence=Confidence(diagnosis_data["confidence"]),
            detailed_analysis=diagnosis_data["detailed_analysis"]
        )
    
    async def _extract_trace_breakdown(
        self, 
        trace: Trace,
        expectation: DomainExpertExpectation
    ) -> Dict[str, Any]:
        """Tool function to extract structured trace analysis."""
        prompt = self._build_trace_analysis_prompt(trace, expectation)
        
        response = await self.llm.complete(
            prompt=prompt,
            system_prompt=TRACE_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.1,  # Very low temperature for factual analysis
            max_tokens=3000
        )
        
        return self._parse_trace_analysis_response(response)
    
    async def _compare_to_expected_tool(
        self,
        analysis: TraceAnalysis,
        expectation: DomainExpertExpectation
    ) -> Dict[str, Any]:
        """Tool function to compare actual vs expected behavior."""
        prompt = self._build_gap_analysis_prompt(analysis, expectation)
        
        response = await self.llm.complete(
            prompt=prompt,
            system_prompt=GAP_ANALYSIS_SYSTEM_PROMPT,
            temperature=0.2,
            max_tokens=2000
        )
        
        return self._parse_gap_analysis_response(response)
    
    def _build_trace_analysis_prompt(
        self, 
        trace: Trace,
        expectation: DomainExpertExpectation
    ) -> str:
        """Build prompt for trace analysis using Jinja2 template."""
        template = Template(TRACE_ANALYSIS_PROMPT_TEMPLATE)
        
        # Prepare trace data for the template with aggressive truncation
        runs_data = []
        for run in trace.runs:
            # Truncate inputs/outputs for token management
            inputs_str = json.dumps(run.inputs)
            if len(inputs_str) > 500:
                inputs_str = inputs_str[:500] + "... [truncated]"
                
            outputs_str = "None"
            if run.outputs:
                outputs_str = json.dumps(run.outputs)
                if len(outputs_str) > 500:
                    outputs_str = outputs_str[:500] + "... [truncated]"
            
            runs_data.append({
                "id": run.id,
                "name": run.name,
                "type": run.run_type.value,
                "inputs": inputs_str,
                "outputs": outputs_str,
                "error": run.error,
                "duration_ms": run.duration_ms,
                "parent_id": run.parent_run_id,
                "dotted_order": run.dotted_order
            })
        
        return template.render(
            trace_id=trace.trace_id,
            runs=runs_data,
            expectation=expectation.description,
            business_context=expectation.business_context or "Not provided",
            specific_issues=expectation.specific_issues
        )
    
    def _build_gap_analysis_prompt(
        self,
        analysis: TraceAnalysis,
        expectation: DomainExpertExpectation
    ) -> str:
        """Build prompt for gap analysis."""
        template = Template(GAP_ANALYSIS_PROMPT_TEMPLATE)
        
        return template.render(
            trace_id=analysis.trace_id,
            execution_flow=json.dumps(analysis.execution_flow, indent=2),
            context_at_each_step=json.dumps(analysis.context_at_each_step, indent=2),
            data_transformations=json.dumps(analysis.data_transformations, indent=2),
            identified_issues=analysis.identified_issues,
            expected_description=expectation.description,
            expected_output=expectation.expected_output or "Not specified",
            business_context=expectation.business_context or "Not provided",
            specific_issues=expectation.specific_issues
        )
    
    def _build_diagnosis_prompt(
        self,
        trace_analysis: TraceAnalysis,
        gap_analysis: GapAnalysis
    ) -> str:
        """Build prompt for root cause diagnosis."""
        template = Template(DIAGNOSIS_PROMPT_TEMPLATE)
        
        return template.render(
            trace_id=trace_analysis.trace_id,
            execution_flow=json.dumps(trace_analysis.execution_flow, indent=2),
            identified_issues=trace_analysis.identified_issues,
            error_propagation_path=trace_analysis.error_propagation_path,
            behavioral_differences=gap_analysis.behavioral_differences,
            missing_context=gap_analysis.missing_context,
            incorrect_assumptions=gap_analysis.incorrect_assumptions,
            suggested_focus_areas=gap_analysis.suggested_focus_areas
        )
    
    def _parse_trace_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse the structured trace analysis response."""
        try:
            # Extract JSON from the response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            json_str = response[json_start:json_end]
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to parse trace analysis response: {e}")
            # Return a fallback structure
            return {
                "execution_flow": [],
                "context_at_each_step": {},
                "data_transformations": [],
                "error_propagation_path": None,
                "identified_issues": [{"issue": "Failed to parse analysis", "severity": "high"}]
            }
    
    def _parse_gap_analysis_response(self, response: str) -> Dict[str, Any]:
        """Parse the structured gap analysis response."""
        try:
            # Extract JSON from the response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            json_str = response[json_start:json_end]
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Failed to parse gap analysis response: {e}")
            # Return a fallback structure
            return {
                "behavioral_differences": ["Unable to parse gap analysis"],
                "missing_context": [],
                "incorrect_assumptions": [],
                "suggested_focus_areas": ["Review analysis parsing"]
            }
    
    def _parse_diagnosis_response(self, response: str) -> Dict[str, Any]:
        """Parse the structured diagnosis response."""
        try:
            # Extract JSON from the response
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            # Validate and normalize the response
            valid_failure_types = [ft.value for ft in FailureType]
            if data["failure_type"] not in valid_failure_types:
                data["failure_type"] = FailureType.ORCHESTRATION_ISSUE.value
            
            valid_confidence_levels = [c.value for c in Confidence]
            if data["confidence"] not in valid_confidence_levels:
                data["confidence"] = Confidence.MEDIUM.value
            
            return data
        except Exception as e:
            logger.error(f"Failed to parse diagnosis response: {e}")
            # Return a fallback diagnosis
            return {
                "failure_type": FailureType.ORCHESTRATION_ISSUE.value,
                "root_cause": "Failed to parse diagnosis",
                "evidence": ["Analysis parsing error"],
                "affected_components": ["diagnosis_parser"],
                "confidence": Confidence.LOW.value,
                "detailed_analysis": f"Error parsing diagnosis: {str(e)}"
            }


# Prompt templates using advanced prompting strategies

TRACE_ANALYSIS_SYSTEM_PROMPT = """You are an expert AI agent failure analyst. Your task is to analyze execution traces and provide structured breakdowns of what happened during the agent's execution.

You specialize in:
- Understanding complex agent architectures and execution flows
- Identifying data transformations and context changes
- Detecting error propagation patterns
- Recognizing common failure patterns in AI systems

Always provide factual, evidence-based analysis grounded in the trace data."""

TRACE_ANALYSIS_PROMPT_TEMPLATE = """Task: Analyze this AI agent execution trace and provide a structured breakdown.

Trace ID: {{ trace_id }}

Expected Behavior:
{{ expectation }}

Business Context:
{{ business_context }}

{% if specific_issues %}
Specific Issues Reported:
{% for issue in specific_issues %}
- {{ issue }}
{% endfor %}
{% endif %}

Execution Trace:
{% for run in runs %}
=== Run: {{ run.name }} ({{ run.type }}) ===
ID: {{ run.id }}
Parent: {{ run.parent_id or "Root" }}
Order: {{ run.dotted_order }}
Duration: {{ run.duration_ms }}ms

Inputs:
{{ run.inputs }}

Outputs:
{{ run.outputs }}

{% if run.error %}
ERROR: {{ run.error }}
{% endif %}

{% endfor %}

Using chain-of-thought reasoning, analyze this trace step by step:

1. First, identify the overall execution flow - what was the agent trying to accomplish?
2. For each step, analyze what context was available and how it changed
3. Track data transformations - how did inputs become outputs?
4. If there were errors, trace how they propagated through the system
5. Identify any issues or anomalies in the execution

Provide your analysis in this JSON structure:
{
  "execution_flow": [
    {
      "step": 1,
      "run_id": "run_id",
      "action": "what happened",
      "purpose": "why it happened",
      "outcome": "success/failure/partial"
    }
  ],
  "context_at_each_step": {
    "run_id": {
      "available_context": ["list of context items"],
      "missing_context": ["what was needed but not available"],
      "context_usage": "how the context was used"
    }
  },
  "data_transformations": [
    {
      "from_run": "run_id",
      "to_run": "run_id",
      "transformation": "description of how data changed",
      "data_loss": "any information lost",
      "data_corruption": "any corruption detected"
    }
  ],
  "error_propagation_path": ["run_id1", "run_id2", "..."] or null,
  "identified_issues": [
    {
      "issue": "description",
      "severity": "high/medium/low",
      "affected_runs": ["run_ids"],
      "evidence": ["specific evidence from trace"]
    }
  ]
}"""

GAP_ANALYSIS_SYSTEM_PROMPT = """You are an expert at comparing actual AI agent behavior to expected behavior. Your task is to identify gaps, missing context, and incorrect assumptions that led to unexpected outcomes.

Focus on:
- Behavioral differences between expected and actual outcomes
- Missing information or context that could have changed the result
- Incorrect assumptions made by the agent
- Specific areas that need attention for improvement

Be precise and actionable in your analysis."""

DIAGNOSIS_SYSTEM_PROMPT = """You are an expert AI failure diagnostician. Your task is to provide root cause analysis for AI agent failures based on trace analysis and gap analysis.

Focus on:
- Identifying the fundamental reason for failure
- Categorizing the failure type accurately
- Providing specific evidence from the trace
- Assessing confidence levels realistically
- Giving actionable insights for fixes

Return structured JSON diagnosis."""

GAP_ANALYSIS_PROMPT_TEMPLATE = """Task: Compare the actual agent behavior to what was expected.

Trace ID: {{ trace_id }}

Expected Behavior:
Description: {{ expected_description }}
{% if expected_output %}
Expected Output: {{ expected_output }}
{% endif %}
Business Context: {{ business_context }}

{% if specific_issues %}
Specific Issues:
{% for issue in specific_issues %}
- {{ issue }}
{% endfor %}
{% endif %}

Actual Behavior Analysis:
Execution Flow:
{{ execution_flow }}

Context at Each Step:
{{ context_at_each_step }}

Data Transformations:
{{ data_transformations }}

{% if identified_issues %}
Identified Issues:
{% for issue in identified_issues %}
- {{ issue }}
{% endfor %}
{% endif %}

Using careful analysis, identify:

1. What are the key behavioral differences between expected and actual?
2. What context or information was missing that could have helped?
3. What incorrect assumptions did the agent make?
4. What specific areas should we focus on for improvement?

Provide your analysis in this JSON structure:
{
  "behavioral_differences": [
    "Clear description of each difference between expected and actual behavior"
  ],
  "missing_context": [
    "Information that was needed but not available to the agent"
  ],
  "incorrect_assumptions": [
    "Assumptions the agent made that turned out to be wrong"
  ],
  "suggested_focus_areas": [
    "Specific, actionable areas to investigate for fixes"
  ]
}"""

DIAGNOSIS_PROMPT_TEMPLATE = """Task: Provide a root cause diagnosis for this AI agent failure.

Trace ID: {{ trace_id }}

Execution Analysis:
{{ execution_flow }}

{% if identified_issues %}
Identified Issues:
{% for issue in identified_issues %}
- {{ issue }}
{% endfor %}
{% endif %}

{% if error_propagation_path %}
Error Propagation Path: {{ error_propagation_path }}
{% endif %}

Gap Analysis Results:
Behavioral Differences:
{% for diff in behavioral_differences %}
- {{ diff }}
{% endfor %}

Missing Context:
{% for context in missing_context %}
- {{ context }}
{% endfor %}

Incorrect Assumptions:
{% for assumption in incorrect_assumptions %}
- {{ assumption }}
{% endfor %}

Suggested Focus Areas:
{% for area in suggested_focus_areas %}
- {{ area }}
{% endfor %}

Based on this comprehensive analysis, diagnose the root cause:

1. First, categorize the failure type:
   - prompt_issue: Problems with prompt design or instructions
   - context_issue: Missing or incorrect context/information
   - model_limitation: Inherent model capability limitations
   - orchestration_issue: Problems with agent flow or architecture
   - retrieval_issue: RAG or data retrieval problems
   - output_parsing_issue: Problems parsing or formatting outputs

2. Identify the root cause - the fundamental reason for failure

3. List specific evidence supporting your diagnosis

4. Identify which components/systems were affected

5. Assess your confidence level (low/medium/high)

6. Provide a detailed analysis explaining the failure

Return your diagnosis in this JSON structure:
{
  "failure_type": "one of the categories above",
  "root_cause": "concise description of the fundamental issue",
  "evidence": [
    "specific evidence point 1",
    "specific evidence point 2"
  ],
  "affected_components": [
    "component/system names"
  ],
  "confidence": "low/medium/high",
  "detailed_analysis": "comprehensive explanation of the failure and its implications"
}"""