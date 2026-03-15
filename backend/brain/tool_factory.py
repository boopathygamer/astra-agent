"""
Dynamic Tool & Agent Factory — Runtime System Creation.
========================================================
Allows the ASI to create custom tools, agents, and even
entire subsystems at runtime to solve novel problems.

Capabilities:
  1. Create tools from code strings (sandboxed)
  2. Create specialized agents with custom behaviors
  3. Compose pipelines from existing tools
  4. Generate solution templates for unknown problem types
  5. Self-register new capabilities into the Cortex

Classes:
  ToolBlueprint    — Blueprint for a dynamic tool
  AgentBlueprint   — Blueprint for a custom agent
  PipelineBlueprint — Blueprint for a tool pipeline
  ToolFactory      — The factory that creates everything
"""

import ast
import hashlib
import inspect
import json
import logging
import secrets
import textwrap
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
# Blueprints
# ══════════════════════════════════════════════════════════════

@dataclass
class ToolBlueprint:
    """Blueprint for creating a dynamic tool."""
    id: str = ""
    name: str = ""
    description: str = ""
    category: str = "custom"
    input_params: Dict[str, str] = field(default_factory=dict)  # name: type
    output_type: str = "dict"
    code: str = ""
    version: int = 1
    author: str = "asi"
    created_at: float = field(default_factory=time.time)
    safety_checked: bool = False
    enabled: bool = True

    def __post_init__(self):
        if not self.id:
            self.id = f"tool_{secrets.token_hex(4)}"


@dataclass
class AgentBlueprint:
    """Blueprint for creating a custom agent."""
    id: str = ""
    name: str = ""
    role: str = "custom"
    description: str = ""
    expertise: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    behavior_rules: List[str] = field(default_factory=list)
    priority_bias: float = 0.5
    risk_tolerance: float = 0.3
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.id:
            self.id = f"agent_{secrets.token_hex(4)}"


@dataclass
class PipelineBlueprint:
    """Blueprint for a multi-step tool pipeline."""
    id: str = ""
    name: str = ""
    description: str = ""
    steps: List[Dict[str, Any]] = field(default_factory=list)
    error_handling: str = "stop"  # stop, skip, retry
    max_retries: int = 2
    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.id:
            self.id = f"pipe_{secrets.token_hex(4)}"


# ══════════════════════════════════════════════════════════════
# Code Safety Validator
# ══════════════════════════════════════════════════════════════

class CodeSafetyValidator:
    """Validates dynamically generated code for safety."""

    # Dangerous patterns that must NEVER appear
    BLOCKED_IMPORTS = frozenset({
        "subprocess", "shutil", "ctypes", "multiprocessing",
        "signal", "resource", "pty", "fcntl",
    })

    BLOCKED_BUILTINS = frozenset({
        "exec", "eval", "compile", "__import__", "globals", "locals",
        "getattr", "setattr", "delattr", "breakpoint",
    })

    BLOCKED_PATTERNS = [
        "os.system", "os.popen", "os.remove", "os.unlink",
        "os.rmdir", "os.rename", "open(", "pathlib",
        "socket.", "http.", "urllib.",
        "sys.exit", "exit(", "quit(",
    ]

    @classmethod
    def validate(cls, code: str) -> Tuple[bool, str]:
        """Validate code safety. Returns (is_safe, reason)."""
        if not code.strip():
            return False, "Empty code"

        # Parse AST
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {e}"

        # Check imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[0] in cls.BLOCKED_IMPORTS:
                        return False, f"Blocked import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in cls.BLOCKED_IMPORTS:
                    return False, f"Blocked import: {node.module}"

        # Check for blocked builtins
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in cls.BLOCKED_BUILTINS:
                        return False, f"Blocked builtin: {node.func.id}"

        # Check string patterns
        code_lower = code.lower()
        for pattern in cls.BLOCKED_PATTERNS:
            if pattern.lower() in code_lower:
                return False, f"Blocked pattern: {pattern}"

        return True, "Safe"


# ══════════════════════════════════════════════════════════════
# Tool Factory
# ══════════════════════════════════════════════════════════════

