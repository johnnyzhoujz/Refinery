import asyncio
from pathlib import Path
import os
from refinery.core.context import RefineryContext


def run_async(coro):
    """Simple async wrapper for Streamlit."""
    return asyncio.run(coro)


def load_context_json():
    """Load existing context.json if available (Option B)."""
    try:
        context_file = Path(os.getcwd()) / ".refinery" / "context.json"
        if context_file.exists():
            import json
            with open(context_file) as f:
                return json.load(f)
    except Exception:
        pass  # Silently ignore and proceed with defaults
    return {}


def load_project_context_for_trace(project_name: str) -> dict:
    """Load project context with actual file contents for a trace."""
    context_manager = RefineryContext(os.getcwd())
    project_context = context_manager.get_project_context(project_name)
    
    if not project_context:
        return {"prompt_files": {}, "eval_files": {}}
    
    # Load actual file contents
    prompt_contents = {}
    eval_contents = {}
    
    # Load prompt files
    for prompt_file in project_context.get("prompt_files", []):
        try:
            with open(prompt_file, 'r', encoding='utf-8') as f:
                prompt_contents[prompt_file] = f.read()
        except Exception:
            pass  # Skip files that can't be read
    
    # Load eval files  
    for eval_file in project_context.get("eval_files", []):
        try:
            with open(eval_file, 'r', encoding='utf-8') as f:
                eval_contents[eval_file] = f.read()
        except Exception:
            pass  # Skip files that can't be read
    
    return {
        "prompt_files": prompt_contents,
        "eval_files": eval_contents
    }