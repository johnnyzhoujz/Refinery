# Refinery Context System - User Guide

## Overview

Refinery's context system remembers which files to analyze for each project, so you don't have to specify them every time.

## First Time Setup

When you first use Refinery for a project, specify the files:

```bash
refinery fix abc123 \
  --project customer-service \
  --expected "Agent should identify premium customers correctly" \
  --prompt-files prompts/system_prompt.py prompts/billing_template.py \
  --eval-files tests/test_billing.py tests/test_premium.py
```

Refinery creates `.refinery/context.json` to remember these files.

## Subsequent Uses - Much Simpler!

After the first setup, just run:

```bash
refinery fix xyz789 \
  --project customer-service \
  --expected "Handle refund requests properly"
```

Refinery automatically uses the saved files - no need to specify them again!

## Managing Your Context

### View Saved Context
```bash
# See all projects with saved contexts
refinery context --list

# View specific project context
refinery context --project customer-service

# View with file details (debug mode)
refinery context --project customer-service --debug
```

### Add More Files
```bash
# Add a new prompt file
refinery fix abc123 --project customer-service --add-prompt prompts/refund_prompt.py --expected "..."

# Add a new eval file
refinery fix abc123 --project customer-service --add-eval tests/test_refunds.py --expected "..."
```

### Remove Files
```bash
# Remove a prompt file
refinery fix abc123 --project customer-service --remove-prompt prompts/old_prompt.py --expected "..."

# Remove an eval file  
refinery fix abc123 --project customer-service --remove-eval tests/old_test.py --expected "..."
```

### Replace All Files
```bash
# Completely replace the file list
refinery fix abc123 \
  --project customer-service \
  --prompt-files prompts/new_system.py \
  --eval-files tests/new_tests.py \
  --update \
  --expected "..."
```

### Clear Context
```bash
# Remove all saved context for a project
refinery context --clear customer-service
```

## How It Works

1. **Storage**: Context saved in `.refinery/context.json` in your project root
2. **Portability**: Uses relative paths, so works when you move your project
3. **Validation**: Automatically removes missing files and warns you
4. **Multi-Project**: Supports multiple projects in the same repository

## Benefits

- **One-time setup**: Specify files once, reuse forever
- **Team friendly**: Context file can be committed to Git
- **Incremental**: Add/remove files as your agent evolves
- **Smart validation**: Handles moved/deleted files gracefully

## Example Workflow

```bash
# First time setup
refinery fix trace_001 --project billing-agent \
  --prompt-files prompts/system.py prompts/billing.py \
  --eval-files tests/billing_tests.py \
  --expected "Correct premium billing calculation"

# Next day - much simpler!
refinery fix trace_002 --project billing-agent \
  --expected "Handle enterprise customer discounts"

# Add new capability
refinery fix trace_003 --project billing-agent \
  --add-prompt prompts/enterprise_discounts.py \
  --expected "Calculate enterprise discounts correctly"

# Check what's saved
refinery context --project billing-agent
```

This system makes Refinery much more convenient for daily use while maintaining full control over what files are analyzed.