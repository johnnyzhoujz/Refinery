#!/usr/bin/env python3
"""
Debug the actual response structure from OpenAI Responses API.
"""
import asyncio
import json
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from refinery.integrations.responses_client import ResponsesClient
from refinery.integrations.responses_request_builder import build_canary_test_body
from refinery.utils.config import config

async def debug_response_structure():
    """Debug the exact response structure from OpenAI."""
    
    if not config.openai_api_key:
        print("❌ OPENAI_API_KEY not configured")
        return False
    
    print("🔍 Debugging OpenAI Responses API structure...")
    
    # Initialize client
    client = ResponsesClient(config.openai_api_key)
    
    # Build simple test request
    body = build_canary_test_body()
    
    try:
        # Send request
        response = await client.create(body)
        
        print("📥 Full raw response structure:")
        print(json.dumps(response, indent=2))
        
        # Show what we get from different parsing attempts
        print("\n" + "="*50)
        print("PARSING ANALYSIS:")
        print("="*50)
        
        # Check if output_text exists
        if "output_text" in response:
            print(f"✅ Found output_text: {response['output_text']}")
        else:
            print("❌ No output_text field")
        
        # Check output array structure
        if "output" in response and len(response["output"]) > 0:
            print(f"✅ Found output array with {len(response['output'])} items")
            
            for i, output_item in enumerate(response["output"]):
                print(f"\nOutput item {i}:")
                print(f"  Type: {output_item.get('type')}")
                print(f"  Status: {output_item.get('status')}")
                
                if "content" in output_item:
                    print(f"  Content items: {len(output_item['content'])}")
                    for j, content_item in enumerate(output_item["content"]):
                        print(f"    Content {j}: type={content_item.get('type')}")
                        if content_item.get("type") == "output_text":
                            text = content_item.get("text", "")
                            print(f"    Text length: {len(text)}")
                            print(f"    Text preview: {text[:200]}...")
        else:
            print("❌ No output array or empty")
        
        # Check choices (chat completions format)
        if "choices" in response:
            print(f"✅ Found choices array with {len(response['choices'])} items")
        else:
            print("❌ No choices array")
            
        return True
        
    except Exception as e:
        print(f"❌ Debug failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(debug_response_structure())
    sys.exit(0 if success else 1)