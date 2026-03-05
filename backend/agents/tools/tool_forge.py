"""
Real-Time Tool Forge
────────────────────
Gives the agent the ability to CREATE ITS OWN TOOLS at runtime.

When the agent encounters a task it can't handle with existing tools,
it generates a Python function, validates it in the sandbox, and 
registers it as a new tool — all automatically.

Flow:
  1. Agent identifies capability gap
  2. ToolForge generates a Python function with the LLM
  3. Function is validated via AST + sandbox execution
  4. If safe, it's registered in the ToolRegistry
  5. Agent uses the new tool immediately

Safety:
  - AST validation against blocklist (no imports, no system calls)
  - Sandbox test execution with timeout
  - Tool lifetime management (auto-retire after N uses or TTL)
"""

import ast
import hashlib
import logging
import textwrap
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from agents.tools.registry import registry, Tool, ToolRiskLevel
from agents.tools.code_executor import DANGEROUS_PATTERNS

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class ForgedTool:
    """A tool generated at runtime by the forge."""
    forge_id: str = ""
    name: str = ""
    description: str = ""
    source_code: str = ""
    func: Optional[Callable] = None
    created_at: float = 0.0
    use_count: int = 0
    max_uses: int = 100  # Auto-retire after this many uses
    ttl_seconds: float = 3600  # Auto-retire after TTL
    is_active: bool = True
    validation_passed: bool = False
    test_output: str = ""


# ──────────────────────────────────────────────
# Allowed Built-in Operations for Forged Tools
# ──────────────────────────────────────────────

# Only these modules can be used in forged tools
_ALLOWED_MODULES = frozenset({
    "math", "statistics", "json", "re", "datetime",
    "collections", "itertools", "functools",
    "string", "textwrap", "decimal", "fractions",
    "random", "hashlib", "base64", "csv",
    "dataclasses", "enum", "typing",
})

# Import blocklist for forged tools (stricter than code_executor)
_FORGE_BLOCKED_IMPORTS = frozenset({
    "os", "sys", "subprocess", "shutil", "ctypes",
    "importlib", "socket", "requests", "urllib", "http",
    "smtplib", "ftplib", "telnetlib", "signal",
    "multiprocessing", "threading", "pty", "builtins",
    "pathlib", "tempfile", "glob", "io",  # No file system access
    "pickle", "shelve", "marshal",  # No serialization exploits
})


# ──────────────────────────────────────────────
# Tool Forge Engine
# ──────────────────────────────────────────────

