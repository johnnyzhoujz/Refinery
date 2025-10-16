"""
Safe code editing and Git integration utilities.

This module provides a production-ready implementation of the CodeManager interface
with comprehensive safety features, AST parsing, and Git integration.
"""

import ast
import difflib
import hashlib
import json
import os
import re
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import git
import structlog
import yaml
from filelock import FileLock

from ..core.interfaces import CodeManager
from ..core.models import (
    ChangeType,
    CodeContext,
    Confidence,
    FileChange,
    ImpactReport,
    ValidationResult,
)
from ..utils.config import config

logger = structlog.get_logger(__name__)


class SafeCodeManager(CodeManager):
    """Safe implementation of CodeManager with Git integration and rollback capability."""

    def __init__(self, repository_path: Optional[str] = None):
        """Initialize the code manager.

        Args:
            repository_path: Path to the Git repository. If None, uses current directory.
        """
        self.repository_path = Path(repository_path or os.getcwd())
        self._validate_repository()
        self.repo = git.Repo(self.repository_path)
        self._lock_manager = LockManager(self.repository_path)
        self._import_cache: Dict[str, Set[str]] = {}
        self._ast_cache: Dict[str, ast.AST] = {}

    def _validate_repository(self) -> None:
        """Validate that we're working with a valid Git repository."""
        if not self.repository_path.exists():
            raise ValueError(f"Repository path does not exist: {self.repository_path}")

        try:
            git.Repo(self.repository_path)
        except git.InvalidGitRepositoryError:
            raise ValueError(f"Not a valid Git repository: {self.repository_path}")

    async def analyze_codebase(self, path: str) -> CodeContext:
        """Analyze the codebase structure.

        Args:
            path: Path to analyze (relative to repository root)

        Returns:
            CodeContext with codebase information
        """
        full_path = self.repository_path / path
        if not full_path.exists():
            raise ValueError(f"Path does not exist: {full_path}")

        logger.info("Analyzing codebase", path=path)

        # Determine main language
        language_counts = defaultdict(int)
        relevant_files = []

        for file_path in self._find_code_files(full_path):
            ext = file_path.suffix.lower()
            if ext == ".py":
                language_counts["python"] += 1
            elif ext in [".js", ".jsx", ".ts", ".tsx"]:
                language_counts["javascript"] += 1
            elif ext in [".java"]:
                language_counts["java"] += 1
            elif ext in [".go"]:
                language_counts["go"] += 1

            relevant_files.append(str(file_path.relative_to(self.repository_path)))

        main_language = (
            max(language_counts.items(), key=lambda x: x[1])[0]
            if language_counts
            else "python"
        )

        # Extract dependencies
        dependencies = {}
        if main_language == "python":
            dependencies = await self._extract_python_dependencies(full_path)

        # Detect framework
        framework = await self._detect_framework(full_path, main_language)

        return CodeContext(
            repository_path=str(self.repository_path),
            main_language=main_language,
            framework=framework,
            relevant_files=relevant_files[:100],  # Limit to avoid huge contexts
            dependencies=dependencies,
        )

    async def get_related_files(self, file_path: str) -> List[str]:
        """Find files related to the target file.

        Args:
            file_path: Path to the file (relative to repository root)

        Returns:
            List of related file paths
        """
        full_path = self.repository_path / file_path
        if not full_path.exists():
            return []

        logger.info("Finding related files", file_path=file_path)

        related = set()

        # For Python files, analyze imports
        if full_path.suffix == ".py":
            # Get imports from this file
            imports = await self._get_python_imports(full_path)
            related.update(imports)

            # Find files that import this module
            module_name = self._path_to_module(file_path)
            for py_file in self._find_code_files(self.repository_path, pattern="*.py"):
                if py_file == full_path:
                    continue

                file_imports = await self._get_python_imports(py_file)
                if module_name in file_imports or file_path in file_imports:
                    related.add(str(py_file.relative_to(self.repository_path)))

        # Add test files
        test_files = self._find_test_files(file_path)
        related.update(test_files)

        # Add configuration files if this is a config-related file
        if "config" in file_path.lower() or "settings" in file_path.lower():
            for config_file in self._find_config_files():
                related.add(config_file)

        return sorted(list(related))

    async def validate_change(self, change: FileChange) -> ValidationResult:
        """Validate a proposed change.

        Args:
            change: The proposed file change

        Returns:
            ValidationResult with validation details
        """
        logger.info("Validating change", file_path=change.file_path)

        issues = []
        warnings = []

        # Check file size
        if len(change.new_content.encode("utf-8")) > config.max_file_size_kb * 1024:
            issues.append(f"File size exceeds limit of {config.max_file_size_kb}KB")

        # Check for credentials/secrets
        secret_patterns = [
            r'(?i)(api[_-]?key|apikey|secret|password|pwd|token|bearer)\s*[:=]\s*["\']?[A-Za-z0-9+/]{20,}',
            r"(?i)(aws[_-]?access[_-]?key[_-]?id|aws[_-]?secret[_-]?access[_-]?key)\s*[:=]",
            r"(?i)private[_-]?key\s*[:=]",
            r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
        ]

        for pattern in secret_patterns:
            if re.search(pattern, change.new_content):
                issues.append("Potential credential or secret detected in change")
                break

        # Language-specific validation
        file_path = Path(change.file_path)
        if file_path.suffix == ".py":
            py_issues, py_warnings = await self._validate_python_change(change)
            issues.extend(py_issues)
            warnings.extend(py_warnings)
        elif file_path.suffix in [".yaml", ".yml"]:
            yaml_issues = await self._validate_yaml_change(change)
            issues.extend(yaml_issues)
        elif file_path.suffix == ".json":
            json_issues = await self._validate_json_change(change)
            issues.extend(json_issues)

        # Check for breaking changes
        if change.original_content:
            breaking_changes = await self._check_breaking_changes(change)
            warnings.extend(breaking_changes)

        return ValidationResult(
            is_valid=len(issues) == 0, issues=issues, warnings=warnings
        )

    async def analyze_impact(self, changes: List[FileChange]) -> ImpactReport:
        """Analyze the impact of proposed changes.

        Args:
            changes: List of proposed changes

        Returns:
            ImpactReport with impact analysis
        """
        logger.info("Analyzing impact", num_changes=len(changes))

        affected_files = set()
        potential_breaking_changes = []
        suggested_tests = []

        for change in changes:
            # Add the changed file
            affected_files.add(change.file_path)

            # Find related files
            related = await self.get_related_files(change.file_path)
            affected_files.update(related)

            # Analyze breaking changes
            if change.change_type == ChangeType.ORCHESTRATION_SUGGESTION:
                potential_breaking_changes.append(
                    f"Orchestration change in {change.file_path} may affect execution flow"
                )

            # Language-specific impact analysis
            file_path = Path(change.file_path)
            if file_path.suffix == ".py":
                py_impact = await self._analyze_python_impact(change, related)
                potential_breaking_changes.extend(py_impact["breaking_changes"])
                suggested_tests.extend(py_impact["tests"])

        # Determine confidence based on impact
        confidence = Confidence.HIGH
        if len(potential_breaking_changes) > 5:
            confidence = Confidence.LOW
        elif len(potential_breaking_changes) > 2:
            confidence = Confidence.MEDIUM

        # Add general test suggestions
        if not suggested_tests:
            suggested_tests = [
                "Run existing test suite",
                "Manual testing of affected features",
                "Integration tests for changed components",
            ]

        return ImpactReport(
            affected_files=sorted(list(affected_files)),
            potential_breaking_changes=potential_breaking_changes,
            suggested_tests=suggested_tests,
            confidence=confidence,
        )

    async def apply_changes(
        self, changes: List[FileChange], message: str
    ) -> Dict[str, Any]:
        """Apply changes with Git integration.

        Args:
            changes: List of changes to apply
            message: Commit message

        Returns:
            Dictionary with results including commit ID
        """
        if not changes:
            return {"status": "no_changes", "message": "No changes to apply"}

        logger.info("Applying changes", num_changes=len(changes), message=message)

        # Validate all changes first
        validation_results = []
        for change in changes:
            result = await self.validate_change(change)
            validation_results.append((change, result))
            if not result.is_valid:
                return {
                    "status": "validation_failed",
                    "errors": {
                        change.file_path: result.issues
                        for change, result in validation_results
                        if not result.is_valid
                    },
                }

        # Create a stash point for rollback
        stash_created = False
        if self.repo.is_dirty():
            self.repo.git.stash("push", "-m", f"Before applying changes: {message}")
            stash_created = True

        try:
            # Apply changes atomically
            applied_files = []
            with self._atomic_changes():
                for change in changes:
                    file_path = self.repository_path / change.file_path

                    # Acquire file lock
                    with self._lock_manager.acquire(change.file_path):
                        # Backup original content
                        original_exists = file_path.exists()
                        file_path.read_text() if original_exists else ""

                        # Create parent directories if needed
                        file_path.parent.mkdir(parents=True, exist_ok=True)

                        # Write new content
                        file_path.write_text(change.new_content)
                        applied_files.append(change.file_path)

                # Stage all changes
                self.repo.index.add(applied_files)

                # Create commit
                commit = self.repo.index.commit(
                    f"{message}\n\nApplied {len(changes)} changes via Refinery"
                )

                logger.info("Changes committed", commit_id=commit.hexsha)

                # Generate summary
                summary = {
                    "status": "success",
                    "commit_id": commit.hexsha,
                    "files_changed": len(applied_files),
                    "files": applied_files,
                    "message": message,
                    "warnings": [],
                }

                # Add any validation warnings
                for change, result in validation_results:
                    if result.warnings:
                        summary["warnings"].extend(
                            [
                                f"{change.file_path}: {warning}"
                                for warning in result.warnings
                            ]
                        )

                return summary

        except Exception as e:
            logger.error("Failed to apply changes", error=str(e))

            # Rollback changes
            if stash_created:
                try:
                    self.repo.git.stash("pop")
                except:
                    pass

            # Hard reset if needed
            self.repo.head.reset(index=True, working_tree=True)

            return {
                "status": "failed",
                "error": str(e),
                "message": "Changes rolled back due to error",
            }

    async def rollback_changes(self, commit_id: str) -> bool:
        """Rollback changes to a previous state.

        Args:
            commit_id: The commit ID to rollback

        Returns:
            True if successful, False otherwise
        """
        logger.info("Rolling back changes", commit_id=commit_id)

        try:
            # Validate commit exists
            try:
                commit = self.repo.commit(commit_id)
            except git.BadName:
                logger.error("Invalid commit ID", commit_id=commit_id)
                return False

            # Create a revert commit
            revert_message = f'Revert "{commit.message.split(chr(10))[0]}"\n\nThis reverts commit {commit_id}'

            # Use git revert
            try:
                self.repo.git.revert(commit_id, "--no-edit")
            except git.GitCommandError:
                # If automatic revert fails, try manual approach
                logger.warning("Automatic revert failed, attempting manual rollback")

                # Get the parent commit
                if commit.parents:
                    parent = commit.parents[0]

                    # Reset to parent and create new commit
                    self.repo.head.reset(parent, index=True, working_tree=True)
                    self.repo.index.commit(revert_message)
                else:
                    logger.error("Cannot rollback initial commit")
                    return False

            logger.info("Successfully rolled back changes", commit_id=commit_id)
            return True

        except Exception as e:
            logger.error("Rollback failed", commit_id=commit_id, error=str(e))
            return False

    # Helper methods

    @contextmanager
    def _atomic_changes(self):
        """Context manager for atomic changes."""
        checkpoint = self.repo.head.commit
        try:
            yield
        except Exception:
            # Reset to checkpoint on any error
            self.repo.head.reset(checkpoint, index=True, working_tree=True)
            raise

    def _find_code_files(self, path: Path, pattern: str = "*") -> List[Path]:
        """Find code files in a directory."""
        code_extensions = {
            ".py",
            ".js",
            ".jsx",
            ".ts",
            ".tsx",
            ".java",
            ".go",
            ".rb",
            ".php",
        }
        exclude_dirs = {
            "__pycache__",
            ".git",
            "node_modules",
            ".venv",
            "venv",
            "dist",
            "build",
        }

        files = []
        for file_path in path.rglob(pattern):
            if file_path.is_file():
                # Skip excluded directories
                if any(excluded in file_path.parts for excluded in exclude_dirs):
                    continue

                # Check extension
                if pattern != "*" or file_path.suffix in code_extensions:
                    files.append(file_path)

        return files

    async def _extract_python_dependencies(self, path: Path) -> Dict[str, str]:
        """Extract Python dependencies from requirements files."""
        dependencies = {}

        # Check common dependency files
        dep_files = [
            "requirements.txt",
            "setup.py",
            "setup.cfg",
            "pyproject.toml",
            "Pipfile",
        ]

        for dep_file in dep_files:
            file_path = path / dep_file
            if file_path.exists():
                try:
                    content = file_path.read_text()

                    if dep_file == "requirements.txt":
                        for line in content.splitlines():
                            line = line.strip()
                            if line and not line.startswith("#"):
                                # Parse package==version
                                match = re.match(
                                    r"^([a-zA-Z0-9\-_]+)([<>=!]+)?(.*)$", line
                                )
                                if match:
                                    pkg, op, ver = match.groups()
                                    dependencies[pkg] = f"{op or ''}{ver or ''}"

                    elif dep_file == "pyproject.toml":
                        # Basic TOML parsing for dependencies
                        in_deps = False
                        for line in content.splitlines():
                            if "[tool.poetry.dependencies]" in line:
                                in_deps = True
                            elif in_deps and line.strip() and not line.startswith("["):
                                match = re.match(
                                    r'^([a-zA-Z0-9\-_]+)\s*=\s*"([^"]+)"', line
                                )
                                if match:
                                    dependencies[match.group(1)] = match.group(2)
                            elif in_deps and line.startswith("["):
                                in_deps = False

                except Exception as e:
                    logger.warning(f"Failed to parse {dep_file}", error=str(e))

        return dependencies

    async def _detect_framework(self, path: Path, language: str) -> Optional[str]:
        """Detect the framework being used."""
        if language == "python":
            # Check for common Python frameworks
            files = list(path.rglob("*.py"))
            file_contents = []
            for f in files[:20]:  # Sample first 20 files
                try:
                    file_contents.append(f.read_text())
                except:
                    pass

            combined = " ".join(file_contents)

            if "from django" in combined or "django" in combined.lower():
                return "django"
            elif "from flask" in combined or "Flask(" in combined:
                return "flask"
            elif "from fastapi" in combined or "FastAPI(" in combined:
                return "fastapi"
            elif "import streamlit" in combined:
                return "streamlit"
            elif "from langchain" in combined or "import langchain" in combined:
                return "langchain"

        return None

    async def _get_python_imports(self, file_path: Path) -> Set[str]:
        """Extract imports from a Python file."""
        cache_key = str(file_path)
        if cache_key in self._import_cache:
            return self._import_cache[cache_key]

        imports = set()

        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module)

            # Convert imports to potential file paths
            file_imports = set()
            for imp in imports:
                # Try to find corresponding file
                potential_paths = [
                    f"{imp.replace('.', '/')}.py",
                    f"{imp.replace('.', '/')}/__init__.py",
                ]

                for pot_path in potential_paths:
                    full_path = self.repository_path / pot_path
                    if full_path.exists():
                        file_imports.add(pot_path)

            self._import_cache[cache_key] = file_imports
            return file_imports

        except Exception as e:
            logger.warning(f"Failed to parse imports from {file_path}", error=str(e))
            return set()

    def _path_to_module(self, file_path: str) -> str:
        """Convert file path to module name."""
        # Remove .py extension and convert / to .
        module = file_path.replace(".py", "").replace("/", ".")

        # Remove __init__ from the end
        if module.endswith(".__init__"):
            module = module[:-9]

        return module

    def _find_test_files(self, file_path: str) -> List[str]:
        """Find test files for a given source file."""
        test_files = []
        file_name = Path(file_path).stem

        # Common test file patterns
        patterns = [
            f"test_{file_name}.py",
            f"{file_name}_test.py",
            f"tests/test_{file_name}.py",
            f"tests/{file_name}_test.py",
            f"test/test_{file_name}.py",
        ]

        for pattern in patterns:
            for test_file in self.repository_path.rglob(pattern):
                rel_path = str(test_file.relative_to(self.repository_path))
                test_files.append(rel_path)

        return test_files

    def _find_config_files(self) -> List[str]:
        """Find configuration files in the repository."""
        config_patterns = [
            "*.yaml",
            "*.yml",
            "*.json",
            "*.toml",
            "*.ini",
            "*.cfg",
            "*.env",
            ".env.*",
            "config.py",
            "settings.py",
            "configuration.py",
        ]

        config_files = []
        for pattern in config_patterns:
            for file_path in self.repository_path.rglob(pattern):
                if ".git" not in file_path.parts:
                    rel_path = str(file_path.relative_to(self.repository_path))
                    config_files.append(rel_path)

        return config_files[:20]  # Limit to avoid too many results

    async def _validate_python_change(
        self, change: FileChange
    ) -> Tuple[List[str], List[str]]:
        """Validate Python-specific changes."""
        issues = []
        warnings = []

        # Try to parse the new content
        try:
            ast.parse(change.new_content)
        except SyntaxError as e:
            issues.append(f"Python syntax error: {e.msg} at line {e.lineno}")
            return issues, warnings

        # Check for common issues
        tree = ast.parse(change.new_content)

        # Check for print statements (might want logging instead)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "print":
                    warnings.append(
                        f"Found print statement at line {node.lineno}. Consider using logging instead."
                    )

        # Check for broad exception handling
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                if node.type is None or (
                    isinstance(node.type, ast.Name) and node.type.id == "Exception"
                ):
                    warnings.append(
                        f"Broad exception handling at line {node.lineno}. Consider catching specific exceptions."
                    )

        # Check imports are at the top
        import_lines = []
        other_lines = []
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                import_lines.append(node.lineno)
            else:
                other_lines.append(node.lineno)

        if import_lines and other_lines and max(import_lines) > min(other_lines):
            warnings.append("Imports should be at the top of the file")

        return issues, warnings

    async def _validate_yaml_change(self, change: FileChange) -> List[str]:
        """Validate YAML changes."""
        issues = []

        try:
            yaml.safe_load(change.new_content)
        except yaml.YAMLError as e:
            issues.append(f"Invalid YAML: {str(e)}")

        return issues

    async def _validate_json_change(self, change: FileChange) -> List[str]:
        """Validate JSON changes."""
        issues = []

        try:
            json.loads(change.new_content)
        except json.JSONDecodeError as e:
            issues.append(f"Invalid JSON: {str(e)}")

        return issues

    async def _check_breaking_changes(self, change: FileChange) -> List[str]:
        """Check for potential breaking changes."""
        warnings = []

        if not change.original_content:
            return warnings

        # For Python files, check for removed functions/classes
        if Path(change.file_path).suffix == ".py":
            try:
                old_tree = ast.parse(change.original_content)
                new_tree = ast.parse(change.new_content)

                old_defs = self._extract_definitions(old_tree)
                new_defs = self._extract_definitions(new_tree)

                removed = old_defs - new_defs
                if removed:
                    warnings.append(f"Removed definitions: {', '.join(removed)}")

                # Check for signature changes
                for name in old_defs & new_defs:
                    old_sig = self._get_function_signature(old_tree, name)
                    new_sig = self._get_function_signature(new_tree, name)
                    if old_sig and new_sig and old_sig != new_sig:
                        warnings.append(f"Function signature changed: {name}")

            except:
                pass

        return warnings

    def _extract_definitions(self, tree: ast.AST) -> Set[str]:
        """Extract function and class definitions from AST."""
        definitions = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                definitions.add(node.name)
            elif isinstance(node, ast.ClassDef):
                definitions.add(node.name)

        return definitions

    def _get_function_signature(self, tree: ast.AST, name: str) -> Optional[str]:
        """Get function signature as string."""
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == name:
                args = []
                for arg in node.args.args:
                    args.append(arg.arg)
                return f"{name}({', '.join(args)})"
        return None

    async def _analyze_python_impact(
        self, change: FileChange, related_files: List[str]
    ) -> Dict[str, List[str]]:
        """Analyze Python-specific impact."""
        breaking_changes = []
        tests = []

        # Check if this is a public API change
        if "api" in change.file_path.lower() or "interface" in change.file_path.lower():
            breaking_changes.append(
                f"API change in {change.file_path} may affect external consumers"
            )

        # Suggest tests based on what changed
        file_name = Path(change.file_path).stem
        tests.extend(
            [
                f"Run unit tests for {file_name}",
                f"Run integration tests involving {file_name}",
            ]
        )

        # If many files are affected, suggest broader testing
        if len(related_files) > 5:
            tests.append("Run full test suite due to wide impact")

        return {"breaking_changes": breaking_changes, "tests": tests}


class LockManager:
    """Manages file locks for concurrent safety."""

    def __init__(self, repository_path: Path):
        self.repository_path = repository_path
        self.lock_dir = repository_path / ".refinery" / "locks"
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._locks: Dict[str, FileLock] = {}

    @contextmanager
    def acquire(self, file_path: str, timeout: float = 10.0):
        """Acquire a lock for a file."""
        lock_path = (
            self.lock_dir / f"{hashlib.md5(file_path.encode()).hexdigest()}.lock"
        )

        if file_path not in self._locks:
            self._locks[file_path] = FileLock(lock_path, timeout=timeout)

        lock = self._locks[file_path]

        try:
            lock.acquire()
            yield
        finally:
            lock.release()


# Helper function for generating diffs
def generate_diff(original: str, new: str, file_path: str) -> str:
    """Generate a unified diff between original and new content."""
    original_lines = original.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        new_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm="",
    )

    return "".join(diff)


# Update FileChange.get_diff method
def _get_diff_method(self) -> str:
    """Generate a diff of the changes."""
    return generate_diff(self.original_content, self.new_content, self.file_path)


# Monkey patch the FileChange class to add proper diff generation
FileChange.get_diff = _get_diff_method
