#!/usr/bin/env python3
"""
Demonstration of the Customer Agent Implementation Parser

This script shows how to use the agent parser to analyze a codebase
and understand its AI agent structure.
"""

import json
import sys
from pathlib import Path

# Add the refinery module to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from refinery.analysis.agent_parser import parse_agent_codebase, CustomerAgentParser


def demo_parse_current_codebase():
    """Demonstrate parsing the current refinery codebase."""
    print("=== Customer Agent Implementation Parser Demo ===\n")
    
    # Get the path to the refinery codebase
    refinery_path = Path(__file__).parent.parent
    print(f"Analyzing codebase at: {refinery_path}\n")
    
    # Parse the codebase
    blueprint = parse_agent_codebase(str(refinery_path))
    
    # Display results
    print("📊 ANALYSIS RESULTS")
    print("=" * 50)
    print(f"Codebase Path: {blueprint.codebase_path}")
    print(f"Main Language: {blueprint.main_language}")
    print(f"Framework: {blueprint.framework or 'Custom/Unknown'}")
    print(f"Architecture Summary: {blueprint.architecture_summary}")
    print()
    
    # Prompt Analysis
    print("📝 PROMPTS DISCOVERED")
    print("=" * 30)
    if blueprint.prompts:
        for path, prompt in blueprint.prompts.items():
            print(f"• {Path(path).name}")
            print(f"  Type: {prompt.prompt_type}")
            print(f"  Template Engine: {prompt.template_engine}")
            print(f"  Variables: {prompt.variables}")
            print(f"  Content Preview: {prompt.content[:100]}...")
            print()
    else:
        print("No prompt files detected.")
    print()
    
    # Evaluation Analysis
    print("🧪 EVALUATIONS DISCOVERED")
    print("=" * 30)
    if blueprint.evals:
        for path, eval_info in blueprint.evals.items():
            print(f"• {Path(path).name}")
            print(f"  Type: {eval_info.eval_type}")
            print(f"  Test Cases: {len(eval_info.test_cases)}")
            print(f"  Prompts Tested: {eval_info.prompts_tested}")
            print()
    else:
        print("No evaluation files detected.")
    print()
    
    # Model Configuration Analysis
    print("🤖 MODEL CONFIGURATIONS")
    print("=" * 30)
    if blueprint.models:
        for model in blueprint.models:
            print(f"• {model.model_name}")
            print(f"  Provider: {model.provider}")
            print(f"  Parameters: {model.parameters}")
            print(f"  Context: {model.usage_context}")
            print()
    else:
        print("No model configurations detected.")
    print()
    
    # Workflow Pattern Analysis
    print("🔄 WORKFLOW PATTERNS")
    print("=" * 30)
    if blueprint.workflows:
        for workflow in blueprint.workflows:
            print(f"• {workflow.pattern_type.title()} Pattern")
            print(f"  Components: {workflow.components}")
            print(f"  Description: {workflow.flow_description}")
            print()
    else:
        print("No workflow patterns detected.")
    print()
    
    # Dependencies
    print("🔗 DEPENDENCIES")
    print("=" * 20)
    if blueprint.dependencies:
        for source, target in blueprint.dependencies.items():
            print(f"• {Path(source).name} → {Path(target).name}")
    else:
        print("No internal dependencies mapped.")
    print()
    
    return blueprint


