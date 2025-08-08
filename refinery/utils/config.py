"""Configuration management for Refinery."""

import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class RefineryConfig:
    """Configuration settings for Refinery."""
    
    # LangSmith
    langsmith_api_key: str
    langsmith_api_url: str = "https://api.smith.langchain.com"
    
    # LLM Configuration
    llm_provider: str = "openai"  # openai, anthropic, azure_openai, gemini
    
    # OpenAI
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o"
    
    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-3-opus-20240229"
    
    # Azure OpenAI
    azure_openai_api_key: Optional[str] = None
    azure_openai_endpoint: Optional[str] = None
    azure_openai_deployment: Optional[str] = None
    
    # Gemini
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.0-flash"
    
    # General settings
    log_level: str = "INFO"
    debug: bool = False
    cache_ttl: int = 900  # seconds
    
    # Safety settings
    max_file_size_kb: int = 1000
    max_changes_per_hypothesis: int = 10
    require_approval_for_changes: bool = True
    
    @classmethod
    def from_env(cls) -> "RefineryConfig":
        """Load configuration from environment variables."""
        return cls(
            langsmith_api_key=os.getenv("LANGSMITH_API_KEY", ""),
            langsmith_api_url=os.getenv("LANGSMITH_API_URL", "https://api.smith.langchain.com"),
            llm_provider=os.getenv("LLM_PROVIDER", "openai"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229"),
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            cache_ttl=int(os.getenv("CACHE_TTL", "900")),
            max_file_size_kb=int(os.getenv("MAX_FILE_SIZE_KB", "1000")),
            max_changes_per_hypothesis=int(os.getenv("MAX_CHANGES_PER_HYPOTHESIS", "10")),
            require_approval_for_changes=os.getenv("REQUIRE_APPROVAL_FOR_CHANGES", "true").lower() == "true"
        )
    
    def validate(self) -> None:
        """Validate configuration."""
        if not self.langsmith_api_key:
            raise ValueError("LANGSMITH_API_KEY is required")
        
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when using OpenAI provider")
        
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when using Anthropic provider")
        
        if self.llm_provider == "azure_openai":
            if not all([self.azure_openai_api_key, self.azure_openai_endpoint, self.azure_openai_deployment]):
                raise ValueError("Azure OpenAI requires API key, endpoint, and deployment")
        
        if self.llm_provider == "gemini" and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required when using Gemini provider")


# Global config instance
config = RefineryConfig.from_env()