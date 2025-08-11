"""
Holistic analysis templates and schemas for single-shot batch processing.
"""

# JSON Schema for structured holistic analysis output
HOLISTIC_ANALYSIS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "trace_analysis": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "execution_summary": {"type": "string"},
                "key_issues": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["execution_summary", "key_issues"]
        },
        "gap_analysis": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "behavioral_differences": {"type": "array", "items": {"type": "string"}},
                "missing_context": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["behavioral_differences", "missing_context"]
        },
        "diagnosis": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "failure_type": {"type": "string"},
                "root_cause": {"type": "string"},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]}
            },
            "required": ["failure_type", "root_cause", "confidence"]
        },
        "executive_summary": {"type": "string"}
    },
    "required": ["trace_analysis", "gap_analysis", "diagnosis", "executive_summary"]
}


# Holistic analysis prompt template using Jinja2
HOLISTIC_ANALYSIS_TEMPLATE = """
You will perform a comprehensive 3-section analysis of this AI agent failure using the attached trace data.

=== ANALYSIS TASK ===

Expected Behavior: {{ expected_behavior }}
{% if business_context %}
Business Context: {{ business_context }}
{% endif %}

{% if specific_issues %}
Specific Issues Reported:
{% for issue in specific_issues %}
- {{ issue }}
{% endfor %}
{% endif %}

The complete trace data with ALL runs (no truncation) and agent context files is attached as a file.

=== SECTION 1: TRACE ANALYSIS ===

Analyze the execution trace systematically:
1. Map the execution flow - what was the agent trying to accomplish?
2. For each step, analyze what context was available vs needed  
3. Track data transformations - how did inputs become outputs?
4. If there were errors, trace how they propagated
5. Identify any issues or anomalies in execution

=== SECTION 2: GAP ANALYSIS ===

Compare actual behavior to expected behavior:
1. What are the key differences between expected and actual outcomes?
2. What context or information was missing that could have helped?
3. What incorrect assumptions did the agent make?
4. What specific areas should we focus on for improvement?

=== SECTION 3: DIAGNOSIS ===

Provide root cause diagnosis:
1. Categorize the failure type (context_issue, model_limitation, orchestration_issue, etc.)
2. Identify the fundamental reason for failure
3. List specific evidence supporting your diagnosis
4. Assess confidence level realistically
5. Provide detailed analysis explaining the failure

=== CLEAR SEPARATORS ===
Use the attached file data to inform all sections. The file contains:
- Complete trace metadata
- ALL execution runs with full inputs/outputs (no truncation)
- Agent prompt files (if provided)
- Agent evaluation files (if provided) 
- Expectation details

=== OUTPUT REQUIREMENTS ===

Return ONLY valid JSON matching the exact schema provided. Include:
- trace_analysis: Complete execution analysis
- gap_analysis: Expected vs actual comparison
- diagnosis: Root cause with evidence
- executive_summary: 2-3 sentence business-friendly summary

Focus on evidence-based analysis grounded in the trace data. Quote specific run inputs/outputs to support findings.
"""