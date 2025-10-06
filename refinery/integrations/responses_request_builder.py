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
    seed: Optional[int] = None,
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
        }
    }

    if temperature is not None and _supports_temperature(model):
        body["temperature"] = temperature
    
    # Add reasoning configuration when provided
    if reasoning_effort and _supports_reasoning(model):
        body["reasoning"] = {"effort": reasoning_effort}

    if max_output_tokens is not None and _supports_max_output_tokens(model):
        body["max_output_tokens"] = max_output_tokens

    if seed is not None and _supports_seed(model):
        body["seed"] = seed
    
    return body


def build_responses_body_no_tools(
    model: str,
    system_text: str,
    user_text: str,
    json_schema_obj: Dict[str, Any],
    max_output_tokens: int = 1000,
    temperature: float = 0.2,
    reasoning_effort: Optional[str] = None,
    seed: Optional[int] = None,
    strict: bool = True,
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
        strict: Enable strict JSON schema validation (default True, disable to avoid GPT-5 bugs)

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
                "strict": strict,
                "schema": json_schema_obj
            }
        }
    }

    if temperature is not None and _supports_temperature(model):
        body["temperature"] = temperature
    
    # Add reasoning configuration when provided
    if reasoning_effort and _supports_reasoning(model):
        body["reasoning"] = {"effort": reasoning_effort}

    if max_output_tokens is not None and _supports_max_output_tokens(model):
        body["max_output_tokens"] = max_output_tokens

    if seed is not None and _supports_seed(model):
        body["seed"] = seed

    return body


def _supports_reasoning(model: str) -> bool:
    """Return True if the model supports reasoning configuration."""
    return "gpt-5" in model.lower()


def _supports_temperature(model: str) -> bool:
    """Return True if the model supports temperature parameter."""
    return "gpt-5" not in model.lower()


def _supports_max_output_tokens(model: str) -> bool:
    """Return True if the model accepts max_output_tokens."""
    return True


def _supports_seed(model: str) -> bool:
    """Return True if the model accepts deterministic seed parameter."""
    return "gpt-5" not in model.lower()


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
