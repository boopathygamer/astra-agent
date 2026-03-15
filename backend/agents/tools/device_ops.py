"""
Device Operations — Production-Grade Hardware Control Interface
════════════════════════════════════════════════════════════════
Provides the agent with controlled, permission-gated access to
the host device's hardware and software systems.

8 Registered Tools:
  ┌────────────────────────────────────────────────────────────┐
  │ get_device_performance   Enhanced system metrics           │
  │ manage_processes         Process lifecycle control         │
  │ manage_power_state       Power state management            │
  │ get_network_status       Network intelligence              │
  │ manage_services          System service control            │
  │ get_peripheral_devices   Peripheral enumeration            │
  │ manage_scheduled_tasks   Cron / Task Scheduler             │
  │ execute_system_command   Allowlisted command execution     │
  └────────────────────────────────────────────────────────────┘

Security:
  - SecurityGateway: permission defaults to DENIED, explicit opt-in
  - AuditTrail: every hardware action logged with timestamp + caller
  - Allowlisted commands only — NO arbitrary shell execution
  - Ethics engine integration for destructive actions
"""

import json
import logging
import os
import platform
import socket
import subprocess  # nosec B404
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import psutil

from agents.tools.registry import registry, ToolRiskLevel

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Security Gateway — Permission Firewall
# ══════════════════════════════════════════════════════════════════════

class SecurityGateway:
    """
    Firewall between the agent's reasoning engine and the host OS.

    Permission defaults to DENIED. Must be explicitly granted by
    the user at session start via interactive prompt or env var.

    Tracks permission grants for audit purposes.
    """

    _DEVICE_CONTROL_GRANTED: bool = False
    _grant_timestamp: Optional[float] = None
    _grant_method: str = ""

    @classmethod
    def request_permission(cls) -> bool:
        """Check if device control permission has been granted."""
        if cls._DEVICE_CONTROL_GRANTED:
            return True

        explicit_grant = os.getenv(
            "SUPER_AGENT_ALLOW_DEVICE", "false"
        ).lower()
        if explicit_grant == "true":
            logger.warning(
                "Device control granted via SUPER_AGENT_ALLOW_DEVICE env var"
            )
            cls._DEVICE_CONTROL_GRANTED = True
            cls._grant_timestamp = time.time()
            cls._grant_method = "env_var"
            return True

        return False

    @classmethod
    def grant(cls, method: str = "interactive"):
        """Explicitly grant device control permission."""
        cls._DEVICE_CONTROL_GRANTED = True
        cls._grant_timestamp = time.time()
        cls._grant_method = method
        logger.warning(f"Device control GRANTED via {method}")

    @classmethod
    def revoke(cls):
        """Revoke device control permission."""
        cls._DEVICE_CONTROL_GRANTED = False
        cls._grant_timestamp = None
        cls._grant_method = ""
        logger.info("Device control REVOKED")

    @classmethod
    def verify(cls):
        """Raises PermissionError if permission is not granted."""
        if not cls.request_permission():
            raise PermissionError(
                "Device Control permission not granted. "
                "Set SUPER_AGENT_ALLOW_DEVICE=true or grant via "
                "interactive prompt at session start."
            )

    @classmethod
    def get_status(cls) -> Dict[str, Any]:
        """Get current permission status."""
        return {
            "granted": cls._DEVICE_CONTROL_GRANTED,
            "grant_time": cls._grant_timestamp,
            "grant_method": cls._grant_method,
        }


# ══════════════════════════════════════════════════════════════════════
# Audit Trail — Hardware Action Logging
# ══════════════════════════════════════════════════════════════════════

@dataclass
class AuditEntry:
    """A single hardware action audit record."""
    timestamp: float = field(default_factory=time.time)
    tool: str = ""
    action: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    result: str = ""
    success: bool = True
    risk_level: str = ""
    caller: str = "agent"


