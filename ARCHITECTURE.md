# Refinery POC Architecture Document

## Executive Summary

Refinery accelerates AI agent improvement cycles from weeks to hours by empowering domain experts to diagnose failures and implement fixes without engineering dependencies. This POC demonstrates the core capability: AI-assisted failure analysis and hypothesis generation with direct code modification.

The architecture embodies three critical insights:
1. **Compound error rates kill AI agents** - Even 99% reliable prompts fail 4% of the time when chained (Karpathy's "jagged intelligence")
2. **Domain experts have the knowledge but lack the tools** - They understand what "right" looks like but can't translate it to technical improvements
3. **Speed determines winners** - The startup that iterates fastest on AI performance wins the market

## Design Philosophy

### First Principles (Karpathy-inspired)
- **LLMs are compilers for natural language**: Treat prompts as code that compiles to behavior
- **Context is everything**: Failures usually stem from missing or wrong context, not model limitations
- **Evaluation is your test suite**: Without rigorous evals, you're flying blind
- **Determinism is an illusion**: Build for stochastic systems, not deterministic ones

### Engineering Principles (Carmack-inspired)
- **Minimize abstraction layers**: Direct access to traces, prompts, and evals
- **Optimize the critical path**: Failure → Diagnosis → Fix → Test must be <10 minutes
- **Measure everything**: Token usage, latency, success rates
- **Fail fast and explicitly**: No silent failures or ambiguous states

### Strategic Principles (Altman-inspired)
- **Iteration velocity > Perfect architecture**: Ship fast, learn, improve
- **Empower the domain expert**: They're closer to customers than engineers
- **Build moats through specialized knowledge**: Prompts and evals are IP
- **Compress learning cycles**: What takes competitors weeks should take hours

### Safety Principles (Amodei-inspired)
- **Human-in-the-loop by default**: No autonomous code deployment
- **Reversibility**: Every change must be undoable
- **Bounded autonomy**: Clear limits on what the system can modify
- **Audit trails**: Complete history of all modifications

## System Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        Domain Expert CLI                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐ │
│  │  Trace       │    │    Failure       │    │  Hypothesis  │ │
│  │  Ingestion   │───▶│    Analyst       │───▶│  Generator   │ │
│  │  Service     │    │    Agent         │    │  Agent       │ │
│  └──────────────┘    └──────────────────┘    └──────────────┘ │
│         │                     │                       │          │
│         ▼                     ▼                       ▼          │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Shared Services Layer                  │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐ │  │
│  │  │ LLM Router │  │ Code Context │  │ Best Practices  │ │  │
│  │  │            │  │   Manager    │  │      RAG        │ │  │
│  │  └────────────┘  └──────────────┘  └─────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Data Layer                             │  │
│  │  ┌────────────┐  ┌──────────────┐  ┌─────────────────┐ │  │
│  │  │ Trace Store│  │ Code Repo    │  │ Change History  │ │  │
│  │  │            │  │  Access      │  │                 │ │  │
│  │  └────────────┘  └──────────────┘  └─────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Component Details

#### 1. Trace Ingestion Service
**Purpose**: Fetch and normalize traces from LangSmith (extensible to other platforms)

**Key Design Decisions**:
- **Lazy loading**: Only fetch trace details when needed (minimize API calls)
- **Caching layer**: 15-minute cache for recently accessed traces
- **Structured extraction**: Convert LangSmith's run format to internal schema

**Interface**:
```python
class TraceIngestion:
    async def fetch_trace(self, trace_id: str) -> Trace
    async def fetch_failed_traces(self, project: str, time_range: TimeRange) -> List[TraceSummary]
    async def fetch_trace_hierarchy(self, trace_id: str) -> TraceTree
```

**Critical Considerations**:
- Handle nested traces elegantly using `dotted_order`
- Preserve all metadata for root cause analysis
- Support incremental loading for large traces

#### 2. Failure Analyst Agent
**Purpose**: Diagnose root causes of AI agent failures using trace analysis

**Key Capabilities**:
- **Multi-level analysis**: System, prompt, context, and output levels
- **Pattern recognition**: Identify common failure modes
- **Interactive diagnosis**: Domain expert provides business context

**Tool Implementations**:
```python
class FailureAnalystTools:
    def extract_trace_breakdown(self, trace: Trace) -> TraceAnalysis:
        """
        Breaks down trace into:
        - Execution flow (what happened when)
        - Context at each step
        - Inputs/outputs transformation
        - Error propagation path
        """
        
    def compare_to_expected(self, 
                          actual: TraceAnalysis, 
                          expected: DomainExpertExpectation) -> GapAnalysis:
        """
        Identifies gaps between actual and expected:
        - Behavioral differences
        - Missing context or capabilities
        - Incorrect assumptions in prompts
        """
```

**LLM Prompting Strategy**:
```python
FAILURE_ANALYST_PROMPT = """
You are an expert AI systems debugger. Given a trace of an AI agent execution:

1. UNDERSTAND THE FLOW
   - Map the execution path
   - Identify data transformations
   - Note decision points

2. DIAGNOSE FAILURES
   - Where did behavior diverge from expected?
   - What context was missing/incorrect?
   - Which assumptions failed?

3. CATEGORIZE ROOT CAUSE
   - Prompt issue (ambiguous instructions)
   - Context issue (missing/wrong information)
   - Model limitation (task beyond capability)
   - Orchestration issue (wrong flow/sequence)

Trace: {trace}
Expected behavior: {expected}

Provide structured analysis focusing on actionable insights.
"""
```

#### 3. Hypothesis Generator Agent
**Purpose**: Generate and test improvement hypotheses based on failure diagnosis

**Key Capabilities**:
- **Multi-strategy generation**: Different approaches for different failure types
- **Best practices integration**: RAG over OpenAI, Anthropic, and community guides
- **Risk assessment**: Evaluate potential side effects of changes

**Tool Implementations**:
```python
class HypothesisGeneratorTools:
    def search_prompting_guides(self, 
                              failure_type: str, 
                              model: str) -> List[RelevantPractice]:
        """
        RAG search over:
        - Model-specific prompting guides
        - Community best practices
        - Internal knowledge base of successful fixes
        """
        
    def generate_hypotheses(self, 
                          diagnosis: Diagnosis, 
                          context: CodeContext) -> List[Hypothesis]:
        """
        Generates 3-5 hypotheses ranked by:
        - Likelihood of fixing the issue
        - Implementation complexity
        - Risk of side effects
        """
        
    def file_edit(self, 
                 hypothesis: Hypothesis, 
                 target_file: str) -> FileChanges:
        """
        Implements hypothesis as code changes:
        - Preserves formatting and style
        - Adds safety checks where needed
        - Documents changes inline
        """
```

**Hypothesis Generation Strategy**:
```python
HYPOTHESIS_GENERATOR_PROMPT = """
Given this diagnosis of an AI agent failure:
{diagnosis}

Current implementation:
{current_code}

Generate specific, testable hypotheses to fix the issue:

For each hypothesis provide:
1. CHANGE: Specific modification to make
2. RATIONALE: Why this addresses the root cause
3. EXAMPLE: Before/after code snippet
4. RISKS: Potential side effects
5. CONFIDENCE: Low/Medium/High

Prioritize hypotheses that:
- Address root cause, not symptoms
- Minimize changes (Occam's razor)
- Follow established best practices
- Maintain backward compatibility
"""
```

#### 4. Code Context Manager
**Purpose**: Intelligent code understanding and modification

**Key Features**:
- **Dependency tracking**: Understand which files relate to each other
- **Change impact analysis**: Predict effects of modifications
- **Style preservation**: Maintain existing code conventions

**Implementation Approach**:
```python
class CodeContextManager:
    def __init__(self, repo_path: str):
        self.repo = GitRepo(repo_path)
        self.ast_cache = {}
        
    def get_related_files(self, file_path: str) -> List[str]:
        """Find files that import or are imported by target"""
        
    def analyze_change_impact(self, changes: FileChanges) -> ImpactReport:
        """Predict what else might break"""
        
    def apply_changes_safely(self, changes: FileChanges) -> Result:
        """Apply changes with rollback capability"""
```

### Data Flow

#### Critical Path: Failure → Fix
```
1. OBSERVE (30s)
   User reports: "AI agent gave wrong billing info to customer"
   ↓
2. FETCH (10s)
   Pull trace from LangSmith with full context
   ↓
3. ANALYZE (60s)
   Failure Analyst identifies: "RAG retrieved old pricing doc"
   ↓
4. HYPOTHESIZE (45s)
   Generator suggests: "Add date filtering to retrieval prompt"
   ↓
5. IMPLEMENT (30s)
   Direct edit to prompt file with safety checks
   ↓
6. VALIDATE (60s)
   Test against similar queries
   ↓
Total: ~4 minutes (vs. 1 week traditional)
```

### Performance Optimizations

#### Token Usage Minimization
- **Semantic compression**: Summarize long traces before analysis
- **Incremental loading**: Only expand relevant parts of trace
- **Caching**: Reuse analysis results across similar failures

#### Latency Reduction
- **Parallel analysis**: Run multiple hypotheses concurrently
- **Streaming responses**: Show progress during long operations
- **Pre-computation**: Cache common patterns and fixes

### Safety Mechanisms

#### Change Control
```python
class SafetyGuard:
    def validate_change(self, change: FileChange) -> ValidationResult:
        """
        Checks:
        - No credentials or secrets added
        - No destructive operations
        - Maintains syntactic validity
        - Preserves existing tests
        """
        
    def require_approval(self, change: FileChange) -> bool:
        """
        Requires explicit approval for:
        - Changes to core system files
        - Modifications affecting >N lines
        - Deletions of any kind
        - New external dependencies
        """
```

#### Rollback Capability
- Every change creates a git commit
- Automatic rollback on test failure
- Change history with reasoning preserved

### Error Handling Philosophy

**Fail Explicitly**: No silent failures or degraded functionality
```python
class RefineryError(Exception):
    """Base exception with context preservation"""
    
class TraceNotFoundError(RefineryError):
    """Explicit error when trace doesn't exist"""
    
class AnalysisFailureError(RefineryError):
    """When we can't determine root cause"""
    
class UnsafeChangeError(RefineryError):
    """When proposed change violates safety rules"""
```

### Extensibility Points

#### Adding New Observability Platforms
```python
class ObservabilityAdapter(ABC):
    @abstractmethod
    async def fetch_trace(self, trace_id: str) -> Trace
    
class LangSmithAdapter(ObservabilityAdapter):
    """Current implementation"""
    
class DatadogAdapter(ObservabilityAdapter):
    """Future: Datadog RUM traces"""
    
class OpenTelemetryAdapter(ObservabilityAdapter):
    """Future: Generic OTel support"""
```

#### Supporting New Failure Types
- Pluggable analyzers for specific domains
- Custom hypothesis generators
- Domain-specific best practices

### Metrics and Monitoring

#### Success Metrics
- **Time to Fix**: Failure reported → Fix deployed
- **Fix Success Rate**: Fixes that actually work
- **Domain Expert Autonomy**: % of fixes without eng help

#### Operational Metrics
- **Token usage per fix**
- **Cache hit rates**
- **LLM latency by operation**
- **Safety intervention rate**

### Technical Debt Acceptable for POC

1. **Single-tenant assumptions**: No multi-tenancy isolation
2. **Limited auth**: Simple API key, no fine-grained permissions
3. **In-memory caching**: No distributed cache
4. **Synchronous operations**: No job queue for long analyses
5. **Basic logging**: Console output, no structured logging

### Technical Excellence Required Even for POC

1. **Git integration**: Proper commits, never corrupt repo
2. **Error handling**: Clear errors, no crashes
3. **Code safety**: Never break user's codebase
4. **Data integrity**: Never lose traces or changes
5. **Idempotency**: Re-running operations is safe

## Implementation Roadmap

### Phase 1: Core Loop (Week 1)
- [ ] LangSmith integration
- [ ] Basic failure analysis
- [ ] Simple prompt modifications
- [ ] CLI skeleton

### Phase 2: Intelligence (Week 2)
- [ ] Advanced root cause analysis
- [ ] Best practices RAG
- [ ] Hypothesis ranking
- [ ] Safety guards

### Phase 3: Polish (Week 3)
- [ ] Performance optimization
- [ ] Comprehensive error handling
- [ ] Documentation
- [ ] Partner testing

## Key Insights and Warnings

### What Makes This Hard
1. **LLMs lie convincingly**: Generated fixes might look good but break things
2. **Context window limits**: Can't analyze massive traces naively
3. **Prompt brittleness**: Small changes can have large effects
4. **Multi-file coherence**: Changes must work together

### What Makes This Valuable
1. **Domain expert empowerment**: They have the knowledge, we provide tools
2. **Iteration speed**: 4 minutes vs 1 week changes everything
3. **Learning acceleration**: Each fix teaches the system
4. **Competitive advantage**: Fast iteration → better AI → more customers

### Critical Success Factors
1. **Trust**: Domain experts must trust the system won't break things
2. **Speed**: Must be faster than asking engineering
3. **Accuracy**: Fixes must actually work
4. **Usability**: Non-technical users must succeed

## Conclusion

This architecture optimizes for the critical path: helping domain experts fix AI agent failures quickly and safely. By combining intelligent analysis, automated hypothesis generation, and safe code modification, we compress the learning cycle that creates competitive advantage.

The POC proves the core thesis: domain experts can improve AI agents without engineering dependencies. The full platform will add collaboration, versioning, and production deployment, but this foundation demonstrates the transformative potential.

Remember: **We're not building better AI tools. We're building better AI teams.**