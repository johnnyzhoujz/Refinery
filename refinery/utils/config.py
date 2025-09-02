"""Configuration management for Refinery."""

import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class ChunkedAnalysisConfig:
    """Configuration for chunked analysis to handle large traces."""
    
    # Core chunking parameters
    group_size_runs: int = 6  # Number of runs per group for chunked analysis
    chunking_threshold: int = 20  # Use chunking for traces with >20 runs
    
    # Token management
    max_num_results_stage1: int = 2  # File search results for Stage 1 chunks
    max_num_results_other: int = 3  # File search results for Stages 2-3
    max_output_tokens_stage1: int = 900  # Output tokens for Stage 1 chunks
    max_output_tokens_other: int = 1000  # Output tokens for Stages 2-3
    
    # Rate limiting
    inter_group_sleep_s: int = 10  # Seconds between group calls
    tpm_limit: int = 30000  # TPM limit for rate limiting
    tpm_buffer: int = 2000  # Buffer below TPM limit
    
    # Model settings
    temperature: float = 0.2  # Low temperature for consistency
    
    # Feature flags
    disable_chunking: bool = False  # Emergency disable flag
    
    @classmethod
    def from_env(cls) -> "ChunkedAnalysisConfig":
        """Load chunked analysis configuration from environment variables."""
        return cls(
            group_size_runs=int(os.getenv("GROUP_SIZE_RUNS", "6")),
            chunking_threshold=int(os.getenv("CHUNKING_THRESHOLD", "20")),
            max_num_results_stage1=int(os.getenv("MAX_NUM_RESULTS_STAGE1", "2")),
            max_num_results_other=int(os.getenv("MAX_NUM_RESULTS_OTHER", "3")),
            max_output_tokens_stage1=int(os.getenv("MAX_OUTPUT_TOKENS_STAGE1", "900")),
            max_output_tokens_other=int(os.getenv("MAX_OUTPUT_TOKENS_OTHER", "1000")),
            inter_group_sleep_s=int(os.getenv("INTER_GROUP_SLEEP_S", "10")),
            tpm_limit=int(os.getenv("TPM_LIMIT", "30000")),
            tpm_buffer=int(os.getenv("TPM_BUFFER", "2000")),
            temperature=float(os.getenv("TEMPERATURE", "0.2")),
            disable_chunking=os.getenv("REFINERY_DISABLE_CHUNKING", "false").lower() == "true"
        )


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
    
    # Hypothesis generation settings (for customer experiments)
    hypothesis_llm_provider: str = "openai"
    hypothesis_model: str = "gpt-5"  # GPT-5 exists as of Sept 2025
    hypothesis_temperature: float = 0.0  # Deterministic generation
    hypothesis_max_tokens: int = 4000
    
    # Safety settings
    max_file_size_kb: int = 1000
    max_changes_per_hypothesis: int = 10
    require_approval_for_changes: bool = True
    
    # Chunked analysis configuration
    chunked_analysis: ChunkedAnalysisConfig = None
    
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
            hypothesis_llm_provider=os.getenv("HYPOTHESIS_LLM_PROVIDER", "openai"),
            hypothesis_model=os.getenv("HYPOTHESIS_MODEL", "gpt-5"),
            hypothesis_temperature=float(os.getenv("HYPOTHESIS_TEMPERATURE", "0.0")),
            hypothesis_max_tokens=int(os.getenv("HYPOTHESIS_MAX_TOKENS", "4000")),
            max_file_size_kb=int(os.getenv("MAX_FILE_SIZE_KB", "1000")),
            max_changes_per_hypothesis=int(os.getenv("MAX_CHANGES_PER_HYPOTHESIS", "10")),
            require_approval_for_changes=os.getenv("REQUIRE_APPROVAL_FOR_CHANGES", "true").lower() == "true",
            chunked_analysis=ChunkedAnalysisConfig.from_env()
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
        
        # Validate hypothesis-specific LLM settings
        if self.hypothesis_llm_provider == "openai" and not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for hypothesis generation")
        
        if self.hypothesis_llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for hypothesis generation")
        
        if self.hypothesis_llm_provider == "gemini" and not self.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is required for hypothesis generation")
        
        if self.hypothesis_temperature < 0.0 or self.hypothesis_temperature > 2.0:
            raise ValueError("hypothesis_temperature must be between 0.0 and 2.0")
        
        if self.hypothesis_max_tokens < 100 or self.hypothesis_max_tokens > 16000:
            raise ValueError("hypothesis_max_tokens must be between 100 and 16000")


# Global config instance
config = RefineryConfig.from_env()