# Testing the Refinery POC

## Quick Setup

1. **Install Refinery:**
   ```bash
   python setup_dev.py
   ```

2. **Configure API Keys:**
   Edit `.env` file with your credentials:
   ```
   LANGSMITH_API_KEY=your_langsmith_key_here
   OPENAI_API_KEY=your_openai_key_here  # or ANTHROPIC_API_KEY
   LLM_PROVIDER=openai  # or anthropic
   ```

3. **Test Configuration:**
   ```bash
   refinery config-check
   ```

## End-to-End Workflow Test

### Step 1: Analyze a Failed Trace
```bash
refinery analyze <TRACE_ID> \
  --project "your-langsmith-project" \
  --expected "The agent should have retrieved the correct billing information" \
  --context "Customer asked about their premium plan pricing"
```

**Expected Output:**
- ✅ Fetches trace from LangSmith
- ✅ AI agent analyzes the trace execution flow
- ✅ Compares actual vs expected behavior
- ✅ Provides root cause diagnosis with confidence level
- ✅ Shows failure type (prompt_issue, context_issue, etc.)

### Step 2: Generate and Preview Fixes
```bash
refinery fix <TRACE_ID> \
  --project "your-langsmith-project" \
  --expected "The agent should have retrieved the correct billing information" \
  --read-impl "**/*prompt*.py" "**/*eval*.py" \
  --codebase /path/to/your/ai/agent/code
```

**Expected Output:**
- ✅ Reads existing prompt/eval files 
- ✅ Generates 3-5 ranked hypotheses
- ✅ Shows specific file changes for each hypothesis
- ✅ Validates changes (dry run by default)
- ✅ Displays risk assessment

### Step 3: Apply Best Fix
```bash
refinery fix <TRACE_ID> \
  --project "your-langsmith-project" \
  --expected "The agent should have retrieved the correct billing information" \
  --apply \
  --codebase /path/to/your/ai/agent/code
```

**Expected Output:**
- ✅ Applies the best hypothesis
- ✅ Creates Git commit with changes
- ✅ Shows commit ID for rollback if needed

## What Each Component Does

### 1. LangSmith Integration (`langsmith_client.py`)
- Fetches traces via LangSmith API
- Handles rate limiting and caching
- Converts to internal trace format

### 2. Failure Analyst (`failure_analyst.py`)
- Analyzes trace execution flow
- Identifies failure patterns
- Compares to domain expert expectations
- Provides structured diagnosis

### 3. Hypothesis Generator (`hypothesis_generator.py`)
- Searches best practices knowledge base
- Generates specific, implementable fixes
- Ranks by likelihood of success and risk
- Creates file change proposals

### 4. Code Manager (`code_manager.py`)
- Safely modifies code files
- Git integration for commits/rollbacks
- Validates changes for security/syntax
- Handles different file types (Python, YAML, JSON)

## Success Criteria

The POC is working correctly if:

1. **Trace Analysis Works:** Can fetch a LangSmith trace and analyze what went wrong
2. **Failure Diagnosis Works:** AI provides meaningful root cause with evidence
3. **Code Reading Works:** Can read existing prompts/evals to understand implementation
4. **Hypothesis Generation Works:** Generates specific, actionable fixes
5. **Safe Code Modification Works:** Can validate and apply changes with Git tracking

## Expected Timeline

- **4 minutes:** Complete failure → diagnosis → fix workflow
- **vs 1 week:** Traditional engineering-dependent approach

## Key Differentiators

- **Domain Expert Empowerment:** Non-technical users can drive AI improvements
- **Context-Aware Analysis:** Understands business requirements, not just technical failures
- **Safe Automation:** Changes are validated and tracked in Git
- **Rapid Iteration:** Multiple hypotheses generated and ranked automatically