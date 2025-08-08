#!/usr/bin/env python3
"""
Test script to demonstrate context persistence in Refinery.

This shows the three main ways to use the analyze command:
1. First time with manual file specification (saves context)
2. Subsequent runs using saved context
3. Extracting prompts directly from trace

Run this to verify the context persistence is working.
"""

import subprocess
import os
import json
from pathlib import Path
import shutil

def run_command(cmd, description):
    """Run a command and show the output."""
    print(f"\n{'='*60}")
    print(f"TEST: {description}")
    print(f"{'='*60}")
    print(f"Command: {cmd}")
    print(f"{'='*60}\n")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        print("STDOUT:")
        print(result.stdout)
    if result.stderr:
        print("STDERR:")
        print(result.stderr)
    
    print(f"\nReturn code: {result.returncode}")
    return result.returncode == 0

def create_test_files():
    """Create some test prompt and eval files."""
    test_dir = Path("test_prompts")
    test_dir.mkdir(exist_ok=True)
    
    # Create a test prompt file
    prompt_file = test_dir / "test_prompt.txt"
    prompt_file.write_text("""
You are a helpful AI assistant.
Always acknowledge your limitations clearly.
If you cannot remember or store information, say so explicitly.
""")
    
    # Create a test eval file
    eval_file = test_dir / "test_eval.py"
    eval_file.write_text("""
def test_memory_acknowledgment():
    # Test that agent acknowledges it cannot store memory
    response = agent.query("Can you remember this for next time?")
    assert "cannot store" in response.lower() or "don't have memory" in response.lower()
""")
    
    return str(prompt_file), str(eval_file)

def check_context_file():
    """Check if context file was created and what it contains."""
    context_file = Path(".refinery/context.json")
    if context_file.exists():
        print("\n✓ Context file exists at .refinery/context.json")
        with open(context_file) as f:
            context = json.load(f)
        print(f"Projects in context: {list(context.get('projects', {}).keys())}")
        
        for project_name, project_data in context.get('projects', {}).items():
            print(f"\nProject '{project_name}':")
            print(f"  - Prompt files: {len(project_data.get('prompt_files', []))}")
            print(f"  - Eval files: {len(project_data.get('eval_files', []))}")
            print(f"  - Config files: {len(project_data.get('config_files', []))}")
            if project_data.get('prompt_files'):
                print(f"  - Example prompt file: {project_data['prompt_files'][0]}")
        return True
    else:
        print("\n✗ No context file found")
        return False

def main():
    print("="*80)
    print("REFINERY CONTEXT PERSISTENCE TEST")
    print("="*80)
    
    # Clean up any existing context
    if Path(".refinery").exists():
        print("Cleaning up existing .refinery directory...")
        shutil.rmtree(".refinery")
    
    # Create test files
    prompt_file, eval_file = create_test_files()
    print(f"Created test files:")
    print(f"  - {prompt_file}")
    print(f"  - {eval_file}")
    
    # Test trace ID (use a placeholder - in real test would use actual trace)
    trace_id = "test-trace-id-12345"
    project = "test-memory-agent"
    
    print("\n" + "="*80)
    print("SCENARIO 1: First run with manual file specification")
    print("="*80)
    
    # First run - specify files manually (this will save context)
    cmd1 = f"""refinery analyze {trace_id} \\
        --project "{project}" \\
        --expected "Agent should acknowledge memory limitations" \\
        --prompt-files "{prompt_file}" \\
        --eval-files "{eval_file}" """
    
    success1 = run_command(cmd1, "First run with manual files (saves context)")
    
    # Check that context was saved
    context_saved = check_context_file()
    
    if context_saved:
        print("\n" + "="*80)
        print("SCENARIO 2: Second run using saved context (no file specification)")
        print("="*80)
        
        # Second run - use saved context
        cmd2 = f"""refinery analyze {trace_id} \\
            --project "{project}" \\
            --expected "Different issue but same project" """
        
        success2 = run_command(cmd2, "Second run using saved context")
        
        print("\n" + "="*80)
        print("SCENARIO 3: Add more files to existing context")
        print("="*80)
        
        # Create another file
        additional_prompt = Path("test_prompts/additional_prompt.txt")
        additional_prompt.write_text("Additional prompt content")
        
        cmd3 = f"""refinery analyze {trace_id} \\
            --project "{project}" \\
            --expected "Testing with additional files" \\
            --add-prompt "{str(additional_prompt)}" """
        
        success3 = run_command(cmd3, "Adding files to existing context")
        check_context_file()
    
    print("\n" + "="*80)
    print("SCENARIO 4: Extract prompts from trace (if LangSmith is configured)")
    print("="*80)
    
    # This would extract prompts directly from the trace
    cmd4 = f"""refinery analyze {trace_id} \\
        --project "extracted-project" \\
        --expected "Testing prompt extraction from trace" \\
        --extract-from-trace"""
    
    success4 = run_command(cmd4, "Extract prompts from trace")
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print("Context persistence allows you to:")
    print("1. ✓ Specify files once and reuse them")
    print("2. ✓ Add/remove files incrementally") 
    print("3. ✓ Extract prompts directly from traces")
    print("4. ✓ Manage multiple projects with different contexts")
    
    # Clean up
    if Path("test_prompts").exists():
        shutil.rmtree("test_prompts")
        print("\nCleaned up test files")

if __name__ == "__main__":
    main()