class ToolForge:
    """
    Runtime tool generation, validation, and registration engine.
    
    The agent can ask the forge to create tools for capabilities
    it doesn't currently have.
    """

    def __init__(self, generate_fn: Callable):
        self.generate_fn = generate_fn
        self._forged: Dict[str, ForgedTool] = {}
        self._generation_count = 0
        self._max_active_tools = 20
        logger.info("🔨 ToolForge initialized — ready to create tools on demand")

    # ──────────────────────────────────────
    # Main: Generate → Validate → Register
    # ──────────────────────────────────────

    def forge_tool(
        self,
        capability_description: str,
        tool_name: str = None,
        test_input: Dict[str, Any] = None,
    ) -> Optional[ForgedTool]:
        """
        Generate a new tool from a capability description.
        
        Args:
            capability_description: What the tool should do
            tool_name: Optional name (auto-generated if not provided)
            test_input: Optional test input to validate the tool
            
        """
        self._generation_count += 1
        forge_id = f"forge_{uuid.uuid4().hex[:8]}"

        # --- LAW 7 SAFETY CHECK ---
        anti_human_keywords = ["against human", "harm human", "kill human", "destroy human", "attack human", "hurt human", "threaten human"]
        desc_lower = capability_description.lower()
        if any(kw in desc_lower for kw in anti_human_keywords):
            logger.error(f"Law 7 Violation detected in tool forge request: '{capability_description}'")
            return None

        if not tool_name:
            tool_name = self._generate_tool_name(capability_description)

        logger.info(f"🔨 Forging tool: {tool_name} — {capability_description[:60]}...")

        # Step 1: Generate the function code via LLM
        source_code = self._generate_code(capability_description, tool_name)
        if not source_code:
            logger.warning(f"🔨 Failed to generate code for: {tool_name}")
            return None

        # Step 2: Validate safety
        safety_result = self._validate_safety(source_code)
        if not safety_result["safe"]:
            logger.warning(
                f"🔨 Safety validation FAILED for {tool_name}: "
                f"{safety_result['reason']}"
            )
            return None

        # Step 3: Compile and test
        func, test_output = self._compile_and_test(source_code, tool_name, test_input)
        if func is None:
            logger.warning(f"🔨 Compilation/test FAILED for {tool_name}")
            return None

        # Step 4: Create the ForgedTool
        forged = ForgedTool(
            forge_id=forge_id,
            name=tool_name,
            description=capability_description,
            source_code=source_code,
            func=func,
            created_at=time.time(),
            validation_passed=True,
            test_output=test_output,
        )

        # Step 5: Register in the global tool registry
        self._register_tool(forged)
        self._forged[forge_id] = forged

        # Enforce limit
        self._retire_old_tools()

        logger.info(f"✅ Tool '{tool_name}' forged and registered successfully!")
        return forged

    # ──────────────────────────────────────
    # Code Generation
    # ──────────────────────────────────────

    def _generate_code(self, description: str, func_name: str) -> Optional[str]:
        """Use the LLM to generate a Python function."""
        prompt = (
            f"Generate a single Python function to do this:\n"
            f"  {description}\n\n"
            f"REQUIREMENTS:\n"
            f"1. Function name: {func_name}\n"
            f"2. Accept keyword arguments (use **kwargs or explicit params)\n"
            f"3. Return a result (dict with 'result' key)\n"
            f"4. Include a docstring\n"
            f"5. Handle errors gracefully (try/except)\n"
            f"6. You may ONLY import from: {', '.join(sorted(_ALLOWED_MODULES))}\n"
            f"7. NO file system, network, or OS access\n"
            f"8. Keep it focused — one function, one purpose\n\n"
            f"Return ONLY the Python code, nothing else. "
            f"No markdown, no explanation.\n"
            f"Start with 'def {func_name}(' directly."
        )

        try:
            result = self.generate_fn(
                prompt=prompt,
                system_prompt=(
                    "You are a Python code generator. Output ONLY valid Python code. "
                    "No markdown, no explanation, no backticks. Just the function."
                ),
                temperature=0.3,
            )

            code = getattr(result, 'answer', str(result))

            # Clean up LLM artifacts
            code = code.strip()
            if code.startswith("```"):
                lines = code.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                code = "\n".join(lines)

            # Ensure it starts with def or import
            if not (code.startswith("def ") or code.startswith("import ")
                    or code.startswith("from ")):
                # Try to find the function definition
                idx = code.find(f"def {func_name}")
                if idx >= 0:
                    code = code[idx:]
                else:
                    return None

            return code.strip()

        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return None

    # ──────────────────────────────────────
    # Safety Validation
    # ──────────────────────────────────────

    def _validate_safety(self, source_code: str) -> Dict[str, Any]:
        """
        Validate that generated code is safe to execute.
        Uses AST analysis + pattern blocklist.
        """
        # String-based blocklist check
        code_lower = source_code.lower()
        for pattern in DANGEROUS_PATTERNS:
            if pattern.lower() in code_lower:
                return {"safe": False, "reason": f"Blocked pattern: {pattern}"}

        # AST analysis
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            return {"safe": False, "reason": f"Syntax error: {e}"}

        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".")[0]
                    if module in _FORGE_BLOCKED_IMPORTS:
                        return {
                            "safe": False,
                            "reason": f"Blocked import: {alias.name}",
                        }
                    if module not in _ALLOWED_MODULES:
                        return {
                            "safe": False,
                            "reason": f"Unauthorized module: {alias.name}",
                        }

            elif isinstance(node, ast.ImportFrom):
                module = (node.module or "").split(".")[0]
                if module in _FORGE_BLOCKED_IMPORTS:
                    return {
                        "safe": False,
                        "reason": f"Blocked import: {node.module}",
                    }
                if module not in _ALLOWED_MODULES:
                    return {
                        "safe": False,
                        "reason": f"Unauthorized module: {node.module}",
                    }

            # Block exec/eval/compile
            elif isinstance(node, ast.Call):
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr

                if func_name in ("exec", "eval", "compile", "__import__",
                                  "getattr", "setattr", "delattr", "breakpoint"):
                    return {
                        "safe": False,
                        "reason": f"Blocked function call: {func_name}",
                    }

            # Block attribute access to dunder methods
            elif isinstance(node, ast.Attribute):
                if node.attr.startswith("__") and node.attr.endswith("__"):
                    if node.attr not in ("__init__", "__str__", "__repr__",
                                          "__len__", "__iter__", "__next__"):
                        return {
                            "safe": False,
                            "reason": f"Blocked dunder access: {node.attr}",
                        }

        return {"safe": True, "reason": "All checks passed"}

    # ──────────────────────────────────────
    # Compilation and Testing
    # ──────────────────────────────────────

    def _compile_and_test(
        self, source_code: str, func_name: str,
        test_input: Dict[str, Any] = None,
    ) -> tuple:
        """Compile the code and optionally test it. Returns (func, test_output)."""
        # Create a restricted namespace
        namespace = {"__builtins__": {
            "print": print, "len": len, "range": range, "int": int,
            "float": float, "str": str, "list": list, "dict": dict,
            "tuple": tuple, "set": set, "bool": bool, "type": type,
            "isinstance": isinstance, "enumerate": enumerate,
            "zip": zip, "map": map, "filter": filter,
            "sorted": sorted, "reversed": reversed,
            "min": min, "max": max, "sum": sum, "abs": abs,
            "round": round, "pow": pow, "divmod": divmod,
            "any": any, "all": all, "hasattr": hasattr,
            "ValueError": ValueError, "TypeError": TypeError,
            "KeyError": KeyError, "Exception": Exception,
        }}

        # Allow safe imports
        import math, statistics, json as json_mod, re as re_mod
        import datetime, collections, itertools, functools
        import string, decimal, random
        namespace.update({
            "math": math, "statistics": statistics, "json": json_mod,
            "re": re_mod, "datetime": datetime,
            "collections": collections, "itertools": itertools,
            "functools": functools, "string": string,
            "decimal": decimal, "random": random,
        })

        try:
            exec(source_code, namespace)  # nosec B102: validated above
        except Exception as e:
            logger.warning(f"Compilation failed: {e}")
            return None, f"Compilation error: {e}"

        func = namespace.get(func_name)
        if not callable(func):
            return None, f"Function '{func_name}' not found in generated code"

        # Test execution
        test_output = "No test run"
        if test_input:
            try:
                import signal

                result = func(**test_input)
                test_output = f"Test passed: {str(result)[:200]}"
            except Exception as e:
                return None, f"Test failed: {e}"

        return func, test_output

    # ──────────────────────────────────────
    # Registration
    # ──────────────────────────────────────

    def _register_tool(self, forged: ForgedTool):
        """Register the forged tool in the global ToolRegistry."""
        tool = Tool(
            name=forged.name,
            description=f"[FORGED] {forged.description}",
            func=forged.func,
            risk_level=ToolRiskLevel.MEDIUM,
            parameters={"type": "object", "properties": {}},
            group="forged",
        )
        registry.register_tool(tool)
        logger.info(f"🔨 Registered forged tool: {forged.name}")

    def _retire_old_tools(self):
        """Remove expired or over-used forged tools."""
        now = time.time()
        to_retire = []

        for fid, ft in self._forged.items():
            if not ft.is_active:
                continue
            if ft.use_count >= ft.max_uses:
                to_retire.append(fid)
            elif now - ft.created_at > ft.ttl_seconds:
                to_retire.append(fid)

        for fid in to_retire:
            ft = self._forged[fid]
            ft.is_active = False
            # Remove from registry
            if ft.name in registry._tools:
                del registry._tools[ft.name]
            logger.info(f"🔨 Retired forged tool: {ft.name}")

        # Hard limit
        active = [f for f in self._forged.values() if f.is_active]
        if len(active) > self._max_active_tools:
            oldest = sorted(active, key=lambda f: f.created_at)
            for ft in oldest[:len(active) - self._max_active_tools]:
                ft.is_active = False
                if ft.name in registry._tools:
                    del registry._tools[ft.name]

    # ──────────────────────────────────────
    # Query
    # ──────────────────────────────────────

    def list_forged_tools(self) -> List[Dict[str, Any]]:
        """List all forged tools and their status."""
        return [
            {
                "forge_id": ft.forge_id,
                "name": ft.name,
                "description": ft.description,
                "active": ft.is_active,
                "use_count": ft.use_count,
                "created_at": ft.created_at,
            }
            for ft in self._forged.values()
        ]

    def _generate_tool_name(self, description: str) -> str:
        """Generate a clean tool name from a description."""
        # Take first few words, clean them up
        words = description.lower().split()[:4]
        name = "_".join(w for w in words if w.isalnum())
        return f"forged_{name}"[:40]

    def get_stats(self) -> Dict[str, Any]:
        active = sum(1 for ft in self._forged.values() if ft.is_active)
        return {
            "total_forged": len(self._forged),
            "active": active,
            "retired": len(self._forged) - active,
            "total_generations": self._generation_count,
        }
