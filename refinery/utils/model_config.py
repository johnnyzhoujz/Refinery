"""Model configuration for different token requirements."""

from typing import Any, Dict

# Model configurations with context windows (August 2025)
MODEL_CONFIGS = {
    "gemini": {
        "flash": {
            "model": "gemini-2.0-flash",
            "context_window": 1_048_576,  # 1M tokens
            "recommended_max_input": 900_000,
            "output_limit": 8_192,
            "best_for": "high-volume, high-frequency tasks",
        },
        "pro": {
            "model": "gemini-2.5-pro",
            "context_window": 2_000_000,  # 2M tokens
            "recommended_max_input": 1_800_000,
            "output_limit": 8_192,
            "best_for": "complex reasoning with Deep Think mode",
        },
    },
    "openai": {
        "gpt4o": {
            "model": "gpt-4o",
            "context_window": 128_000,
            "recommended_max_input": 100_000,
            "output_limit": 16_384,
            "best_for": "fast multimodal processing",
        },
        "gpt45": {
            "model": "gpt-4.5-orion",
            "context_window": 256_000,
            "recommended_max_input": 200_000,
            "output_limit": 32_000,
            "best_for": "extended context with latest knowledge",
        },
        "o3": {
            "model": "o3",
            "context_window": 200_000,
            "recommended_max_input": 180_000,
            "output_limit": 100_000,
            "best_for": "SOTA coding and reasoning with tool use",
        },
        "o4-mini": {
            "model": "o4-mini",
            "context_window": 128_000,
            "recommended_max_input": 100_000,
            "output_limit": 16_384,
            "best_for": "balanced speed/cost for coding",
        },
    },
    "anthropic": {
        "claude-3.7-sonnet": {
            "model": "claude-3.7-sonnet",
            "context_window": 200_000,
            "recommended_max_input": 180_000,
            "output_limit": 4_096,
            "best_for": "complex coding with Extended Thinking",
        },
        "claude-4": {
            "model": "claude-4-opus",
            "context_window": 200_000,
            "recommended_max_input": 180_000,
            "output_limit": 4_096,
            "best_for": "frontier intelligence for complex agents",
        },
        "claude-4-sonnet": {
            "model": "claude-4-sonnet",
            "context_window": 200_000,
            "recommended_max_input": 180_000,
            "output_limit": 4_096,
            "best_for": "speed optimized Claude 4",
        },
    },
    "magic": {
        "ltm-2-mini": {
            "model": "ltm-2-mini",
            "context_window": 100_000_000,  # 100M tokens!
            "recommended_max_input": 90_000_000,
            "output_limit": 32_000,
            "best_for": "analyzing entire codebases (10M lines)",
        }
    },
    "meta": {
        "llama-4-scout": {
            "model": "llama-4-scout",
            "context_window": 10_000_000,  # 10M tokens
            "recommended_max_input": 9_000_000,
            "output_limit": 8_192,
            "best_for": "open-source, self-hosted large context",
        }
    },
    "deepseek": {
        "r1": {
            "model": "deepseek-r1",
            "context_window": 128_000,
            "recommended_max_input": 100_000,
            "output_limit": 8_192,
            "best_for": "low-cost reasoning and debugging",
        }
    },
}


def select_model_for_trace_size(provider: str, trace_tokens: int) -> Dict[str, Any]:
    """Select appropriate model based on trace size."""
    configs = MODEL_CONFIGS.get(provider, MODEL_CONFIGS["openai"])

    # Add 30% buffer for prompts, response, and extracted context
    required_tokens = int(trace_tokens * 1.3)

    # Provider-specific selection logic
    if provider == "gemini":
        # For small traces, use Flash for speed
        if required_tokens < 100_000:
            return configs["flash"]
        else:
            return configs["pro"]  # For large traces, use Pro

    elif provider == "openai":
        # Prioritize o3 for complex reasoning
        if required_tokens < 100_000:
            return configs["o4-mini"]  # Fast and cheap
        elif required_tokens < 180_000:
            return configs["o3"]  # Best reasoning
        else:
            return configs["gpt45"]  # Largest context

    elif provider == "anthropic":
        # Use Claude 3.7 Sonnet for most tasks
        if required_tokens < 180_000:
            return configs["claude-3.7-sonnet"]
        else:
            return configs["claude-4"]  # Frontier model

    elif provider == "magic":
        # Only one model, ideal for massive codebases
        return configs["ltm-2-mini"]

    elif provider == "meta":
        # Open source option
        return configs["llama-4-scout"]

    elif provider == "deepseek":
        # Low cost option
        return configs["r1"]

    # Default fallback
    return list(configs.values())[0]


def should_truncate(trace_tokens: int, model_config: Dict[str, Any]) -> bool:
    """Determine if truncation is needed."""
    return trace_tokens > model_config["recommended_max_input"] * 0.8


def get_recommended_models_for_refinery() -> List[Dict[str, Any]]:
    """Get recommended models for Refinery's code analysis use case."""
    return [
        {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "reason": "2M token window with Deep Think mode for complex reasoning",
        },
        {
            "provider": "openai",
            "model": "o3",
            "reason": "SOTA coding performance with integrated tool use",
        },
        {
            "provider": "anthropic",
            "model": "claude-3.7-sonnet",
            "reason": "Extended Thinking mode ideal for failure diagnosis",
        },
        {
            "provider": "magic",
            "model": "ltm-2-mini",
            "reason": "100M tokens for analyzing entire codebases",
        },
    ]