class ToolFactory:
    """
    Dynamic factory for creating tools, agents, and pipelines at runtime.

    The ASI uses this to extend its own capabilities when facing
    novel problems that existing tools can't solve.

    Usage:
        factory = ToolFactory(cortex=cortex)

        # Create a custom tool
        tool = factory.create_tool(
            name="sentiment_analyzer",
            description="Analyze text sentiment",
            code='''
def run(text: str) -> dict:
    positive = ["good", "great", "awesome", "love"]
    negative = ["bad", "terrible", "hate", "awful"]
    words = text.lower().split()
    pos = sum(1 for w in words if w in positive)
    neg = sum(1 for w in words if w in negative)
    total = pos + neg or 1
    return {"sentiment": "positive" if pos > neg else "negative",
            "confidence": max(pos, neg) / total}
            ''',
        )

        # Create a pipeline
        pipe = factory.create_pipeline(
            name="full_analysis",
            steps=[
                {"tool": "code_analyzer", "args": {"path": "."}},
                {"tool": "generate_tests", "args": {"source": "$prev.output"}},
            ]
        )

        # Create a custom agent
        agent = factory.create_agent(
            name="DataEngineer",
            expertise=["etl", "data_pipeline", "transformation"],
            tools=["db_query", "file_read", "data_transform"],
        )
    """

    # Pre-built tool templates for common needs
    TOOL_TEMPLATES = {
        "text_processor": {
            "description": "Process and transform text data",
            "code": textwrap.dedent("""
                def run(text: str, operation: str = "wordcount") -> dict:
                    if operation == "wordcount":
                        words = text.split()
                        return {"count": len(words), "unique": len(set(words))}
                    elif operation == "reverse":
                        return {"result": text[::-1]}
                    elif operation == "uppercase":
                        return {"result": text.upper()}
                    elif operation == "summarize":
                        sentences = text.split(".")
                        return {"summary": ". ".join(sentences[:3]) + ".",
                                "total_sentences": len(sentences)}
                    return {"error": f"Unknown operation: {operation}"}
            """).strip(),
        },
        "data_validator": {
            "description": "Validate data against rules",
            "code": textwrap.dedent("""
                def run(data: dict, rules: dict = None) -> dict:
                    rules = rules or {}
                    errors = []
                    for field, rule in rules.items():
                        value = data.get(field)
                        if rule.get("required") and value is None:
                            errors.append(f"Missing required field: {field}")
                        if rule.get("type") and value is not None:
                            expected = rule["type"]
                            if expected == "str" and not isinstance(value, str):
                                errors.append(f"{field} must be string")
                            elif expected == "int" and not isinstance(value, int):
                                errors.append(f"{field} must be integer")
                    return {"valid": len(errors) == 0, "errors": errors}
            """).strip(),
        },
        "pattern_matcher": {
            "description": "Find patterns in text using simple matching",
            "code": textwrap.dedent("""
                def run(text: str, patterns: list = None) -> dict:
                    import re
                    patterns = patterns or []
                    matches = {}
                    for pattern in patterns:
                        found = re.findall(pattern, text)
                        if found:
                            matches[pattern] = found
                    return {"matches": matches, "total": sum(len(v) for v in matches.values())}
            """).strip(),
        },
        "math_solver": {
            "description": "Solve mathematical expressions safely using AST",
            "code": textwrap.dedent("""
                def run(expression: str) -> dict:
                    import ast, math, operator
                    ops = {ast.Add: operator.add, ast.Sub: operator.sub,
                           ast.Mult: operator.mul, ast.Div: operator.truediv,
                           ast.Pow: operator.pow, ast.USub: operator.neg,
                           ast.UAdd: operator.pos, ast.Mod: operator.mod}
                    fns = {"sqrt": math.sqrt, "log": math.log, "sin": math.sin,
                           "cos": math.cos, "abs": abs, "round": round,
                           "pow": pow, "min": min, "max": max}
                    consts = {"pi": math.pi, "e": math.e}
                    def _eval(node):
                        if isinstance(node, ast.Expression):
                            return _eval(node.body)
                        elif isinstance(node, ast.Constant):
                            return node.value
                        elif isinstance(node, ast.BinOp):
                            return ops[type(node.op)](_eval(node.left), _eval(node.right))
                        elif isinstance(node, ast.UnaryOp):
                            return ops[type(node.op)](_eval(node.operand))
                        elif isinstance(node, ast.Call):
                            name = node.func.id if isinstance(node.func, ast.Name) else ""
                            if name in fns:
                                args = [_eval(a) for a in node.args]
                                return fns[name](*args)
                            raise ValueError(f"Unknown function: {name}")
                        elif isinstance(node, ast.Name):
                            if node.id in consts:
                                return consts[node.id]
                            raise ValueError(f"Unknown: {node.id}")
                        raise ValueError(f"Unsupported: {type(node).__name__}")
                    try:
                        tree = ast.parse(expression, mode="eval")
                        result = float(_eval(tree))
                        return {"result": result, "expression": expression}
                    except Exception as e:
                        return {"error": str(e), "expression": expression}
            """).strip(),
        },
        "json_transformer": {
            "description": "Transform JSON data structures",
            "code": textwrap.dedent("""
                def run(data: dict, transformations: list = None) -> dict:
                    import json
                    result = dict(data)
                    transformations = transformations or []
                    for t in transformations:
                        op = t.get("op")
                        key = t.get("key", "")
                        if op == "rename" and key in result:
                            result[t.get("to", key)] = result.pop(key)
                        elif op == "delete" and key in result:
                            del result[key]
                        elif op == "add":
                            result[key] = t.get("value")
                        elif op == "uppercase" and key in result:
                            result[key] = str(result[key]).upper()
                    return {"transformed": result, "operations": len(transformations)}
            """).strip(),
        },
    }

    # Agent templates for common roles
    AGENT_TEMPLATES = {
        "data_engineer": AgentBlueprint(
            name="DataEngineer", role="data_engineering",
            expertise=["etl", "data_pipeline", "transformation", "cleaning"],
            tools=["db_query", "file_read", "data_validator", "json_transformer"],
            behavior_rules=["Validate data before processing",
                           "Log all transformations",
                           "Handle null values gracefully"],
            priority_bias=0.7, risk_tolerance=0.2,
        ),
        "performance_optimizer": AgentBlueprint(
            name="PerformanceOptimizer", role="optimization",
            expertise=["profiling", "caching", "algorithm_optimization", "memory"],
            tools=["code_analyzer", "code_executor", "math_solver"],
            behavior_rules=["Measure before optimizing",
                           "Document performance gains",
                           "Never sacrifice correctness for speed"],
            priority_bias=0.8, risk_tolerance=0.3,
        ),
        "documentation_writer": AgentBlueprint(
            name="DocWriter", role="documentation",
            expertise=["documentation", "api_docs", "tutorials", "readmes"],
            tools=["file_read", "file_write", "code_analyzer", "text_processor"],
            behavior_rules=["Include code examples",
                           "Write for the target audience",
                           "Keep documentation up to date"],
            priority_bias=0.6, risk_tolerance=0.1,
        ),
        "incident_responder": AgentBlueprint(
            name="IncidentResponder", role="incident_response",
            expertise=["debugging", "root_cause", "mitigation", "post_mortem"],
            tools=["code_analyzer", "file_read", "threat_full_scan", "code_executor"],
            behavior_rules=["Contain the issue first",
                           "Document timeline of events",
                           "Identify root cause, not symptoms"],
            priority_bias=1.0, risk_tolerance=0.1,
        ),
    }

    def __init__(self, cortex=None, memory_store=None):
        self.cortex = cortex
        self.memory = memory_store
        self._tools: Dict[str, ToolBlueprint] = {}
        self._agents: Dict[str, AgentBlueprint] = {}
        self._pipelines: Dict[str, PipelineBlueprint] = {}
        self._compiled_tools: Dict[str, Callable] = {}

    # ── Tool Creation ──

    def create_tool(self, name: str, description: str = "",
                    code: str = "", category: str = "custom",
                    input_params: Dict[str, str] = None) -> ToolBlueprint:
        """Create a new tool from code."""
        blueprint = ToolBlueprint(
            name=name, description=description, code=code,
            category=category, input_params=input_params or {},
        )

        # Safety check
        is_safe, reason = CodeSafetyValidator.validate(code)
        blueprint.safety_checked = is_safe

        if not is_safe:
            logger.warning(f"[FACTORY] Tool '{name}' failed safety check: {reason}")
            blueprint.enabled = False
            self._tools[name] = blueprint
            return blueprint

        # Compile the tool
        compiled = self._compile_tool(name, code)
        if compiled:
            self._compiled_tools[name] = compiled
            blueprint.enabled = True

            # Register with cortex if available
            if self.cortex:
                self.cortex.register_tool(name, compiled, description)

        self._tools[name] = blueprint

        # Persist
        if self.memory:
            self.memory.remember(
                f"factory_tool_{name}",
                {"name": name, "description": description, "code": code,
                 "category": category, "safe": is_safe},
                category="factory_tools",
                importance=0.6,
            )

        logger.info(f"[FACTORY] Tool created: {name} (safe={is_safe})")
        return blueprint

    def create_tool_from_template(self, template_name: str,
                                   custom_name: str = "") -> Optional[ToolBlueprint]:
        """Create a tool from a pre-built template."""
        template = self.TOOL_TEMPLATES.get(template_name)
        if not template:
            return None

        name = custom_name or template_name
        return self.create_tool(
            name=name,
            description=template["description"],
            code=template["code"],
            category="template",
        )

    def _compile_tool(self, name: str, code: str) -> Optional[Callable]:
        """Safely compile tool code into a callable function."""
        try:
            # Safe import whitelist
            _SAFE_MODULES = frozenset({
                "math", "re", "json", "ast", "operator",
                "collections", "itertools", "functools",
                "datetime", "string", "textwrap",
            })
            def _safe_import(name, *args, **kwargs):
                if name.split(".")[0] not in _SAFE_MODULES:
                    raise ImportError(f"Import blocked: {name}")
                return __builtins__["__import__"](name, *args, **kwargs) \
                    if isinstance(__builtins__, dict) else __import__(name, *args, **kwargs)

            # Create isolated namespace
            namespace = {"__builtins__": {
                "__import__": _safe_import,
                "len": len, "str": str, "int": int, "float": float,
                "bool": bool, "list": list, "dict": dict, "tuple": tuple,
                "set": set, "range": range, "enumerate": enumerate,
                "zip": zip, "map": map, "filter": filter,
                "sorted": sorted, "reversed": reversed,
                "min": min, "max": max, "sum": sum, "abs": abs,
                "pow": pow, "round": round, "isinstance": isinstance, "type": type,
                "print": lambda *a, **kw: None,  # silenced
                "True": True, "False": False, "None": None,
                "ValueError": ValueError, "TypeError": TypeError,
                "KeyError": KeyError, "IndexError": IndexError,
                "Exception": Exception, "ImportError": ImportError,
            }}

            # Allow safe module imports
            import math
            import re
            import json as json_mod
            import ast as ast_mod
            import operator as operator_mod
            namespace["math"] = math
            namespace["re"] = re
            namespace["json"] = json_mod
            namespace["ast"] = ast_mod
            namespace["operator"] = operator_mod

            exec(code, namespace)  # noqa: S102

            # Find the 'run' function
            if "run" in namespace and callable(namespace["run"]):
                return namespace["run"]

            # Find any callable
            for key, val in namespace.items():
                if callable(val) and not key.startswith("_"):
                    return val

            return None
        except Exception as e:
            logger.error(f"[FACTORY] Compilation failed for '{name}': {e}")
            return None

    # ── Agent Creation ──

    def create_agent(self, name: str, role: str = "custom",
                     expertise: List[str] = None,
                     tools: List[str] = None,
                     behavior_rules: List[str] = None,
                     priority_bias: float = 0.5,
                     risk_tolerance: float = 0.3) -> AgentBlueprint:
        """Create a custom agent blueprint."""
        blueprint = AgentBlueprint(
            name=name, role=role,
            expertise=expertise or [],
            tools=tools or [],
            behavior_rules=behavior_rules or [],
            priority_bias=priority_bias,
            risk_tolerance=risk_tolerance,
        )
        self._agents[name] = blueprint

        # Persist
        if self.memory:
            self.memory.remember(
                f"factory_agent_{name}",
                {"name": name, "role": role, "expertise": expertise,
                 "tools": tools, "rules": behavior_rules},
                category="factory_agents",
                importance=0.6,
            )

        logger.info(f"[FACTORY] Agent created: {name} (role={role})")
        return blueprint

    def create_agent_from_template(self, template_name: str,
                                    custom_name: str = "") -> Optional[AgentBlueprint]:
        """Create an agent from a pre-built template."""
        template = self.AGENT_TEMPLATES.get(template_name)
        if not template:
            return None

        blueprint = AgentBlueprint(
            name=custom_name or template.name,
            role=template.role,
            expertise=list(template.expertise),
            tools=list(template.tools),
            behavior_rules=list(template.behavior_rules),
            priority_bias=template.priority_bias,
            risk_tolerance=template.risk_tolerance,
        )
        self._agents[blueprint.name] = blueprint
        return blueprint

    # ── Pipeline Creation ──

    def create_pipeline(self, name: str, description: str = "",
                        steps: List[Dict] = None,
                        error_handling: str = "stop") -> PipelineBlueprint:
        """
        Create a multi-step tool pipeline.

        Steps format:
            [
                {"tool": "tool_name", "args": {"key": "value"}},
                {"tool": "tool_2", "args": {"input": "$prev.output"}},
            ]

        Special variables in args:
            $prev.output  — Output from previous step
            $prev.result  — Full result dict from previous step
            $step_N.output — Output from step N (0-indexed)
        """
        blueprint = PipelineBlueprint(
            name=name, description=description,
            steps=steps or [], error_handling=error_handling,
        )
        self._pipelines[name] = blueprint
        logger.info(f"[FACTORY] Pipeline created: {name} ({len(steps or [])} steps)")
        return blueprint

    def execute_pipeline(self, name: str, initial_input: Dict = None) -> Dict[str, Any]:
        """Execute a previously created pipeline."""
        pipeline = self._pipelines.get(name)
        if not pipeline:
            return {"success": False, "error": f"Pipeline '{name}' not found"}

        results = []
        prev_result = initial_input or {}

        for i, step in enumerate(pipeline.steps):
            tool_name = step.get("tool", "")
            raw_args = step.get("args", {})

            # Resolve variable references
            resolved_args = self._resolve_pipeline_vars(raw_args, results, prev_result)

            # Execute tool
            if tool_name in self._compiled_tools:
                try:
                    result = self._compiled_tools[tool_name](**resolved_args)
                    if not isinstance(result, dict):
                        result = {"output": result}
                    result["success"] = True
                except Exception as e:
                    result = {"success": False, "error": str(e)}
            elif self.cortex:
                result = self.cortex._execute_tool(tool_name, resolved_args)
            else:
                result = {"success": True, "output": f"Simulated: {tool_name}",
                          "simulated": True}

            result["step"] = i
            result["tool"] = tool_name
            results.append(result)
            prev_result = result

            # Error handling
            if not result.get("success"):
                if pipeline.error_handling == "stop":
                    break
                elif pipeline.error_handling == "retry":
                    for retry in range(pipeline.max_retries):
                        result = self.cortex._execute_tool(tool_name, resolved_args) \
                            if self.cortex else result
                        if result.get("success"):
                            break

        return {
            "pipeline": name,
            "steps_total": len(pipeline.steps),
            "steps_completed": sum(1 for r in results if r.get("success")),
            "success": all(r.get("success") for r in results),
            "results": results,
        }

    def _resolve_pipeline_vars(self, args: Dict, results: List[Dict],
                                prev: Dict) -> Dict:
        """Resolve $prev and $step_N references in pipeline args."""
        resolved = {}
        for key, value in args.items():
            if isinstance(value, str):
                if value == "$prev.output":
                    resolved[key] = prev.get("output", prev)
                elif value == "$prev.result":
                    resolved[key] = prev
                elif value.startswith("$step_"):
                    try:
                        parts = value.split(".")
                        idx = int(parts[0].replace("$step_", ""))
                        field = parts[1] if len(parts) > 1 else "output"
                        resolved[key] = results[idx].get(field, results[idx])
                    except (IndexError, ValueError):
                        resolved[key] = value
                else:
                    resolved[key] = value
            else:
                resolved[key] = value
        return resolved

    # ── Auto-Solve (Problem → Custom Tool) ──

    def auto_solve(self, problem_description: str) -> Dict[str, Any]:
        """
        Analyze a problem and automatically create the right tool/pipeline.
        This is the ASI's self-extension mechanism.
        """
        desc = problem_description.lower()

        # Match to templates
        if any(w in desc for w in ["text", "string", "parse", "word"]):
            tool = self.create_tool_from_template("text_processor",
                                                   f"auto_{secrets.token_hex(3)}")
            return {"type": "tool", "template": "text_processor", "tool": tool.name if tool else None}

        elif any(w in desc for w in ["validate", "check", "verify", "rule"]):
            tool = self.create_tool_from_template("data_validator",
                                                   f"auto_{secrets.token_hex(3)}")
            return {"type": "tool", "template": "data_validator", "tool": tool.name if tool else None}

        elif any(w in desc for w in ["pattern", "regex", "match", "find"]):
            tool = self.create_tool_from_template("pattern_matcher",
                                                   f"auto_{secrets.token_hex(3)}")
            return {"type": "tool", "template": "pattern_matcher", "tool": tool.name if tool else None}

        elif any(w in desc for w in ["math", "calculate", "compute", "formula"]):
            tool = self.create_tool_from_template("math_solver",
                                                   f"auto_{secrets.token_hex(3)}")
            return {"type": "tool", "template": "math_solver", "tool": tool.name if tool else None}

        elif any(w in desc for w in ["transform", "convert", "json", "data"]):
            tool = self.create_tool_from_template("json_transformer",
                                                   f"auto_{secrets.token_hex(3)}")
            return {"type": "tool", "template": "json_transformer", "tool": tool.name if tool else None}

        elif any(w in desc for w in ["debug", "incident", "crash", "error"]):
            agent = self.create_agent_from_template("incident_responder")
            return {"type": "agent", "template": "incident_responder",
                    "agent": agent.name if agent else None}

        elif any(w in desc for w in ["document", "readme", "guide", "tutorial"]):
            agent = self.create_agent_from_template("documentation_writer")
            return {"type": "agent", "template": "documentation_writer",
                    "agent": agent.name if agent else None}

        elif any(w in desc for w in ["slow", "performance", "optimize", "cache"]):
            agent = self.create_agent_from_template("performance_optimizer")
            return {"type": "agent", "template": "performance_optimizer",
                    "agent": agent.name if agent else None}

        else:
            # No template matched — create a generic analysis pipeline
            self.create_pipeline(
                name=f"solve_{secrets.token_hex(3)}",
                description=f"Auto-generated pipeline for: {problem_description}",
                steps=[
                    {"tool": "code_analyzer", "args": {"description": problem_description}},
                    {"tool": "web_search", "args": {"query": problem_description}},
                ],
            )
            return {"type": "pipeline", "template": "generic_analysis",
                    "description": "Created analysis pipeline"}

    # ── Inventory ──

    def list_tools(self) -> List[Dict]:
        return [{"name": t.name, "category": t.category, "enabled": t.enabled,
                 "safe": t.safety_checked, "description": t.description}
                for t in self._tools.values()]

    def list_agents(self) -> List[Dict]:
        return [{"name": a.name, "role": a.role, "expertise": a.expertise,
                 "tools": a.tools}
                for a in self._agents.values()]

    def list_pipelines(self) -> List[Dict]:
        return [{"name": p.name, "steps": len(p.steps),
                 "description": p.description}
                for p in self._pipelines.values()]

    def list_templates(self) -> Dict[str, List[str]]:
        return {
            "tools": list(self.TOOL_TEMPLATES.keys()),
            "agents": list(self.AGENT_TEMPLATES.keys()),
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "tools_created": len(self._tools),
            "tools_enabled": sum(1 for t in self._tools.values() if t.enabled),
            "agents_created": len(self._agents),
            "pipelines_created": len(self._pipelines),
            "compiled_tools": len(self._compiled_tools),
            "templates_available": {
                "tools": len(self.TOOL_TEMPLATES),
                "agents": len(self.AGENT_TEMPLATES),
            },
        }
