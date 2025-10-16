"""Simple code reader for finding and analyzing prompt/eval files in customer codebases."""

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# File patterns for different types
PROMPT_PATTERNS = ["*prompt*", "*template*", "system_*", "user_*", "instruction*"]

EVAL_PATTERNS = ["*eval*", "*test*", "*validation*", "*assess*"]

CONFIG_PATTERNS = ["config*", "setting*", ".env", "*.yaml", "*.json"]

# Common variable patterns
VARIABLE_PATTERNS = [
    r"\{\w+\}",  # {variable}
    r"\{\{\w+\}\}",  # {{variable}}
    r"\$\{\w+\}",  # ${variable}
    r'f["\'].*\{.*\}.*["\']',  # f-strings
]

# File size limit
MAX_FILE_SIZE = 1024 * 1024  # 1MB


@dataclass
class SimplePromptInfo:
    """Simple representation of a prompt/eval/config file."""

    file_path: str
    content: str
    file_type: str  # prompt, eval, config
    estimated_role: str  # system, user, template, test
    size_chars: int
    contains_variables: bool  # simple check for {}, f"", {{}}


@dataclass
class SimpleAgentContext:
    """Context about a codebase's prompts and evals."""

    codebase_path: str
    prompt_files: Dict[str, SimplePromptInfo] = field(default_factory=dict)
    eval_files: Dict[str, SimplePromptInfo] = field(default_factory=dict)
    config_files: Dict[str, SimplePromptInfo] = field(default_factory=dict)
    summary: str = ""


def _check_contains_variables(content: str) -> bool:
    """Check if content contains any variable patterns."""
    for pattern in VARIABLE_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            return True
    return False


def _estimate_role(file_path: str, content: str) -> str:
    """Estimate the role/purpose of a file from its name and content."""
    path_lower = file_path.lower()
    content_lower = content.lower()[:1000]  # Check first 1000 chars

    # For prompts
    if "system" in path_lower or "system prompt" in content_lower:
        return "system"
    elif "user" in path_lower or "user prompt" in content_lower:
        return "user"
    elif "template" in path_lower:
        return "template"
    elif "instruction" in path_lower:
        return "instruction"

    # For evals
    elif "test" in path_lower or "def test_" in content_lower:
        return "test"
    elif "eval" in path_lower:
        return "evaluation"
    elif "benchmark" in path_lower:
        return "benchmark"
    elif "validation" in path_lower:
        return "validation"

    # For configs
    elif "config" in path_lower:
        return "configuration"
    elif ".env" in path_lower:
        return "environment"
    elif path_lower.endswith((".yaml", ".yml", ".json")):
        # Check if it contains model/llm configuration
        if any(
            term in content_lower
            for term in ["model", "llm", "openai", "anthropic", "gpt"]
        ):
            return "model_config"
        return "configuration"

    return "unknown"


def _read_file_safely(file_path: str) -> Optional[str]:
    """Read a file safely, handling encoding issues."""
    try:
        # Check file size first
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            logger.warning(f"Skipping large file: {file_path} ({file_size} bytes)")
            return None

        # Try common encodings
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
        for encoding in encodings:
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                return content
            except UnicodeDecodeError:
                continue

        logger.error(f"Could not decode file with any common encoding: {file_path}")
        return None

    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        return None


async def find_prompt_files(codebase_path: str) -> List[str]:
    """Find all prompt-related files in the codebase."""
    return await _find_files_by_patterns(codebase_path, PROMPT_PATTERNS)


async def find_eval_files(codebase_path: str) -> List[str]:
    """Find all eval-related files in the codebase."""
    return await _find_files_by_patterns(codebase_path, EVAL_PATTERNS)


async def find_config_files(codebase_path: str) -> List[str]:
    """Find all config files that might contain model configurations."""
    config_files = await _find_files_by_patterns(codebase_path, CONFIG_PATTERNS)

    # Filter to only model-related configs
    filtered_configs = []
    for file_path in config_files:
        content = _read_file_safely(file_path)
        if content and _is_model_config(content):
            filtered_configs.append(file_path)

    return filtered_configs


def _is_model_config(content: str) -> bool:
    """Check if content likely contains model configuration."""
    model_keywords = [
        "model",
        "llm",
        "openai",
        "anthropic",
        "gpt",
        "claude",
        "temperature",
        "max_tokens",
        "api_key",
    ]
    content_lower = content.lower()
    return any(keyword in content_lower for keyword in model_keywords)


async def _find_files_by_patterns(codebase_path: str, patterns: List[str]) -> List[str]:
    """Find files matching given patterns."""
    found_files = set()
    path = Path(codebase_path)

    # Common directories to skip
    skip_dirs = {
        ".git",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        "env",
        "dist",
        "build",
        ".pytest_cache",
        ".mypy_cache",
    }

    for pattern in patterns:
        try:
            # Use pathlib's rglob for recursive search
            for file_path in path.rglob(pattern):
                # Skip if in ignored directory
                if any(skip_dir in file_path.parts for skip_dir in skip_dirs):
                    continue

                # Skip if not a file
                if not file_path.is_file():
                    continue

                # Skip binary files
                if file_path.suffix in {".pyc", ".pyo", ".so", ".dll", ".exe", ".bin"}:
                    continue

                # Check file size
                if file_path.stat().st_size > MAX_FILE_SIZE:
                    logger.info(f"Skipping large file: {file_path}")
                    continue

                found_files.add(str(file_path.absolute()))

        except Exception as e:
            logger.error(f"Error finding files with pattern {pattern}: {e}")

    return list(found_files)


