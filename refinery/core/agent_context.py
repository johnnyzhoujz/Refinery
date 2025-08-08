"""Agent context management for Refinery.

This module provides ways to gather context about the agent being analyzed,
including prompts, evals, configuration, and implementation details.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class AgentContext:
    """Complete context about an agent implementation."""
    # Source information
    source_type: str  # "trace", "local", "remote", "package"
    source_path: Optional[str] = None
    
    # Prompts
    system_prompts: Dict[str, str] = None  # name -> content
    user_templates: Dict[str, str] = None  # name -> template
    
    # Evaluations
    eval_cases: List[Dict[str, Any]] = None
    test_files: Dict[str, str] = None  # path -> content
    
    # Configuration
    model_config: Dict[str, Any] = None
    tool_definitions: List[Dict[str, Any]] = None
    
    # Implementation
    agent_type: str = None  # "langchain", "custom", "crewai", etc.
    entry_point: str = None
    dependencies: List[str] = None
    
    # Metadata
    version: str = None
    last_updated: str = None
    

class AgentContextBuilder:
    """Builds comprehensive agent context from multiple sources."""
    
    def __init__(self):
        self.context = AgentContext(source_type="unknown")
    
    async def build_from_trace(self, trace, langsmith_client) -> AgentContext:
        """Build context from a LangSmith trace."""
        logger.info("Building context from trace", trace_id=trace.trace_id)
        
        # Extract prompts from trace
        extracted = langsmith_client.extract_prompts_from_trace(trace)
        
        self.context = AgentContext(
            source_type="trace",
            source_path=trace.trace_id,
            system_prompts={
                f"system_{i}": prompt["content"] 
                for i, prompt in enumerate(extracted.get("system_prompts", []))
            },
            user_templates={
                f"user_{i}": prompt["content"]
                for i, prompt in enumerate(extracted.get("user_prompts", []))
            },
            model_config=extracted.get("model_configs", [{}])[0] if extracted.get("model_configs") else {},
            agent_type=self._detect_agent_type(trace)
        )
        
        return self.context
    
    async def build_from_directory(self, directory: str) -> AgentContext:
        """Build context from a local directory."""
        logger.info("Building context from directory", path=directory)
        
        # Look for common agent patterns
        context = AgentContext(
            source_type="local",
            source_path=directory,
            system_prompts={},
            user_templates={},
            test_files={},
            eval_cases=[]
        )
        
        # Find prompt files
        prompt_patterns = ["*prompt*.txt", "*prompt*.md", "*system*.txt", "*template*"]
        for pattern in prompt_patterns:
            for file_path in Path(directory).rglob(pattern):
                if file_path.is_file():
                    content = file_path.read_text()
                    name = file_path.stem
                    
                    if "system" in name.lower():
                        context.system_prompts[name] = content
                    else:
                        context.user_templates[name] = content
        
        # Find eval/test files
        test_patterns = ["*test*.py", "*eval*.py", "*test*.json", "*eval*.json"]
        for pattern in test_patterns:
            for file_path in Path(directory).rglob(pattern):
                if file_path.is_file():
                    content = file_path.read_text()
                    context.test_files[str(file_path.relative_to(directory))] = content
                    
                    # Try to extract test cases from Python files
                    if file_path.suffix == ".py":
                        test_cases = self._extract_test_cases_from_python(content)
                        context.eval_cases.extend(test_cases)
        
        # Detect agent type from files
        context.agent_type = self._detect_agent_type_from_files(directory)
        
        return context
    
    async def build_from_package(self, package_path: str) -> AgentContext:
        """Build context from an agent package (e.g., refinery.json)."""
        logger.info("Building context from package", path=package_path)
        
        with open(package_path, 'r') as f:
            package_data = json.load(f)
        
        return AgentContext(
            source_type="package",
            source_path=package_path,
            system_prompts=package_data.get("prompts", {}).get("system", {}),
            user_templates=package_data.get("prompts", {}).get("user", {}),
            eval_cases=package_data.get("evals", []),
            model_config=package_data.get("model_config", {}),
            tool_definitions=package_data.get("tools", []),
            agent_type=package_data.get("agent_type", "unknown"),
            dependencies=package_data.get("dependencies", []),
            version=package_data.get("version", "unknown")
        )
    
    async def build_from_github(self, repo_url: str, branch: str = "main") -> AgentContext:
        """Build context from a GitHub repository."""
        # This would clone the repo and analyze it
        # For now, just a placeholder
        raise NotImplementedError("GitHub context building not yet implemented")
    
    def merge_contexts(self, *contexts: AgentContext) -> AgentContext:
        """Merge multiple contexts, with later ones taking precedence."""
        merged = AgentContext(source_type="merged")
        
        for context in contexts:
            # Merge prompts
            if context.system_prompts:
                if not merged.system_prompts:
                    merged.system_prompts = {}
                merged.system_prompts.update(context.system_prompts)
            
            if context.user_templates:
                if not merged.user_templates:
                    merged.user_templates = {}
                merged.user_templates.update(context.user_templates)
            
            # Merge evals
            if context.eval_cases:
                if not merged.eval_cases:
                    merged.eval_cases = []
                merged.eval_cases.extend(context.eval_cases)
            
            # Take latest config
            if context.model_config:
                merged.model_config = context.model_config
            
            # Update metadata
            if context.agent_type and context.agent_type != "unknown":
                merged.agent_type = context.agent_type
        
        return merged
    
    def _detect_agent_type(self, trace) -> str:
        """Detect agent type from trace patterns."""
        run_names = [run.name.lower() for run in trace.runs]
        
        if any("langchain" in name for name in run_names):
            return "langchain"
        elif any("crew" in name for name in run_names):
            return "crewai"
        elif any("autogen" in name for name in run_names):
            return "autogen"
        else:
            return "custom"
    
    def _detect_agent_type_from_files(self, directory: str) -> str:
        """Detect agent type from file patterns."""
        files = list(Path(directory).rglob("*.py"))
        
        for file_path in files:
            content = file_path.read_text()
            if "from langchain" in content or "import langchain" in content:
                return "langchain"
            elif "from crewai" in content or "import crewai" in content:
                return "crewai"
            elif "from autogen" in content or "import autogen" in content:
                return "autogen"
        
        return "custom"
    
    def _extract_test_cases_from_python(self, content: str) -> List[Dict[str, Any]]:
        """Extract test cases from Python test files."""
        test_cases = []
        
        # Simple regex to find test functions and their docstrings
        import re
        test_pattern = r'def (test_\w+)\([^)]*\):\s*"""([^"]+)"""'
        
        for match in re.finditer(test_pattern, content):
            test_name = match.group(1)
            test_doc = match.group(2).strip()
            
            test_cases.append({
                "name": test_name,
                "description": test_doc,
                "type": "unit_test"
            })
        
        return test_cases


class AgentContextResolver:
    """Resolves agent context using multiple strategies."""
    
    def __init__(self, codebase_path: str):
        self.codebase_path = codebase_path
        self.builder = AgentContextBuilder()
    
    async def resolve_context(
        self,
        trace=None,
        langsmith_client=None,
        local_path: Optional[str] = None,
        package_path: Optional[str] = None,
        auto_detect: bool = True
    ) -> AgentContext:
        """Resolve agent context using available sources."""
        contexts = []
        
        # 1. Always try to extract from trace if available
        if trace and langsmith_client:
            trace_context = await self.builder.build_from_trace(trace, langsmith_client)
            contexts.append(trace_context)
            logger.info("Extracted context from trace", 
                       prompts=len(trace_context.system_prompts or {}))
        
        # 2. Check for local agent files
        if local_path and os.path.exists(local_path):
            local_context = await self.builder.build_from_directory(local_path)
            contexts.append(local_context)
            logger.info("Loaded context from local files", 
                       prompts=len(local_context.system_prompts or {}))
        
        # 3. Check for agent package file
        if package_path and os.path.exists(package_path):
            package_context = await self.builder.build_from_package(package_path)
            contexts.append(package_context)
            logger.info("Loaded context from package")
        
        # 4. Auto-detect in current directory
        if auto_detect and not local_path:
            # Look for .refinery/agent.json
            auto_package = os.path.join(self.codebase_path, ".refinery", "agent.json")
            if os.path.exists(auto_package):
                auto_context = await self.builder.build_from_package(auto_package)
                contexts.append(auto_context)
                logger.info("Auto-detected agent package")
        
        # Merge all contexts
        if contexts:
            final_context = self.builder.merge_contexts(*contexts)
            logger.info("Resolved agent context", 
                       sources=len(contexts),
                       total_prompts=len(final_context.system_prompts or {}) + 
                                    len(final_context.user_templates or {}))
            return final_context
        else:
            logger.warning("No agent context found")
            return AgentContext(source_type="none")