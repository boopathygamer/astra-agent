"""
Code Executor Tool — Run Python code in a sandboxed subprocess.
Hardened: AST-validated eval, code blocklist, length limits.
"""

import ast
import logging
import subprocess  # nosec B404
import sys
import tempfile
from pathlib import Path

from agents.tools.registry import registry, RiskLevel
from config.settings import agent_config

logger = logging.getLogger(__name__)

# ── Security constants ──
MAX_CODE_LENGTH = 10_000  # chars
MAX_EXPRESSION_LENGTH = 1_000

DANGEROUS_PATTERNS = [
    # Core dangerous operations
    "import os", "import sys", "import subprocess", "import shutil",
    "__import__", "eval(", "exec(", "compile(",
    "open(", "os.system", "os.popen", "os.remove", "os.unlink",
    "shutil.rmtree", "subprocess.", "ctypes.",
    "importlib.", "__builtins__", "builtins", "globals(", "locals(",
    "getattr(", "setattr(", "delattr(",
    "breakpoint(", "__class__", "__subclasses__",
    "__bases__", "__mro__", "__globals__",
    # Encoding-based bypass attempts
    "base64.b64decode", "codecs.decode",
    "bytes.fromhex", "bytearray.fromhex",
    # Network attack & exploitation tools
    "import scapy", "from scapy", "import nmap", "from nmap",
    "import paramiko", "from paramiko",
    "import socket", "from socket",
    "import requests", "from requests",
    "import urllib", "from urllib",
    "import http", "from http",
    # Data exfiltration patterns
    "import smtplib", "from smtplib",
    "import ftplib", "from ftplib",
    "import telnetlib", "from telnetlib",
    # Keylogging / screen capture
    "import pynput", "from pynput",
    "import keyboard", "from keyboard",
    "import pyautogui", "from pyautogui",
    # Credential theft
    "import win32crypt", "from win32crypt",
    "import sqlite3",  # often used to steal browser data
    "import winreg", "from winreg",
    # Process/system manipulation
    "import signal", "from signal",
    "import multiprocessing", "from multiprocessing",
    "import threading", "from threading",
    "import pty", "from pty",
]

# AST node types allowed in safe expression evaluation
_SAFE_AST_NODES = (
    ast.Expression, ast.BinOp, ast.UnaryOp, ast.BoolOp,
    ast.Compare, ast.IfExp, ast.Call, ast.Constant, ast.Num, ast.Str,
    ast.Name, ast.Load, ast.Tuple, ast.List, ast.Dict, ast.Set,
    ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod, ast.Pow,
    ast.USub, ast.UAdd, ast.Not, ast.And, ast.Or,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.In, ast.NotIn, ast.Is, ast.IsNot,
    ast.Subscript, ast.Index, ast.Slice,
    ast.Attribute,
)

# Names allowed in safe expression context
_SAFE_NAMES = frozenset({
    "abs", "len", "max", "min", "sum", "round", "int", "float",
    "str", "bool", "list", "dict", "tuple", "set", "range",
    "sorted", "reversed", "enumerate", "zip", "map", "filter",
    "True", "False", "None",
    "math", "pi", "e", "sqrt", "log", "sin", "cos", "tan",
    "ceil", "floor", "pow",
})