def demo_export_blueprint(blueprint, output_file="agent_blueprint.json"):
    """Export the blueprint to a JSON file for further analysis."""
    print(f"💾 EXPORTING BLUEPRINT")
    print("=" * 30)
    
    # Convert blueprint to dictionary for JSON serialization
    blueprint_dict = {
        "codebase_path": blueprint.codebase_path,
        "main_language": blueprint.main_language,
        "framework": blueprint.framework,
        "architecture_summary": blueprint.architecture_summary,
        "prompts": {
            path: {
                "file_path": prompt.file_path,
                "prompt_type": prompt.prompt_type,
                "variables": prompt.variables,
                "template_engine": prompt.template_engine,
                "model_references": prompt.model_references,
                "dependencies": prompt.dependencies,
                "metadata": prompt.metadata,
                "content_preview": prompt.content[:200] + "..." if len(prompt.content) > 200 else prompt.content
            }
            for path, prompt in blueprint.prompts.items()
        },
        "evals": {
            path: {
                "file_path": eval_info.file_path,
                "eval_type": eval_info.eval_type,
                "test_cases": eval_info.test_cases,
                "prompts_tested": eval_info.prompts_tested,
                "success_criteria": eval_info.success_criteria,
                "metadata": eval_info.metadata
            }
            for path, eval_info in blueprint.evals.items()
        },
        "models": [
            {
                "model_name": model.model_name,
                "provider": model.provider,
                "parameters": model.parameters,
                "usage_context": model.usage_context,
                "file_location": model.file_location
            }
            for model in blueprint.models
        ],
        "workflows": [
            {
                "pattern_type": workflow.pattern_type,
                "components": workflow.components,
                "flow_description": workflow.flow_description,
                "entry_points": workflow.entry_points
            }
            for workflow in blueprint.workflows
        ],
        "dependencies": blueprint.dependencies
    }
    
    # Write to file
    output_path = Path(__file__).parent / output_file
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(blueprint_dict, f, indent=2, ensure_ascii=False)
    
    print(f"Blueprint exported to: {output_path}")
    print(f"File size: {output_path.stat().st_size} bytes")


def demo_advanced_analysis():
    """Demonstrate advanced analysis capabilities."""
    print("\n🔍 ADVANCED ANALYSIS FEATURES")
    print("=" * 40)
    
    # Create parser instance for direct access to components
    parser = CustomerAgentParser()
    
    # Demonstrate template variable extraction
    print("Template Variable Extraction:")
    
    jinja_example = "Hello {{ name }}, your balance is {{ account.balance }}!"
    jinja_vars = parser.template_extractor.extract_jinja2_variables(jinja_example)
    print(f"  Jinja2: '{jinja_example}' → {jinja_vars}")
    
    fstring_example = 'f"Welcome {user_name}, you have {message_count} messages"'
    fstring_vars = parser.template_extractor.extract_fstring_variables(fstring_example)
    print(f"  F-string: '{fstring_example}' → {fstring_vars}")
    
    format_example = "Processing {task_name} with {priority} priority"
    format_vars = parser.template_extractor.extract_format_variables(format_example)
    print(f"  Format: '{format_example}' → {format_vars}")
    
    print()
    
    # Demonstrate file type detection
    print("File Type Detection:")
    test_cases = [
        ("system_prompt.txt", "You are a helpful AI assistant."),
        ("test_agent.py", "def test_response(): assert response.status == 200"),
        ("config.yaml", "model: gpt-4\ntemperature: 0.7"),
        ("user_template.md", "## Task\nUser: {{ user_input }}")
    ]
    
    for filename, content in test_cases:
        purpose = parser.file_detector.detect_file_purpose(filename, content)
        print(f"  {filename} → {purpose}")
    
    print()
    
    # Demonstrate framework detection
    print("Framework Detection:")
    framework_examples = [
        ("from langchain.chains import LLMChain", "langchain"),
        ("from llama_index import VectorStoreIndex", "llamaindex"),
        ("import openai; client = openai.Client()", "custom"),
    ]
    
    for code, expected in framework_examples:
        detected = parser.framework_detector.detect_framework(code, [code])
        print(f"  '{code}' → {detected or 'custom'}")


if __name__ == "__main__":
    try:
        # Run the main demo
        blueprint = demo_parse_current_codebase()
        
        # Export blueprint
        demo_export_blueprint(blueprint)
        
        # Show advanced features
        demo_advanced_analysis()
        
        print("\n✅ Demo completed successfully!")
        print("\nNext steps:")
        print("1. Try parsing your own agent codebase:")
        print("   python agent_parser_demo.py /path/to/your/agent/code")
        print("2. Use the generated blueprint in other refinery agents")
        print("3. Extend the parser with custom detection patterns")
        
    except Exception as e:
        print(f"❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)