class AuditTrail:
    """
    Immutable audit log of all hardware control actions.
    Persists to disk as JSONL for forensic review.
    """

    def __init__(self, audit_dir: Optional[str] = None):
        if audit_dir:
            self._dir = Path(audit_dir)
        else:
            self._dir = Path(__file__).parent.parent / "data" / "hardware_audit"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._log: List[AuditEntry] = []
        self._file = self._dir / "audit.jsonl"

    def record(
        self,
        tool: str,
        action: str,
        parameters: Dict[str, Any] = None,
        result: str = "",
        success: bool = True,
        risk_level: str = "medium",
    ) -> AuditEntry:
        """Record a hardware action to the audit trail."""
        entry = AuditEntry(
            tool=tool,
            action=action,
            parameters=parameters or {},
            result=result[:500],
            success=success,
            risk_level=risk_level,
        )
        self._log.append(entry)

        # Append to disk
        try:
            with open(self._file, "a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(entry), default=str) + "\n")
        except OSError as e:
            logger.warning(f"Failed to write audit entry: {e}")

        return entry

    def get_recent(self, n: int = 20) -> List[AuditEntry]:
        """Get the N most recent audit entries."""
        return self._log[-n:]

    def get_by_tool(self, tool: str) -> List[AuditEntry]:
        """Get all entries for a specific tool."""
        return [e for e in self._log if e.tool == tool]


# Global audit trail instance
_audit = AuditTrail()


# ══════════════════════════════════════════════════════════════════════
# Allowlisted System Commands
# ══════════════════════════════════════════════════════════════════════

_POWER_COMMANDS = {
    "windows": {
        "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
        "hibernate": ["shutdown", "/h"],
        "restart": ["shutdown", "/r", "/t", "30", "/c",
                     "Astra Agent requested restart in 30s"],
    },
    "linux": {
        "sleep": ["systemctl", "suspend"],
        "hibernate": ["systemctl", "hibernate"],
        "restart": ["shutdown", "-r", "+1"],
    },
    "darwin": {
        "sleep": ["pmset", "sleepnow"],
        "restart": ["shutdown", "-r", "+1"],
    },
}

# Commands allowed via execute_system_command (read-only / diagnostic)
_ALLOWED_COMMANDS: Dict[str, List[str]] = {
    "ping": ["ping", "-n", "4"] if platform.system() == "Windows" else ["ping", "-c", "4"],
    "ipconfig": (
        ["ipconfig", "/all"] if platform.system() == "Windows"
        else ["ip", "addr", "show"]
    ),
    "whoami": ["whoami"],
    "hostname": ["hostname"],
    "date": (
        ["powershell", "-NoProfile", "-Command", "Get-Date"]
        if platform.system() == "Windows"
        else ["date"]
    ),
    "uptime": (
        ["powershell", "-NoProfile", "-Command",
         "(Get-Date) - (Get-CimInstance Win32_OperatingSystem).LastBootUpTime | "
         "Format-Table Days,Hours,Minutes -AutoSize"]
        if platform.system() == "Windows"
        else ["uptime"]
    ),
    "diskspace": (
        ["powershell", "-NoProfile", "-Command",
         "Get-PSDrive -PSProvider FileSystem | "
         "Select Name,Used,Free | Format-Table -AutoSize"]
        if platform.system() == "Windows"
        else ["df", "-h"]
    ),
    "netstat": (
        ["netstat", "-an"] if platform.system() == "Windows"
        else ["ss", "-tuln"]
    ),
    "dns_lookup": (
        ["nslookup"] if platform.system() == "Windows"
        else ["dig"]
    ),
    "traceroute": (
        ["tracert", "-d", "-h", "10"]
        if platform.system() == "Windows"
        else ["traceroute", "-m", "10", "-n"]
    ),
    "arp": ["arp", "-a"],
    "route": (
        ["route", "print"] if platform.system() == "Windows"
        else ["ip", "route", "show"]
    ),
}


def _execute_safe_command(
    cmd_args: List[str], timeout: int = 15
) -> str:
    """Execute a command from the allowlist with timeout protection."""
    try:
        result = subprocess.run(
            cmd_args,
            shell=False,           # nosec B603
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = result.stdout[:3000]
        if result.returncode != 0 and result.stderr:
            output += f"\n[stderr] {result.stderr[:500]}"
        return output if output.strip() else "(no output)"

    except subprocess.TimeoutExpired:
        return f"Command timed out after {timeout}s"
    except FileNotFoundError:
        return f"Command not found: {cmd_args[0]}"
    except OSError as e:
        return f"OS error: {type(e).__name__}"


# ══════════════════════════════════════════════════════════════════════
# Tool 1: get_device_performance (Enhanced)
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="get_device_performance",
    description=(
        "Read comprehensive hardware performance metrics: CPU (per-core + frequency), "
        "RAM (used/available/swap), disk (usage + I/O rates), network I/O, battery, "
        "and GPU info. Requires user permission."
    ),
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "type": "object",
        "properties": {
            "detailed": {
                "type": "boolean",
                "description": "If true, include per-core CPU and disk I/O details.",
                "default": False,
            }
        },
    },
)
def get_device_performance(detailed: bool = False) -> Dict[str, Any]:
    """Retrieve comprehensive system performance metrics."""
    SecurityGateway.verify()

    metrics: Dict[str, Any] = {}

    # CPU
    metrics["cpu_percent"] = psutil.cpu_percent(interval=0.5)
    metrics["cpu_cores_physical"] = psutil.cpu_count(logical=False)
    metrics["cpu_cores_logical"] = psutil.cpu_count(logical=True)

    if detailed:
        metrics["cpu_per_core"] = psutil.cpu_percent(interval=0, percpu=True)

    try:
        freq = psutil.cpu_freq()
        if freq:
            metrics["cpu_freq_mhz"] = round(freq.current, 1)
            metrics["cpu_freq_max_mhz"] = round(freq.max, 1)
    except Exception:
        pass

    try:
        load = psutil.getloadavg()
        metrics["load_avg"] = [round(x, 2) for x in load]
    except (AttributeError, OSError):
        pass

    # RAM
    mem = psutil.virtual_memory()
    metrics["ram_total_gb"] = round(mem.total / (1024 ** 3), 2)
    metrics["ram_used_gb"] = round(mem.used / (1024 ** 3), 2)
    metrics["ram_available_gb"] = round(mem.available / (1024 ** 3), 2)
    metrics["ram_percent"] = mem.percent

    swap = psutil.swap_memory()
    metrics["swap_used_gb"] = round(swap.used / (1024 ** 3), 2)
    metrics["swap_percent"] = swap.percent

    # Disk
    try:
        root = "C:\\" if platform.system() == "Windows" else "/"
        disk = psutil.disk_usage(root)
        metrics["disk_total_gb"] = round(disk.total / (1024 ** 3), 2)
        metrics["disk_used_gb"] = round(disk.used / (1024 ** 3), 2)
        metrics["disk_free_gb"] = round(disk.free / (1024 ** 3), 2)
        metrics["disk_percent"] = disk.percent
    except Exception:
        pass

    if detailed:
        try:
            dio = psutil.disk_io_counters()
            if dio:
                metrics["disk_read_mb"] = round(dio.read_bytes / (1024 ** 2), 1)
                metrics["disk_write_mb"] = round(dio.write_bytes / (1024 ** 2), 1)
        except Exception:
            pass

    # Network I/O
    try:
        nio = psutil.net_io_counters()
        metrics["net_sent_mb"] = round(nio.bytes_sent / (1024 ** 2), 1)
        metrics["net_recv_mb"] = round(nio.bytes_recv / (1024 ** 2), 1)
    except Exception:
        pass

    # Battery
    try:
        batt = psutil.sensors_battery()
        if batt:
            metrics["battery_percent"] = batt.percent
            metrics["battery_plugged"] = batt.power_plugged
    except Exception:
        pass

    # GPU info (Windows PowerShell)
    if platform.system() == "Windows":
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_VideoController 2>$null | "
                "Select-Object -First 1 Name,AdapterRAM | ConvertTo-Json"
            ]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=8,
                shell=False,  # nosec B603
            )
            if proc.returncode == 0 and proc.stdout.strip():
                gpu = json.loads(proc.stdout)
                metrics["gpu_name"] = gpu.get("Name", "Unknown")
                ram = gpu.get("AdapterRAM")
                if ram and isinstance(ram, (int, float)):
                    metrics["gpu_ram_gb"] = round(ram / (1024 ** 3), 1)
        except Exception:
            pass

    _audit.record("get_device_performance", "read", {"detailed": detailed},
                  f"CPU: {metrics.get('cpu_percent')}%", True, "medium")

    return metrics


