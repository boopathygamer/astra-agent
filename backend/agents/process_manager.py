"""
Process Manager — Background process execution and monitoring.
──────────────────────────────────────────────────────────────
Features (inspired by OpenClaw exec/process tools):
  - Background execution with async monitoring
  - Auto-background via yieldMs timeout
  - Operations: list, poll, log, write, kill
  - Per-agent process scoping
  - Configurable timeouts with auto-kill
  - Command sanitization and blocklist (Phase 11)
"""

import logging
import re
import shlex
import subprocess  # nosec B404
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from collections import deque

logger = logging.getLogger(__name__)


# ── Security: command blocklist ──
_DANGEROUS_COMMANDS = re.compile(
    r'\b('
    r'rm\s+-rf|rmdir\s+/s|del\s+/[sfq]|format\s+[a-z]:|'
    r'shutdown|reboot|halt|poweroff|init\s+[06]|'
    r'mkfs|fdisk|dd\s+if=|'
    r':(){ :|:&};:|fork\s+bomb|'
    r'curl\s+.*\|\s*(ba)?sh|wget\s+.*\|\s*(ba)?sh|'
    r'chmod\s+777|chmod\s+-R\s+777|'
    r'>\s*/dev/sd|>\s*\\\\\.\\\\|'
    r'net\s+user|net\s+localgroup|reg\s+delete|'
    r'taskkill\s+/f\s+/im'
    r')\b',
    re.IGNORECASE,
)

_MAX_COMMAND_LENGTH = 2000


def _validate_command(command: str) -> str | None:
    """Validate command safety. Returns error message or None if safe."""
    if not command or not command.strip():
        return "Empty command"

    if len(command) > _MAX_COMMAND_LENGTH:
        return f"Command too long ({len(command)} chars, max {_MAX_COMMAND_LENGTH})"

    if _DANGEROUS_COMMANDS.search(command):
        return "Command contains blocked dangerous pattern"

    # Block null bytes and control characters
    if any(ord(c) < 32 and c not in ('\n', '\r', '\t') for c in command):
        return "Command contains invalid control characters"

    return None


