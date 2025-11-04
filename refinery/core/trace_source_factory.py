"""
TraceSourceFactory for creating trace providers.

Factory pattern for instantiating the correct TraceProvider based on
configuration or CLI arguments. Supports LangSmith, Langfuse, and OTLP providers.
"""

from typing import Optional, Dict, Any
import structlog
from pathlib import Path

logger = structlog.get_logger(__name__)


class TraceSourceFactory:
    """Factory for creating trace provider instances."""

    @staticmethod
    def create_from_provider(
        provider: str,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Create trace provider from explicit provider name.

        Args:
            provider: Provider name ("langsmith", "langfuse", "otlp", "local-file")
            config: Optional configuration dict

        Returns:
            TraceProvider instance

        Raises:
            ValueError: If provider is invalid or required config missing

        Example:
            >>> factory = TraceSourceFactory()
            >>> provider = factory.create_from_provider("langfuse", {
            ...     "public_key": "pk-...",
            ...     "secret_key": "sk-...",
            ... })
        """
        config = config or {}
        provider = provider.lower()

        if provider == "langsmith":
            return TraceSourceFactory._create_langsmith(config)
        elif provider == "langfuse":
            return TraceSourceFactory._create_langfuse(config)
        elif provider in ("otlp", "local-file"):
            return TraceSourceFactory._create_local_file(config)
        else:
            raise ValueError(
                f"Unknown provider: {provider}. "
                f"Valid options: langsmith, langfuse, otlp, local-file"
            )

    @staticmethod
    def create_from_config(config: Dict[str, Any]):
        """
        Create trace provider from configuration dict.

        Auto-detects provider type from config keys or explicit "provider" field.

        Args:
            config: Configuration dictionary

        Returns:
            TraceProvider instance

        Raises:
            ValueError: If provider cannot be determined or config is invalid

        Example:
            >>> config = {"provider": "langfuse", "public_key": "pk-...", ...}
            >>> provider = TraceSourceFactory.create_from_config(config)
        """
        # Check for explicit provider field
        if "provider" in config:
            provider = config["provider"]
            return TraceSourceFactory.create_from_provider(provider, config)

        # Auto-detect from config keys
        if "LANGFUSE_PUBLIC_KEY" in config or "public_key" in config:
            logger.info("Auto-detected Langfuse from config")
            return TraceSourceFactory._create_langfuse(config)
        elif "LANGCHAIN_API_KEY" in config or "api_key" in config:
            logger.info("Auto-detected LangSmith from config")
            return TraceSourceFactory._create_langsmith(config)
        elif "file_path" in config or "trace_file" in config:
            logger.info("Auto-detected local file from config")
            return TraceSourceFactory._create_local_file(config)
        else:
            raise ValueError(
                "Cannot auto-detect provider from config. "
                "Provide 'provider' field or use provider-specific keys."
            )

    @staticmethod
    def create_for_cli(
        provider: Optional[str] = None,
        trace_id: Optional[str] = None,
        file_path: Optional[str] = None,
    ):
        """
        Create trace provider for CLI usage.

        Handles common CLI patterns with smart defaults and auto-detection.

        Args:
            provider: Optional explicit provider name
            trace_id: Optional trace ID (for LangSmith/Langfuse)
            file_path: Optional file path (for OTLP/local-file)

        Returns:
            TraceProvider instance

        Raises:
            ValueError: If insufficient information provided

        Example:
            >>> # Explicit provider
            >>> provider = TraceSourceFactory.create_for_cli(provider="langfuse")
            >>> # Auto-detect from file path
            >>> provider = TraceSourceFactory.create_for_cli(file_path="trace.json")
            >>> # Use trace_id with default provider
            >>> provider = TraceSourceFactory.create_for_cli(trace_id="abc123")
        """
        # Case 1: Explicit provider specified
        if provider:
            return TraceSourceFactory.create_from_provider(provider, {
                "trace_id": trace_id,
                "file_path": file_path,
            })

        # Case 2: File path provided → auto-detect OTLP/local-file
        if file_path:
            logger.info("Auto-detected local file provider from file path")
            return TraceSourceFactory._create_local_file({"file_path": file_path})

        # Case 3: Trace ID provided → default to LangSmith (backward compatibility)
        if trace_id:
            logger.info("Defaulting to LangSmith for trace ID (backward compatibility)")
            return TraceSourceFactory._create_langsmith({"trace_id": trace_id})

        # Case 4: No information provided → default to LangSmith
        logger.info("No provider specified, defaulting to LangSmith")
        return TraceSourceFactory._create_langsmith({})

    @staticmethod
    def _create_langsmith(config: Dict[str, Any]):
        """Create LangSmith trace provider."""
        from ..integrations.langsmith_client_simple import SimpleLangSmithClient

        # SimpleLangSmithClient reads credentials from global config object
        return SimpleLangSmithClient()

    @staticmethod
    def _create_langfuse(config: Dict[str, Any]):
        """Create Langfuse trace provider."""
        from ..integrations.langfuse_client import LangfuseClient

        # LangfuseClient reads credentials from global config and validates in __init__
        return LangfuseClient()

    @staticmethod
    def _create_local_file(config: Dict[str, Any]):
        """Create local file trace provider for OTLP."""
        from ..integrations.local_file_provider import LocalFileTraceProvider

        file_path = config.get("file_path") or config.get("trace_file")

        if not file_path:
            raise ValueError(
                "Local file provider requires 'file_path'. "
                "Provide file path via config or CLI argument."
            )

        # Validate file exists
        path = Path(file_path)
        if not path.exists():
            raise ValueError(f"Trace file not found: {file_path}")

        return LocalFileTraceProvider(file_path=str(path))
