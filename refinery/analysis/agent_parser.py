"""
Comprehensive Customer Agent Implementation Parser

This module provides tools to analyze any AI agent codebase and understand its structure,
including prompts, evaluations, model configurations, and workflow patterns.
"""

import ast
import json
import logging
import os
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import toml

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PromptInfo:
    """Information about a prompt file and its characteristics."""
    file_path: str
    prompt_type: str  # system, user, template, few_shot
    content: str
    variables: List[str] = field(default_factory=list)  # extracted template variables
    template_engine: str = "none"  # jinja2, fstring, mustache, none
    model_references: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # other files this references
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass 
class EvalInfo:
    """Information about evaluation files and test cases."""
    file_path: str
    eval_type: str  # unit_test, integration_test, performance_test
    test_cases: List[Dict[str, Any]] = field(default_factory=list)
    prompts_tested: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelConfig:
    """Configuration information for AI models."""
    model_name: str
    provider: str  # openai, anthropic, google, etc
    parameters: Dict[str, Any] = field(default_factory=dict)  # temperature, max_tokens, etc
    usage_context: str = ""  # where this model is used
    file_location: str = ""


@dataclass  
class WorkflowPattern:
    """Identified workflow patterns in the codebase."""
    pattern_type: str  # chain, parallel, conditional, loop
    components: List[str] = field(default_factory=list)
    flow_description: str = ""
    entry_points: List[str] = field(default_factory=list)


@dataclass
class AgentBlueprint:
    """Complete blueprint of an AI agent codebase."""
    codebase_path: str
    main_language: str
    framework: Optional[str] = None  # langchain, llamaindex, custom
    prompts: Dict[str, PromptInfo] = field(default_factory=dict)
    evals: Dict[str, EvalInfo] = field(default_factory=dict)
    models: List[ModelConfig] = field(default_factory=list)
    workflows: List[WorkflowPattern] = field(default_factory=list)
    dependencies: Dict[str, str] = field(default_factory=dict)
    architecture_summary: str = ""


class TemplateVariableExtractor:
    """Extract template variables from different template engines."""
    
    @staticmethod
    def extract_jinja2_variables(content: str) -> List[str]:
        """Extract variables from Jinja2 templates."""
        # Matches {{ variable }}, {% for var in vars %}, etc.
        patterns = [
            r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\s*\}\}',  # {{ var }}
            r'\{%\s*for\s+([a-zA-Z_][a-zA-Z0-9_]*)\s+in\s+[^%]*%\}',  # {% for var in ... %}
            r'\{%\s*if\s+([a-zA-Z_][a-zA-Z0-9_]*)',  # {% if var %}
            r'\{%\s*set\s+([a-zA-Z_][a-zA-Z0-9_]*)',  # {% set var %}
        ]
        
        variables = set()
        for pattern in patterns:
            matches = re.findall(pattern, content)
            variables.update(matches)
        
        return list(variables)
    
    @staticmethod
    def extract_fstring_variables(content: str) -> List[str]:
        """Extract variables from f-string templates."""
        # Matches {variable} in f-strings
        pattern = r'f["\'].*?\{([a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*)\}.*?["\']'
        matches = re.findall(pattern, content, re.DOTALL)
        return list(set(matches))
    
    @staticmethod
    def extract_format_variables(content: str) -> List[str]:
        """Extract variables from .format() and % formatting."""
        variables = set()
        
        # {variable} format
        format_pattern = r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}'
        variables.update(re.findall(format_pattern, content))
        
        # %(variable)s format
        percent_pattern = r'%\(([a-zA-Z_][a-zA-Z0-9_]*)\)[sd]'
        variables.update(re.findall(percent_pattern, content))
        
        return list(variables)
    
    @staticmethod
    def extract_mustache_variables(content: str) -> List[str]:
        """Extract variables from Mustache templates."""
        # Matches {{variable}} and {{{variable}}}
        pattern = r'\{\{\{?([a-zA-Z_][a-zA-Z0-9_]*)\}?\}\}'
        matches = re.findall(pattern, content)
        return list(set(matches))


