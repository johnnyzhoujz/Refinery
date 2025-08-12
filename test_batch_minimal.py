#!/usr/bin/env python3
"""
Systematic test to isolate 90K token limit cause.
Following the exact methodology to prove what's triggering the limit.
"""

import json
import tiktoken
import tempfile
import openai
from pathlib import Path
from refinery.utils.config import config

def count_tokens(text: str) -> int:
    """Count tokens using tiktoken"""
    encoding = tiktoken.encoding_for_model("gpt-4o")
    return len(encoding.encode(text))

def create_minimal_batch_body(vector_store_id=None, include_tools=True):
    """Create minimal batch body for testing"""
    
    body = {
        "model": "gpt-4o",
        "input": [
            {
                "type": "message",
                "role": "system",
                "content": [{"type": "input_text", "text": "Use file_search in bounded passes (8 chunks max per pass, stop after 6 or no new). Output JSON only per schema."}]
            },
            {
                "type": "message", 
                "role": "user",
                "content": [{"type": "input_text", "text": "Analyze the trace and return timeline, events, coverage, evidence."}]
            }
        ],
        "response_format": {"type": "json_schema", "json_schema": {"type": "object"}},
        "temperature": 0.2,
        "max_output_tokens": 800
    }
    
    # Add tools if requested
    if include_tools and vector_store_id:
        body["tools"] = [
            {"type": "file_search", "vector_store_ids": [vector_store_id], "max_num_results": 8}
        ]
    
    return body

def test_batch_submission(test_name, batch_body):
    """Test a batch submission and return result"""
    
    print(f"\n=== {test_name} ===")
    
    # Create batch request
    batch_request = {
        "custom_id": f"test_{test_name.lower().replace(' ', '_')}",
        "method": "POST",
        "url": "/v1/responses", 
        "body": batch_body
    }
    
    # Check JSONL line count
    jsonl_content = json.dumps(batch_request)
    jsonl_lines = jsonl_content.count('\n') + 1  # +1 because no trailing newline
    print(f"JSONL lines: {jsonl_lines}")
    
    # Count exact tokens of what we're submitting
    final_tokens = count_tokens(jsonl_content)
    print(f"Final serialized tokens: {final_tokens}")
    
    # Show the request size breakdown
    if "tools" in batch_body:
        tools_tokens = count_tokens(json.dumps(batch_body["tools"]))
        print(f"  - Tools section: {tools_tokens} tokens")
    
    schema_tokens = count_tokens(json.dumps(batch_body["response_format"]))
    print(f"  - Response format: {schema_tokens} tokens")
    
    client = openai.Client(api_key=config.openai_api_key)
    
    try:
        # Write batch file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            f.write(jsonl_content + '\n')
            batch_file_path = f.name
        
        # Upload batch file
        with open(batch_file_path, 'rb') as f:
            batch_file = client.files.create(file=f, purpose="batch")
        
        # Submit batch
        batch = client.batches.create(
            input_file_id=batch_file.id,
            endpoint="/v1/responses",
            completion_window="24h"
        )
        
        print(f"✅ SUCCESS: Batch submitted - {batch.id}")
        
        # Cancel it immediately since this is just a test
        try:
            client.batches.cancel(batch.id)
            print(f"✅ Cancelled test batch: {batch.id}")
        except Exception as e:
            print(f"⚠️  Could not cancel: {e}")
        
        # Cleanup
        Path(batch_file_path).unlink()
        
        return True, batch.id
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        
        # Check if it's the 90K error specifically
        error_str = str(e)
        if "90" in error_str and ("token" in error_str.lower() or "limit" in error_str.lower()):
            print(f"🎯 This is the 90K token limit error!")
        
        # Cleanup
        if 'batch_file_path' in locals():
            Path(batch_file_path).unlink()
        
        return False, error_str

def main():
    print("🔬 SYSTEMATIC 90K TOKEN LIMIT INVESTIGATION")
    print("=" * 60)
    
    client = openai.Client(api_key=config.openai_api_key)
    
    # Test 1: Empty vector store
    print("\n📋 Test 1: Empty vector store (0 files)")
    empty_vector_store = client.vector_stores.create(
        name="empty_test_store",
        expires_after={"anchor": "last_active_at", "days": 1}
    )
    
    body1 = create_minimal_batch_body(vector_store_id=empty_vector_store.id, include_tools=True)
    success1, result1 = test_batch_submission("Empty Vector Store", body1)
    
    # Test 2: No tools at all
    print("\n📋 Test 2: No tools at all")
    body2 = create_minimal_batch_body(vector_store_id=None, include_tools=False)
    success2, result2 = test_batch_submission("No Tools", body2)
    
    # Test 3: With existing big vector store (if we have one)
    print("\n📋 Test 3: Big vector store (if available)")
    print("NOTE: This would use an existing vector store with 500K tokens of content")
    print("Skipping for now - would need to create one first")
    
    print("\n" + "=" * 60)
    print("🎯 RESULTS SUMMARY:")
    print(f"Empty vector store: {'✅ SUCCESS' if success1 else '❌ FAILED'}")
    print(f"No tools: {'✅ SUCCESS' if success2 else '❌ FAILED'}")
    
    if success1 and success2:
        print("\n✅ Neither empty vector store nor no-tools failed!")
        print("   → The issue is likely NOT vector store size")
        print("   → Need to test with actual big vector store or investigate other causes")
    elif not success1 and not success2:
        print("\n❌ Both failed with same error!")
        print("   → The issue is in the batch request itself, not vector stores")
        print("   → Check: multiple JSONL lines, schema size, hidden bloat, or org limits")
    elif success2 and not success1:
        print("\n🤔 No-tools worked, but empty vector store failed!")
        print("   → Issue might be with file_search tool configuration")
    else:
        print("\n🤔 Unexpected pattern - investigate further")
    
    # Cleanup
    try:
        client.vector_stores.delete(empty_vector_store.id)
        print(f"\n🧹 Cleaned up empty vector store: {empty_vector_store.id}")
    except Exception as e:
        print(f"⚠️  Could not cleanup vector store: {e}")

if __name__ == "__main__":
    main()