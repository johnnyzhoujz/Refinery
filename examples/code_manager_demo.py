#!/usr/bin/env python3
"""
Demo script showing how to use the SafeCodeManager for safe code editing.

This demonstrates:
1. Analyzing a codebase
2. Finding related files
3. Validating changes before applying
4. Applying changes with Git integration
5. Rolling back if needed
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from refinery.core.models import ChangeType, FileChange
from refinery.integrations.code_manager import SafeCodeManager


async def main():
    """Run the demo."""
    # Initialize the code manager with current directory
    # In production, this would be the path to your project
    manager = SafeCodeManager()
    
    print("🔍 Analyzing codebase...")
    context = await manager.analyze_codebase("refinery")
    print(f"  Repository: {context.repository_path}")
    print(f"  Language: {context.main_language}")
    print(f"  Framework: {context.framework}")
    print(f"  Files found: {len(context.relevant_files)}")
    
    # Example: Find related files for a specific module
    print("\n🔗 Finding related files for 'refinery/core/models.py'...")
    related = await manager.get_related_files("refinery/core/models.py")
    print(f"  Found {len(related)} related files:")
    for file in related[:5]:  # Show first 5
        print(f"    - {file}")
    
    # Example: Create a safe change
    print("\n✏️  Creating a sample change...")
    
    # Read the current content of a file
    target_file = "refinery/core/models.py"
    current_content = (Path(target_file).read_text() 
                      if Path(target_file).exists() else "")
    
    # Create a change that adds a comment
    change = FileChange(
        file_path=target_file,
        original_content=current_content,
        new_content=current_content.replace(
            '"""Shared data models and interfaces for Refinery.',
            '"""Shared data models and interfaces for Refinery.\n\n[Demo: This comment was added by SafeCodeManager]'
        ),
        change_type=ChangeType.PROMPT_MODIFICATION,
        description="Add demo comment to module docstring"
    )
    
    # Validate the change
    print("\n✅ Validating change...")
    validation = await manager.validate_change(change)
    
    if validation.is_valid:
        print("  Change is valid!")
        if validation.warnings:
            print("  Warnings:")
            for warning in validation.warnings:
                print(f"    ⚠️  {warning}")
    else:
        print("  ❌ Change validation failed:")
        for issue in validation.issues:
            print(f"    - {issue}")
        return
    
    # Analyze impact
    print("\n📊 Analyzing impact...")
    impact = await manager.analyze_impact([change])
    print(f"  Affected files: {len(impact.affected_files)}")
    print(f"  Confidence: {impact.confidence}")
    if impact.potential_breaking_changes:
        print("  Potential breaking changes:")
        for breaking in impact.potential_breaking_changes:
            print(f"    - {breaking}")
    
    # Apply the change (in demo mode, we'll skip actual application)
    print("\n🚀 Demo complete!")
    print("\nTo actually apply changes, you would use:")
    print('  result = await manager.apply_changes([change], "Your commit message")')
    print('  if result["status"] == "success":')
    print('      print(f"Committed with ID: {result[\'commit_id\']}")')
    print("\nTo rollback changes:")
    print('  success = await manager.rollback_changes(commit_id)')
    
    # Show diff
    print("\n📄 Generated diff:")
    print("-" * 60)
    diff_lines = change.get_diff().split('\n')
    for line in diff_lines[:10]:  # Show first 10 lines
        print(line)
    if len(diff_lines) > 10:
        print("... (truncated)")


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())