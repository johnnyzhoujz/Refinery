"""
Schemas for the staged analysis approach using Vector Store + File Search.

Each stage produces structured JSON that feeds into the next stage.
"""

# Stage 1: Trace Analysis Schema
TRACE_ANALYSIS_SCHEMA = {
    "type": "object",
    "title": "TraceAnalysisResult",
    "additionalProperties": False,
    "properties": {
        "timeline": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "sequence": {"type": "integer"},
                    "run_id": {"type": "string"},
                    "run_name": {"type": "string"},
                    "action": {"type": "string"},
                    "duration_ms": {"type": "number"},
                    "status": {"type": "string", "enum": ["success", "error", "partial"]},
                    "citations": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["sequence", "run_id", "run_name", "action", "duration_ms", "status", "citations"]
            }
        },
        "events": {
            "type": "array", 
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "event_type": {"type": "string", "enum": ["error", "warning", "milestone", "decision_point"]},
                    "run_id": {"type": "string"},
                    "description": {"type": "string"},
                    "impact": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "citations": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["event_type", "run_id", "description", "impact", "citations"]
            }
        },
        "coverage": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "files_scanned": {"type": "array", "items": {"type": "string"}},
                "runs_analyzed": {"type": "array", "items": {"type": "string"}},
                "remaining": {"type": "array", "items": {"type": "string"}},
                "completion_percentage": {"type": "number"}
            },
            "required": ["files_scanned", "runs_analyzed", "remaining", "completion_percentage"]
        },
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "evidence_id": {"type": "string"},
                    "type": {"type": "string", "enum": ["input", "output", "error", "decision", "context"]},
                    "run_id": {"type": "string"},
                    "content_summary": {"type": "string"},
                    "citations": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["evidence_id", "type", "run_id", "content_summary", "citations"]
            }
        }
    },
    "required": ["timeline", "events", "coverage", "evidence"]
}

# Stage 2: Gap Analysis Schema  
GAP_ANALYSIS_SCHEMA = {
    "type": "object",
    "title": "GapAnalysisResult", 
    "additionalProperties": False,
    "properties": {
        "gaps": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "gap_id": {"type": "string"},
                    "expectation_clause": {"type": "string"},
                    "actual_behavior": {"type": "string"},
                    "expected_behavior": {"type": "string"},
                    "status": {"type": "string", "enum": ["met", "partial", "missing", "incorrect"]},
                    "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "citations": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["gap_id", "expectation_clause", "actual_behavior", "expected_behavior", "status", "severity", "evidence", "citations"]
            }
        },
        "metrics": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "expectations_met": {"type": "integer"},
                "expectations_missed": {"type": "integer"},
                "critical_gaps": {"type": "integer"},
                "success_rate": {"type": "number"}
            },
            "required": ["expectations_met", "expectations_missed", "critical_gaps", "success_rate"]
        },
        "coverage": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "eval_files_analyzed": {"type": "array", "items": {"type": "string"}},
                "trace_sections_referenced": {"type": "array", "items": {"type": "string"}},
                "additional_retrievals": {"type": "array", "items": {"type": "string"}}
            },
            "required": ["eval_files_analyzed", "trace_sections_referenced", "additional_retrievals"]
        }
    },
    "required": ["gaps", "metrics", "coverage"]
}

# Stage 3: Diagnosis Schema
DIAGNOSIS_SCHEMA = {
    "type": "object",
    "title": "DiagnosisResult", 
    "additionalProperties": False,
    "properties": {
        "causes": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "cause_id": {"type": "string"},
                    "hypothesis": {"type": "string"},
                    "likelihood": {"type": "string", "enum": ["very_high", "high", "medium", "low", "very_low"]},
                    "category": {"type": "string", "enum": ["prompt_engineering", "data_quality", "model_limitation", "evaluation_design", "system_integration"]},
                    "chain_of_evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "step": {"type": "integer"},
                                "observation": {"type": "string"},
                                "citation": {"type": "string"}
                            },
                            "required": ["step", "observation", "citation"]
                        }
                    },
                    "supporting_gaps": {"type": "array", "items": {"type": "string"}},
                    "supporting_events": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["cause_id", "hypothesis", "likelihood", "category", "chain_of_evidence", "supporting_gaps", "supporting_events"]
            }
        },
        "remediations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "remediation_id": {"type": "string"},
                    "target_cause": {"type": "string"},
                    "action": {"type": "string"},
                    "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "effort_estimate": {"type": "string", "enum": ["trivial", "small", "medium", "large", "extensive"]},
                    "expected_impact": {"type": "string"}
                },
                "required": ["remediation_id", "target_cause", "action", "priority", "effort_estimate", "expected_impact"]
            }
        },
        "confidence": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "overall": {"type": "string", "enum": ["very_high", "high", "medium", "low", "very_low"]},
                "primary_cause_confidence": {"type": "string", "enum": ["very_high", "high", "medium", "low", "very_low"]},
                "data_quality": {"type": "string", "enum": ["excellent", "good", "fair", "poor"]},
                "coverage_completeness": {"type": "number"}
            },
            "required": ["overall", "primary_cause_confidence", "data_quality", "coverage_completeness"]
        }
    },
    "required": ["causes", "remediations", "confidence"]
}

# Stage 4: Synthesis Schema
SYNTHESIS_SCHEMA = {
    "type": "object",
    "title": "SynthesisResult",
    "additionalProperties": False, 
    "properties": {
        "summary": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "executive_summary": {"type": "string"},
                "problem_statement": {"type": "string"},
                "business_impact": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                "time_to_resolution": {"type": "string", "enum": ["immediate", "hours", "days", "weeks"]}
            },
            "required": ["executive_summary", "problem_statement", "business_impact", "time_to_resolution"]
        },
        "top_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "finding": {"type": "string"},
                    "supporting_cause_ids": {"type": "array", "items": {"type": "string"}},
                    "supporting_gap_ids": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "string", "enum": ["very_high", "high", "medium", "low", "very_low"]}
                },
                "required": ["finding", "supporting_cause_ids", "supporting_gap_ids", "confidence"]
            }
        },
        "actions_next": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "action": {"type": "string"},
                    "priority": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
                    "owner": {"type": "string", "enum": ["domain_expert", "engineer", "product_manager", "team"]},
                    "timeline": {"type": "string"},
                    "success_criteria": {"type": "string"}
                },
                "required": ["action", "priority", "owner", "timeline", "success_criteria"]
            }
        },
        "metrics": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "analysis_duration": {"type": "string"},
                "confidence_score": {"type": "number"},
                "actionable_recommendations": {"type": "integer"},
                "critical_issues": {"type": "integer"}
            },
            "required": ["analysis_duration", "confidence_score", "actionable_recommendations", "critical_issues"]
        }
    },
    "required": ["summary", "top_findings", "actions_next", "metrics"]
}