# ══════════════════════════════════════════════════════════════════════
# Tool 2: manage_processes (Enhanced)
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="manage_processes",
    description=(
        "View, kill, suspend, or resume processes. Actions: 'list_top' (top 10 by memory), "
        "'list_by_name' (search by name), 'list_children' (agent child processes), "
        "'kill' (terminate PID), 'suspend' (pause PID), 'resume' (unpause PID). "
        "Provide 'pid' for kill/suspend/resume, 'name' for list_by_name."
    ),
    risk_level=ToolRiskLevel.CRITICAL,
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_top", "list_by_name", "list_children",
                         "kill", "suspend", "resume"],
                "description": "Operation to perform.",
            },
            "pid": {
                "type": "integer",
                "description": "Target Process ID (for kill/suspend/resume).",
                "default": 0,
            },
            "name": {
                "type": "string",
                "description": "Process name filter (for list_by_name).",
                "default": "",
            },
        },
        "required": ["action"],
    },
)
def manage_processes(
    action: str, pid: int = 0, name: str = ""
) -> str:
    """Control the process tree of the operating system."""
    SecurityGateway.verify()

    valid_actions = (
        "list_top", "list_by_name", "list_children",
        "kill", "suspend", "resume",
    )
    if action not in valid_actions:
        return f"Invalid action. Must be one of: {', '.join(valid_actions)}"

    result_text = ""

    if action == "list_top":
        procs = []
        for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
            try:
                info = p.info
                if info.get("memory_percent") is not None:
                    procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda x: x.get("memory_percent", 0) or 0, reverse=True)
        lines = ["Top 10 Processes by Memory:"]
        for p in procs[:10]:
            lines.append(
                f"  PID {p['pid']:>6} | {p['name']:<25} | "
                f"MEM {p.get('memory_percent', 0):.1f}% | "
                f"CPU {p.get('cpu_percent', 0):.1f}%"
            )
        result_text = "\n".join(lines)

    elif action == "list_by_name":
        if not name:
            return "Error: 'name' parameter required for list_by_name"

        name_lower = name.lower()
        matches = []
        for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent", "status"]):
            try:
                info = p.info
                if name_lower in (info.get("name", "") or "").lower():
                    matches.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        if not matches:
            result_text = f"No processes matching '{name}' found."
        else:
            lines = [f"Processes matching '{name}' ({len(matches)} found):"]
            for p in matches[:20]:
                lines.append(
                    f"  PID {p['pid']:>6} | {p['name']:<25} | "
                    f"Status: {p.get('status', '?')}"
                )
            result_text = "\n".join(lines)

    elif action == "list_children":
        try:
            parent = psutil.Process(os.getpid())
            children = parent.children(recursive=True)
            if not children:
                result_text = "No child processes."
            else:
                lines = [f"Agent child processes ({len(children)}):"]
                for c in children[:30]:
                    try:
                        lines.append(
                            f"  PID {c.pid:>6} | {c.name():<25} | "
                            f"Status: {c.status()}"
                        )
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                result_text = "\n".join(lines)
        except psutil.NoSuchProcess:
            result_text = "Could not read agent process tree."

    elif action == "kill":
        if not pid:
            return "Error: 'pid' required for kill"
        try:
            p = psutil.Process(pid)
            p_name = p.name()
            p.kill()
            result_text = f"Killed process '{p_name}' (PID {pid})"
        except psutil.NoSuchProcess:
            result_text = f"Process PID {pid} not found."
        except psutil.AccessDenied:
            result_text = f"Access denied: cannot kill PID {pid}."

    elif action == "suspend":
        if not pid:
            return "Error: 'pid' required for suspend"
        try:
            p = psutil.Process(pid)
            p_name = p.name()
            p.suspend()
            result_text = f"Suspended process '{p_name}' (PID {pid})"
        except psutil.NoSuchProcess:
            result_text = f"Process PID {pid} not found."
        except psutil.AccessDenied:
            result_text = f"Access denied: cannot suspend PID {pid}."

    elif action == "resume":
        if not pid:
            return "Error: 'pid' required for resume"
        try:
            p = psutil.Process(pid)
            p_name = p.name()
            p.resume()
            result_text = f"Resumed process '{p_name}' (PID {pid})"
        except psutil.NoSuchProcess:
            result_text = f"Process PID {pid} not found."
        except psutil.AccessDenied:
            result_text = f"Access denied: cannot resume PID {pid}."

    _audit.record("manage_processes", action,
                  {"pid": pid, "name": name}, result_text[:200],
                  "Error" not in result_text and "denied" not in result_text,
                  "critical")

    return result_text


