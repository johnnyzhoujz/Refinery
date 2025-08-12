#!/usr/bin/env python3
"""
Debug batch quota issue - check for ghost batches and test minimal request.
"""

import json
import asyncio
import openai
from refinery.utils.config import config

async def main():
    print("=== BATCH QUOTA DEBUGGING ===")
    
    client = openai.Client(api_key=config.openai_api_key)
    
    # Check for existing batches
    print("1. Checking existing batches...")
    try:
        batches = client.batches.list(limit=20)
        print(f"Found {len(batches.data)} recent batches:")
        
        for batch in batches.data:
            print(f"  - {batch.id}: {batch.status} ({batch.created_at})")
            if batch.status in ["validating", "in_progress", "finalizing"]:
                print(f"    ⚠️  This batch may be holding quota!")
        
        active_batches = [b for b in batches.data if b.status in ["validating", "in_progress", "finalizing"]]
        if active_batches:
            print(f"\n🚨 Found {len(active_batches)} active batches that may be using quota")
        else:
            print("\n✅ No active batches found")
            
    except Exception as e:
        print(f"Error listing batches: {e}")
    
    print("\n" + "="*50)
    print("2. Testing minimal batch request...")
    
    # Create ultra-minimal request (following your guidance)
    minimal_body = {
        "model": "gpt-4o",
        "tools": [
            {"type": "file_search", "vector_store_ids": ["vs_fake"], "max_num_results": 8}
        ],
        "input": [
            {"type": "message", "role": "system",
             "content": [{"type": "input_text", "text": "Use file_search in bounded passes (8 chunks max per pass, stop after 6 or no new). Output JSON only per schema."}]},
            {"type": "message", "role": "user",
             "content": [{"type": "input_text", "text": "Analyze the trace and return timeline, events, coverage, evidence."}]}
        ],
        "response_format": {"type": "json_schema", "json_schema": {"type": "object"}},
        "temperature": 0.2,
        "max_output_tokens": 800
    }
    
    minimal_request = {
        "custom_id": "minimal_test",
        "method": "POST", 
        "url": "/v1/responses",
        "body": minimal_body
    }
    
    print("Minimal request created with:")
    print(f"  - System prompt: ~60 tokens")
    print(f"  - User prompt: ~40 tokens") 
    print(f"  - Schema: minimal object (3 tokens)")
    print(f"  - Max output: 800 tokens")
    print(f"  - Total estimate: ~1000 tokens")
    
    # Try to submit (but don't actually do it - just simulate)
    print(f"\nMinimal batch JSONL line:")
    print(json.dumps(minimal_request))
    
    print(f"\nThis should be well under 90K tokens. If it still fails:")
    print(f"  - Ghost quota from finalizing batches")
    print(f"  - OpenAI accounting includes hidden overhead")
    print(f"  - Try gpt-4o-mini to test")

if __name__ == "__main__":
    asyncio.run(main())