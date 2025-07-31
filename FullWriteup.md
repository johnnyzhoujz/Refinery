# Full Write up

# Refinery: Strategic Analysis

## Executive Summary

**What Refinery Is:** The first AI development platform built specifically to accelerate domain expert experimentation and learning, transforming the AI improvement workflow from weeks to hours while enabling non-technical stakeholders to drive AI performance optimization.

**Core Value Proposition:** "While competitors focus on better AI tools, we're building better AI teams." Current tools show you what happened, but Refinery accelerates the complete learning cycle from failure to deployed improvement, enabling domain experts to build competitive moats through rapid iteration.

**Strategic Position:** Not competing with observability tools, but creating a new category: AI Development Platform for Domain Expert Empowerment. Building the infrastructure that enables the people closest to customers to rapidly improve AI performance without engineering bottlenecks.

**Market Opportunity:** AI startups compete on iteration velocity. Domain experts have business judgment but lack rapid AI iteration capability. Refinery compresses the time to develop technical AI judgment while preserving domain expertise.

---

## The Problem: Domain Expert Speed Bottleneck

AI startups compete on iteration velocity. The current improvement cycle—observe failure → diagnose root cause → hypothesize fixes → test solutions → deploy—takes weeks because domain experts (closest to customers) face engineering dependencies and friction at every step.

### Current Reality:

**Diagnosis Gap:** Domain experts see bad outputs but struggle to pinpoint root causes

**Translation Barrier:** Domain experts know what "right" looks like but find it difficult to translate into effective prompts/evals

**Workflow Fragmentation:** Each step requires different tools and engineering handoffs

**Iteration Friction:** Every improvement cycle becomes an engineering project

### The Real Bottleneck: Domain Experts Can't Learn Fast Enough

**The Core Issue:** Domain experts closest to customers understand what good performance looks like, but face significant barriers in improvement cycles due to technical complexity and tool fragmentation. This friction prevents startups from quickly developing proprietary AI assets - specialized prompts, context patterns, evals, and workflows that create competitive moats.

**The Bottleneck Has Shifted:** AI coding tools have accelerated engineering productivity but created a new constraint in domain expert iteration speed. This represents a fundamental shift from engineering constraints to domain expert iteration constraints.

**Specific Pain Points:**

1. **Investigation Bottleneck:** When an AI agent fails, domain experts can see it failed but can't dig into why without engineering help
2. **Hypothesis Paralysis:** No systematic way to generate and test improvement hypotheses - domain experts know something's wrong but not what to try
3. **Implementation Gap:** Domain experts can articulate what better performance looks like but can't translate that insight into working prompts or evals
4. **Testing Friction:** Each experimental fix requires engineering to set up test scenarios, deploy changes, and measure results
5. **Iteration Dependency:** Every improvement cycle becomes an engineering project, blocking rapid experimentation

### Real-World Impact Example

*"Our enterprise customer reported our AI agent gave wrong billing information. Our PM knew this was critical but couldn't investigate directly. Our engineer spent 2 days finding the specific conversation, another day figuring out it was a RAG retrieval issue with our new prompt version, manually created 5 test cases, fixed the prompt, tested it, and deployed. Total time: 1 week. Our competitor with faster iteration tools fixed a similar issue in 4 hours and won the next enterprise deal."*

---

## The Desired State

Domain experts can quickly experiment and improve AI performance through prompts ("what to do") and evals ("typically what not to do") across their entire AI stack with minimal engineering dependencies.

This means intelligent automation that:

**Diagnoses root causes** while preserving domain expert judgment and decision-making

**Translates domain insights** into effective prompts and evals without managing technical overhead, such as model variability and prompting best practices

**Accelerates iteration cycles** with rollback mechanisms and engineering oversight

### The Vision: AI-Powered Domain Expert Empowerment

Making the right technical decisions in AI development can accelerate solutions from months to days, while wrong decisions lead to extended blind alleys. Refinery enables domain experts to make the right technical decisions rapidly through AI-assisted learning.

**Enable Domain Experts to:**

- Investigate AI failures with AI-assisted root cause analysis
- Generate improvement hypotheses based on business context and patterns
- Test fixes rapidly without engineering dependencies
- Deploy improvements with confidence and rollback capabilities
- Build proprietary AI advantages through accelerated learning cycles

