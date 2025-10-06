"""
Client for OpenAI Responses API.

This module handles POST requests to the /v1/responses endpoint
and parses the structured JSON output.
"""

import json
import asyncio
import logging
import time
from typing import Dict, Any, Optional, Tuple
import httpx

logger = logging.getLogger(__name__)


class ResponsesClient:
    """Client for interacting with OpenAI Responses API."""
    
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com"):
        """
        Initialize the Responses API client.
        
        Args:
            api_key: OpenAI API key
            base_url: Base URL for OpenAI API
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def create(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send a request to the Responses API.
        
        Args:
            body: Complete request body built by responses_request_builder
        
        Returns:
            Raw response from the API
        
        Raises:
            Exception: On API errors or network issues
        """
        url = f"{self.base_url}/v1/responses"

        # Use extended timeout for GPT-5 reasoning jobs
        timeout_config = httpx.Timeout(timeout=1200.0, connect=60.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            try:
                response = await client.post(
                    url,
                    headers=self.headers,
                    json=body
                )
                
                response_text = response.text
                
                # Handle rate limits with exponential backoff
                for attempt in range(3):
                    if response.status_code == 429:
                        wait_time = 60 * (2 ** attempt)  # 60s, 120s, 240s
                        logger.warning(f"Rate limit hit, waiting {wait_time}s (attempt {attempt+1}/3)")
                        await asyncio.sleep(wait_time)
                        
                        response = await client.post(
                            url,
                            headers=self.headers,
                            json=body
                        )
                        continue
                    break
                else:
                    if response.status_code == 429:
                        raise Exception("Rate limit persists after 3 attempts")
                
                # Check for other errors
                if response.status_code != 200:
                    logger.error(f"API error {response.status_code}: {response_text}")
                    raise Exception(f"API error {response.status_code}: {response_text}")
                
                # Parse response
                try:
                    return json.loads(response_text)
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse response JSON: {response_text[:500]}")
                    raise Exception(f"Invalid JSON response: {response_text[:500]}")
                    
            except httpx.TimeoutException:
                raise Exception("Request timeout after 5 minutes")
            except httpx.RequestError as e:
                raise Exception(f"Network error: {str(e)}")

    async def retrieve(self, response_id: str) -> Dict[str, Any]:
        """Retrieve a background Responses job."""
        url = f"{self.base_url}/v1/responses/{response_id}"

        # Use extended timeout for GPT-5 reasoning jobs
        timeout_config = httpx.Timeout(timeout=1200.0, connect=60.0)
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            try:
                # Increased timeout to 20 minutes for GPT-5 reasoning jobs
                response = await client.get(url, headers=self.headers)
            except httpx.TimeoutException:
                raise Exception("Retrieve request timeout after 20 minutes")
            except httpx.RequestError as e:
                raise Exception(f"Network error on retrieve: {str(e)}")

        if response.status_code != 200:
            raise Exception(
                f"Retrieve error {response.status_code}: {response.text[:200]}"
            )

        try:
            return response.json()
        except json.JSONDecodeError:
            raise Exception(f"Invalid JSON from retrieve: {response.text[:200]}")
    
    def parse_json_output(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract and parse JSON from the Responses API response.

        Args:
            response: Raw response from the API

        Returns:
            Parsed JSON object from the model's output

        Raises:
            Exception: If JSON parsing fails
        """
        try:
            # DEBUG: Log entry to parser
            logger.debug(f"[GPT5-DEBUG] parse_json_output called with response keys: {list(response.keys())}")

            # First try: Look for output_text field (some SDKs expose this)
            if "output_text" in response:
                logger.debug(f"[GPT5-DEBUG] Found output_text field")
                return json.loads(response["output_text"])
            
            # Second try: Extract from output array structure
            if "output" in response and len(response["output"]) > 0:
                logger.debug(f"[GPT5-DEBUG] Found output array with {len(response['output'])} items")
                # Find the message output item (skip file_search_call items)
                for idx, output_item in enumerate(response["output"]):
                    logger.debug(f"[GPT5-DEBUG] Output item {idx}: type={output_item.get('type')}")
                    if output_item.get("type") == "message":
                        output_content = output_item.get("content", [])
                        logger.debug(f"[GPT5-DEBUG] Found message with {len(output_content)} content items")

                        # Concatenate all output_text content items
                        text_parts = []
                        for item in output_content:
                            if item.get("type") == "output_text":
                                text = item.get("text", "")
                                logger.debug(f"[GPT5-DEBUG] Found output_text: {text[:200]}...")
                                text_parts.append(text)

                        if text_parts:
                            full_text = "".join(text_parts)
                            logger.info(f"[GPT5-DEBUG] Successfully extracted text ({len(full_text)} chars), parsing JSON...")
                            return json.loads(full_text)
            
            # Third try: Look for choices array (chat completions format)
            if "choices" in response and len(response["choices"]) > 0:
                choice = response["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    return json.loads(choice["message"]["content"])
            
            # If we can't find the JSON, log the response structure
            logger.error(f"Cannot find JSON in response structure: {json.dumps(response, indent=2)[:1000]}")
            raise Exception("Cannot extract JSON from response")
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            # Try to extract just the JSON part if there's extra text
            text_to_parse = None
            if "full_text" in locals() and isinstance(full_text, str):
                text_to_parse = full_text
            elif text_parts:
                text_to_parse = "".join(text_parts)
            
            if text_to_parse and "{" in text_to_parse:
                # Find the JSON boundaries
                start = text_to_parse.find("{")
                end = text_to_parse.rfind("}") + 1
                if start >= 0 and end > start:
                    try:
                        json_str = text_to_parse[start:end]
                        return json.loads(json_str)
                    except:
                        pass
            
            raise Exception(f"Failed to parse JSON output: {str(e)}")
    
    def parse_json_and_usage(self, response: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[int]]:
        """
        Extract and parse JSON from the Responses API response along with usage information.
        
        Args:
            response: Raw response from the API
        
        Returns:
            Tuple of (parsed JSON object, total_tokens or None)
        
        Raises:
            Exception: If JSON parsing fails
        """
        # Parse the JSON output first
        json_output = self.parse_json_output(response)
        
        # Extract usage information
        usage_total = None
        try:
            # Check for usage in top-level response (standard format)
            if "usage" in response and "total_tokens" in response["usage"]:
                usage_total = response["usage"]["total_tokens"]
            
            # Fallback: Check for usage in choices format
            elif "choices" in response and len(response["choices"]) > 0:
                choice = response["choices"][0]
                if "usage" in choice and "total_tokens" in choice["usage"]:
                    usage_total = choice["usage"]["total_tokens"]
            
            # Log if we found usage info
            if usage_total is not None:
                logger.debug(f"Extracted usage: {usage_total} total tokens")
            else:
                logger.debug("No usage information found in response")
                
        except Exception as e:
            logger.warning(f"Failed to extract usage information: {str(e)}")
            usage_total = None
        
        return json_output, usage_total

    def _build_metadata(
        self,
        response: Dict[str, Any],
        usage_total: Optional[int],
    ) -> Dict[str, Any]:
        metadata: Dict[str, Any] = {
            "response_id": response.get("id"),
            "status": response.get("status"),
            "model": response.get("model"),
            "usage_total_tokens": usage_total,
            "file_search_calls": [],
            "retrieved_chunk_ids": [],
        }

        for item in response.get("output", []):
            if item.get("type") == "file_search_call":
                results = item.get("results") or []
                metadata["file_search_calls"].append(
                    {
                        "id": item.get("id"),
                        "results": results,
                    }
                )
                for result in results:
                    chunk_id = result.get("chunk_id")
                    if chunk_id:
                        metadata["retrieved_chunk_ids"].append(chunk_id)

        return metadata
    
    async def create_with_retry(
        self, 
        body: Dict[str, Any],
        max_format_retries: int = 1
    ) -> Dict[str, Any]:
        """
        Create with automatic retry on JSON format issues.
        
        Args:
            body: Request body
            max_format_retries: Number of times to retry on format issues
        
        Returns:
            Parsed JSON output
        """
        response = await self.create(body)
        
        try:
            return self.parse_json_output(response)
        except Exception as e:
            if max_format_retries > 0 and "parse" in str(e).lower():
                logger.warning("JSON parse failed, retrying with format-only request")
                
                # Modify the user message to request JSON only
                retry_body = body.copy()
                retry_body["input"][1]["content"][0]["text"] = (
                    "Return ONLY the exact JSON output matching the schema. "
                    "No additional text or explanation.\n\n" +
                    "Previous output that needs reformatting:\n" +
                    json.dumps(response, indent=2)[:2000]
                )
                
                retry_response = await self.create(retry_body)
                return self.parse_json_output(retry_response)
            
            raise

    async def create_background(
        self,
        body: Dict[str, Any],
        poll_interval: float = 5.0,
        timeout: Optional[float] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Create a background job and poll until completion."""

        payload = dict(body)
        payload["background"] = True
        payload.setdefault("store", True)

        initial = await self.create(payload)
        status = initial.get("status")
        response_id = initial.get("id")

        # DEBUG: Log raw response structure for GPT-5 debugging
        logger.info(f"[GPT5-DEBUG] Initial response status: {status}, id: {response_id}")
        logger.info(f"[GPT5-DEBUG] Response keys: {list(initial.keys())}")

        if status in {"succeeded", "completed"}:
            # DEBUG: Log full response structure before parsing
            logger.info(f"[GPT5-DEBUG] Fast-complete response structure: {json.dumps(initial, indent=2)[:2000]}")
            json_output, usage_total = self.parse_json_and_usage(initial)
            logger.info(f"[GPT5-DEBUG] Parsed JSON keys: {list(json_output.keys()) if isinstance(json_output, dict) else type(json_output)}")
            logger.info(f"[GPT5-DEBUG] Usage: {usage_total} tokens")
            metadata = self._build_metadata(initial, usage_total)
            return json_output, metadata

        if not response_id:
            raise Exception("Background response missing id")

        if status not in {"queued", "in_progress"}:
            raise Exception(
                f"Background job failed fast: status={status}, details={initial.get('incomplete_details') or initial.get('error')}"
            )

        deadline = time.time() + timeout if timeout else None

        while True:
            if deadline and time.time() > deadline:
                raise Exception(
                    f"Background job timed out after {timeout} seconds (id={response_id})"
                )

            await asyncio.sleep(poll_interval)
            job = await self.retrieve(response_id)
            job_status = job.get("status")

            if job_status in {"succeeded", "completed"}:
                # DEBUG: Log full polled response before parsing
                logger.info(f"[GPT5-DEBUG] Polled job complete. Response structure: {json.dumps(job, indent=2)[:2000]}")
                json_output, usage_total = self.parse_json_and_usage(job)
                logger.info(f"[GPT5-DEBUG] Parsed JSON keys: {list(json_output.keys()) if isinstance(json_output, dict) else type(json_output)}")
                logger.info(f"[GPT5-DEBUG] Usage: {usage_total} tokens")
                metadata = self._build_metadata(job, usage_total)
                return json_output, metadata

            if job_status in {"failed", "cancelled", "incomplete", "requires_action"}:
                raise Exception(
                    f"Background job failed: status={job_status}, details={job.get('incomplete_details') or job.get('error')}"
                )

            # Continue polling while queued or in progress


# Module-level convenience functions
_client: Optional[ResponsesClient] = None

def init_client(api_key: str, base_url: str = "https://api.openai.com"):
    """Initialize the module-level client."""
    global _client
    _client = ResponsesClient(api_key, base_url)

async def create(body: Dict[str, Any]) -> Dict[str, Any]:
    """Send a request using the module-level client."""
    if _client is None:
        raise Exception("Client not initialized. Call init_client() first.")
    return await _client.create(body)

def parse_json_output(response: Dict[str, Any]) -> Dict[str, Any]:
    """Parse JSON using the module-level client."""
    if _client is None:
        raise Exception("Client not initialized. Call init_client() first.")
    return _client.parse_json_output(response)

def parse_json_and_usage(response: Dict[str, Any]) -> Tuple[Dict[str, Any], Optional[int]]:
    """Parse JSON and usage information using the module-level client."""
    if _client is None:
        raise Exception("Client not initialized. Call init_client() first.")
    return _client.parse_json_and_usage(response)

async def create_with_retry(body: Dict[str, Any]) -> Dict[str, Any]:
    """Create with retry using the module-level client."""
    if _client is None:
        raise Exception("Client not initialized. Call init_client() first.")
    return await _client.create_with_retry(body)

async def retrieve(response_id: str) -> Dict[str, Any]:
    """Retrieve a background job using the module-level client."""
    if _client is None:
        raise Exception("Client not initialized. Call init_client() first.")
    return await _client.retrieve(response_id)

async def create_background(
    body: Dict[str, Any],
    poll_interval: float = 5.0,
    timeout: Optional[float] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Create a background job using the module-level client."""
    if _client is None:
        raise Exception("Client not initialized. Call init_client() first.")
    return await _client.create_background(body, poll_interval=poll_interval, timeout=timeout)
