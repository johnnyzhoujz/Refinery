"""
Tests for the SafeCodeManager implementation.

This module provides comprehensive tests for the code manager functionality,
including safety checks, Git integration, and rollback capabilities.
"""

import asyncio
import tempfile
from pathlib import Path

import git
import pytest

from ..core.models import ChangeType, FileChange
from .code_manager import SafeCodeManager


@pytest.fixture
async def temp_git_repo():
    """Create a temporary Git repository for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize Git repo
        repo = git.Repo.init(temp_dir)

        # Create some initial files
        (Path(temp_dir) / "main.py").write_text(
            '''
def hello_world():
    """Say hello."""
    print("Hello, World!")

def add_numbers(a, b):
    """Add two numbers."""
    return a + b
'''
        )

        (Path(temp_dir) / "config.yaml").write_text(
            """
app:
  name: "Test App"
  version: "1.0.0"
  debug: false
"""
        )

        (Path(temp_dir) / "utils.py").write_text(
            '''
from main import hello_world

def run_hello():
    """Run hello world."""
    hello_world()
'''
        )

        # Create test file
        test_dir = Path(temp_dir) / "tests"
        test_dir.mkdir()
        (test_dir / "test_main.py").write_text(
            """
from main import add_numbers

def test_add_numbers():
    assert add_numbers(2, 3) == 5
"""
        )

        # Commit initial files
        repo.index.add(["main.py", "config.yaml", "utils.py", "tests/test_main.py"])
        repo.index.commit("Initial commit")

        yield temp_dir


@pytest.mark.asyncio
async def test_analyze_codebase(temp_git_repo):
    """Test codebase analysis functionality."""
    manager = SafeCodeManager(temp_git_repo)

    context = await manager.analyze_codebase(".")

    assert context.repository_path == temp_git_repo
    assert context.main_language == "python"
    assert len(context.relevant_files) > 0
    assert "main.py" in context.relevant_files
    assert "utils.py" in context.relevant_files


@pytest.mark.asyncio
async def test_get_related_files(temp_git_repo):
    """Test finding related files."""
    manager = SafeCodeManager(temp_git_repo)

    # Test finding files related to main.py
    related = await manager.get_related_files("main.py")

    assert "utils.py" in related  # utils.py imports from main
    assert "tests/test_main.py" in related  # test file for main.py


@pytest.mark.asyncio
async def test_validate_change_success(temp_git_repo):
    """Test successful change validation."""
    manager = SafeCodeManager(temp_git_repo)

    change = FileChange(
        file_path="main.py",
        original_content=(Path(temp_git_repo) / "main.py").read_text(),
        new_content='''
def hello_world():
    """Say hello."""
    print("Hello, Refinery!")

def add_numbers(a, b):
    """Add two numbers."""
    return a + b

def multiply_numbers(a, b):
    """Multiply two numbers."""
    return a * b
''',
        change_type=ChangeType.PROMPT_MODIFICATION,
        description="Added multiply function and changed greeting",
    )

    result = await manager.validate_change(change)

    assert result.is_valid
    assert len(result.issues) == 0


@pytest.mark.asyncio
async def test_validate_change_with_syntax_error(temp_git_repo):
    """Test validation catches syntax errors."""
    manager = SafeCodeManager(temp_git_repo)

    change = FileChange(
        file_path="main.py",
        original_content=(Path(temp_git_repo) / "main.py").read_text(),
        new_content="""
