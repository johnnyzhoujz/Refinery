# SafeCodeManager Documentation

The `SafeCodeManager` is a production-ready implementation of the `CodeManager` interface that provides safe code editing capabilities with comprehensive Git integration, AST parsing, and rollback functionality.

## Features

### Core Capabilities
- **AST-based Python code analysis** - Understands code structure, not just text
- **Import graph analysis** - Tracks dependencies between files
- **Multi-language support** - Python, YAML, JSON, and more
- **Atomic operations** - All changes succeed or all fail
- **File locking** - Safe concurrent access
- **Comprehensive validation** - Syntax, secrets, and breaking change detection
- **Git integration** - Automatic commits and rollback capability
- **Diff generation** - Preview changes before applying

### Safety Features
1. **Credential Detection** - Scans for API keys, passwords, and secrets
2. **Syntax Validation** - Ensures code is valid before applying
3. **File Size Limits** - Configurable limits to prevent huge files
4. **Breaking Change Detection** - Identifies removed functions/classes
5. **Automatic Rollback** - Revert changes if something goes wrong
6. **Stash Points** - Preserves uncommitted work during operations

## Usage

### Basic Example

```python
from refinery.integrations.code_manager import SafeCodeManager
from refinery.core.models import FileChange, ChangeType

# Initialize manager
manager = SafeCodeManager("/path/to/repository")

# Create a change
change = FileChange(
    file_path="src/main.py",
    original_content=original_content,
    new_content=new_content,
    change_type=ChangeType.PROMPT_MODIFICATION,
    description="Update prompt template"
)

# Validate before applying
result = await manager.validate_change(change)
if result.is_valid:
    # Apply the change
    commit_result = await manager.apply_changes(
        [change], 
        "Update prompt template for better clarity"
    )
    print(f"Committed: {commit_result['commit_id']}")
else:
    print(f"Validation failed: {result.issues}")
```

### Analyzing a Codebase

```python
# Analyze project structure
context = await manager.analyze_codebase("src")

print(f"Language: {context.main_language}")
print(f"Framework: {context.framework}")
print(f"Files: {len(context.relevant_files)}")
print(f"Dependencies: {context.dependencies}")
```

### Finding Related Files

```python
# Find files that import from or are imported by a target file
related = await manager.get_related_files("src/utils/helpers.py")

for file in related:
    print(f"Related: {file}")
```

### Impact Analysis

```python
# Analyze the impact of multiple changes
changes = [change1, change2, change3]
impact = await manager.analyze_impact(changes)

print(f"Affected files: {impact.affected_files}")
print(f"Breaking changes: {impact.potential_breaking_changes}")
print(f"Suggested tests: {impact.suggested_tests}")
print(f"Confidence: {impact.confidence}")
```

### Rollback Changes

```python
# Rollback a specific commit
success = await manager.rollback_changes(commit_id)
if success:
    print("Successfully rolled back changes")
```

## Validation Rules

### Python Files
- Syntax must be valid
- Imports should be at the top
- No broad exception handling warnings
- No print statements (warning - suggests logging)
- Function signature changes detected

### YAML Files
- Must be valid YAML syntax
- Proper indentation required

### JSON Files
- Must be valid JSON syntax
- No trailing commas
- Proper quote usage

### Security Checks
The following patterns trigger security warnings:
- API keys and tokens
- Passwords and secrets
- Private keys
- AWS credentials
- Connection strings with credentials

## Configuration

Configure via environment variables or `RefineryConfig`:

```python
# Maximum file size in KB
MAX_FILE_SIZE_KB=1000

# Maximum changes per hypothesis
MAX_CHANGES_PER_HYPOTHESIS=10

# Require approval for changes
REQUIRE_APPROVAL_FOR_CHANGES=true
```

## Best Practices

1. **Always validate before applying** - Use `validate_change()` first
2. **Batch related changes** - Apply multiple changes in one commit
3. **Use descriptive messages** - Clear commit messages help with debugging
4. **Check impact** - Use `analyze_impact()` for complex changes
5. **Test rollback** - Ensure your rollback strategy works
6. **Handle warnings** - Don't ignore validation warnings

## Error Handling

The manager provides detailed error information:

```python
result = await manager.apply_changes(changes, message)

if result["status"] == "validation_failed":
    for file, issues in result["errors"].items():
        print(f"{file}: {issues}")
elif result["status"] == "failed":
    print(f"Error: {result['error']}")
    print(f"Message: {result['message']}")
```

## Advanced Features

### Custom Validation

Extend validation by subclassing:

```python
class CustomCodeManager(SafeCodeManager):
    async def _validate_python_change(self, change):
        issues, warnings = await super()._validate_python_change(change)
        
        # Add custom validation
        if "TODO" in change.new_content:
            warnings.append("Found TODO comment")
        
        return issues, warnings
```

### Dry Run Mode

Preview changes without applying:

```python
# Get diff preview
diff = change.get_diff()
print(diff)

# Analyze impact without applying
impact = await manager.analyze_impact([change])
```

## Performance Considerations

- **Import caching** - Import graphs are cached for performance
- **AST caching** - Parsed ASTs are cached to avoid re-parsing
- **Parallel validation** - Multiple files validated concurrently
- **Efficient file finding** - Uses gitignore rules and smart filtering

## Testing

Comprehensive test coverage includes:
- Syntax validation
- Secret detection  
- Concurrent access
- Git operations
- Rollback scenarios
- Multi-language support

Run tests with:
```bash
pytest refinery/integrations/test_code_manager.py -v
```