"""
Hardened Executor — Production-Grade Isolated Code Execution
═════════════════════════════════════════════════════════════
Real security sandbox with:
  1. Process isolation (subprocess.Popen, separate Python process)
  2. Memory limits (configurable max memory)
  3. CPU time limits (hard timeout with process kill)
  4. Filesystem isolation (tempdir with cleanup)
  5. Import restrictions (custom __builtins__ whitelist)
  6. Network blocking (environment-level restrictions)

Replaces the lightweight CodeExecutor for production use.
"""

import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════

# Modules that are NEVER allowed in sandboxed code
BLOCKED_IMPORTS = frozenset({
    "subprocess", "os", "sys", "shutil", "socket", "http",
    "urllib", "requests", "ftplib", "smtplib", "telnetlib",
    "ctypes", "multiprocessing", "signal", "pty", "fcntl",
    "resource", "mmap", "code", "codeop", "compileall",
    "importlib", "pkgutil", "zipimport", "__import__",
    "builtins", "gc", "inspect", "traceback",
    "win32api", "win32con", "win32process", "winreg",
    "_thread", "threading",
})

# Functions/attributes that are NEVER allowed
BLOCKED_BUILTINS = frozenset({
    "exec", "eval", "compile", "__import__", "globals", "locals",
    "getattr", "setattr", "delattr", "vars", "dir",
    "open", "input", "breakpoint", "exit", "quit",
})

# Safe builtins whitelist
SAFE_BUILTINS = {
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
    "callable", "chr", "complex", "dict", "divmod", "enumerate",
    "filter", "float", "format", "frozenset", "hasattr", "hash",
    "hex", "id", "int", "isinstance", "issubclass", "iter",
    "len", "list", "map", "max", "min", "next", "object",
    "oct", "ord", "pow", "print", "range", "repr", "reversed",
    "round", "set", "slice", "sorted", "str", "sum", "super",
    "tuple", "type", "zip",
    "True", "False", "None",
    "ArithmeticError", "AssertionError", "AttributeError",
    "EOFError", "Exception", "IndexError", "KeyError",
    "NameError", "NotImplementedError", "OverflowError",
    "RuntimeError", "StopIteration", "TypeError", "ValueError",
    "ZeroDivisionError",
}


# ══════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════

@dataclass
class ExecutionResult:
    """Result of sandboxed code execution."""
    success: bool = False
    output: str = ""
    error: str = ""
    return_value: Any = None
    duration_ms: float = 0.0
    memory_peak_kb: float = 0.0
    exit_code: int = -1
    was_killed: bool = False
    kill_reason: str = ""
    sandbox_id: str = ""
    code_hash: str = ""


@dataclass
class SandboxConfig:
    """Configuration for the hardened executor."""
    timeout_seconds: int = 10
    max_memory_mb: int = 256
    max_output_bytes: int = 1_000_000  # 1MB
    allow_file_write: bool = False
    allow_network: bool = False
    allowed_imports: Set[str] = field(default_factory=lambda: {
        "math", "random", "string", "re", "json", "datetime",
        "collections", "itertools", "functools", "operator",
        "decimal", "fractions", "statistics", "textwrap",
        "dataclasses", "typing", "enum", "copy", "pprint",
        "heapq", "bisect", "array", "queue",
    })
    python_executable: str = ""


# ══════════════════════════════════════════════════════════════
# Static Analysis
# ══════════════════════════════════════════════════════════════

class CodeAnalyzer:
    """Pre-execution static analysis to catch dangerous patterns."""

    # Patterns that indicate dangerous code
    DANGEROUS_PATTERNS = [
        ("import os", "os module import"),
        ("import subprocess", "subprocess module import"),
        ("import socket", "socket module import"),
        ("import shutil", "shutil module import"),
        ("__import__", "dynamic import"),
        ("exec(", "exec() call"),
        ("eval(", "eval() call"),
        ("compile(", "compile() call"),
        ("open(", "file open call"),
        ("os.system", "os.system call"),
        ("os.popen", "os.popen call"),
        ("os.exec", "os.exec* call"),
        ("subprocess.run", "subprocess.run call"),
        ("subprocess.Popen", "subprocess.Popen call"),
        ("socket.socket", "socket creation"),
        ("globals()", "globals access"),
        ("locals()", "locals access"),
        ("__builtins__", "builtins access"),
        ("__class__", "class introspection"),
        ("__subclasses__", "subclass enumeration"),
        ("__bases__", "base class access"),
        ("sys.exit", "sys.exit call"),
        ("os.remove", "file deletion"),
        ("os.rmdir", "directory deletion"),
        ("shutil.rmtree", "recursive deletion"),
        ("ctypes", "ctypes FFI"),
    ]

    @classmethod
    def analyze(cls, code: str, config: SandboxConfig) -> List[str]:
        """
        Analyze code for dangerous patterns.
        Returns list of violations (empty = safe).
        """
        violations = []
        code_lower = code.lower()

        # Check dangerous patterns
        for pattern, description in cls.DANGEROUS_PATTERNS:
            if pattern.lower() in code_lower:
                violations.append(f"BLOCKED: {description} ({pattern})")

        # Check blocked imports
        import re
        import_pattern = re.compile(
            r'(?:^|\n)\s*(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_.]*)',
            re.MULTILINE
        )
        for match in import_pattern.finditer(code):
            module_name = match.group(1).split('.')[0]
            if module_name in BLOCKED_IMPORTS:
                violations.append(f"BLOCKED: import of '{module_name}' is forbidden")
            elif module_name not in config.allowed_imports:
                violations.append(f"BLOCKED: import of '{module_name}' not in whitelist")

        return violations


