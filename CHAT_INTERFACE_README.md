# Refinery Chat Interface

A simple, conversational interface for Refinery that makes AI agent debugging feel more natural and interactive.

## Quick Start

```bash
# Interactive chat mode
refinery chat

# With specific project
refinery chat --project customer-service

# With specific codebase path  
refinery chat --codebase /path/to/agent
```

## What It Does

The chat interface provides a friendly, step-by-step conversation for analyzing AI agent failures:

1. **🤖 Welcome** - Explains what information is needed
2. **📝 Gather Info** - Asks for trace ID and expected behavior  
3. **🔍 Analyze** - Runs the full Refinery analysis
4. **📊 Results** - Shows diagnosis with rich formatting
5. **🛠️ Fix Option** - Offers to apply fixes directly

## Example Interaction

```
🤖 Refinery Agent
Hi! I'll help you analyze and fix AI agent failures.

What's the trace ID? 60b467c0-b9db-4ee4-934a-ad23a15bd8cd

What should have happened? The agent should acknowledge it has no memory

🔍 Fetching trace from LangSmith...
📊 Analyzing trace execution flow... (this may take a minute)

┌─────────────────────── Trace Analysis ────────────────────────┐
│ Execution Flow:                                                │
│ • Step 1: User asked about memory capabilities                │
│ • Step 2: Agent claimed memory storage abilities              │
│ • Step 3: No memory disclaimer found                          │
│                                                                │
│ Issues Identified:                                             │
│ • Missing memory limitation instructions                       │
│ • No capability disclaimers in responses                      │
└────────────────────────────────────────────────────────────────┘

┌──────────────────────── Gap Analysis ─────────────────────────┐
│ Behavioral Differences:                                        │
│ • Expected: Acknowledge no memory                              │
│ • Actual: Claimed memory capabilities                          │
│                                                                │
│ Missing Context:                                               │
│ • Memory limitation instructions                               │
│ • Capability disclaimers                                       │
└────────────────────────────────────────────────────────────────┘

┌────────────────── Root Cause Diagnosis ───────────────────────┐
│ Type: Context Issue | Confidence: HIGH                        │
│                                                                │
│ Root Cause:                                                    │
│ System prompts lack explicit instructions about memory        │
│ limitations                                                    │
│                                                                │
│ Evidence:                                                      │
│ • No memory disclaimers in prompts                            │
│ • Agent made false capability claims                          │
└────────────────────────────────────────────────────────────────┘

✅ Analysis complete! Use 'refinery analyze --apply' with this trace ID if you want to generate and apply fixes.
```

## Architecture - Built for Future Evolution

### Clean Separation of Concerns

```
refinery/interfaces/
├── chat_interface.py     # Interface implementations (current: CLI)
├── chat_session.py       # Core reusable business logic  
└── __init__.py          # Package exports
```

### Easy Interface Replacement

The current implementation can be easily upgraded:

```python
# Today: Simple CLI prompts
interface = ChatInterface()

# Future: Natural language understanding
interface = NLInterface(llm_provider=create_llm_provider()) 

# Future: Web UI
interface = StreamlitInterface(port=8501)
```

**The core business logic in `chat_session.py` stays exactly the same!**

## Current Features

- ✅ **Simple CLI prompts** - No command-line syntax to remember
- ✅ **Rich formatting** - Beautiful console output with colors and panels  
- ✅ **Full integration** - Uses all existing Refinery analysis logic
- ✅ **Context aware** - Works with saved project contexts
- ✅ **Comprehensive analysis** - Shows trace analysis, gap analysis, and diagnosis
- ✅ **Progress indicators** - Multiple progress updates during long analysis
- ✅ **Detailed evidence** - Shows execution flow, behavioral differences, and evidence
- ✅ **Error handling** - Graceful error messages and validation

## Future Possibilities

### Natural Language Interface
```python
# User says: "trace abc123 failed because bot claimed memory but it can't remember"
# NL interface extracts: trace_id="abc123", expected="acknowledge no memory"
```

### Web Interface  
```python
# Rich web UI with:
# - File upload for traces
# - Visual trace timeline
# - Interactive fix previews
# - Project management dashboard
```

### API Interface
```python
# RESTful endpoints:
# POST /analyze {"trace_id": "...", "expected": "..."}  
# GET /projects/{name}/context
# POST /fixes/{id}/apply
```

## Implementation Details

### BaseChatInterface (Abstract)
Defines the contract that all interfaces must implement:
- `get_trace_id()` - How to get trace ID from user
- `get_expected_behavior()` - How to get expected behavior  
- `show_diagnosis()` - How to display results
- `confirm_action()` - How to get user confirmation

### ChatInterface (Current Implementation)  
Simple CLI implementation using Rich console:
- Prompts for input with `console.input()`
- Rich panels and markdown for output
- Color-coded success/error messages

### run_chat_session() (Core Logic)
Reusable business logic that works with any interface:
1. Gather user inputs via interface methods
2. Set up Refinery context and orchestrator  
3. Run analysis using existing logic
4. Display results via interface methods
5. Handle fix application if requested

## Testing

```bash
# Test basic interface functionality
python test_chat_interface.py

# Test with demos and examples
python examples/chat_interface_demo.py

# Test live (requires actual trace ID)
refinery chat --project demo
```

## Benefits

### For Users
- **Conversational** - Natural step-by-step interaction
- **No syntax** - No need to remember command-line flags
- **Visual** - Rich formatted output easier to read
- **Interactive** - Immediate fix application option

### For Developers  
- **Maintainable** - Clean separation of interface vs logic
- **Extensible** - Easy to add new interface types
- **Reusable** - Core logic works across all interfaces
- **Future-proof** - Can evolve interfaces without breaking changes

## Integration with Existing Refinery

The chat interface is a **thin wrapper** around existing functionality:

- ✅ **Zero changes** to core analysis logic
- ✅ **Reuses** orchestrator, context management, and agents
- ✅ **Compatible** with all existing features (extract-from-trace, context persistence, etc)
- ✅ **Additive** - Existing CLI commands unchanged

Users can freely mix and match:
```bash
# Set up context with existing command
refinery analyze abc123 --project test --extract-from-trace --expected "should work"

# Then use chat for subsequent analyses  
refinery chat --project test
```

---

**Status: Ready to ship** ✅

This provides immediate value while establishing the foundation for much richer interfaces in the future.