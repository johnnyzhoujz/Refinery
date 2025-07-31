"""
Context persistence for Refinery.

This module manages the persistent context that Refinery uses across runs,
storing which files to analyze for each project to avoid repetitive input.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import structlog

logger = structlog.get_logger(__name__)

CONTEXT_VERSION = "1.0"
CONTEXT_DIR = ".refinery"
CONTEXT_FILE = "context.json"


class RefineryContext:
    """Manages persistent context for Refinery projects."""
    
    def __init__(self, codebase_path: str):
        self.codebase_path = Path(codebase_path).resolve()
        self.context_dir = self.codebase_path / CONTEXT_DIR
        self.context_file = self.context_dir / CONTEXT_FILE
        self._ensure_context_dir()
    
    def _ensure_context_dir(self) -> None:
        """Ensure the context directory exists."""
        self.context_dir.mkdir(exist_ok=True)
        
        # Create .gitignore if it doesn't exist
        gitignore_path = self.context_dir / ".gitignore"
        if not gitignore_path.exists():
            gitignore_path.write_text("# Refinery context files\n# Uncomment the next line to ignore context\n# context.json\n")
    
    def _load_all_contexts(self) -> Dict[str, Any]:
        """Load all project contexts from file."""
        if not self.context_file.exists():
            return {"version": CONTEXT_VERSION, "projects": {}}
        
        try:
            with open(self.context_file, 'r') as f:
                data = json.load(f)
                
            # Handle version migration if needed
            if data.get("version") != CONTEXT_VERSION:
                logger.warning("Context version mismatch, migrating", 
                             old_version=data.get("version"), 
                             new_version=CONTEXT_VERSION)
                # In future, add migration logic here
                
            return data
        except (json.JSONDecodeError, KeyError) as e:
            logger.error("Failed to load context file, starting fresh", error=str(e))
            return {"version": CONTEXT_VERSION, "projects": {}}
    
    def _save_all_contexts(self, data: Dict[str, Any]) -> None:
        """Save all project contexts to file."""
        try:
            with open(self.context_file, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info("Saved context", file=str(self.context_file))
        except Exception as e:
            logger.error("Failed to save context", error=str(e))
            raise
    
    def _normalize_paths(self, paths: List[str]) -> List[str]:
        """Convert paths to relative paths from codebase root."""
        normalized = []
        for path in paths:
            abs_path = Path(path).resolve()
            try:
                rel_path = abs_path.relative_to(self.codebase_path)
                normalized.append(str(rel_path))
            except ValueError:
                # Path is outside codebase, store as absolute
                logger.warning("Path outside codebase, storing as absolute", path=path)
                normalized.append(str(abs_path))
        return normalized
    
    def _validate_paths(self, paths: List[str]) -> tuple[List[str], List[str]]:
        """Validate that paths exist and return (valid, missing)."""
        valid = []
        missing = []
        
        for path in paths:
            full_path = self.codebase_path / path
            if full_path.exists():
                valid.append(path)
            else:
                missing.append(path)
                
        return valid, missing
    
    def get_project_context(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Get context for a specific project."""
        all_contexts = self._load_all_contexts()
        return all_contexts.get("projects", {}).get(project_name)
    
    def create_or_update_context(
        self,
        project_name: str,
        prompt_files: Optional[List[str]] = None,
        eval_files: Optional[List[str]] = None,
        config_files: Optional[List[str]] = None,
        append: bool = False,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Create or update context for a project."""
        all_contexts = self._load_all_contexts()
        
        # Get existing project context or create new
        project_context = all_contexts.get("projects", {}).get(project_name, {
            "prompt_files": [],
            "eval_files": [],
            "config_files": [],
            "metadata": {}
        })
        
        # Update file lists
        if prompt_files is not None:
            normalized = self._normalize_paths(prompt_files)
            if append:
                # Add to existing, avoiding duplicates
                existing = set(project_context.get("prompt_files", []))
                project_context["prompt_files"] = list(existing.union(normalized))
            else:
                project_context["prompt_files"] = normalized
        
        if eval_files is not None:
            normalized = self._normalize_paths(eval_files)
            if append:
                existing = set(project_context.get("eval_files", []))
                project_context["eval_files"] = list(existing.union(normalized))
            else:
                project_context["eval_files"] = normalized
        
        if config_files is not None:
            normalized = self._normalize_paths(config_files)
            if append:
                existing = set(project_context.get("config_files", []))
                project_context["config_files"] = list(existing.union(normalized))
            else:
                project_context["config_files"] = normalized
        
        # Update metadata
        project_context["metadata"]["last_updated"] = datetime.now().isoformat()
        if metadata:
            project_context["metadata"].update(metadata)
        
        # Save back
        if "projects" not in all_contexts:
            all_contexts["projects"] = {}
        all_contexts["projects"][project_name] = project_context
        self._save_all_contexts(all_contexts)
        
        logger.info("Updated context", 
                   project=project_name,
                   prompt_files=len(project_context["prompt_files"]),
                   eval_files=len(project_context["eval_files"]))
        
        return project_context
    
    def remove_files(
        self,
        project_name: str,
        prompt_files: Optional[List[str]] = None,
        eval_files: Optional[List[str]] = None,
        config_files: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Remove specific files from project context."""
        context = self.get_project_context(project_name)
        if not context:
            raise ValueError(f"No context found for project: {project_name}")
        
        # Remove specified files
        if prompt_files:
            normalized = self._normalize_paths(prompt_files)
            context["prompt_files"] = [f for f in context.get("prompt_files", []) 
                                      if f not in normalized]
        
        if eval_files:
            normalized = self._normalize_paths(eval_files)
            context["eval_files"] = [f for f in context.get("eval_files", []) 
                                    if f not in normalized]
        
        if config_files:
            normalized = self._normalize_paths(config_files)
            context["config_files"] = [f for f in context.get("config_files", []) 
                                      if f not in normalized]
        
        # Update and save
        return self.create_or_update_context(
            project_name,
            prompt_files=context["prompt_files"],
            eval_files=context["eval_files"],
            config_files=context["config_files"],
            append=False
        )
    
    def validate_and_clean_context(self, project_name: str) -> Dict[str, Any]:
        """Validate stored paths exist and remove missing ones."""
        context = self.get_project_context(project_name)
        if not context:
            raise ValueError(f"No context found for project: {project_name}")
        
        # Check each file type
        all_missing = []
        cleaned_context = context.copy()
        
        for file_type in ["prompt_files", "eval_files", "config_files"]:
            files = context.get(file_type, [])
            valid, missing = self._validate_paths(files)
            
            if missing:
                logger.warning(f"Found missing {file_type}", 
                             missing_files=missing,
                             project=project_name)
                all_missing.extend(missing)
                cleaned_context[file_type] = valid
        
        # Update context if files were removed
        if all_missing:
            self.create_or_update_context(
                project_name,
                prompt_files=cleaned_context["prompt_files"],
                eval_files=cleaned_context["eval_files"],
                config_files=cleaned_context["config_files"],
                append=False
            )
            
        return {
            "context": cleaned_context,
            "missing_files": all_missing
        }
    
    def clear_project_context(self, project_name: str) -> None:
        """Clear context for a specific project."""
        all_contexts = self._load_all_contexts()
        if "projects" in all_contexts and project_name in all_contexts["projects"]:
            del all_contexts["projects"][project_name]
            self._save_all_contexts(all_contexts)
            logger.info("Cleared context", project=project_name)
    
    def list_projects(self) -> List[str]:
        """List all projects with saved contexts."""
        all_contexts = self._load_all_contexts()
        return list(all_contexts.get("projects", {}).keys())
    
    def get_file_paths(self, project_name: str) -> Dict[str, List[str]]:
        """Get absolute file paths for a project."""
        context = self.get_project_context(project_name)
        if not context:
            return {"prompt_files": [], "eval_files": [], "config_files": []}
        
        # Convert relative paths back to absolute
        result = {}
        for file_type in ["prompt_files", "eval_files", "config_files"]:
            result[file_type] = []
            for rel_path in context.get(file_type, []):
                if os.path.isabs(rel_path):
                    # Already absolute (file was outside codebase)
                    result[file_type].append(rel_path)
                else:
                    # Convert to absolute
                    abs_path = self.codebase_path / rel_path
                    result[file_type].append(str(abs_path))
        
        return result


def load_or_create_context(codebase_path: str, project_name: str) -> tuple[Dict[str, Any], bool]:
    """Load existing context or return empty context.
    
    Returns:
        (context, exists) - context dict and whether it already existed
    """
    manager = RefineryContext(codebase_path)
    context = manager.get_project_context(project_name)
    
    if context:
        # Validate and clean
        validation_result = manager.validate_and_clean_context(project_name)
        return validation_result["context"], True
    else:
        return {
            "prompt_files": [],
            "eval_files": [],
            "config_files": [],
            "metadata": {}
        }, False