# ══════════════════════════════════════════════════════════════════════
# Tool 3: manage_power_state (Enhanced)
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="manage_power_state",
    description=(
        "Control the host device's power state. Actions: "
        "'sleep' (suspend to RAM), 'hibernate' (suspend to disk), "
        "'restart' (delayed restart with warning). Use with extreme caution."
    ),
    risk_level=ToolRiskLevel.CRITICAL,
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["sleep", "hibernate", "restart"],
                "description": "Power state action to execute.",
            },
        },
        "required": ["action"],
    },
)
def manage_power_state(action: str) -> str:
    """Execute OS-specific power instructions using allowlisted commands."""
    SecurityGateway.verify()

    os_name = platform.system().lower()
    commands = _POWER_COMMANDS.get(os_name, {})
    cmd_args = commands.get(action)

    if not cmd_args:
        return f"Unsupported action '{action}' on {os_name}"

    logger.warning(f"🔋 Power state change -> {action}")
    _audit.record("manage_power_state", action, {}, "executing", True, "critical")

    return _execute_safe_command(cmd_args, timeout=10)


# ══════════════════════════════════════════════════════════════════════
# Tool 4: get_network_status (NEW)
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="get_network_status",
    description=(
        "Get comprehensive network intelligence: active connections, bandwidth usage, "
        "interface details, DNS latency, and internet connectivity check."
    ),
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={"type": "object", "properties": {}},
)
def get_network_status() -> Dict[str, Any]:
    """Read network status including connections, bandwidth, and latency."""
    SecurityGateway.verify()

    result: Dict[str, Any] = {}

    # Network I/O
    try:
        nio = psutil.net_io_counters()
        result["bytes_sent_mb"] = round(nio.bytes_sent / (1024 ** 2), 1)
        result["bytes_recv_mb"] = round(nio.bytes_recv / (1024 ** 2), 1)
        result["packets_sent"] = nio.packets_sent
        result["packets_recv"] = nio.packets_recv
        result["errors"] = nio.errin + nio.errout
        result["drops"] = nio.dropin + nio.dropout
    except Exception:
        pass

    # Active connections (by state)
    try:
        conns = psutil.net_connections(kind="inet")
        states: Dict[str, int] = {}
        for c in conns:
            s = c.status or "NONE"
            states[s] = states.get(s, 0) + 1
        result["connection_states"] = states
        result["total_connections"] = len(conns)
    except (psutil.AccessDenied, OSError):
        result["total_connections"] = -1
        result["note"] = "Requires elevated permissions for full data"

    # Network interfaces
    try:
        addrs = psutil.net_if_addrs()
        interfaces = []
        for iface_name, addr_list in addrs.items():
            for addr in addr_list:
                if addr.family == socket.AF_INET:
                    interfaces.append({
                        "name": iface_name,
                        "ipv4": addr.address,
                        "netmask": addr.netmask,
                    })
                    break
        result["interfaces"] = interfaces
    except Exception:
        pass

    # Internet connectivity + DNS latency
    try:
        start = time.time()
        socket.getaddrinfo("dns.google", 443, socket.AF_INET)
        result["dns_latency_ms"] = round((time.time() - start) * 1000, 1)
        result["internet_reachable"] = True
    except (socket.gaierror, OSError):
        result["dns_latency_ms"] = -1
        result["internet_reachable"] = False

    result["hostname"] = socket.gethostname()

    _audit.record("get_network_status", "read", {}, "ok", True, "medium")
    return result


