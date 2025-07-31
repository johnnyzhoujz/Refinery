# Refinery POC - Updated Implementation Plan

## Current Status: Core Infrastructure Complete ✅
- ✅ Project structure and shared interfaces
- ✅ LangSmith integration with caching/rate limiting
- ✅ Basic failure analyst and hypothesis generator agents
- ✅ Code manager with Git integration and safety checks
- ✅ CLI interface with orchestrator

## Critical Missing Components Identified 🚨

### **1. Customer Agent Implementation Parser**
**Problem:** We can't understand the customer's AI agent setup
**Need:** Deep analysis of customer codebase to build "agent blueprint"

**Requirements:**
- Parse prompt files and understand their roles (system, user, template, etc.)
- Analyze eval files and what they test
- Map relationships between prompts (workflows, chains, hierarchies)
- Detect model configurations and parameters
- Understand orchestration patterns (LangChain, custom workflows)
- Build structured context that our agents can reason about

**Implementation:**
```python
class CustomerAgentParser:
    async def analyze_agent_implementation(self, codebase_path: str) -> AgentBlueprint:
        # Returns comprehensive understanding of customer's agent
        pass
    
    async def extract_prompt_hierarchy(self) -> Dict[str, PromptInfo]
    async def extract_eval_patterns(self) -> Dict[str, EvalInfo]  
    async def detect_model_usage(self) -> List[ModelConfig]
    async def map_workflow_patterns(self) -> WorkflowGraph
```

### **2. Detailed System Prompts for Our Agents**
**Problem:** Our agents lack clear, detailed instructions
**Need:** Comprehensive system prompts that define agent behavior precisely

**Failure Analyst System Prompt Requirements:**
- Role definition as AI systems debugger
- Specific focus areas (prompts, context, retrieval, orchestration)
- Analysis methodology (trace parsing, evidence gathering)
- Output format requirements (structured diagnosis)
- Confidence calibration guidelines
- Business context integration instructions

**Hypothesis Generator System Prompt Requirements:**
- Role definition as prompt engineer and optimizer
- Model-specific optimization strategies
- Risk assessment methodology
- Ranking criteria (likelihood of success, implementation complexity, side effects)
- Code change guidelines (what to modify, what to avoid)
- Safety considerations and validation requirements

**Code Manager System Prompt Requirements:**
- Role definition as safe code modification specialist
- File type handling strategies
- Git workflow best practices
- Validation and safety check procedures
- Rollback decision criteria

### **3. Model-Specific Best Practices Database**
**Problem:** Generic fixes don't work - each model needs specific approaches
**Need:** Comprehensive database of prompting guides for each major model

**Required Model Guides:**
- **OpenAI GPT-4/GPT-3.5**: Official prompting guide, best practices, JSON mode, function calling
- **Anthropic Claude**: Constitutional AI, XML tags, thinking patterns, tool usage
- **Google Gemini**: Multi-modal prompts, code execution, reasoning chains
- **Azure OpenAI**: Enterprise patterns, function calling, deployment-specific optimizations
- **Meta Llama**: Open-source optimization, fine-tuning patterns
- **Mistral**: European AI patterns, efficiency optimizations

**Implementation Strategy:**
```python
class ModelSpecificGuides:
    async def fetch_official_guide(self, model_provider: str) -> PromptingGuide
    async def extract_best_practices(self, guide: PromptingGuide) -> List[BestPractice]
    async def generate_model_specific_fix(self, diagnosis: Diagnosis, model: str) -> Hypothesis
```

**Data Sources to Fetch:**
- OpenAI: https://platform.openai.com/docs/guides/prompt-engineering
- Anthropic: https://docs.anthropic.com/claude/docs/prompt-engineering
- Google: https://ai.google.dev/docs/prompt_best_practices
- Azure: https://learn.microsoft.com/en-us/azure/ai-services/openai/concepts/prompt-engineering
- Mistral: https://docs.mistral.ai/guides/prompting/
- Meta: https://llama.meta.com/docs/how-to-guides/prompting

### **4. Enhanced Context Management**
**Problem:** Current context passing is too simplistic
**Need:** Rich context objects that preserve customer implementation details

**Context Enhancement Requirements:**
- Structured prompt information with metadata
- Eval test case understanding and coverage analysis
- Model parameter tracking and optimization history
- Workflow dependency mapping
- Performance metrics and failure pattern history

## Updated Implementation Priority

### **Phase 1: Critical Missing Components (High Priority)**

#### **1A. Customer Agent Implementation Parser**
- Build comprehensive codebase analysis
- Extract prompt hierarchy and relationships
- Understand eval patterns and coverage
- Detect model configurations and usage patterns
- Create structured AgentBlueprint representation

#### **1B. Enhanced System Prompts**
- Write detailed system prompts for each agent (2000+ words each)
- Include role definitions, methodologies, output formats
- Add business context integration guidelines
- Define confidence calibration and risk assessment criteria

