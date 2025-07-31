#!/usr/bin/env python3
"""
Demo script for the Simple Code Reader

Shows how to use the simple code reader to analyze customer codebases
for prompt/eval files and configurations.
"""

import asyncio
import sys
from pathlib import Path

# Add the refinery package to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from refinery.analysis.simple_code_reader import (
    build_simple_context,
    find_prompt_files,
    analyze_file,
    SimpleCodeReader
)


async def demo_basic_usage():
    """Demo basic usage of the simple code reader"""
    print("=== Simple Code Reader Demo ===\n")
    
    # Use current directory as example
    codebase_path = str(Path(__file__).parent.parent)
    print(f"Analyzing codebase: {codebase_path}")
    
    # Build complete context
    print("\n1. Building complete context...")
    context = await build_simple_context(codebase_path)
    
    print("\n" + "="*50)
    print(context.summary)
    print("="*50)
    
    # Show detailed information about found files
    if context.prompt_files:
        print("\n2. Detailed Prompt Files:")
        for file_path, info in list(context.prompt_files.items())[:3]:  # Show first 3
            print(f"\n  File: {Path(file_path).name}")
            print(f"  Role: {info.estimated_role}")
            print(f"  Size: {info.size_chars} chars")
            print(f"  Variables: {info.contains_variables}")
            preview = info.content.replace('\n', ' ')[:100]
            print(f"  Preview: {preview}...")
    
    if context.eval_files:
        print("\n3. Detailed Eval Files:")
        for file_path, info in list(context.eval_files.items())[:2]:  # Show first 2
            print(f"\n  File: {Path(file_path).name}")
            print(f"  Role: {info.estimated_role}")
            print(f"  Size: {info.size_chars} chars")
            preview = info.content.replace('\n', ' ')[:100]
            print(f"  Preview: {preview}...")
    
    if context.config_files:
        print("\n4. Detailed Config Files:")
        for file_path, info in list(context.config_files.items())[:2]:  # Show first 2
            print(f"\n  File: {Path(file_path).name}")
            print(f"  Size: {info.size_chars} chars")
            print(f"  Variables: {info.contains_variables}")


async def demo_individual_functions():
    """Demo individual functions"""
    print("\n\n=== Individual Function Demo ===\n")
    
    codebase_path = str(Path(__file__).parent.parent)
    
    # Find prompt files
    print("1. Finding prompt files...")
    prompt_files = await find_prompt_files(codebase_path)
    print(f"Found {len(prompt_files)} prompt files:")
    for file_path in prompt_files[:3]:
        print(f"  - {Path(file_path).relative_to(codebase_path)}")
    
    # Analyze a specific file
    if prompt_files:
        print(f"\n2. Analyzing specific file: {Path(prompt_files[0]).name}")
        info = await analyze_file(prompt_files[0])
        if info:
            print(f"  Type: {info.file_type}")
            print(f"  Role: {info.estimated_role}")
            print(f"  Size: {info.size_chars} chars")
            print(f"  Contains variables: {info.contains_variables}")


async def demo_custom_reader():
    """Demo using the reader class directly with custom settings"""
    print("\n\n=== Custom Reader Demo ===\n")
    
    # Create reader with custom settings
    reader = SimpleCodeReader(max_file_size=512 * 1024)  # 512KB max
    
    codebase_path = str(Path(__file__).parent.parent)
    
    print("1. Using custom reader settings...")
    context = await reader.build_simple_context(codebase_path)
    
    print(f"Found files with custom reader:")
    print(f"  - {len(context.prompt_files)} prompt files")
    print(f"  - {len(context.eval_files)} eval files") 
    print(f"  - {len(context.config_files)} config files")
    
    # Show file size distribution
    all_files = {**context.prompt_files, **context.eval_files, **context.config_files}
    if all_files:
        sizes = [info.size_chars for info in all_files.values()]
        print(f"\nFile size stats:")
        print(f"  - Smallest: {min(sizes)} chars")
        print(f"  - Largest: {max(sizes)} chars")
        print(f"  - Average: {sum(sizes) // len(sizes)} chars")
    
    # Show variable usage
    variable_files = [info for info in all_files.values() if info.contains_variables]
    print(f"\nFiles with variables: {len(variable_files)}")
    for info in variable_files[:3]:
        filename = Path(info.file_path).name
        print(f"  - {filename} ({info.file_type})")


async def main():
    """Run all demos"""
    try:
        await demo_basic_usage()
        await demo_individual_functions()
        await demo_custom_reader()
        
        print("\n\n=== Demo Complete ===")
        print("The Simple Code Reader provides a straightforward way to:")
        print("- Find prompt, eval, and config files in customer codebases")
        print("- Extract content and basic metadata without complex parsing")
        print("- Classify files by type and estimated role")
        print("- Detect template variables for dynamic content")
        print("- Handle encoding issues and file size limits gracefully")
        
    except Exception as e:
        print(f"Error running demo: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())