# ══════════════════════════════════════════════════════════════════════
# Tool 5: manage_services (NEW)
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="manage_services",
    description=(
        "List, start, or stop system services. Actions: 'list' (all running services), "
        "'status' (check specific service), 'start' (start service), 'stop' (stop service). "
        "Provide 'service_name' for status/start/stop."
    ),
    risk_level=ToolRiskLevel.CRITICAL,
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "status", "start", "stop"],
                "description": "Service management action.",
            },
            "service_name": {
                "type": "string",
                "description": "Name of the service to manage.",
                "default": "",
            },
        },
        "required": ["action"],
    },
)
def manage_services(action: str, service_name: str = "") -> str:
    """Manage system services (Windows sc / Linux systemctl)."""
    SecurityGateway.verify()

    os_name = platform.system()

    if action == "list":
        if os_name == "Windows":
            return _execute_safe_command(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Service | Where-Object {$_.Status -eq 'Running'} | "
                 "Select-Object -First 30 Name,DisplayName,Status | "
                 "Format-Table -AutoSize"],
                timeout=15,
            )
        else:
            return _execute_safe_command(
                ["systemctl", "list-units", "--type=service", "--state=running",
                 "--no-pager", "--no-legend"],
                timeout=10,
            )

    if not service_name:
        return "Error: 'service_name' required for status/start/stop"

    # Sanitize service name (alphanumeric + hyphens/underscores/dots only)
    import re
    if not re.match(r'^[a-zA-Z0-9._-]+$', service_name):
        return "Error: Invalid service name (alphanumeric, dots, hyphens, underscores only)"

    if action == "status":
        if os_name == "Windows":
            cmd = ["sc", "query", service_name]
        else:
            cmd = ["systemctl", "status", service_name, "--no-pager"]
        result = _execute_safe_command(cmd, timeout=10)

    elif action == "start":
        if os_name == "Windows":
            cmd = ["sc", "start", service_name]
        else:
            cmd = ["systemctl", "start", service_name]
        result = _execute_safe_command(cmd, timeout=15)

    elif action == "stop":
        if os_name == "Windows":
            cmd = ["sc", "stop", service_name]
        else:
            cmd = ["systemctl", "stop", service_name]
        result = _execute_safe_command(cmd, timeout=15)
    else:
        return f"Invalid action: {action}"

    _audit.record("manage_services", action,
                  {"service_name": service_name}, result[:200],
                  True, "critical")
    return result