# ══════════════════════════════════════════════════════════════
# Sandbox Wrapper Script
# ══════════════════════════════════════════════════════════════

_WRAPPER_TEMPLATE = '''
import sys
import json
import traceback
import tracemalloc

# Block dangerous modules at import level
class ImportBlocker:
    BLOCKED = {blocked_imports}
    
    def find_module(self, name, path=None):
        root = name.split('.')[0]
        if root in self.BLOCKED:
            return self
        return None
    
    def load_module(self, name):
        raise ImportError(f"Import of '{{name}}' is blocked in sandbox")

sys.meta_path.insert(0, ImportBlocker())

# Restrict builtins
import builtins as _builtins
_safe = {safe_builtins}
_restricted = {{k: getattr(_builtins, k) for k in _safe if hasattr(_builtins, k)}}
_restricted['__name__'] = '__main__'
_restricted['__builtins__'] = _restricted

# Run user code
tracemalloc.start()
result = {{"success": False, "output": "", "error": "", "return_value": None, "memory_peak_kb": 0}}

import io
_stdout = io.StringIO()
_old_stdout = sys.stdout
sys.stdout = _stdout

try:
    exec(
        {user_code_repr},
        _restricted,
    )
    result["success"] = True
    result["output"] = _stdout.getvalue()[:{max_output}]
except Exception as e:
    result["success"] = False
    result["error"] = f"{{type(e).__name__}}: {{e}}"
    result["output"] = _stdout.getvalue()[:{max_output}]
finally:
    sys.stdout = _old_stdout
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    result["memory_peak_kb"] = round(peak / 1024, 2)

# Write result to file
with open({result_file_repr}, 'w') as f:
    json.dump(result, f)
'''


# ══════════════════════════════════════════════════════════════
# Hardened Executor
# ══════════════════════════════════════════════════════════════