class FileTypeDetector:
    """Detect file types and purposes automatically."""
    
    PROMPT_INDICATORS = [
        'prompt', 'template', 'system', 'user', 'instruction',
        'few_shot', 'example', 'context', 'persona'
    ]
    
    EVAL_INDICATORS = [
        'test', 'eval', 'benchmark', 'validation', 'assess',
        'metric', 'score', 'performance'
    ]
    
    CONFIG_INDICATORS = [
        'config', 'setting', 'param', 'option', 'env'
    ]
    
    @classmethod
    def detect_file_purpose(cls, file_path: str, content: str) -> str:
        """Detect the purpose of a file based on path and content."""
        file_path_lower = file_path.lower()
        content_lower = content.lower()
        
        # Check for prompt files
        if any(indicator in file_path_lower for indicator in cls.PROMPT_INDICATORS):
            return 'prompt'
        
        # Check for eval files
        if any(indicator in file_path_lower for indicator in cls.EVAL_INDICATORS):
            return 'eval'
            
        # Check for config files
        if any(indicator in file_path_lower for indicator in cls.CONFIG_INDICATORS):
            return 'config'
        
        # Content-based detection
        if any(keyword in content_lower for keyword in ['system:', 'user:', 'assistant:']):
            return 'prompt'
        
        if any(keyword in content_lower for keyword in ['def test_', 'class test', 'assert']):
            return 'eval'
            
        return 'unknown'


