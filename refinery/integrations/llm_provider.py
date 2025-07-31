"""LLM provider implementation with support for multiple backends."""

import json
from typing import Any, Dict, List, Optional
import structlog
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic

from ..core.interfaces import LLMProvider
from ..utils.config import config

logger = structlog.get_logger(__name__)


class ConfigurableLLMProvider(LLMProvider):
    """LLM provider that supports multiple backends based on configuration."""
    
    def __init__(self):
        self.provider = config.llm_provider
        
        if self.provider == "openai":
            if not config.openai_api_key:
                raise ValueError("OpenAI API key not configured")
            self.client = AsyncOpenAI(api_key=config.openai_api_key)
            self.model = config.openai_model
            
        elif self.provider == "anthropic":
            if not config.anthropic_api_key:
                raise ValueError("Anthropic API key not configured")
            self.client = AsyncAnthropic(api_key=config.anthropic_api_key)
            self.model = config.anthropic_model
            
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")
        
        logger.info(f"Initialized LLM provider", provider=self.provider, model=self.model)
    
    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """Get a completion from the LLM."""
        try:
            if self.provider == "openai":
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content
                
            elif self.provider == "anthropic":
                kwargs = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": temperature,
                    "max_tokens": max_tokens or 4096
                }
                if system_prompt:
                    kwargs["system"] = system_prompt
                
                response = await self.client.messages.create(**kwargs)
                return response.content[0].text
                
        except Exception as e:
            logger.error(f"LLM completion failed", error=str(e), provider=self.provider)
            raise
    
    async def complete_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get a completion with tool usage."""
        try:
            # Add instructions for structured output
            enhanced_prompt = f"""
{prompt}

Please provide your response in the following JSON format:
{{
    "reasoning": "Your step-by-step reasoning",
    "tool_calls": [
        {{
            "tool_name": "name_of_tool",
            "arguments": {{}}
        }}
    ],
    "result": "The final result or conclusion"
}}
"""
            
            response = await self.complete(
                enhanced_prompt,
                system_prompt=system_prompt,
                temperature=0.1  # Lower temperature for structured output
            )
            
            # Try to parse as JSON
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # Fallback if not valid JSON
                return {
                    "reasoning": response,
                    "tool_calls": [],
                    "result": response
                }
                
        except Exception as e:
            logger.error(f"LLM tool completion failed", error=str(e), provider=self.provider)
            raise


def create_llm_provider() -> LLMProvider:
    """Factory function to create an LLM provider."""
    return ConfigurableLLMProvider()