def hello_world(:  # Syntax error
    print("Hello!")
""",
        change_type=ChangeType.PROMPT_MODIFICATION,
        description="Broken code",
    )

    result = await manager.validate_change(change)

    assert not result.is_valid
    assert any("syntax error" in issue.lower() for issue in result.issues)


@pytest.mark.asyncio
async def test_validate_change_with_secrets(temp_git_repo):
    """Test validation catches secrets."""
    manager = SafeCodeManager(temp_git_repo)

    change = FileChange(
        file_path="config.py",
        original_content="",
        new_content="""
API_KEY = "sk-1234567890abcdef1234567890abcdef"
DATABASE_PASSWORD = "super_secret_password_123"
""",
        change_type=ChangeType.CONFIG_CHANGE,
        description="Add config",
    )

    result = await manager.validate_change(change)

    assert not result.is_valid
    assert any(
        "credential" in issue.lower() or "secret" in issue.lower()
        for issue in result.issues
    )


@pytest.mark.asyncio
async def test_analyze_impact(temp_git_repo):
    """Test impact analysis."""
    manager = SafeCodeManager(temp_git_repo)

    changes = [
        FileChange(
            file_path="main.py",
            original_content=(Path(temp_git_repo) / "main.py").read_text(),
            new_content='''
def hello_world(name="World"):
    """Say hello to someone."""
    print(f"Hello, {name}!")

def add_numbers(a, b):
    """Add two numbers."""
    return a + b
''',
            change_type=ChangeType.PROMPT_MODIFICATION,
            description="Modified hello_world signature",
        )
    ]

    impact = await manager.analyze_impact(changes)

    assert "main.py" in impact.affected_files
    assert "utils.py" in impact.affected_files  # Uses hello_world
    assert len(impact.potential_breaking_changes) > 0
    assert len(impact.suggested_tests) > 0


@pytest.mark.asyncio
async def test_apply_changes(temp_git_repo):
    """Test applying changes with Git integration."""
    manager = SafeCodeManager(temp_git_repo)

    original_content = (Path(temp_git_repo) / "main.py").read_text()

    changes = [
        FileChange(
            file_path="main.py",
            original_content=original_content,
            new_content=original_content
            + '''

def greet(name):
    """Greet someone by name."""
    return f"Greetings, {name}!"
''',
            change_type=ChangeType.PROMPT_MODIFICATION,
            description="Added greet function",
        ),
        FileChange(
            file_path="new_file.py",
            original_content="",
            new_content='''
"""New module for testing."""

def test_function():
    """Test function."""
    return "test"
''',
            change_type=ChangeType.PROMPT_MODIFICATION,
            description="Created new file",
        ),
    ]

    result = await manager.apply_changes(changes, "Add greet function and new file")

    assert result["status"] == "success"
    assert "commit_id" in result
    assert result["files_changed"] == 2

    # Verify files were actually changed
    assert (Path(temp_git_repo) / "new_file.py").exists()
    assert "def greet" in (Path(temp_git_repo) / "main.py").read_text()

    # Verify Git commit was made
    repo = git.Repo(temp_git_repo)
    assert len(list(repo.iter_commits())) == 2  # Initial + our commit


@pytest.mark.asyncio
async def test_rollback_changes(temp_git_repo):
    """Test rolling back changes."""
    manager = SafeCodeManager(temp_git_repo)

    # First, apply a change
    original_content = (Path(temp_git_repo) / "main.py").read_text()

    changes = [
        FileChange(
            file_path="main.py",
            original_content=original_content,
            new_content='''
def broken_function():
    """This replaces everything!"""
    raise NotImplementedError("Oops!")
''',
            change_type=ChangeType.PROMPT_MODIFICATION,
            description="Breaking change",
        )
    ]

    result = await manager.apply_changes(changes, "Breaking change for test")
    commit_id = result["commit_id"]

    # Verify the change was applied
    assert "broken_function" in (Path(temp_git_repo) / "main.py").read_text()
    assert "hello_world" not in (Path(temp_git_repo) / "main.py").read_text()

    # Now rollback
    success = await manager.rollback_changes(commit_id)
    assert success

    # Verify the rollback worked
    rolled_back_content = (Path(temp_git_repo) / "main.py").read_text()
    assert "hello_world" in rolled_back_content
    assert "broken_function" not in rolled_back_content


@pytest.mark.asyncio
async def test_concurrent_file_access(temp_git_repo):
    """Test concurrent file access with locking."""
    manager = SafeCodeManager(temp_git_repo)

    async def make_change(suffix: str):
        """Make a change to the file."""
        original = (Path(temp_git_repo) / "main.py").read_text()

        change = FileChange(
            file_path="main.py",
            original_content=original,
            new_content=original + f"\n# Change {suffix}\n",
            change_type=ChangeType.PROMPT_MODIFICATION,
            description=f"Add comment {suffix}",
        )

        return await manager.apply_changes([change], f"Add comment {suffix}")

    # Run multiple changes concurrently
    tasks = [make_change(str(i)) for i in range(3)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # All should succeed (file locking should prevent conflicts)
    successful = [
        r for r in results if isinstance(r, dict) and r.get("status") == "success"
    ]
    assert len(successful) == 3


@pytest.mark.asyncio
async def test_diff_generation(temp_git_repo):
    """Test diff generation for changes."""
    original = """def hello():
    print("Hello")
"""

    new = """def hello():
    print("Hello, World!")

def goodbye():
    print("Goodbye!")
"""

    change = FileChange(
        file_path="test.py",
        original_content=original,
        new_content=new,
        change_type=ChangeType.PROMPT_MODIFICATION,
        description="Add goodbye function",
    )

    diff = change.get_diff()

    assert "--- a/test.py" in diff
    assert "+++ b/test.py" in diff
    assert '-    print("Hello")' in diff
    assert '+    print("Hello, World!")' in diff
    assert "+def goodbye():" in diff


@pytest.mark.asyncio
async def test_yaml_validation(temp_git_repo):
    """Test YAML file validation."""
    manager = SafeCodeManager(temp_git_repo)

    # Valid YAML
    valid_change = FileChange(
        file_path="config.yaml",
        original_content=(Path(temp_git_repo) / "config.yaml").read_text(),
        new_content="""
app:
  name: "Updated App"
  version: "2.0.0"
  features:
    - logging
    - monitoring
""",
        change_type=ChangeType.CONFIG_CHANGE,
        description="Update config",
    )

    result = await manager.validate_change(valid_change)
    assert result.is_valid

    # Invalid YAML
    invalid_change = FileChange(
        file_path="config.yaml",
        original_content=(Path(temp_git_repo) / "config.yaml").read_text(),
        new_content="""
app:
  name: "Bad YAML"
    version: "2.0.0"  # Bad indentation
  features
    - logging
""",
        change_type=ChangeType.CONFIG_CHANGE,
        description="Broken YAML",
    )

    result = await manager.validate_change(invalid_change)
    assert not result.is_valid
    assert any("YAML" in issue for issue in result.issues)


@pytest.mark.asyncio
async def test_json_validation(temp_git_repo):
    """Test JSON file validation."""
    manager = SafeCodeManager(temp_git_repo)

    # Create a JSON file first
    json_path = Path(temp_git_repo) / "settings.json"
    json_path.write_text('{"key": "value"}')

    # Valid JSON
    valid_change = FileChange(
        file_path="settings.json",
        original_content='{"key": "value"}',
        new_content='{"key": "updated", "new_key": 123}',
        change_type=ChangeType.CONFIG_CHANGE,
        description="Update JSON",
    )

    result = await manager.validate_change(valid_change)
    assert result.is_valid

    # Invalid JSON
    invalid_change = FileChange(
        file_path="settings.json",
        original_content='{"key": "value"}',
        new_content='{"key": "value", "bad": }',  # Invalid JSON
        change_type=ChangeType.CONFIG_CHANGE,
        description="Broken JSON",
    )

    result = await manager.validate_change(invalid_change)
    assert not result.is_valid
    assert any("JSON" in issue for issue in result.issues)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
