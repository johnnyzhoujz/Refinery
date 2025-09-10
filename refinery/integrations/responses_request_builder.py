"""
Request builder for OpenAI Responses API.

This module constructs proper request bodies for the Interactive Responses API
with Vector Store + File Search integration.
"""

from typing import Dict, Any, List, Optional


def build_responses_body(
    model: str,
    vector_store_id: str,
    system_text: str,
    user_text: str,
    json_schema_obj: Dict[str, Any],
    max_num_results: int = 8,
    max_output_tokens: int = 1000,
    temperature: float = 0.2,
    reasoning_effort: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a complete request body for OpenAI Responses API.
    
    Args:
        model: Model to use (e.g., "gpt-4o")
        vector_store_id: ID of the vector store containing files
        system_text: System prompt (unchanged from existing prompts)
        user_text: User prompt (unchanged from existing stage prompts)
        json_schema_obj: JSON schema for structured output (must have type: "object")
        max_num_results: Max results per file search retrieval
        max_output_tokens: Max tokens in response
        temperature: Model temperature
        reasoning_effort: Reasoning effort for GPT-5 models (minimal, low, medium, high)
    
    Returns:
        Complete request body for /v1/responses endpoint
    """
    
    # Validate schema has root type object
    if not json_schema_obj.get("type") == "object":
        raise ValueError("Schema must have root type: 'object'")
    
    body = {
        "model": model,
        "tools": [
            {
                "type": "file_search",
                "vector_store_ids": [vector_store_id],
                "max_num_results": max_num_results
            }
        ],
        "input": [
            {
                "type": "message",
                "role": "system",
                "content": [
                    {"type": "input_text", "text": system_text}
                ]
            },
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_text}
                ]
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "stage_output",
                "strict": True,
                "schema": json_schema_obj  # MUST be {"type": "object", ...}
            }
        },
        "temperature": temperature,
        "max_output_tokens": max_output_tokens
    }
    
    # Add reasoning_effort for GPT-5 models
    if "gpt-5" in model.lower() and reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    
    return body


def build_responses_body_no_tools(
    model: str,
    system_text: str,
    user_text: str,
    json_schema_obj: Dict[str, Any],
    max_output_tokens: int = 1000,
    temperature: float = 0.2,
    reasoning_effort: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Build a request body without file_search tools (for Stage 4 synthesis).
    
    Args:
        model: Model to use (e.g., "gpt-4o")
        system_text: System prompt
        user_text: User prompt with all context included
        json_schema_obj: JSON schema for structured output
        max_output_tokens: Max tokens in response
        temperature: Model temperature
        reasoning_effort: Reasoning effort for GPT-5 models (minimal, low, medium, high)
    
    Returns:
        Complete request body for /v1/responses endpoint without tools
    """
    
    # Validate schema has root type object
    if not json_schema_obj.get("type") == "object":
        raise ValueError("Schema must have root type: 'object'")
    
    body = {
        "model": model,
        "input": [
            {
                "type": "message",
                "role": "system",
                "content": [
                    {"type": "input_text", "text": system_text}
                ]
            },
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": user_text}
                ]
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "stage_output",
                "strict": True,
                "schema": json_schema_obj
            }
        },
        "temperature": temperature,
        "max_output_tokens": max_output_tokens
    }
    
    # Add reasoning_effort for GPT-5 models
    if "gpt-5" in model.lower() and reasoning_effort:
        body["reasoning_effort"] = reasoning_effort
    
    return body


def build_canary_test_body() -> Dict[str, Any]:
    """
    Build a minimal canary test request to validate API connectivity.
    
    Returns:
        Minimal request body for basic connectivity test
    """
    return {
        "model": "gpt-4o",
        "input": [
            {
                "type": "message",
                "role": "user", 
                "content": [
                    {"type": "input_text", "text": "Reply PONG"}
                ]
            }
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "check",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "response": {"type": "string"}
                    },
                    "required": ["response"],
                    "additionalProperties": False
                }
            }
        }
    }