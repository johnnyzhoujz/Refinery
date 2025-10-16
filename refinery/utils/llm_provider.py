"""
Configurable LLM provider implementation for Refinery.

Supports OpenAI, Anthropic, and Azure OpenAI with a unified interface.
"""

import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from anthropic import AsyncAnthropic
from openai import AsyncAzureOpenAI, AsyncOpenAI

from ..core.interfaces import LLMProvider
from .config import RefineryConfig

logger = logging.getLogger(__name__)


class ConfigurableLLMProvider(LLMProvider):
    """Configurable LLM provider that supports multiple backends."""

    def __init__(self, config: RefineryConfig):
        self.config = config
        self._client = None
        self._setup_client()

    def _setup_client(self) -> None:
        """Setup the appropriate client based on configuration."""
        if self.config.llm_provider == "openai":
            self._client = AsyncOpenAI(api_key=self.config.openai_api_key)
            self._model = self.config.openai_model
        elif self.config.llm_provider == "anthropic":
            self._client = AsyncAnthropic(api_key=self.config.anthropic_api_key)
            self._model = self.config.anthropic_model
        elif self.config.llm_provider == "azure_openai":
            self._client = AsyncAzureOpenAI(
                api_key=self.config.azure_openai_api_key,
                azure_endpoint=self.config.azure_openai_endpoint,
                api_version="2024-02-01",
            )
            self._model = self.config.azure_openai_deployment
        else:
            raise ValueError(f"Unsupported LLM provider: {self.config.llm_provider}")

    async def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        """Get a completion from the LLM."""
        try:
            if self.config.llm_provider in ["openai", "azure_openai"]:
                return await self._openai_complete(
                    prompt, system_prompt, temperature, max_tokens, reasoning_effort
                )
            elif self.config.llm_provider == "anthropic":
                return await self._anthropic_complete(
                    prompt, system_prompt, temperature, max_tokens
                )
            else:
                raise ValueError(f"Unsupported provider: {self.config.llm_provider}")
        except Exception as e:
            logger.error(f"LLM completion failed: {e}")
            raise

    async def complete_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get a completion with tool usage."""
        try:
            if self.config.llm_provider in ["openai", "azure_openai"]:
                return await self._openai_complete_with_tools(
                    prompt, tools, system_prompt
                )
            elif self.config.llm_provider == "anthropic":
                return await self._anthropic_complete_with_tools(
                    prompt, tools, system_prompt
                )
            else:
                raise ValueError(f"Unsupported provider: {self.config.llm_provider}")
        except Exception as e:
            logger.error(f"LLM completion with tools failed: {e}")
            raise

    async def _openai_complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        reasoning_effort: Optional[str] = None,
    ) -> str:
        """OpenAI-specific completion."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        kwargs = {
            "model": self._model,
            "messages": messages,
        }
        is_gpt5 = "gpt-5" in (self._model or "").lower()
        if not is_gpt5:
            kwargs["temperature"] = temperature
        if max_tokens:
            if is_gpt5:
                kwargs["max_completion_tokens"] = max_tokens
            else:
                kwargs["max_tokens"] = max_tokens

        # Add reasoning_effort for GPT-5 models
        if reasoning_effort and is_gpt5:
            kwargs["reasoning"] = {"effort": reasoning_effort}

        # Add 2-minute timeout protection
        try:
            response = await asyncio.wait_for(
                self._client.chat.completions.create(**kwargs),
                timeout=120.0,  # 2 minute timeout
            )
            return response.choices[0].message.content
        except asyncio.TimeoutError:
            logger.error("GPT-5 request timed out after 2 minutes")
            raise Exception(
                "Request timed out after 2 minutes - prompt may be too long"
            )

    async def _anthropic_complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Anthropic-specific completion."""
        # Anthropic uses system parameter separately
        kwargs = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        if max_tokens:
            kwargs["max_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = 4096  # Anthropic requires max_tokens

        response = await self._client.messages.create(**kwargs)
        return response.content[0].text

    async def _openai_complete_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """OpenAI-specific completion with tools."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        result = {
            "content": response.choices[0].message.content,
            "tool_calls": [],
        }

        if response.choices[0].message.tool_calls:
            for tool_call in response.choices[0].message.tool_calls:
                result["tool_calls"].append(
                    {
                        "id": tool_call.id,
                        "function": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments),
                    }
                )

        return result

    async def _anthropic_complete_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Anthropic-specific completion with tools."""
        kwargs = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 4096,
            "tools": tools,
        }

        if system_prompt:
            kwargs["system"] = system_prompt

        response = await self._client.messages.create(**kwargs)

        result = {
            "content": "",
            "tool_calls": [],
        }

        for content_block in response.content:
            if content_block.type == "text":
                result["content"] += content_block.text
            elif content_block.type == "tool_use":
                result["tool_calls"].append(
                    {
                        "id": content_block.id,
                        "function": content_block.name,
                        "arguments": content_block.input,
                    }
                )

        return result


def get_llm_provider(config: Optional[RefineryConfig] = None) -> LLMProvider:
    """Get a configured LLM provider instance."""
    if config is None:
        from .config import config as default_config

        config = default_config

    return ConfigurableLLMProvider(config)
