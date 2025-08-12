#!/usr/bin/env python3
"""
Quick token counter to see exactly how big our batch request is.
"""

import json
import tiktoken
from refinery.agents.staged_schemas import TRACE_ANALYSIS_SCHEMA

def count_tokens(text: str) -> int:
    """Count tokens using tiktoken (GPT-4 encoding)"""
    encoding = tiktoken.encoding_for_model("gpt-4o")
    return len(encoding.encode(text))

def main():
    print("=== TOKEN ANALYSIS FOR STAGED BATCH REQUEST ===")
    
    # System prompt
    system_prompt = """You are an impartial agent-behavior analyst.

Use the file_search tool to retrieve only what you need in bounded passes:
- max_num_results per pass: 8
- Stop after 6 passes OR if a pass yields no new sections
- Track coverage: coverage.files_scanned[], coverage.remaining[]

Rules:
- Cite evidence with {file, section_or_lines} when possible (rough is OK for POC).
- Output VALID JSON only that matches the provided schema. No prose outside JSON.
- If coverage is incomplete when you stop, state it explicitly in the JSON."""
    
    # User prompt  
    user_prompt = """Task: Produce an evidence-backed timeline of the agent execution.

Retrieval protocol:
1) Query for sections containing "run", "tool", "input", "output", "error", "exception".
2) Iterate passes (max 6). In each pass, fetch at most 8 chunks. Avoid repeating already-seen sections.
3) Build:
   - timeline[]: ordered runs with key inputs/outputs and tool calls
   - events[]: failures/retries/anomalies
   - coverage: { files_scanned[], remaining[] }
   - evidence[]: { file, section_or_lines, rationale }

Return JSON only per schema. If you hit the stop condition with remaining sections, include them in coverage.remaining."""
    
    # Create the full batch request body
    batch_body = {
        "model": "gpt-4o",
        "tools": [
            {
                "type": "file_search",
                "vector_store_ids": ["vs_placeholder"],
                "max_num_results": 8
            }
        ],
        "input": [
            {
                "type": "message",
                "role": "system", 
                "content": [{"type": "input_text", "text": system_prompt}]
            },
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": user_prompt}]
            }
        ],
        "temperature": 0.2,
        "max_output_tokens": 2000,
        "text": {
            "format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "trace_analysis",
                    "strict": True,
                    "schema": TRACE_ANALYSIS_SCHEMA
                }
            }
        }
    }
    
    # Full batch request with wrapper
    batch_request = {
        "custom_id": "stage1_trace_analysis_test_123",
        "method": "POST", 
        "url": "/v1/responses",
        "body": batch_body
    }
    
    # Count individual components
    system_tokens = count_tokens(system_prompt)
    user_tokens = count_tokens(user_prompt)
    schema_tokens = count_tokens(json.dumps(TRACE_ANALYSIS_SCHEMA))
    
    # Count the full request
    full_request_text = json.dumps(batch_request)
    full_tokens = count_tokens(full_request_text)
    
    print(f"System prompt: {system_tokens} tokens")
    print(f"User prompt: {user_tokens} tokens") 
    print(f"Schema alone: {schema_tokens} tokens")
    print(f"Full batch request: {full_tokens} tokens")
    print()
    print("Schema size breakdown:")
    print(f"  - Raw schema dict: {len(str(TRACE_ANALYSIS_SCHEMA))} chars")
    print(f"  - JSON serialized: {len(json.dumps(TRACE_ANALYSIS_SCHEMA))} chars")
    print(f"  - JSON pretty: {len(json.dumps(TRACE_ANALYSIS_SCHEMA, indent=2))} chars")
    print()
    
    if full_tokens > 90000:
        print("🚨 OVER 90K TOKENS - This will fail!")
    elif full_tokens > 50000:
        print("⚠️  HIGH TOKEN COUNT - Approaching limits")
    else:
        print("✅ Token count looks reasonable")
        
    print()
    print("RECOMMENDATION:")
    if schema_tokens > 20000:
        print(f"Schema is {schema_tokens} tokens - this is the main blocker!")
        print("Use minimal schema: {'type': 'object'} for POC")
    else:
        print("Schema size looks OK - check other components")

if __name__ == "__main__":
    main()