async def analyze_file(file_path: str) -> SimplePromptInfo:
    """Analyze a single file and extract information."""
    content = _read_file_safely(file_path)

    if content is None:
        logger.warning(f"Could not read file: {file_path}")
        return SimplePromptInfo(
            file_path=file_path,
            content="",
            file_type="unknown",
            estimated_role="error",
            size_chars=0,
            contains_variables=False,
        )

    # Determine file type
    file_type = _classify_file_type(file_path, content)

    # Estimate role
    estimated_role = _estimate_role(file_path, content)

    # Check for variables
    contains_variables = _check_contains_variables(content)

    return SimplePromptInfo(
        file_path=file_path,
        content=content,
        file_type=file_type,
        estimated_role=estimated_role,
        size_chars=len(content),
        contains_variables=contains_variables,
    )


def _classify_file_type(file_path: str, content: str) -> str:
    """Classify file as prompt, eval, or config."""
    filename = os.path.basename(file_path).lower()
    content_lower = content.lower()[:1000]

    # Check filename patterns
    if any(pattern in filename for pattern in ["test", "eval", "validation", "assess"]):
        return "eval"

    if any(
        pattern in filename for pattern in ["config", "setting", ".env"]
    ) or filename.endswith((".yaml", ".yml", ".json", ".toml")):
        return "config"

    # Check content patterns
    if "def test_" in content or "assert" in content_lower:
        return "eval"

    # Default to prompt
    return "prompt"


def _generate_summary(context: SimpleAgentContext) -> str:
    """Generate a summary of the found files."""
    summary_parts = [
        f"Codebase analyzed: {context.codebase_path}",
        f"\nPrompt files found: {len(context.prompt_files)}",
    ]

    # Prompt file breakdown
    if context.prompt_files:
        prompt_roles = {}
        for info in context.prompt_files.values():
            role = info.estimated_role
            prompt_roles[role] = prompt_roles.get(role, 0) + 1

        summary_parts.append("  Breakdown:")
        for role, count in sorted(prompt_roles.items()):
            summary_parts.append(f"    - {role}: {count}")

    # Eval file breakdown
    summary_parts.append(f"\nEval files found: {len(context.eval_files)}")
    if context.eval_files:
        eval_roles = {}
        for info in context.eval_files.values():
            role = info.estimated_role
            eval_roles[role] = eval_roles.get(role, 0) + 1

        summary_parts.append("  Breakdown:")
        for role, count in sorted(eval_roles.items()):
            summary_parts.append(f"    - {role}: {count}")

    # Config files
    summary_parts.append(f"\nConfig files found: {len(context.config_files)}")
    model_configs = sum(
        1
        for info in context.config_files.values()
        if info.estimated_role == "model_config"
    )
    if model_configs:
        summary_parts.append(f"  - Model configurations: {model_configs}")

    # Variable usage
    files_with_vars = sum(
        1
        for info in list(context.prompt_files.values())
        + list(context.eval_files.values())
        if info.contains_variables
    )
    if files_with_vars:
        summary_parts.append(f"\nFiles with variables/templates: {files_with_vars}")

    return "\n".join(summary_parts)


async def build_simple_context(codebase_path: str) -> SimpleAgentContext:
    """Build a simple context of the codebase's prompts and evals."""
    if not os.path.exists(codebase_path):
        raise ValueError(f"Codebase path does not exist: {codebase_path}")

    context = SimpleAgentContext(codebase_path=codebase_path)

    # Find all files
    logger.info(f"Searching for files in {codebase_path}")

    prompt_files, eval_files, config_files = await asyncio.gather(
        find_prompt_files(codebase_path),
        find_eval_files(codebase_path),
        find_config_files(codebase_path),
    )

    logger.info(
        f"Found {len(prompt_files)} prompt files, {len(eval_files)} eval files, "
        f"{len(config_files)} config files"
    )

    # Analyze files in parallel
    all_tasks = []

    # Analyze prompt files
    for file_path in prompt_files:
        task = analyze_file(file_path)
        all_tasks.append(("prompt", file_path, task))

    # Analyze eval files
    for file_path in eval_files:
        task = analyze_file(file_path)
        all_tasks.append(("eval", file_path, task))

    # Analyze config files
    for file_path in config_files:
        task = analyze_file(file_path)
        all_tasks.append(("config", file_path, task))

    # Process all analyses
    results = await asyncio.gather(*[task for _, _, task in all_tasks])

    # Store results
    for i, (file_type, file_path, _) in enumerate(all_tasks):
        result = results[i]

        if file_type == "prompt":
            context.prompt_files[file_path] = result
        elif file_type == "eval":
            context.eval_files[file_path] = result
        elif file_type == "config":
            context.config_files[file_path] = result

    # Generate summary
    context.summary = _generate_summary(context)

    return context
