"""
Interfaces for different user interaction modes.

This package provides abstraction layers for various user interfaces:
- CLI chat interface (simple prompts)
- Future: Natural language interface (LLM-powered)
- Future: Web interface (Streamlit/FastAPI)
"""

from .chat_interface import BaseChatInterface, ChatInterface
from .chat_session import run_chat_session

__all__ = ["ChatInterface", "BaseChatInterface", "run_chat_session"]
