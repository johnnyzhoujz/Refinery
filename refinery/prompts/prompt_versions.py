"""
Simple prompt versioning utility for Refinery.

This module provides a lightweight versioning system for all prompts used in the system,
allowing easy switching between versions for testing and gradual rollout.

Usage:
    from refinery.prompts.prompt_versions import get_versioned_prompt
    
    # In your module with prompts:
    DIAGNOSIS_SYSTEM_PROMPT_V1 = "Original prompt..."
    DIAGNOSIS_SYSTEM_PROMPT_V2 = "Improved prompt..."
    
    # Get the right version (defaults to V1 unless env var set)
    DIAGNOSIS_SYSTEM_PROMPT = get_versioned_prompt("DIAGNOSIS_SYSTEM_PROMPT", context=globals())

Environment Variables:
    REFINERY_PROMPT_VERSION: Global version for all prompts (e.g., "V1", "V2")
    <PROMPT_NAME>_VERSION: Override for specific prompt (e.g., "DIAGNOSIS_SYSTEM_PROMPT_VERSION=V2")
"""

import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def get_versioned_prompt(
    base_name: str, 
    version: Optional[str] = None, 
    context: Optional[Dict[str, Any]] = None
) -> str:
    """
    Get a versioned prompt by name.
    
    This function looks for prompts following the naming convention:
    <BASE_NAME>_<VERSION> where VERSION is like V1, V2, etc.
    
    Args:
        base_name: Prompt name without version suffix (e.g., "FAILURE_ANALYST_PROMPT")
        version: Specific version to retrieve (e.g., "V1", "V2"). If None, checks env vars.
        context: The globals() dict from the calling module containing the prompt definitions
        
    Returns:
        The requested prompt string
        
    Raises:
        ValueError: If the requested prompt version cannot be found
        
    Examples:
        >>> # Get default version (V1 unless env var set)
        >>> prompt = get_versioned_prompt("DIAGNOSIS_SYSTEM_PROMPT", context=globals())
        
        >>> # Get specific version
        >>> prompt = get_versioned_prompt("DIAGNOSIS_SYSTEM_PROMPT", version="V2", context=globals())
        
        >>> # Set version via environment
        >>> os.environ["REFINERY_PROMPT_VERSION"] = "V2"
        >>> prompt = get_versioned_prompt("DIAGNOSIS_SYSTEM_PROMPT", context=globals())
    """
    if context is None:
        raise ValueError("Context (globals()) must be provided to access prompt definitions")
    
    # Determine version to use
    if version is None:
        # Check for prompt-specific override first
        specific_env = f"{base_name}_VERSION"
        version = os.getenv(specific_env)
        
        if version:
            logger.info(f"Using version {version} for {base_name} from env var {specific_env}")
        else:
            # Fall back to global version setting
            version = os.getenv("REFINERY_PROMPT_VERSION", "V1")
            logger.debug(f"Using default version {version} for {base_name}")
    
    # Ensure version has V prefix
    if not version.startswith("V"):
        version = f"V{version}"
    
    # Try to get the versioned prompt
    prompt_name = f"{base_name}_{version}"
    
    if prompt_name in context:
        logger.debug(f"Found prompt {prompt_name}")
        return context[prompt_name]
    
    # Try fallback to V1 if requested version not found
    if version != "V1":
        fallback_name = f"{base_name}_V1"
        if fallback_name in context:
            logger.warning(
                f"Prompt {prompt_name} not found, falling back to {fallback_name}"
            )
            return context[fallback_name]
    
    # List available versions for helpful error message
    available = [
        key.replace(f"{base_name}_", "") 
        for key in context.keys() 
        if key.startswith(f"{base_name}_V")
    ]
    
    if available:
        raise ValueError(
            f"Prompt {base_name} version {version} not found. "
            f"Available versions: {', '.join(sorted(available))}"
        )
    else:
        raise ValueError(
            f"No versioned prompts found for {base_name}. "
            f"Expected format: {base_name}_V1, {base_name}_V2, etc."
        )


def list_prompt_versions(base_name: str, context: Optional[Dict[str, Any]] = None) -> list:
    """
    List all available versions of a prompt.
    
    Args:
        base_name: Prompt name without version suffix
        context: The globals() dict from the calling module
        
    Returns:
        List of available version strings (e.g., ["V1", "V2"])
        
    Examples:
        >>> versions = list_prompt_versions("DIAGNOSIS_SYSTEM_PROMPT", context=globals())
        >>> print(f"Available versions: {versions}")
    """
    if context is None:
        return []
    
    versions = []
    for key in context.keys():
        if key.startswith(f"{base_name}_V"):
            version = key.replace(f"{base_name}_", "")
            if version[0] == "V" and version[1:].isdigit():
                versions.append(version)
    
    return sorted(versions)


def get_current_version(base_name: str) -> str:
    """
    Get the current version that would be used for a prompt.
    
    Args:
        base_name: Prompt name without version suffix
        
    Returns:
        The version string that would be used (e.g., "V1", "V2")
        
    Examples:
        >>> current = get_current_version("DIAGNOSIS_SYSTEM_PROMPT")
        >>> print(f"Currently using version: {current}")
    """
    # Check for prompt-specific override
    specific_env = f"{base_name}_VERSION"
    version = os.getenv(specific_env)
    
    if version:
        if not version.startswith("V"):
            version = f"V{version}"
        return version
    
    # Fall back to global version
    version = os.getenv("REFINERY_PROMPT_VERSION", "V1")
    if not version.startswith("V"):
        version = f"V{version}"
    
    return version


# Version migration helper
def migrate_prompt_to_versioned(
    module_globals: Dict[str, Any],
    prompt_names: list,
    default_version: str = "V1"
) -> None:
    """
    Helper to migrate existing prompts to versioned format.
    
    This function helps transition from non-versioned prompts to versioned ones
    by creating _V1 versions and setting up compatibility.
    
    Args:
        module_globals: The globals() dict from the module
        prompt_names: List of prompt names to migrate
        default_version: Version to assign to existing prompts
        
    Examples:
        >>> # In a module with existing prompts
        >>> migrate_prompt_to_versioned(
        ...     globals(),
        ...     ["DIAGNOSIS_SYSTEM_PROMPT", "TRACE_ANALYSIS_PROMPT"]
        ... )
    """
    for name in prompt_names:
        if name in module_globals and f"{name}_{default_version}" not in module_globals:
            # Create versioned copy
            module_globals[f"{name}_{default_version}"] = module_globals[name]
            logger.info(f"Created {name}_{default_version} from existing {name}")