class ASTAnalyzer:
    """Analyze Python AST to understand code structure."""
    
    def __init__(self):
        self.model_providers = {
            'openai': ['OpenAI', 'openai', 'gpt-', 'ChatOpenAI'],
            'anthropic': ['Anthropic', 'anthropic', 'claude-', 'ChatAnthropic'],
            'google': ['google', 'gemini', 'palm', 'bard'],
            'huggingface': ['transformers', 'HuggingFace', 'pipeline'],
            'cohere': ['cohere', 'Cohere'],
            'ai21': ['ai21', 'AI21'],
        }
    
    def analyze_python_file(self, file_path: str, content: str) -> Dict[str, Any]:
        """Analyze a Python file and extract relevant information."""
        try:
            tree = ast.parse(content)
            analysis = {
                'imports': self._extract_imports(tree),
                'functions': self._extract_functions(tree),
                'classes': self._extract_classes(tree),
                'model_configs': self._extract_model_configs(tree, content),
                'string_literals': self._extract_string_literals(tree),
                'variables': self._extract_variables(tree),
            }
            return analysis
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            return {}
    
    def _extract_imports(self, tree: ast.AST) -> List[str]:
        """Extract import statements."""
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ''
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}")
        return imports
    
    def _extract_functions(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract function definitions."""
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    'name': node.name,
                    'args': [arg.arg for arg in node.args.args],
                    'decorators': [ast.unparse(dec) for dec in node.decorator_list],
                    'docstring': ast.get_docstring(node),
                    'line_number': node.lineno,
                }
                functions.append(func_info)
        return functions
    
    def _extract_classes(self, tree: ast.AST) -> List[Dict[str, Any]]:
        """Extract class definitions."""
        classes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_info = {
                    'name': node.name,
                    'bases': [ast.unparse(base) for base in node.bases],
                    'methods': [],
                    'docstring': ast.get_docstring(node),
                    'line_number': node.lineno,
                }
                
                # Extract methods
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        class_info['methods'].append(item.name)
                
                classes.append(class_info)
        return classes
    
    def _extract_model_configs(self, tree: ast.AST, content: str) -> List[Dict[str, Any]]:
        """Extract model configurations from code."""
        configs = []
        
        # Look for model instantiations
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func_name = self._get_call_name(node)
                if func_name and any(provider_term in func_name for provider_terms in self.model_providers.values() for provider_term in provider_terms):
                    config = {
                        'call_name': func_name,
                        'args': [],
                        'kwargs': {},
                        'line_number': node.lineno,
                    }
                    
                    # Extract arguments
                    for arg in node.args:
                        if isinstance(arg, ast.Constant):
                            config['args'].append(arg.value)
                    
                    # Extract keyword arguments
                    for keyword in node.keywords:
                        if isinstance(keyword.value, ast.Constant):
                            config['kwargs'][keyword.arg] = keyword.value.value
                    
                    configs.append(config)
        
        return configs
    
    def _get_call_name(self, node: ast.Call) -> str:
        """Get the name of a function call."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            return ast.unparse(node.func)
        return ""
    
    def _extract_string_literals(self, tree: ast.AST) -> List[str]:
        """Extract string literals that might be prompts."""
        strings = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                # Filter out short strings that are unlikely to be prompts
                if len(node.value) > 50:
                    strings.append(node.value)
        return strings
    
    def _extract_variables(self, tree: ast.AST) -> List[str]:
        """Extract variable names."""
        variables = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                variables.add(node.id)
        return list(variables)


class FrameworkDetector:
    """Detect AI frameworks and orchestration patterns."""
    
    FRAMEWORK_SIGNATURES = {
        'langchain': [
            'langchain', 'LangChain', 'from langchain',
            'Chain', 'LLMChain', 'ConversationChain',
            'PromptTemplate', 'ChatPromptTemplate'
        ],
        'llamaindex': [
            'llama_index', 'LlamaIndex', 'from llama_index',
            'ServiceContext', 'VectorStoreIndex', 'GPTIndex'
        ],
        'haystack': [
            'haystack', 'Haystack', 'from haystack',
            'Pipeline', 'DocumentStore', 'Retriever'
        ],
        'autogen': [
            'autogen', 'AutoGen', 'from autogen',
            'ConversableAgent', 'AssistantAgent'
        ],
        'crewai': [
            'crewai', 'CrewAI', 'from crewai',
            'Agent', 'Task', 'Crew'
        ],
    }
    
    @classmethod
    def detect_framework(cls, content: str, imports: List[str]) -> Optional[str]:
        """Detect which AI framework is being used."""
        content_lower = content.lower()
        imports_str = ' '.join(imports).lower()
        
        for framework, signatures in cls.FRAMEWORK_SIGNATURES.items():
            score = 0
            for signature in signatures:
                if signature.lower() in content_lower:
                    score += 1
                if signature.lower() in imports_str:
                    score += 2  # Imports are stronger indicators
            
            if score >= 2:  # Threshold for framework detection
                return framework
        
        return None


class WorkflowAnalyzer:
    """Analyze workflow patterns in the codebase."""
    
    def analyze_workflows(self, files_analysis: Dict[str, Dict[str, Any]]) -> List[WorkflowPattern]:
        """Analyze workflow patterns across files."""
        workflows = []
        
        # Look for chain patterns
        chain_workflows = self._detect_chain_patterns(files_analysis)
        workflows.extend(chain_workflows)
        
        # Look for parallel patterns
        parallel_workflows = self._detect_parallel_patterns(files_analysis)
        workflows.extend(parallel_workflows)
        
        # Look for conditional patterns
        conditional_workflows = self._detect_conditional_patterns(files_analysis)
        workflows.extend(conditional_workflows)
        
        return workflows
    
    def _detect_chain_patterns(self, files_analysis: Dict[str, Dict[str, Any]]) -> List[WorkflowPattern]:
        """Detect sequential chain patterns."""
        patterns = []
        
        for file_path, analysis in files_analysis.items():
            functions = analysis.get('functions', [])
            
            # Look for functions that call other functions in sequence
            for func in functions:
                if 'chain' in func['name'].lower():
                    pattern = WorkflowPattern(
                        pattern_type='chain',
                        components=[func['name']],
                        flow_description=f"Chain pattern in {func['name']}",
                        entry_points=[func['name']]
                    )
                    patterns.append(pattern)
        
        return patterns
    
    def _detect_parallel_patterns(self, files_analysis: Dict[str, Dict[str, Any]]) -> List[WorkflowPattern]:
        """Detect parallel execution patterns."""
        patterns = []
        
        for file_path, analysis in files_analysis.items():
            content = analysis.get('content', '')
            
            # Look for async/await or threading patterns
            if 'async' in content or 'threading' in content or 'concurrent' in content:
                pattern = WorkflowPattern(
                    pattern_type='parallel',
                    components=[file_path],
                    flow_description="Parallel execution pattern detected",
                    entry_points=[]
                )
                patterns.append(pattern)
        
        return patterns
    
    def _detect_conditional_patterns(self, files_analysis: Dict[str, Dict[str, Any]]) -> List[WorkflowPattern]:
        """Detect conditional flow patterns."""
        patterns = []
        
        for file_path, analysis in files_analysis.items():
            functions = analysis.get('functions', [])
            
            # Look for functions with conditional logic
            for func in functions:
                if func['docstring'] and ('condition' in func['docstring'].lower() or 'if' in func['docstring'].lower()):
                    pattern = WorkflowPattern(
                        pattern_type='conditional',
                        components=[func['name']],
                        flow_description=f"Conditional pattern in {func['name']}",
                        entry_points=[func['name']]
                    )
                    patterns.append(pattern)
        
        return patterns


class CustomerAgentParser:
    """Main parser for analyzing customer agent codebases."""
    
    def __init__(self):
        self.template_extractor = TemplateVariableExtractor()
        self.file_detector = FileTypeDetector()
        self.ast_analyzer = ASTAnalyzer()
        self.framework_detector = FrameworkDetector()
        self.workflow_analyzer = WorkflowAnalyzer()
        
        # File extensions to analyze
        self.code_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx'}
        self.config_extensions = {'.json', '.yaml', '.yml', '.toml', '.ini', '.env'}
        self.text_extensions = {'.txt', '.md', '.rst'}
        
    def parse_codebase(self, codebase_path: str) -> AgentBlueprint:
        """Parse an entire codebase and create an AgentBlueprint."""
        logger.info(f"Starting analysis of codebase: {codebase_path}")
        
        codebase_path = Path(codebase_path).resolve()
        
        # Initialize blueprint
        blueprint = AgentBlueprint(
            codebase_path=str(codebase_path),
            main_language=self._detect_main_language(codebase_path)
        )
        
        # Collect all relevant files
        files_to_analyze = self._collect_files(codebase_path)
        logger.info(f"Found {len(files_to_analyze)} files to analyze")
        
        # Analyze each file
        files_analysis = {}
        for file_path in files_to_analyze:
            try:
                analysis = self._analyze_file(file_path)
                if analysis:
                    files_analysis[str(file_path)] = analysis
            except Exception as e:
                logger.warning(f"Error analyzing {file_path}: {e}")
        
        # Extract information from file analyses
        self._extract_prompts(files_analysis, blueprint)
        self._extract_evals(files_analysis, blueprint)
        self._extract_models(files_analysis, blueprint)
        self._extract_dependencies(files_analysis, blueprint)
        
        # Detect framework
        all_content = ' '.join([analysis.get('content', '') for analysis in files_analysis.values()])
        all_imports = []
        for analysis in files_analysis.values():
            all_imports.extend(analysis.get('imports', []))
        
        blueprint.framework = self.framework_detector.detect_framework(all_content, all_imports)
        
        # Analyze workflows
        blueprint.workflows = self.workflow_analyzer.analyze_workflows(files_analysis)
        
        # Generate architecture summary
        blueprint.architecture_summary = self._generate_architecture_summary(blueprint)
        
        logger.info("Codebase analysis completed")
        return blueprint
    
    def _collect_files(self, codebase_path: Path) -> List[Path]:
        """Collect all relevant files for analysis."""
        files = []
        
        # Directories to skip
        skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env', '.env'}
        
        for root, dirs, filenames in os.walk(codebase_path):
            # Remove skip directories
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            
            for filename in filenames:
                file_path = Path(root) / filename
                extension = file_path.suffix.lower()
                
                # Include relevant file types
                if (extension in self.code_extensions or 
                    extension in self.config_extensions or 
                    extension in self.text_extensions or
                    self._is_likely_prompt_file(file_path)):
                    files.append(file_path)
        
        return files
    
    def _is_likely_prompt_file(self, file_path: Path) -> bool:
        """Check if a file is likely to contain prompts."""
        filename_lower = file_path.name.lower()
        return any(indicator in filename_lower for indicator in self.file_detector.PROMPT_INDICATORS)
    
    def _detect_main_language(self, codebase_path: Path) -> str:
        """Detect the main programming language of the codebase."""
        language_counts = {}
        
        for root, dirs, filenames in os.walk(codebase_path):
            for filename in filenames:
                extension = Path(filename).suffix.lower()
                if extension in ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.cpp', '.c', '.go', '.rs']:
                    language_counts[extension] = language_counts.get(extension, 0) + 1
        
        if not language_counts:
            return 'unknown'
        
        # Map extensions to languages
        ext_to_lang = {
            '.py': 'python',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.cpp': 'cpp',
            '.c': 'c',
            '.go': 'go',
            '.rs': 'rust',
        }
        
        most_common_ext = max(language_counts, key=language_counts.get)
        return ext_to_lang.get(most_common_ext, 'unknown')
    
    def _analyze_file(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Analyze a single file."""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except Exception as e:
            logger.warning(f"Could not read {file_path}: {e}")
            return None
        
        analysis = {
            'path': str(file_path),
            'content': content,
            'extension': file_path.suffix.lower(),
            'purpose': self.file_detector.detect_file_purpose(str(file_path), content),
        }
        
        # Perform extension-specific analysis
        if file_path.suffix.lower() == '.py':
            ast_analysis = self.ast_analyzer.analyze_python_file(str(file_path), content)
            analysis.update(ast_analysis)
        elif file_path.suffix.lower() in ['.json']:
            analysis.update(self._analyze_json_file(content))
        elif file_path.suffix.lower() in ['.yaml', '.yml']:
            analysis.update(self._analyze_yaml_file(content))
        elif file_path.suffix.lower() == '.toml':
            analysis.update(self._analyze_toml_file(content))
        
        return analysis
    
    def _analyze_json_file(self, content: str) -> Dict[str, Any]:
        """Analyze JSON configuration files."""
        try:
            data = json.loads(content)
            return {'json_data': data}
        except json.JSONDecodeError:
            return {}
    
    def _analyze_yaml_file(self, content: str) -> Dict[str, Any]:
        """Analyze YAML configuration files."""
        try:
            data = yaml.safe_load(content)
            return {'yaml_data': data}
        except yaml.YAMLError:
            return {}
    
    def _analyze_toml_file(self, content: str) -> Dict[str, Any]:
        """Analyze TOML configuration files."""
        try:
            data = toml.loads(content)
            return {'toml_data': data}
        except toml.TomlDecodeError:
            return {}
    
    def _extract_prompts(self, files_analysis: Dict[str, Dict[str, Any]], blueprint: AgentBlueprint):
        """Extract prompt information from analyzed files."""
        for file_path, analysis in files_analysis.items():
            if analysis.get('purpose') == 'prompt' or self._contains_prompt_content(analysis):
                prompt_info = self._create_prompt_info(file_path, analysis)
                blueprint.prompts[file_path] = prompt_info
    
    def _contains_prompt_content(self, analysis: Dict[str, Any]) -> bool:
        """Check if file content suggests it contains prompts."""
        content = analysis.get('content', '').lower()
        
        # Look for prompt-like patterns
        prompt_patterns = [
            r'system\s*:\s*',
            r'user\s*:\s*',
            r'assistant\s*:\s*',
            r'you are\s+',
            r'act as\s+',
            r'instruction\s*:\s*',
            r'prompt\s*:\s*',
        ]
        
        return any(re.search(pattern, content) for pattern in prompt_patterns)
    
    def _create_prompt_info(self, file_path: str, analysis: Dict[str, Any]) -> PromptInfo:
        """Create PromptInfo from file analysis."""
        content = analysis.get('content', '')
        
        # Detect template engine and extract variables
        template_engine = 'none'
        variables = []
        
        if '{{' in content and '}}' in content:
            template_engine = 'jinja2'
            variables = self.template_extractor.extract_jinja2_variables(content)
        elif 'f"' in content or "f'" in content:
            template_engine = 'fstring'
            variables = self.template_extractor.extract_fstring_variables(content)
        elif '{' in content and '}' in content:
            if template_engine == 'none':
                template_engine = 'format'
                variables = self.template_extractor.extract_format_variables(content)
        
        # Detect prompt type
        prompt_type = self._detect_prompt_type(content)
        
        # Find model references
        model_references = self._find_model_references(content)
        
        return PromptInfo(
            file_path=file_path,
            prompt_type=prompt_type,
            content=content,
            variables=variables,
            template_engine=template_engine,
            model_references=model_references,
            dependencies=[],  # Will be filled by dependency analysis
            metadata={'file_size': len(content)}
        )
    
    def _detect_prompt_type(self, content: str) -> str:
        """Detect the type of prompt."""
        content_lower = content.lower()
        
        if 'system:' in content_lower or 'system message' in content_lower:
            return 'system'
        elif 'user:' in content_lower or 'human:' in content_lower:
            return 'user'
        elif 'example' in content_lower or 'few-shot' in content_lower:
            return 'few_shot'
        elif '{{' in content or '{' in content:
            return 'template'
        else:
            return 'generic'
    
    def _find_model_references(self, content: str) -> List[str]:
        """Find references to AI models in content."""
        model_patterns = [
            r'gpt-[0-9\.]+',
            r'claude-[a-z0-9\-]+',
            r'gemini-[a-z0-9\-]+',
            r'palm-[a-z0-9\-]+',
        ]
        
        references = []
        for pattern in model_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            references.extend(matches)
        
        return list(set(references))
    
    def _extract_evals(self, files_analysis: Dict[str, Dict[str, Any]], blueprint: AgentBlueprint):
        """Extract evaluation information from analyzed files."""
        for file_path, analysis in files_analysis.items():
            if analysis.get('purpose') == 'eval' or self._contains_eval_content(analysis):
                eval_info = self._create_eval_info(file_path, analysis)
                blueprint.evals[file_path] = eval_info
    
    def _contains_eval_content(self, analysis: Dict[str, Any]) -> bool:
        """Check if file content suggests it contains evaluations."""
        content = analysis.get('content', '').lower()
        functions = analysis.get('functions', [])
        
        # Look for test functions
        test_functions = [f for f in functions if f['name'].startswith('test_')]
        if test_functions:
            return True
        
        # Look for evaluation patterns
        eval_patterns = [
            r'def test_',
            r'class test',
            r'assert\s+',
            r'benchmark',
            r'evaluate',
            r'score',
            r'metric',
        ]
        
        return any(re.search(pattern, content) for pattern in eval_patterns)
    
    def _create_eval_info(self, file_path: str, analysis: Dict[str, Any]) -> EvalInfo:
        """Create EvalInfo from file analysis."""
        content = analysis.get('content', '')
        functions = analysis.get('functions', [])
        
        # Extract test cases
        test_cases = []
        for func in functions:
            if func['name'].startswith('test_'):
                test_cases.append({
                    'name': func['name'],
                    'docstring': func.get('docstring', ''),
                    'line_number': func.get('line_number', 0)
                })
        
        # Detect eval type
        eval_type = self._detect_eval_type(content, functions)
        
        # Find prompts being tested
        prompts_tested = self._find_tested_prompts(content)
        
        # Extract success criteria
        success_criteria = self._extract_success_criteria(content)
        
        return EvalInfo(
            file_path=file_path,
            eval_type=eval_type,
            test_cases=test_cases,
            prompts_tested=prompts_tested,
            success_criteria=success_criteria,
            metadata={'num_test_cases': len(test_cases)}
        )
    
    def _detect_eval_type(self, content: str, functions: List[Dict[str, Any]]) -> str:
        """Detect the type of evaluation."""
        content_lower = content.lower()
        
        if 'performance' in content_lower or 'benchmark' in content_lower:
            return 'performance_test'
        elif 'integration' in content_lower:
            return 'integration_test'
        elif any(f['name'].startswith('test_') for f in functions):
            return 'unit_test'
        else:
            return 'unknown'
    
    def _find_tested_prompts(self, content: str) -> List[str]:
        """Find prompts that are being tested."""
        # Look for file references or prompt names
        prompt_patterns = [
            r'prompt[_\s]*file\s*=\s*["\']([^"\']+)["\']',
            r'load[_\s]*prompt\s*\(["\']([^"\']+)["\']',
            r'["\']([^"\']*prompt[^"\']*\.(?:txt|md|json))["\']',
        ]
        
        prompts = []
        for pattern in prompt_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            prompts.extend(matches)
        
        return list(set(prompts))
    
    def _extract_success_criteria(self, content: str) -> List[str]:
        """Extract success criteria from evaluation content."""
        criteria = []
        
        # Look for assert statements
        assert_pattern = r'assert\s+([^,\n]+)'
        assert_matches = re.findall(assert_pattern, content)
        criteria.extend(assert_matches)
        
        # Look for explicit criteria
        criteria_patterns = [
            r'expect\s+([^,\n]+)',
            r'should\s+([^,\n]+)',
            r'must\s+([^,\n]+)',
        ]
        
        for pattern in criteria_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            criteria.extend(matches)
        
        return criteria[:10]  # Limit to first 10 criteria
    
    def _extract_models(self, files_analysis: Dict[str, Dict[str, Any]], blueprint: AgentBlueprint):
        """Extract model configuration information."""
        for file_path, analysis in files_analysis.items():
            model_configs = analysis.get('model_configs', [])
            
            for config in model_configs:
                model_info = self._create_model_config(file_path, config, analysis)
                if model_info:
                    blueprint.models.append(model_info)
    
    def _create_model_config(self, file_path: str, config: Dict[str, Any], analysis: Dict[str, Any]) -> Optional[ModelConfig]:
        """Create ModelConfig from configuration data."""
        call_name = config.get('call_name', '')
        
        # Determine provider
        provider = 'unknown'
        for prov, signatures in self.ast_analyzer.model_providers.items():
            if any(sig in call_name for sig in signatures):
                provider = prov
                break
        
        # Extract model name
        model_name = 'unknown'
        if 'model' in config.get('kwargs', {}):
            model_name = config['kwargs']['model']
        elif config.get('args'):
            # First argument might be model name
            model_name = str(config['args'][0])
        
        # Extract parameters
        parameters = config.get('kwargs', {}).copy()
        parameters.pop('model', None)  # Remove model name from parameters
        
        return ModelConfig(
            model_name=model_name,
            provider=provider,
            parameters=parameters,
            usage_context=f"Used in {Path(file_path).name}",
            file_location=file_path
        )
    
    def _extract_dependencies(self, files_analysis: Dict[str, Dict[str, Any]], blueprint: AgentBlueprint):
        """Extract dependency relationships between files."""
        for file_path, analysis in files_analysis.items():
            imports = analysis.get('imports', [])
            
            # Map imports to local files
            for imp in imports:
                # Check if import refers to a local file
                potential_files = self._resolve_import_to_files(imp, blueprint.codebase_path)
                for dep_file in potential_files:
                    if dep_file in files_analysis:
                        blueprint.dependencies[file_path] = dep_file
    
    def _resolve_import_to_files(self, import_name: str, codebase_path: str) -> List[str]:
        """Resolve an import statement to potential file paths."""
        potential_files = []
        
        # Handle relative imports
        if import_name.startswith('.'):
            # Relative import - would need more context to resolve properly
            return potential_files
        
        # Convert module path to file path
        module_parts = import_name.split('.')
        
        # Try different combinations
        for i in range(len(module_parts)):
            partial_path = '/'.join(module_parts[:i+1])
            
            # Try as Python file
            py_file = Path(codebase_path) / f"{partial_path}.py"
            if py_file.exists():
                potential_files.append(str(py_file))
            
            # Try as package
            init_file = Path(codebase_path) / partial_path / "__init__.py"
            if init_file.exists():
                potential_files.append(str(init_file))
        
        return potential_files
    
    def _generate_architecture_summary(self, blueprint: AgentBlueprint) -> str:
        """Generate a summary of the codebase architecture."""
        summary_parts = []
        
        # Language and framework
        summary_parts.append(f"Main language: {blueprint.main_language}")
        if blueprint.framework:
            summary_parts.append(f"Framework: {blueprint.framework}")
        
        # Component counts
        summary_parts.append(f"Prompts: {len(blueprint.prompts)}")
        summary_parts.append(f"Evaluations: {len(blueprint.evals)}")
        summary_parts.append(f"Model configurations: {len(blueprint.models)}")
        summary_parts.append(f"Workflow patterns: {len(blueprint.workflows)}")
        
        # Model providers
        if blueprint.models:
            providers = set(model.provider for model in blueprint.models)
            summary_parts.append(f"AI providers: {', '.join(providers)}")
        
        # Workflow types
        if blueprint.workflows:
            workflow_types = set(wf.pattern_type for wf in blueprint.workflows)
            summary_parts.append(f"Workflow patterns: {', '.join(workflow_types)}")
        
        return "; ".join(summary_parts)


# Convenience function for easy usage
def parse_agent_codebase(codebase_path: str) -> AgentBlueprint:
    """Parse an agent codebase and return an AgentBlueprint."""
    parser = CustomerAgentParser()
    return parser.parse_codebase(codebase_path)


if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) > 1:
        codebase_path = sys.argv[1]
        blueprint = parse_agent_codebase(codebase_path)
        
        print(f"Analyzed codebase: {blueprint.codebase_path}")
        print(f"Architecture: {blueprint.architecture_summary}")
        print(f"Found {len(blueprint.prompts)} prompts")
        print(f"Found {len(blueprint.evals)} evaluations") 
        print(f"Found {len(blueprint.models)} model configurations")
        print(f"Found {len(blueprint.workflows)} workflow patterns")
    else:
        print("Usage: python agent_parser.py <codebase_path>")