def _validate_expression_ast(expression: str) -> bool:
    """Validate that an expression only contains safe AST nodes."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if not isinstance(node, _SAFE_AST_NODES):
            return False
        # Block dangerous attribute access
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                return False
        # Block dangerous names
        if isinstance(node, ast.Name):
            if node.id.startswith("_"):
                return False
    return True


def _check_code_safety(code: str) -> str | None:
    """Check code for dangerous patterns. Returns error message or None."""
    if len(code) > MAX_CODE_LENGTH:
        return f"Code too long ({len(code)} chars, max {MAX_CODE_LENGTH})"

    # String-based blocklist check
    code_lower = code.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern.lower() in code_lower:
            return f"Blocked dangerous pattern: {pattern}"

    # AST-based import detection (catches obfuscated imports)
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = getattr(node, 'module', '') or ''
                names = [alias.name for alias in getattr(node, 'names', [])]
                all_names = [module] + names
                blocked_modules = {
                    'os', 'sys', 'subprocess', 'shutil', 'ctypes',
                    'importlib', 'socket', 'requests', 'urllib',
                    'http', 'smtplib', 'ftplib', 'telnetlib',
                    'pynput', 'keyboard', 'pyautogui', 'win32crypt',
                    'winreg', 'signal', 'multiprocessing', 'threading',
                    'pty', 'scapy', 'nmap', 'paramiko',
                }
                for name in all_names:
                    top_module = name.split('.')[0] if name else ''
                    if top_module in blocked_modules:
                        return f"Blocked import: {name}"
    except SyntaxError:
        pass  # Let it fail at execution time

    return None


@registry.register(
    name="execute_python",
    description="Execute Python code in a sandboxed subprocess. Returns stdout, stderr, and exit code.",
    risk_level=RiskLevel.HIGH,
    parameters={"code": "Python code to execute", "timeout": "Timeout in seconds (default 30)"},
)
def execute_python(code: str, timeout: int = None) -> dict:
    """Execute Python code safely in a subprocess with safety checks."""
    # ── Safety checks ──
    safety_error = _check_code_safety(code)
    if safety_error:
        return {"stdout": "", "stderr": safety_error, "exit_code": -1, "success": False}

    timeout = timeout or agent_config.sandbox_timeout

    # Write code to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as f:
        f.write(code)
        temp_path = f.name

    try:
        result = subprocess.run(
            [sys.executable, temp_path],  # nosec B603: strictly runs Python on a temp file
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=tempfile.gettempdir(),
        )

        return {
            "stdout": result.stdout[:50_000],  # Cap output size
            "stderr": result.stderr[:10_000],
            "exit_code": result.returncode,
            "success": result.returncode == 0,
        }

    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Execution timed out after {timeout} seconds",
            "exit_code": -1,
            "success": False,
        }
    except Exception as e:
        return {
            "stdout": "",
            "stderr": f"Execution error: {type(e).__name__}",
            "exit_code": -1,
            "success": False,
        }
    finally:
        try:
            Path(temp_path).unlink()
        except OSError:
            pass


@registry.register(
    name="evaluate_expression",
    description="Safely evaluate a Python math expression and return the result.",
    risk_level=RiskLevel.LOW,
    parameters={"expression": "Python math expression to evaluate"},
)
def evaluate_expression(expression: str) -> dict:
    """Evaluate a simple Python expression with AST validation."""
    if len(expression) > MAX_EXPRESSION_LENGTH:
        return {"success": False, "result": None, "error": "Expression too long"}

    # ── AST validation — block everything except safe nodes ──
    if not _validate_expression_ast(expression):
        return {
            "success": False,
            "result": None,
            "error": "Expression contains unsafe operations",
        }

    # Restricted builtins — no access to __import__, open, etc.
    import math
    safe_builtins = {
        "abs": abs, "len": len, "max": max, "min": min,
        "sum": sum, "round": round, "int": int, "float": float,
        "str": str, "bool": bool, "list": list, "dict": dict,
        "tuple": tuple, "set": set, "range": range,
        "sorted": sorted, "reversed": reversed, "enumerate": enumerate,
        "zip": zip, "map": map, "filter": filter,
        "True": True, "False": False, "None": None,
        "math": math, "pi": math.pi, "e": math.e,
        "sqrt": math.sqrt, "log": math.log,
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "ceil": math.ceil, "floor": math.floor,
        "pow": pow,
    }

    try:
        # Compile with restricted builtins — NO __builtins__ access
        code = compile(expression, "<expression>", "eval")
        result = eval(code, {"__builtins__": {}}, safe_builtins)  # nosec B307
        return {"success": True, "result": str(result)}
    except Exception as e:
        return {"success": False, "result": None, "error": f"{type(e).__name__}: {e}"}

from dataclasses import dataclass
from typing import Optional
import shutil

@dataclass
class CodeResult:
    output: Optional[str] = None
    error: Optional[str] = None

class CodeExecutor:
    def execute(self, code: str, timeout: int = 30) -> CodeResult:
        res = execute_python(code, timeout=timeout)
        if res.get("success"):
            return CodeResult(output=res.get("stdout"))
        else:
            return CodeResult(output=res.get("stdout"), error=res.get("stderr"))


# ── JavaScript Blocklist ──
_JS_DANGEROUS = [
    "require('child_process')", "require('fs')", "require('net')",
    "require('http')", "require('https')", "require('dgram')",
    "process.exit", "process.kill", "process.env",
    "eval(", "Function(", "child_process",
]


def _check_js_safety(code: str) -> str | None:
    """Check JS/TS code for dangerous patterns."""
    if len(code) > MAX_CODE_LENGTH:
        return f"Code too long ({len(code)} chars)"
    for pattern in _JS_DANGEROUS:
        if pattern in code:
            return f"Blocked dangerous pattern: {pattern}"
    return None


@registry.register(
    name="execute_javascript",
    description="Execute JavaScript code in a sandboxed Node.js subprocess.",
    risk_level=RiskLevel.HIGH,
    parameters={"code": "JavaScript code to execute", "timeout": "Timeout in seconds (default 30)"},
)
def execute_javascript(code: str, timeout: int = 30) -> dict:
    """Execute JavaScript code safely in Node.js."""
    safety_error = _check_js_safety(code)
    if safety_error:
        return {"stdout": "", "stderr": safety_error, "exit_code": -1, "success": False}

    node_path = shutil.which("node")
    if not node_path:
        return {"stdout": "", "stderr": "Node.js not found. Install Node.js first.", "exit_code": -1, "success": False}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".js", delete=False, encoding="utf-8") as f:
        f.write(code)
        temp_path = f.name

    try:
        result = subprocess.run(
            [node_path, temp_path],
            capture_output=True, text=True, timeout=timeout,
            cwd=tempfile.gettempdir(),
        )
        return {
            "stdout": result.stdout[:50_000],
            "stderr": result.stderr[:10_000],
            "exit_code": result.returncode,
            "success": result.returncode == 0,
            "language": "javascript",
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timed out after {timeout}s", "exit_code": -1, "success": False}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1, "success": False}
    finally:
        try: Path(temp_path).unlink()
        except OSError: pass


@registry.register(
    name="execute_typescript",
    description="Execute TypeScript code via ts-node or tsx in a sandboxed subprocess.",
    risk_level=RiskLevel.HIGH,
    parameters={"code": "TypeScript code to execute", "timeout": "Timeout in seconds (default 30)"},
)
def execute_typescript(code: str, timeout: int = 30) -> dict:
    """Execute TypeScript code safely."""
    safety_error = _check_js_safety(code)
    if safety_error:
        return {"stdout": "", "stderr": safety_error, "exit_code": -1, "success": False}

    ts_runner = shutil.which("tsx") or shutil.which("ts-node") or shutil.which("npx")
    if not ts_runner:
        return {"stdout": "", "stderr": "TypeScript runner not found (tsx/ts-node/npx)", "exit_code": -1, "success": False}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".ts", delete=False, encoding="utf-8") as f:
        f.write(code)
        temp_path = f.name

    cmd = [ts_runner, temp_path] if "npx" not in ts_runner else [ts_runner, "tsx", temp_path]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd=tempfile.gettempdir())
        return {
            "stdout": result.stdout[:50_000],
            "stderr": result.stderr[:10_000],
            "exit_code": result.returncode,
            "success": result.returncode == 0,
            "language": "typescript",
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timed out after {timeout}s", "exit_code": -1, "success": False}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1, "success": False}
    finally:
        try: Path(temp_path).unlink()
        except OSError: pass


@registry.register(
    name="execute_html",
    description="Write HTML to a temp file and validate its structure. Returns the file path for preview.",
    risk_level=RiskLevel.MEDIUM,
    parameters={"html": "HTML content", "filename": "Output filename"},
)
def execute_html(html: str, filename: str = "preview.html") -> dict:
    """Write and validate HTML content."""
    if len(html) > MAX_CODE_LENGTH * 5:
        return {"success": False, "error": "HTML too long"}

    # Basic validation
    warnings = []
    if "<!DOCTYPE" not in html.upper():
        warnings.append("Missing <!DOCTYPE html> declaration")
    if "<html" not in html.lower():
        warnings.append("Missing <html> tag")
    if "<head" not in html.lower():
        warnings.append("Missing <head> tag")
    if "<title" not in html.lower():
        warnings.append("Missing <title> tag (SEO)")
    if 'meta name="viewport"' not in html.lower() and "viewport" not in html.lower():
        warnings.append("Missing viewport meta tag (mobile)")
    if "<script" in html.lower():
        # Check for inline event handlers
        import re
        if re.search(r'on\w+\s*=', html, re.IGNORECASE):
            warnings.append("Inline event handlers detected — use addEventListener instead")

    out_dir = Path(tempfile.gettempdir()) / "astra_html_preview"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / filename
    out_path.write_text(html, encoding="utf-8")

    return {
        "success": True,
        "file_path": str(out_path),
        "file_size": len(html),
        "warnings": warnings,
        "valid": len(warnings) == 0,
    }


@registry.register(
    name="lint_code",
    description="Lint code for quality issues. Supports Python (pylint/flake8), JavaScript (eslint), and TypeScript.",
    risk_level=RiskLevel.LOW,
    parameters={"code": "Code to lint", "language": "python | javascript | typescript"},
)
def lint_code(code: str, language: str = "python") -> dict:
    """Lint code for quality and style issues."""
    if language == "python":
        return _lint_python(code)
    elif language in ("javascript", "typescript"):
        return _lint_js(code, language)
    return {"success": False, "error": f"Unsupported language: {language}"}


def _lint_python(code: str) -> dict:
    """Lint Python code using AST + basic checks."""
    issues = []
    lines = code.split("\n")

    # Check syntax
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"success": True, "issues": [{"line": e.lineno or 0, "severity": "error",
                "message": f"SyntaxError: {e.msg}"}], "total": 1, "language": "python"}

    # Style checks
    for i, line in enumerate(lines, 1):
        if len(line) > 120:
            issues.append({"line": i, "severity": "warning", "message": f"Line too long ({len(line)} > 120)"})
        if line.rstrip() != line:
            issues.append({"line": i, "severity": "info", "message": "Trailing whitespace"})
        if "\t" in line:
            issues.append({"line": i, "severity": "warning", "message": "Tab indentation (use spaces)"})

    # AST checks
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and not node.body:
            issues.append({"line": node.lineno, "severity": "warning", "message": f"Empty function: {node.name}"})
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "*":
                    issues.append({"line": node.lineno, "severity": "warning", "message": "Wildcard import"})

    return {"success": True, "issues": issues[:100], "total": len(issues), "language": "python"}


def _lint_js(code: str, language: str) -> dict:
    """Lint JS/TS using basic pattern checks."""
    import re
    issues = []
    lines = code.split("\n")

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if len(line) > 120:
            issues.append({"line": i, "severity": "warning", "message": f"Line too long ({len(line)})"})
        if re.search(r'\bvar\b', stripped):
            issues.append({"line": i, "severity": "warning", "message": "Use 'let' or 'const' instead of 'var'"})
        if "==" in stripped and "===" not in stripped and "!==" not in stripped:
            issues.append({"line": i, "severity": "warning", "message": "Use === instead of =="})
        if stripped.endswith("{"):
            pass  # Normal
        if "console.log" in stripped:
            issues.append({"line": i, "severity": "info", "message": "console.log left in code"})
        if "any" in stripped and language == "typescript":
            if re.search(r':\s*any\b', stripped):
                issues.append({"line": i, "severity": "warning", "message": "Avoid 'any' type in TypeScript"})

    return {"success": True, "issues": issues[:100], "total": len(issues), "language": language}