#### **1C. Model-Specific Best Practices Database**
- Fetch official prompting guides from all major providers
- Extract and structure best practices for programmatic use
- Build model detection and guide selection logic
- Implement model-specific hypothesis generation

### **Phase 2: Integration and Enhancement (Medium Priority)**

#### **2A. Enhanced Failure Analysis**
- Integrate customer implementation context into analysis
- Add model-specific failure pattern recognition
- Improve evidence gathering with code context
- Enhance diagnosis accuracy with implementation understanding

#### **2B. Contextual Hypothesis Generation**
- Use customer implementation context for targeted fixes
- Apply model-specific best practices automatically
- Generate more precise, implementable changes
- Improve risk assessment with code understanding

#### **2C. Advanced Code Modification**
- Focus on prompt and eval file modifications
- Add template-aware editing (Jinja2, f-strings, etc.)
- Implement prompt versioning and A/B testing suggestions
- Add eval test case generation and enhancement

### **Phase 3: Production Readiness (Lower Priority)**

#### **3A. Performance Optimization**
- Cache parsed customer implementations
- Optimize context passing between agents
- Implement streaming responses for long operations
- Add parallel processing for multiple hypotheses

#### **3B. Advanced Features**
- Interactive hypothesis refinement
- Multi-model optimization suggestions
- Automated eval expansion based on failure patterns
- Integration with customer CI/CD workflows

#### **3C. Enterprise Features**
- Multi-tenant support
- Advanced logging and monitoring
- Integration with enterprise Git workflows
- Custom model support (fine-tuned, local models)

## Detailed Implementation Tasks

### **Task 1: Build Customer Agent Implementation Parser**
```python
# New file: refinery/analysis/agent_parser.py
class CustomerAgentParser:
    """Comprehensive analysis of customer AI agent implementation."""
    
    async def analyze_agent_implementation(self, codebase_path: str) -> AgentBlueprint
    async def extract_prompt_files(self) -> Dict[str, PromptInfo]
    async def analyze_prompt_relationships(self) -> PromptHierarchy
    async def extract_eval_files(self) -> Dict[str, EvalInfo]
    async def detect_model_configurations(self) -> List[ModelConfig]
    async def map_workflow_patterns(self) -> WorkflowGraph
    async def analyze_dependencies(self) -> DependencyGraph
```

### **Task 2: Create Detailed System Prompts**
```python
# New file: refinery/prompts/system_prompts.py
FAILURE_ANALYST_SYSTEM_PROMPT = """
You are an expert AI systems debugger with deep expertise in LLM agent failures...
[2000+ word detailed system prompt]
"""

HYPOTHESIS_GENERATOR_SYSTEM_PROMPT = """
You are a world-class prompt engineer and AI agent optimizer...
[2000+ word detailed system prompt]
"""
```

### **Task 3: Build Model-Specific Best Practices Database**
```python
# New file: refinery/knowledge/best_practices.py
class ModelSpecificGuides:
    """Database of model-specific prompting best practices."""
    
    async def fetch_openai_guide(self) -> OpenAIGuide
    async def fetch_anthropic_guide(self) -> AnthropicGuide
    async def fetch_google_guide(self) -> GoogleGuide
    async def detect_customer_model(self, agent_blueprint: AgentBlueprint) -> str
    async def get_model_specific_practices(self, model: str) -> List[BestPractice]
```

## Success Criteria (Updated)

### **Technical Success:**
1. **Customer Implementation Understanding:** Can parse and understand any customer AI agent setup
2. **Model-Specific Optimization:** Generates fixes appropriate for the specific model being used
3. **Context-Aware Analysis:** Uses customer's actual prompts/evals in failure analysis
4. **Precise Modifications:** Makes targeted changes to prompts/evals with model best practices
5. **Safe Operations:** All changes validated against customer's implementation patterns

### **Business Success:**
1. **Domain Expert Empowerment:** Non-technical users can drive improvements independently
2. **Time Reduction:** 4-minute failure-to-fix cycle vs 1-week traditional approach
3. **Quality Improvements:** Fixes actually work because they follow model-specific best practices
4. **Customer Trust:** Safe, reversible operations with comprehensive validation
5. **Competitive Advantage:** Customers iterate faster than competitors

## Resource Requirements

### **Web Scraping for Best Practices:**
- Automated fetching of official prompting guides
- Extraction and structuring of best practices
- Regular updates as guides evolve
- Backup strategies for guide availability

### **Implementation Parsing:**
- Advanced AST analysis for Python
- Template parsing (Jinja2, Mustache, etc.)
- YAML/JSON configuration analysis
- Workflow pattern recognition

### **Enhanced LLM Usage:**
- More sophisticated prompts requiring higher token usage
- Model-specific optimization requiring multiple LLM calls
- Context-rich analysis requiring larger context windows
- Structured output parsing and validation

This updated plan addresses all the critical gaps identified and provides a clear roadmap for building a production-ready Refinery POC that can actually help domain experts improve their AI agents.