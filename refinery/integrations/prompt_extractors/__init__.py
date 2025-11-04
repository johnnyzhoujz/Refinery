"""Prompt extraction modules for different trace providers."""

from .otlp_extractor import OTLPPromptExtractor
from .langfuse_extractor import LangfusePromptExtractor

__all__ = ["OTLPPromptExtractor", "LangfusePromptExtractor"]
