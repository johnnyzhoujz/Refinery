# Context Persistence in Refinery

## Overview

Refinery now supports **context persistence** for both `analyze` and `fix` commands. This means you only need to specify your prompt and eval files once, and Refinery will remember them for future runs.

## How It Works

Context is stored in `.refinery/context.json` in your project directory. Each project can have its own set of files.

## Usage Patterns

### 1. First Time Setup - Manual File Specification

```bash
# Specify files manually on first run (saves to context)
refinery analyze <trace_id> \
    --project "my-agent" \
    --expected "Agent should acknowledge memory limitations" \
    --prompt-files "src/prompts/system.py" \
    --prompt-files "src/prompts/user_template.py" \
    --eval-files "tests/memory_test.py" \
    --eval-files "tests/capability_test.py"
```

### 2. Subsequent Runs - Uses Saved Context Automatically

```bash
# No need to specify files again!
refinery analyze <different_trace_id> \
    --project "my-agent" \
    --expected "Different issue but same project"
```

### 3. Extract Prompts Directly from Trace

```bash
# Extract and save prompts from the LangSmith trace itself
refinery analyze <trace_id> \
    --project "my-agent" \
    --expected "Agent should work correctly" \
    --extract-from-trace
```

This will:
- Extract system prompts, user prompts, templates from the trace
- Save them as files in `.refinery/projects/<project>/prompts/`
- Automatically add them to the project context
- Include eval examples from input/output pairs

### 4. Incremental Updates

```bash
# Add files to existing context
refinery analyze <trace_id> \
    --project "my-agent" \
    --expected "Testing with more files" \
    --add-prompt "src/prompts/new_prompt.py" \
    --add-eval "tests/new_test.py"

# Remove files from context
refinery analyze <trace_id> \
    --project "my-agent" \
    --expected "Testing with fewer files" \
    --remove-prompt "src/prompts/old_prompt.py"

# Replace entire context (not append)
refinery analyze <trace_id> \
    --project "my-agent" \
    --expected "Complete refresh" \
    --prompt-files "new_prompt.py" \
    --update
```

## Context Management Commands

```bash
# List all projects with saved contexts
refinery context --list

# Show context for specific project
refinery context --project "my-agent"

# Clear context for a project
refinery context --clear "my-agent"
```

## File Organization

When using `--extract-from-trace`, files are organized as:

```
.refinery/
├── context.json                          # Main context file
└── projects/
    └── my-agent/
        ├── prompts/
        │   ├── system_prompt_0_abc123.txt
        │   ├── user_prompt_0_def456.txt
        │   └── template_query_ghi789.txt
        ├── evals/
        │   └── eval_examples_trace123.json
        └── configs/
            └── model_config_trace123.json
```

## Benefits

1. **No Repetition**: Specify files once, use them forever
2. **Project Isolation**: Each project maintains its own context
3. **Flexibility**: Mix manual files with trace-extracted prompts
4. **Version Control Friendly**: Add `.refinery/context.json` to git if you want to share context with team

## Best Practices

1. **First Time**: Use `--extract-from-trace` to automatically get prompts from a working trace
2. **Add Custom Files**: Use `--add-prompt` and `--add-eval` to include your custom implementations
3. **Multiple Projects**: Use different project names for different agents/use cases
4. **Clean Regularly**: Use `refinery context --clear` to remove outdated projects

## Example Workflow

```bash
# 1. Initial setup with trace extraction
refinery analyze failing-trace-123 \
    --project "customer-service-bot" \
    --expected "Should handle refunds properly" \
    --extract-from-trace

# 2. Add your custom eval files
refinery analyze failing-trace-123 \
    --project "customer-service-bot" \
    --expected "Should handle refunds properly" \
    --add-eval "tests/refund_test.py" \
    --add-eval "tests/edge_cases.py"

# 3. Future analyses just work!
refinery analyze new-failing-trace-456 \
    --project "customer-service-bot" \
    --expected "Should handle cancellations"

# 4. Generate fixes using same context
refinery fix another-trace-789 \
    --project "customer-service-bot" \
    --expected "Should validate input properly"
```

## Testing

Run the test script to verify context persistence is working:

```bash
python test_context_persistence.py
```

This will demonstrate all usage patterns and verify the context is properly saved and loaded.