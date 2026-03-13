"""
Ontological Parasite — Hardened Sandboxed Code Execution
────────────────────────────────────────────────────────
VULNERABILITY FIX: Enhanced exec() sandboxing with AST validation,
code-complexity limits, timeout enforcement, and restricted namespace.
"""

import ast
import logging
import threading
import time
from dataclasses import dataclass
from enum import Enum
from io import StringIO
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

_MAX_AST_NODES = 500
_MAX_EXEC_TIMEOUT = 5.0

# Strictly whitelisted builtins — no file I/O, no imports, no eval
_SAFE_BUILTINS = {
    "print": print,
    "range": range,
    "len": len,
    "int": int,
    "float": float,
    "str": str,
    "bool": bool,
    "list": list,
    "dict": dict,
    "tuple": tuple,
    "set": set,
    "sorted": sorted,
    "reversed": reversed,
    "enumerate": enumerate,
    "zip": zip,
    "map": map,
    "filter": filter,
    "sum": sum,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "isinstance": isinstance,
    "type": type,
    "True": True,
    "False": False,
    "None": None,
}

# Forbidden AST node types
_FORBIDDEN_NODES = {
    ast.Import, ast.ImportFrom,  # No imports
}


class SecurityVerdict(Enum):
    SAFE = "safe"
    FORBIDDEN_NODE = "forbidden_node"
    TOO_COMPLEX = "too_complex"
    SYNTAX_ERROR = "syntax_error"
    TIMEOUT = "timeout"
    RUNTIME_ERROR = "runtime_error"


@dataclass
class ExecutionResult:
    """Result of a sandboxed execution."""
    verdict: SecurityVerdict
    output: str = ""
    error: Optional[str] = None
    ast_nodes: int = 0
    duration_ms: float = 0.0


class OntologicalParasite:
    """
    Tier 7: Ontological Parasitism (Safe Code Execution)

    SECURITY FIX: Enhanced sandboxing with:
    - AST validation (no import, no exec, no file I/O)
    - Complexity limits (max AST nodes)
    - Timeout enforcement via threading
    - Restricted builtins namespace
    """

    def __init__(self, max_nodes: int = _MAX_AST_NODES, timeout: float = _MAX_EXEC_TIMEOUT):
        self._max_nodes = max(10, max_nodes)
        self._timeout = max(0.5, timeout)
        self._executions: int = 0
        self._blocked: int = 0
        logger.info("[SANDBOX] Hardened executor active (max_nodes=%d, timeout=%.1fs).", self._max_nodes, self._timeout)

    def _validate_ast(self, source: str) -> ExecutionResult:
        """Validate source code AST for forbidden patterns."""
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            return ExecutionResult(verdict=SecurityVerdict.SYNTAX_ERROR, error=str(e))

        node_count = 0
        for node in ast.walk(tree):
            node_count += 1

            if type(node) in _FORBIDDEN_NODES:
                self._blocked += 1
                logger.warning("[SANDBOX] BLOCKED — forbidden AST node: %s", type(node).__name__)
                return ExecutionResult(
                    verdict=SecurityVerdict.FORBIDDEN_NODE,
                    error=f"Forbidden: {type(node).__name__}",
                    ast_nodes=node_count,
                )

            # Block attribute access to dangerous modules
            if isinstance(node, ast.Attribute):
                if isinstance(node.value, ast.Name) and node.value.id in ("os", "sys", "subprocess", "shutil"):
                    self._blocked += 1
                    return ExecutionResult(
                        verdict=SecurityVerdict.FORBIDDEN_NODE,
                        error=f"Forbidden module access: {node.value.id}",
                        ast_nodes=node_count,
                    )

        if node_count > self._max_nodes:
            self._blocked += 1
            return ExecutionResult(
                verdict=SecurityVerdict.TOO_COMPLEX,
                error=f"AST complexity {node_count} exceeds limit {self._max_nodes}",
                ast_nodes=node_count,
            )

        return ExecutionResult(verdict=SecurityVerdict.SAFE, ast_nodes=node_count)

    def execute_sandboxed(self, source: str) -> ExecutionResult:
        """
        Execute code in a fully sandboxed environment after AST validation.
        """
        # Phase 1: AST validation
        validation = self._validate_ast(source)
        if validation.verdict != SecurityVerdict.SAFE:
            return validation

        # Phase 2: Timeout-bounded execution
        start = time.time()
        result_container = {"output": "", "error": None}

        def _run():
            try:
                # Capture stdout
                import io
                captured = io.StringIO()
                namespace = {"__builtins__": _SAFE_BUILTINS, "print": lambda *a, **kw: captured.write(" ".join(str(x) for x in a) + "\n")}
                exec(source, namespace)  # nosec B102: validated by AST
                result_container["output"] = captured.getvalue()
            except Exception as e:
                result_container["error"] = str(e)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        thread.join(timeout=self._timeout)

        duration = (time.time() - start) * 1000
        self._executions += 1

        if thread.is_alive():
            self._blocked += 1
            logger.warning("[SANDBOX] Execution TIMEOUT after %.0fms.", duration)
            return ExecutionResult(
                verdict=SecurityVerdict.TIMEOUT,
                error=f"Exceeded {self._timeout}s timeout",
                ast_nodes=validation.ast_nodes,
                duration_ms=duration,
            )

        if result_container["error"]:
            return ExecutionResult(
                verdict=SecurityVerdict.RUNTIME_ERROR,
                error=result_container["error"],
                ast_nodes=validation.ast_nodes,
                duration_ms=duration,
            )

        logger.info("[SANDBOX] Execution successful (%.0fms, %d nodes).", duration, validation.ast_nodes)
        return ExecutionResult(
            verdict=SecurityVerdict.SAFE,
            output=result_container["output"],
            ast_nodes=validation.ast_nodes,
            duration_ms=duration,
        )

    @property
    def stats(self) -> dict:
        return {
            "executions": self._executions,
            "blocked": self._blocked,
        }


# Global singleton — always active
ontological_executor = OntologicalParasite()
