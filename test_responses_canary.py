#!/usr/bin/env python3
"""
Test basic OpenAI Responses API connectivity.
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

async def test_canary():
    """Test basic API connectivity with a simple request."""
    
    if not config.openai_api_key:
        print("❌ OPENAI_API_KEY not configured")
        return False
    
    print("🧪 Testing OpenAI Responses API connectivity...")
    
    # Initialize client
    client = ResponsesClient(config.openai_api_key)
    
    # Build canary test request
    body = build_canary_test_body()
    
    print("📤 Sending canary test request...")
    print(f"Request: {json.dumps(body, indent=2)}")
    
    try:
        # Send request
        response = await client.create(body)
        
        print("📥 Raw response received:")
        print(json.dumps(response, indent=2))
        
        # Try to parse JSON output
        parsed = client.parse_json_output(response)
        
        print("✅ Canary test successful!")
        print(f"Parsed output: {parsed}")
        
        return True
        
    except Exception as e:
        print(f"❌ Canary test failed: {str(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_canary())
    sys.exit(0 if success else 1)