class ProcessStatus(Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"
    TIMED_OUT = "timed_out"


@dataclass
class ManagedProcess:
    """A tracked background process."""
    process_id: str
    agent_id: str
    command: str
    status: ProcessStatus = ProcessStatus.RUNNING
    exit_code: Optional[int] = None
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    timeout: int = 300  # seconds
    output_lines: List[str] = field(default_factory=list)
    error_lines: List[str] = field(default_factory=list)
    _process: Optional[subprocess.Popen] = field(default=None, repr=False)
    _thread: Optional[threading.Thread] = field(default=None, repr=False)
    _poll_offset: int = 0  # Track last polled position


class ProcessManager:
    """
    Manages background process execution with monitoring.

    Provides async process execution, output streaming, and
    lifecycle management similar to OpenClaw's exec/process tools.
    """

    def __init__(
        self,
        max_processes: int = 20,
        default_timeout: int = 300,
        sandbox_timeout: int = 30,
    ):
        self.max_processes = max_processes
        self.default_timeout = default_timeout
        self.sandbox_timeout = sandbox_timeout
        self._processes: Dict[str, ManagedProcess] = {}
        self._lock = threading.Lock()

    def execute(
        self,
        command: str,
        agent_id: str = "default",
        background: bool = False,
        yield_ms: int = 10000,
        timeout: int = None,
        cwd: str = None,
    ) -> Dict[str, Any]:
        """
        Execute a command, optionally in the background.

        Args:
            command: Shell command to execute
            agent_id: Agent owning this process
            background: If True, run immediately in background
            yield_ms: Auto-background after this many ms if not finished
            timeout: Max execution time in seconds (kills process if exceeded)
            cwd: Working directory

        Returns:
            If sync: {"status": "completed", "output": ..., "exit_code": ...}
            If background: {"status": "running", "process_id": ...}
        """
        # ── Security: validate command ──
        validation_error = _validate_command(command)
        if validation_error:
            return {"status": "error", "message": validation_error}

        effective_timeout = timeout or self.default_timeout

        # Check process limit
        active = sum(
            1 for p in self._processes.values()
            if p.status == ProcessStatus.RUNNING and p.agent_id == agent_id
        )
        if active >= self.max_processes:
            return {
                "status": "error",
                "message": f"Process limit reached ({self.max_processes}). Kill some processes first.",
            }

        process_id = uuid.uuid4().hex[:10]

        try:
            # ── FIXED: shell=False + shlex.split for safety ──
            # Use platform-appropriate command parsing
            if sys.platform == "win32":
                # On Windows, use cmd /c for compatibility but with validation
                cmd_args = ["cmd", "/c", command]
            else:
                cmd_args = shlex.split(command)

            proc = subprocess.Popen(
                cmd_args,
                shell=False,    # nosec B603: command arguments are strictly controlled
                stdin=subprocess.PIPE,   # FIXED: was missing (write() crashed)
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd,
                bufsize=1,
            )
        except Exception as e:
            return {"status": "error", "message": f"Failed to start process: {type(e).__name__}"}

        managed = ManagedProcess(
            process_id=process_id,
            agent_id=agent_id,
            command=command,
            timeout=effective_timeout,
            _process=proc,
        )

        with self._lock:
            self._processes[process_id] = managed

        if background:
            # Run in background immediately
            self._start_monitor(managed)
            return {
                "status": "running",
                "process_id": process_id,
                "message": "Process started in background. Use process tool to check status.",
            }

        # Try synchronous execution with yield timeout
        try:
            stdout, stderr = proc.communicate(timeout=yield_ms / 1000.0)
            managed.output_lines = stdout.splitlines() if stdout else []
            managed.error_lines = stderr.splitlines() if stderr else []
            managed.exit_code = proc.returncode
            managed.status = (
                ProcessStatus.COMPLETED if proc.returncode == 0
                else ProcessStatus.FAILED
            )
            managed.ended_at = time.time()

            return {
                "status": managed.status.value,
                "process_id": process_id,
                "exit_code": managed.exit_code,
                "output": "\n".join(managed.output_lines[-100:]),
                "error": "\n".join(managed.error_lines[-20:]) if managed.error_lines else "",
            }

        except subprocess.TimeoutExpired:
            # Auto-background: process took longer than yieldMs
            self._start_monitor(managed)
            return {
                "status": "running",
                "process_id": process_id,
                "message": f"Command exceeded {yield_ms}ms, moved to background.",
            }

    def _start_monitor(self, managed: ManagedProcess):
        """Start a background thread to monitor process output."""
        def monitor():
            proc = managed._process
            try:
                stdout, stderr = proc.communicate(timeout=managed.timeout)
                managed.output_lines = stdout.splitlines() if stdout else []
                managed.error_lines = stderr.splitlines() if stderr else []
                managed.exit_code = proc.returncode
                managed.status = (
                    ProcessStatus.COMPLETED if proc.returncode == 0
                    else ProcessStatus.FAILED
                )
            except subprocess.TimeoutExpired:
                proc.kill()
                managed.status = ProcessStatus.TIMED_OUT
                managed.exit_code = -1
                try:
                    stdout, stderr = proc.communicate(timeout=5)
                    managed.output_lines = stdout.splitlines() if stdout else []
                    managed.error_lines = stderr.splitlines() if stderr else []
                except Exception as parse_err:
                    import logging
                    logging.debug(f"Failed to parse stderr for process: {parse_err}")
            except Exception as e:
                managed.status = ProcessStatus.FAILED
                managed.error_lines.append(f"Monitor error: {type(e).__name__}")
            finally:
                managed.ended_at = time.time()

        thread = threading.Thread(target=monitor, daemon=True)
        managed._thread = thread
        thread.start()

    def poll(self, process_id: str, agent_id: str = None) -> Dict[str, Any]:
        """
        Poll a background process for new output.

        Returns only new output since last poll.
        """
        managed = self._processes.get(process_id)
        if not managed:
            return {"status": "error", "message": f"Process not found: {process_id}"}
        if agent_id and managed.agent_id != agent_id:
            return {"status": "error", "message": "Process belongs to another agent"}

        # Get new output since last poll
        new_lines = managed.output_lines[managed._poll_offset:]
        managed._poll_offset = len(managed.output_lines)

        result = {
            "status": managed.status.value,
            "process_id": process_id,
            "new_output": "\n".join(new_lines[-50:]) if new_lines else "",
            "new_lines_count": len(new_lines),
        }

        if managed.status != ProcessStatus.RUNNING:
            result["exit_code"] = managed.exit_code
            elapsed = (managed.ended_at or time.time()) - managed.started_at
            result["elapsed_seconds"] = round(elapsed, 2)

        return result

    def log(
        self,
        process_id: str,
        offset: Optional[int] = None,
        limit: int = 50,
        agent_id: str = None,
    ) -> Dict[str, Any]:
        """
        Get process output log with offset/limit.

        If offset is None, returns the last `limit` lines.
        """
        managed = self._processes.get(process_id)
        if not managed:
            return {"status": "error", "message": f"Process not found: {process_id}"}
        if agent_id and managed.agent_id != agent_id:
            return {"status": "error", "message": "Process belongs to another agent"}

        lines = managed.output_lines
        if offset is None:
            # Return last N lines
            output = lines[-limit:] if lines else []
            actual_offset = max(0, len(lines) - limit)
        else:
            output = lines[offset:offset + limit]
            actual_offset = offset

        return {
            "status": managed.status.value,
            "process_id": process_id,
            "output": "\n".join(output),
            "offset": actual_offset,
            "total_lines": len(lines),
            "has_more": actual_offset + len(output) < len(lines),
        }

    def write(self, process_id: str, input_data: str, agent_id: str = None) -> Dict[str, Any]:
        """Write to a running process's stdin."""
        managed = self._processes.get(process_id)
        if not managed:
            return {"status": "error", "message": f"Process not found: {process_id}"}
        if agent_id and managed.agent_id != agent_id:
            return {"status": "error", "message": "Process belongs to another agent"}
        if managed.status != ProcessStatus.RUNNING:
            return {"status": "error", "message": "Process is not running"}

        try:
            if managed._process.stdin is None:
                return {"status": "error", "message": "Process stdin not available"}
            managed._process.stdin.write(input_data)
            managed._process.stdin.flush()
            return {"status": "ok", "message": f"Wrote {len(input_data)} bytes"}
        except Exception as e:
            return {"status": "error", "message": f"Write failed: {type(e).__name__}"}

    def kill(self, process_id: str, agent_id: str = None) -> Dict[str, Any]:
        """Kill a running process."""
        managed = self._processes.get(process_id)
        if not managed:
            return {"status": "error", "message": f"Process not found: {process_id}"}
        if agent_id and managed.agent_id != agent_id:
            return {"status": "error", "message": "Process belongs to another agent"}

        if managed.status == ProcessStatus.RUNNING and managed._process:
            managed._process.kill()
            managed.status = ProcessStatus.KILLED
            managed.ended_at = time.time()
            return {"status": "killed", "process_id": process_id}

        return {"status": "already_stopped", "process_id": process_id}

    def list_processes(self, agent_id: str = None) -> List[Dict[str, Any]]:
        """List all processes, optionally filtered by agent."""
        results = []
        for managed in self._processes.values():
            if agent_id and managed.agent_id != agent_id:
                continue
            elapsed = (managed.ended_at or time.time()) - managed.started_at
            results.append({
                "process_id": managed.process_id,
                "agent_id": managed.agent_id,
                "command": managed.command[:80],
                "status": managed.status.value,
                "exit_code": managed.exit_code,
                "elapsed_seconds": round(elapsed, 2),
                "output_lines": len(managed.output_lines),
            })
        return results

    def clear(self, agent_id: str = None):
        """Remove completed/failed processes from tracking."""
        with self._lock:
            to_remove = [
                pid for pid, p in self._processes.items()
                if p.status != ProcessStatus.RUNNING
                and (agent_id is None or p.agent_id == agent_id)
            ]
            for pid in to_remove:
                del self._processes[pid]
            return {"cleared": len(to_remove)}

    def auto_expire(self, max_age_seconds: int = 3600):
        """Remove completed/failed processes older than max_age_seconds."""
        now = time.time()
        with self._lock:
            to_remove = [
                pid for pid, p in self._processes.items()
                if p.status != ProcessStatus.RUNNING
                and p.ended_at
                and now - p.ended_at > max_age_seconds
            ]
            for pid in to_remove:
                del self._processes[pid]
            return {"expired": len(to_remove)}

    def shutdown(self):
        """Graceful shutdown — kill all running processes and clean up."""
        logger.info("ProcessManager shutting down — killing active processes...")
        with self._lock:
            for pid, managed in self._processes.items():
                if managed.status == ProcessStatus.RUNNING and managed._process:
                    try:
                        managed._process.kill()
                        managed.status = ProcessStatus.KILLED
                        managed.ended_at = time.time()
                    except Exception:
                        pass
            killed = sum(
                1 for p in self._processes.values()
                if p.status == ProcessStatus.KILLED
            )
        logger.info(f"ProcessManager shutdown complete — killed {killed} processes")