**We don't replace technical judgment; we compress the time to develop it.**

---

## The Complexity Curve AI Startups Navigate

After our research into thought leaders, interviews with 6 AI startups, and a survey across different stages, we observed that AI teams usually start with simple prompts but quickly evolve into complex management of interactions and dependencies. As teams push for performant AI agents, they need to master the interconnectedness of the AI system. The competitive advantage goes to teams that can iterate across the AI stack quickly.

### The Four Stages of AI System Evolution

**Stage 1: Just Prompts** → Basic functionality, where most AI teams start. They run into limitations and performance issues quickly.

**Stage 2: Prompts + Evaluations** → Teams add testing and better prompts to improve performance and enhance capabilities. Evaluation complexity grows exponentially as evals become competitive barriers that teams guard as proprietary assets.

**Stage 3: Multi-Agent Workflows** → Multiple prompts and agents working together require orchestration. LangChain observes "most agent failures are context failures," introducing context engineering: managing "the right information at each step of an agent's trajectory" while dealing with memory limitations. Agentic AI represents the most important emerging trend opening new startup opportunities.

**Stage 4: Specialized Models** → For deep AI agents that foundational models can't handle, often requiring fine-tuning or advanced treatments. Most AI startups building agents haven't yet reached this stage.

### The Challenge: Domain Expert Empowerment Across All Stages

**The Bottleneck:** Domain experts closest to customers have real-world knowledge of what good performance looks like, but they can't learn how to translate that knowledge into effective AI systems across this complexity curve. Current tools require engineering dependencies for every experimental iteration, breaking the learning loop that would enable domain experts to discover what works.

**Speed as Competitive Advantage:** Teams must continuously benchmark against frontier capabilities and build defensive moats through specialized AI assets. The startup that enables domain experts to experiment and learn this translation directly while competitors require engineering bottlenecks for every iteration builds superior AI systems.

### Notes from Thought Leaders

Karpathy's June 2025 YC talk established that we've entered "Software 3.0" where "natural language becomes the new programming interface." This isn't theoretical - "25% of Y Combinator startup companies in Winter 2025 had codebases that were 95% AI-generated." But Karpathy warns of critical limitations: LLMs have "jagged intelligence" (excel at complex tasks, fail at simple ones), "hallucinate" facts, and suffer "anterograde amnesia" where memory resets each session.

Wang's complexity framework shows how teams progress: prompt engineering → reinforcement learning → agentic orchestration, with each stage requiring "layered AI architecture" to build competitive moats.

Andrew Ng's January 2025 YC framework validates the emergence of a new bottleneck: "with engineers becoming much faster I don't see product management work designing what to build becoming faster at the same speed." He emphasizes that "execution speed" serves as "a strong predictor for startup's odds of success" and advocates for systematic innovation through rapid prototyping, noting that "if you make the right technical decision, you can solve the problem in a couple days. Make the wrong technical decision, you could chase a blind alley for three months."

---

## Why Now: The Foundation is Built, Domain Experts Need Acceleration

### Market Timing: The Performance Race Begins

**Currently:** Observability tools exist and work - teams can see what their AI systems are doing. Basic eval and context engineering capabilities are available. The foundational infrastructure for building AI agents is in place.

**The Gap:** Many startups building vertical AI agents have deep domain experts but face bottlenecks when trying to improve AI performance based on observability insights. Current tools tell you what happened, but don't accelerate the improvement loop that follows. Domain experts have the business judgment but lack the rapid AI iteration capability that engineering now has.

**The Opportunity:** Building beyond observability and basic capabilities to accelerate the development loop powered by domain experts. The foundation tools exist - now teams need to quickly get insights and drive to improvements.

**Speed Determines Market Winners:** Execution speed serves as a strong predictor for startup success, with AI startups competing directly on iteration velocity. This isn't about nice-to-have productivity tools - it's about essential infrastructure for competitive survival.

---

## Competitive Landscape: The Domain Expert Empowerment Gap

Our competitive research reveals that no existing player offers AI-assisted improvement workflow acceleration specifically designed for domain expert empowerment:

### Arize Phoenix: Technical-First Observability

