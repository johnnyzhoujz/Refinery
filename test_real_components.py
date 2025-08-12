#!/usr/bin/env python3
"""
Test our actual schema and prompts to find what triggers 90K limit.
"""

import json
import tiktoken
import tempfile
import openai
from pathlib import Path
from refinery.utils.config import config
from refinery.agents.staged_schemas import TRACE_ANALYSIS_SCHEMA

def count_tokens(text: str) -> int:
    """Count tokens using tiktoken"""
    encoding = tiktoken.encoding_for_model("gpt-4o")
    return len(encoding.encode(text))

def test_with_real_schema():
    """Test with our actual TRACE_ANALYSIS_SCHEMA"""
    
    print("\n🧪 TESTING WITH REAL SCHEMA")
    
    # Our actual prompts from staged_failure_analyst.py
    system_prompt = """You are an impartial agent-behavior analyst.

Use the file_search tool to retrieve only what you need in bounded passes:
- max_num_results per pass: 8
- Stop after 6 passes OR if a pass yields no new sections
- Track coverage: coverage.files_scanned[], coverage.remaining[]

Rules:
- Cite evidence with {file, section_or_lines} when possible (rough is OK for POC).
- Output VALID JSON only that matches the provided schema. No prose outside JSON.
- If coverage is incomplete when you stop, state it explicitly in the JSON."""
    
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
    
    # Create empty vector store
    client = openai.Client(api_key=config.openai_api_key)
    empty_vector_store = client.vector_stores.create(
        name="real_schema_test",
        expires_after={"anchor": "last_active_at", "days": 1}
    )
    
    # Create batch with REAL components
    batch_body = {
        "model": "gpt-4o",
        "tools": [
            {"type": "file_search", "vector_store_ids": [empty_vector_store.id], "max_num_results": 8}
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
        "max_output_tokens": 800,
        "response_format": {
            "type": "json_schema", 
            "json_schema": {
                "name": "trace_analysis",
                "strict": True,
                "schema": TRACE_ANALYSIS_SCHEMA  # The REAL schema
            }
        }
    }
    
    batch_request = {
        "custom_id": "real_schema_test",
        "method": "POST",
        "url": "/v1/responses",
        "body": batch_body
    }
    
    # Analyze token breakdown
    jsonl_content = json.dumps(batch_request)
    final_tokens = count_tokens(jsonl_content)
    
    print(f"📊 TOKEN BREAKDOWN:")
    print(f"System prompt: {count_tokens(system_prompt)} tokens")
    print(f"User prompt: {count_tokens(user_prompt)} tokens")
    print(f"Schema alone: {count_tokens(json.dumps(TRACE_ANALYSIS_SCHEMA))} tokens")
    print(f"Full request: {final_tokens} tokens")
    print(f"JSONL lines: 1")
    
    # Test submission
    try:
        # Write batch file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(jsonl_content + '\n')
            batch_file_path = f.name
        
        # Upload and submit
        with open(batch_file_path, 'rb') as f:
            batch_file = client.files.create(file=f, purpose="batch")
        
        batch = client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/responses",
            completion_window="24h"
        )
        
        print(f"✅ SUCCESS: Real schema batch submitted - {batch.id}")
        
        # Cancel immediately
        try:
            client.batches.cancel(batch.id)
            print(f"✅ Cancelled: {batch.id}")
        except:
            pass
        
        result = "SUCCESS"
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        result = f"FAILED: {e}"
    
    # Cleanup
    Path(batch_file_path).unlink()
    try:
        client.vector_stores.delete(empty_vector_store.id)
    except:
        pass
    
    return result, final_tokens

def main():
    print("🔬 TESTING REAL SCHEMA COMPONENTS")
    print("=" * 50)
    
    result, tokens = test_with_real_schema()
    
    print(f"\n🎯 RESULT:")
    print(f"Real schema test: {result}")
    print(f"Total tokens: {tokens}")
    
    if "SUCCESS" in result:
        print(f"\n✅ SUCCESS! Our real schema works fine at {tokens} tokens")
        print(f"   → The issue is NOT our schema or prompts")
        print(f"   → Must be something else in our actual implementation")
        print(f"   → Check: Different request format? Hidden content? Other org batches?")
    else:
        print(f"\n❌ FAILED! This is the component causing issues")
        print(f"   → Schema or prompts are triggering the 90K limit")
        print(f"   → Need to simplify schema or shorten prompts")

if __name__ == "__main__":
    main()