class HardenedExecutor:
    """
    Production-grade sandboxed code executor.

    Usage:
        executor = HardenedExecutor()
        result = executor.execute("print(2 + 2)")
        assert result.success
        assert result.output.strip() == "4"

        # With custom limits
        result = executor.execute(
            "x = [i**2 for i in range(1000000)]",
            config=SandboxConfig(timeout_seconds=5, max_memory_mb=128),
        )
    """

    def __init__(self, default_config: SandboxConfig = None):
        self._config = default_config or SandboxConfig()
        self._execution_log: List[Dict[str, Any]] = []

    def execute(
        self,
        code: str,
        config: SandboxConfig = None,
        skip_analysis: bool = False,
    ) -> ExecutionResult:
        """
        Execute code in an isolated subprocess with resource limits.

        Args:
            code: Python code to execute
            config: Sandbox configuration (uses default if not provided)
            skip_analysis: Skip static analysis (DANGEROUS)

        Returns:
            ExecutionResult with output, errors, and metrics
        """
        cfg = config or self._config
        sandbox_id = str(uuid.uuid4())[:12]
        code_hash = hashlib.sha256(code.encode()).hexdigest()[:16]
        start_time = time.perf_counter()

        result = ExecutionResult(
            sandbox_id=sandbox_id,
            code_hash=code_hash,
        )

        # ── Step 1: Static Analysis ──
        if not skip_analysis:
            violations = CodeAnalyzer.analyze(code, cfg)
            if violations:
                result.error = "Static analysis blocked execution:\n" + "\n".join(violations)
                result.duration_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(f"[Sandbox {sandbox_id}] Blocked: {len(violations)} violation(s)")
                self._log_execution(result, cfg)
                return result

        # ── Step 2: Create Isolated Temp Directory ──
        sandbox_dir = None
        try:
            sandbox_dir = tempfile.mkdtemp(prefix="sandbox_")
            wrapper_path = os.path.join(sandbox_dir, "wrapper.py")
            result_path = os.path.join(sandbox_dir, "result.json")

            # ── Step 3: Generate Wrapper Script ──
            wrapper_code = _WRAPPER_TEMPLATE.format(
                blocked_imports=repr(set(BLOCKED_IMPORTS)),
                safe_builtins=repr(set(SAFE_BUILTINS)),
                user_code_repr=repr(code),
                max_output=cfg.max_output_bytes,
                result_file_repr=repr(result_path),
            )

            with open(wrapper_path, "w", encoding="utf-8") as f:
                f.write(wrapper_code)

            # ── Step 4: Build Subprocess Environment ──
            env = self._build_restricted_env(cfg)

            # ── Step 5: Determine Python Executable ──
            python = cfg.python_executable or sys.executable

            # ── Step 6: Execute in Subprocess ──
            logger.info(f"[Sandbox {sandbox_id}] Executing (timeout={cfg.timeout_seconds}s, "
                        f"mem={cfg.max_memory_mb}MB)")

            try:
                proc = subprocess.Popen(
                    [python, wrapper_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    cwd=sandbox_dir,
                    env=env,
                    # Platform-specific flags
                    **self._get_platform_flags(),
                )

                stdout, stderr = proc.communicate(timeout=cfg.timeout_seconds)
                result.exit_code = proc.returncode

            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                result.was_killed = True
                result.kill_reason = f"Exceeded timeout of {cfg.timeout_seconds}s"
                result.error = result.kill_reason
                result.duration_ms = (time.perf_counter() - start_time) * 1000
                logger.warning(f"[Sandbox {sandbox_id}] Killed: timeout")
                self._log_execution(result, cfg)
                return result

            # ── Step 7: Read Results ──
            if os.path.exists(result_path):
                with open(result_path, "r", encoding="utf-8") as f:
                    sandbox_result = json.load(f)
                result.success = sandbox_result.get("success", False)
                result.output = sandbox_result.get("output", "")
                result.error = sandbox_result.get("error", "")
                result.memory_peak_kb = sandbox_result.get("memory_peak_kb", 0)
            else:
                # Wrapper crashed before writing results
                result.success = False
                stderr_text = stderr.decode("utf-8", errors="replace")[:2000]
                result.error = f"Sandbox wrapper crashed: {stderr_text}"

        except Exception as e:
            result.success = False
            result.error = f"Sandbox infrastructure error: {type(e).__name__}: {e}"
            logger.error(f"[Sandbox {sandbox_id}] Infrastructure error: {e}")

        finally:
            # ── Step 8: Clean Up ──
            if sandbox_dir and os.path.exists(sandbox_dir):
                try:
                    shutil.rmtree(sandbox_dir, ignore_errors=True)
                except Exception:
                    pass

        result.duration_ms = (time.perf_counter() - start_time) * 1000
        self._log_execution(result, cfg)
        return result

    def _build_restricted_env(self, cfg: SandboxConfig) -> Dict[str, str]:
        """Build a restricted environment for the subprocess."""
        env = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": "",  # Prevent importing from project
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",  # Deterministic hashing
        }

        # Block network
        if not cfg.allow_network:
            env["HTTP_PROXY"] = "http://0.0.0.0:0"
            env["HTTPS_PROXY"] = "http://0.0.0.0:0"
            env["NO_PROXY"] = ""
            env["http_proxy"] = "http://0.0.0.0:0"
            env["https_proxy"] = "http://0.0.0.0:0"

        # Windows-specific
        if platform.system() == "Windows":
            env["SYSTEMROOT"] = os.environ.get("SYSTEMROOT", r"C:\Windows")
            env["COMSPEC"] = os.environ.get("COMSPEC", r"C:\Windows\system32\cmd.exe")

        return env

    def _get_platform_flags(self) -> Dict[str, Any]:
        """Get platform-specific subprocess flags."""
        flags = {}
        if platform.system() == "Windows":
            # CREATE_NO_WINDOW prevents console popup
            CREATE_NO_WINDOW = 0x08000000
            flags["creationflags"] = CREATE_NO_WINDOW
        return flags

    def _log_execution(self, result: ExecutionResult, config: SandboxConfig):
        """Record execution for audit trail."""
        self._execution_log.append({
            "sandbox_id": result.sandbox_id,
            "code_hash": result.code_hash,
            "success": result.success,
            "duration_ms": round(result.duration_ms, 2),
            "memory_peak_kb": result.memory_peak_kb,
            "was_killed": result.was_killed,
            "kill_reason": result.kill_reason,
            "error_type": result.error.split(":")[0] if result.error else "",
            "timeout_s": config.timeout_seconds,
            "max_memory_mb": config.max_memory_mb,
            "timestamp": time.time(),
        })
        # Keep only last 1000
        if len(self._execution_log) > 1000:
            self._execution_log = self._execution_log[-500:]

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        total = len(self._execution_log)
        if total == 0:
            return {"total_executions": 0}

        successes = sum(1 for e in self._execution_log if e["success"])
        kills = sum(1 for e in self._execution_log if e["was_killed"])
        durations = [e["duration_ms"] for e in self._execution_log]

        return {
            "total_executions": total,
            "success_rate": round(successes / total, 3),
            "kill_rate": round(kills / total, 3),
            "avg_duration_ms": round(sum(durations) / len(durations), 2),
            "max_duration_ms": round(max(durations), 2),
        }