- **Strength:** Comprehensive observability with billion+ traces processed, strong technical depth
• **Domain Expert Gap:** Shows diagnostic data but doesn't accelerate experimentation cycles. Primarily designed for technical users with limited collaboration features for domain experts
• **Evidence:** No AI-assisted improvement features found in extensive research. Non-technical users need technical support for most tasks

### Humanloop: Collaborative Management Without Intelligence

- **Strength:** Collaborative prompt management for enterprise teams, UI-first collaborative approach
• **Domain Expert Gap:** Collaboration tools without intelligent experimentation assistance. Manual prompt iteration and evaluation processes
• **Evidence:** Pure workflow management, no AI-powered improvement suggestions. Domain experts can contribute but require ongoing technical support

### Helicone: Infrastructure-Focused

- **Strength:** Fast proxy-based observability (Rust-built, 8ms latency)
• **Domain Expert Gap:** Infrastructure focus without experimentation acceleration or domain expert accessibility
• **Evidence:** Logging and monitoring, no improvement intelligence. Technical requirements limit domain expert independence

### PromptLayer: Version Control Without Intelligence

- **Strength:** "First platform built for prompt engineering," version control capabilities
• **Domain Expert Gap:** Management and testing tools without AI-assisted optimization or domain expert empowerment
• **Evidence:** Version control without intelligent suggestions. Domain experts face technical barriers

### Pezzo: Early-Stage with Fundamental Issues

- **Strength:** Open-source with cost optimization features
• **Domain Expert Gap:** Critical functionality failures, complex setup requirements, no AI-assisted features
• **Evidence:** Basic observability features fail in production environments. Platform unsuitable for domain expert use

### The Strategic Opportunity

**Market Position:** "The first AI development platform built specifically for domain expert empowerment"

**Key Insight:** Traditional observability tools were built for technical teams. AI development requires domain expert involvement for competitive advantage.

**Competitive Differentiation:**

**vs. Observability Tools (Arize, Helicone):**

- **Their Value:** "See what happened"
- **Refinery's Value:** "Empower domain experts to make it better faster"
- **Message:** "We don't compete with your observability - we make it actionable for your business experts"

**vs. Collaboration Platforms (Humanloop):**

- **Their Value:** "Collaborate on AI development"
- **Refinery's Value:** "Accelerate domain expert learning and iteration"
- **Message:** "We don't just help teams work together - we help domain experts drive AI improvement independently"

---

## Refinery's Solution: AI-Powered Domain Expert Acceleration

### The 7-Step Transformation

**From Broken Loop to Domain Expert-Driven Workflow:**

```
Observe → Diagnose → Investigate → Hypothesize → Fix → Test → Deploy
  ↑                                                              ↓
  ←←←←←←← AI-Powered Domain Expert Workflow ←←←←←←←←←←←←←←

```

### Before vs. After: Every Step Transformed for Domain Experts

| **Stage** | **Before (Engineering-Dependent)** | **After (Domain Expert-Enabled)** |
| --- | --- | --- |
| **Observe** | Raw logs with no business context | Business-context-aware traces with customer impact analysis |
| **Diagnose** | Time-consuming manual root-cause analysis | AI-assisted diagnosis with domain-relevant explanations |
| **Investigate** | Data scattered across systems, requires technical expertise | Domain expert-friendly investigation with business context |
| **Hypothesize** | Guesswork with no systematic approach | AI copilot suggests business-relevant fixes based on domain patterns |
| **Fix** | Copy-paste edits requiring technical knowledge | Domain insight-to-implementation translation with AI assistance |
| **Test** | Hours to set up scenarios, requires engineering | Rapid testing with domain expert validation workflows |
| **Deploy** | Engineering bottleneck for every change | Domain expert-initiated deployment with safety rails |

### Key Breakthrough: AI-Powered Domain Expert Workflow

**1. Business-Context Diagnosis**

- AI analyzes traces with business impact context
- Connects technical failures to customer experience
- Explains root causes in domain expert-friendly language

**2. Domain-Aware Hypothesis Generation**

- AI proposes fixes based on business context and domain patterns
- Generates relevant tests from real business scenarios
- Suggests experiments based on successful domain-specific patterns