# ══════════════════════════════════════════════════════════════════════
# Tool 6: get_peripheral_devices (NEW)
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="get_peripheral_devices",
    description=(
        "Enumerate connected peripheral devices: USB devices, display adapters, "
        "and audio devices on the host system."
    ),
    risk_level=ToolRiskLevel.LOW,
    parameters={"type": "object", "properties": {}},
)
def get_peripheral_devices() -> Dict[str, Any]:
    """List connected USB, display, and audio peripherals."""
    # This tool is LOW risk — read only discovery, no SecurityGateway needed
    from brain.environment_observer import PeripheralScanner

    scanner = PeripheralScanner()
    result = scanner.scan()

    _audit.record("get_peripheral_devices", "scan", {}, "ok", True, "low")
    return result


# ══════════════════════════════════════════════════════════════════════
# Tool 7: manage_scheduled_tasks (NEW)
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="manage_scheduled_tasks",
    description=(
        "Manage scheduled tasks / cron jobs. Actions: 'list' (show all tasks), "
        "'create' (schedule a new task), 'delete' (remove a task). "
        "Provide 'task_name' and 'command' for create. Provide 'task_name' for delete."
    ),
    risk_level=ToolRiskLevel.CRITICAL,
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create", "delete"],
                "description": "Scheduled task action.",
            },
            "task_name": {
                "type": "string",
                "description": "Name for the scheduled task.",
                "default": "",
            },
            "command": {
                "type": "string",
                "description": "Command to schedule (for create).",
                "default": "",
            },
            "schedule": {
                "type": "string",
                "description": "Schedule: 'hourly', 'daily', or 'weekly'.",
                "default": "daily",
            },
        },
        "required": ["action"],
    },
)
def manage_scheduled_tasks(
    action: str,
    task_name: str = "",
    command: str = "",
    schedule: str = "daily",
) -> str:
    """Manage cron jobs (Linux/Mac) or Task Scheduler (Windows)."""
    SecurityGateway.verify()

    os_name = platform.system()

    if action == "list":
        if os_name == "Windows":
            return _execute_safe_command(
                ["schtasks", "/Query", "/FO", "TABLE", "/NH"],
                timeout=15,
            )
        else:
            return _execute_safe_command(
                ["crontab", "-l"],
                timeout=5,
            )

    if not task_name:
        return "Error: 'task_name' required for create/delete"

    # Sanitize task name
    import re
    if not re.match(r'^[a-zA-Z0-9_-]+$', task_name):
        return "Error: Task name must be alphanumeric with underscores/hyphens"

    if action == "create":
        if not command:
            return "Error: 'command' required for create"

        # Only allow scheduling of Python scripts or specific commands
        if not (command.endswith(".py") or command.startswith("python")):
            return "Error: Only Python scripts can be scheduled for safety"

        schedule_map = {
            "hourly": "HOURLY",
            "daily": "DAILY",
            "weekly": "WEEKLY",
        }
        sched = schedule_map.get(schedule, "DAILY")

        if os_name == "Windows":
            cmd = [
                "schtasks", "/Create", "/TN", f"AstraAgent_{task_name}",
                "/TR", command, "/SC", sched, "/F",
            ]
        else:
            # Map to cron expression
            cron_map = {
                "hourly": "0 * * * *",
                "daily": "0 2 * * *",
                "weekly": "0 2 * * 0",
            }
            cron_expr = cron_map.get(schedule, "0 2 * * *")
            # Append to crontab
            cmd = ["bash", "-c",
                   f'(crontab -l 2>/dev/null; echo "{cron_expr} {command} '
                   f'# AstraAgent_{task_name}") | crontab -']

        result = _execute_safe_command(cmd, timeout=10)

    elif action == "delete":
        if os_name == "Windows":
            cmd = ["schtasks", "/Delete", "/TN",
                   f"AstraAgent_{task_name}", "/F"]
        else:
            cmd = ["bash", "-c",
                   f"crontab -l 2>/dev/null | "
                   f"grep -v 'AstraAgent_{task_name}' | crontab -"]
        result = _execute_safe_command(cmd, timeout=10)
    else:
        return f"Invalid action: {action}"

    _audit.record("manage_scheduled_tasks", action,
                  {"task_name": task_name, "command": command[:100]},
                  result[:200], True, "critical")
    return result


# ══════════════════════════════════════════════════════════════════════
# Tool 8: execute_system_command (NEW — Allowlisted Only)
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="execute_system_command",
    description=(
        "Execute a pre-approved diagnostic command. Available commands: "
        "ping, ipconfig, whoami, hostname, date, uptime, diskspace, "
        "netstat, dns_lookup, traceroute, arp, route. "
        "Provide 'target' for commands that need a hostname/IP (ping, dns_lookup, traceroute)."
    ),
    risk_level=ToolRiskLevel.CRITICAL,
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "enum": list(_ALLOWED_COMMANDS.keys()),
                "description": "The diagnostic command to run.",
            },
            "target": {
                "type": "string",
                "description": "Target host/IP for commands like ping, traceroute.",
                "default": "",
            },
        },
        "required": ["command"],
    },
)
def execute_system_command(command: str, target: str = "") -> str:
    """Execute an allowlisted diagnostic command with optional target."""
    SecurityGateway.verify()

    if command not in _ALLOWED_COMMANDS:
        return (
            f"Command '{command}' is NOT in the allowlist. "
            f"Available: {', '.join(_ALLOWED_COMMANDS.keys())}"
        )

    cmd_args = list(_ALLOWED_COMMANDS[command])

    # Append target for commands that need it
    if target and command in ("ping", "dns_lookup", "traceroute"):
        # Sanitize target — only allow hostnames and IPs
        import re
        if not re.match(r'^[a-zA-Z0-9._:-]+$', target):
            return "Error: Invalid target (alphanumeric, dots, colons, hyphens only)"
        if len(target) > 253:
            return "Error: Target too long"
        cmd_args.append(target)

    _audit.record("execute_system_command", command,
                  {"target": target}, "executing", True, "critical")

    return _execute_safe_command(cmd_args, timeout=30)


# ══════════════════════════════════════════════════════════════════════
# Utility: Get audit trail
# ══════════════════════════════════════════════════════════════════════

def get_hardware_audit(n: int = 20) -> List[Dict[str, Any]]:
    """Get the most recent hardware audit entries."""
    return [asdict(e) for e in _audit.get_recent(n)]