**3. Rapid Domain Expert Testing**
Teams benefit from systematically pursuing innovations through rapid prototyping and experimentation as prototyping costs have plummeted. Refinery enables this rapid experimentation approach for AI improvement:

- Automatic recreation of business scenarios for testing
- Domain expert validation workflows with technical safety
- Continuous learning from domain expert feedback

**4. Domain Expert Empowerment Interface**

- Business-context-aware improvement suggestions
- Natural language to technical implementation translation
- Collaborative features that preserve domain expert decision-making

---

## Market Assessment and Target Customers

### Primary Customer Segments

**Target 1: AI Product Managers at Growing Startups**

- **Profile:** Series A-B companies building AI-first products
- **Pain:** "I know our AI agent needs improvement but I'm blocked by engineering cycles"
- **Value:** Autonomous ability to diagnose, experiment, and improve AI performance
- **Budget:** $10K-50K annually for PM autonomy tools

**Target 2: Domain Expert Teams at AI Startups**

- **Profile:** Non-technical domain experts (legal, medical, finance) at AI companies
- **Pain:** "I understand what good looks like but can't translate it to better AI performance"
- **Value:** Direct ability to improve AI agents using domain expertise
- **Budget:** $25K-100K annually for domain expert empowerment

**Target 3: AI Engineering Teams Seeking Domain Expert Collaboration**

- **Profile:** Series B+ companies with dedicated AI teams
- **Pain:** "Engineers spend 80% of time on prompt iteration instead of building features"
- **Value:** Engineering focuses on building, domain experts handle optimization
- **Budget:** $50K-200K annually for engineering productivity

### Customer Decision Criteria

**Domain Expert Empowerment:** Can our non-technical experts improve AI performance independently?

**Time to Value:** Can we see AI improvements driven by domain experts within 1 week?

**Workflow Integration:** Does this enhance or replace our existing technical workflows?

**Learning Acceleration:** Can our domain experts develop AI improvement capabilities rapidly?

**ROI Measurement:** Can we measure improvement in both iteration speed and AI performance quality?

---

## Investor Challenges and Responses

### "How many teams actually feel this pain right now?"

Pain hits faster than expected with domain expert involvement. Even basic AI agents require constant business-context iteration once you hit real customers. Humanloop's case studies show legal teams were "extremely manual and time-consuming" with spreadsheet-based prompt management. That's not advanced teams - that's anyone moving past demos where domain experts need to contribute.

### "What stops existing players from just adding this feature?"

**Technical-first DNA:** Existing players built for engineers, not domain experts. Adding domain expert features requires fundamental UX and workflow rebuilding, not feature additions.

**Business Model Misalignment:** Current players monetize technical complexity. Domain expert empowerment requires different pricing, support, and success metrics.

**Market Understanding Gap:** Most competitors don't deeply understand domain expert workflows and decision-making processes in AI improvement cycles.

### "Do domain experts actually want to do this work?"

They're already doing it badly. Humanloop testimonials show "legal domain experts" managing prompts in spreadsheets. Alexander Wang emphasizes domain knowledge creates competitive moats. These experts aren't delegating their core IP - they're struggling with inadequate tools that don't serve their workflow needs.

Domain expert founders are personally invested in AI quality and customer experience. They want control over improvements but lack the tools to exercise that control effectively.

### "Is the AI good enough for this meta-task?"

Conservative approach scales gradually. Start with high-confidence suggestions - obvious business-context improvements, clear domain pattern gaps. Human-in-loop validation for everything. Think Copilot's approach: suggest, don't replace. AI handles technical translation, domain experts make business decisions.

Current AI is already sufficient for technical root cause analysis and implementation suggestion. The challenge is making it accessible and actionable for domain experts.

### "How do you actually reach these customers?"

**Distribution through domain expert communities:** AI Product Managers, industry-specific expert networks, and domain expert conferences where AI improvement is becoming a key topic.

**Pain-point-driven adoption:** When AI agents fail in front of customers, domain experts seek solutions urgently. We reach them when they're motivated to gain independence from engineering cycles.

**Bottom-up adoption:** Domain experts who successfully use Refinery become advocates within their organizations and networks, creating organic growth through demonstrated value.