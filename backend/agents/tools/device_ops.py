"""
Device Operations Tool
──────────────────────
Provides the Super Agent with localized, permission-based control over the host 
device's hardware and software. Utilizes `psutil` for cross-platform performance
monitoring and process management.

All critical actions are gated behind a SecurityGateway with explicit user opt-in.
"""

import logging
import platform
import subprocess  # nosec B404
import sys
from typing import Dict, Any, List

import psutil

from agents.tools.registry import registry, ToolRiskLevel

logger = logging.getLogger(__name__)

# ── Allowlisted power commands per platform ──
_POWER_COMMANDS = {
    "windows": {
        "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
    },
    "linux": {
        "sleep": ["systemctl", "suspend"],
    },
    "darwin": {
        "sleep": ["pmset", "sleepnow"],
    },
}


# --- Security Gateway ---

class SecurityGateway:
    """
    Acts as the firewall between the Agent's reasoning engine and the Host OS.
    
    SECURITY: Permission defaults to DENIED. Must be explicitly granted by
    the user at session start via interactive prompt or env var set to 'true'.
    """
    
    # Global permission flag. Must be granted by the user.
    _DEVICE_CONTROL_GRANTED = False
    
    @classmethod
    def request_permission(cls) -> bool:
        """Check if device control permission has been granted."""
        if cls._DEVICE_CONTROL_GRANTED:
            return True
        
        # Only grant if explicitly set — defaults to DENIED
        import os
        explicit_grant = os.getenv("SUPER_AGENT_ALLOW_DEVICE", "false").lower()
        if explicit_grant == "true":
            logger.warning("Device control granted via SUPER_AGENT_ALLOW_DEVICE env var")
            cls._DEVICE_CONTROL_GRANTED = True
            return True
        
        return False

    @classmethod
    def verify(cls):
        """Raises PermissionError if permission is not granted."""
        if not cls.request_permission():
            raise PermissionError(
                "Device Control permission not granted. "
                "Set SUPER_AGENT_ALLOW_DEVICE=true or grant via interactive prompt."
            )


# --- Platform-safe command execution ---

def _execute_power_command(action: str) -> str:
    """Execute a power command using the platform-specific allowlist."""
    os_name = platform.system().lower()
    
    # Map Darwin to 'darwin'
    platform_key = os_name if os_name in _POWER_COMMANDS else None
    if not platform_key:
        return f"Unsupported platform: {os_name}"
    
    commands = _POWER_COMMANDS.get(platform_key, {})
    cmd_args = commands.get(action)
    
    if not cmd_args:
        return f"Unsupported power action '{action}' on {os_name}"
    
    try:
        result = subprocess.run(
            cmd_args,
            shell=False,           # nosec B603: using allowlisted commands only
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return f"Power command '{action}' executed successfully."
        else:
            return f"Power command failed (exit {result.returncode}): {result.stderr[:200]}"
    except subprocess.TimeoutExpired:
        return f"Power command '{action}' timed out."
    except Exception as e:
        return f"Failed to execute power command: {type(e).__name__}"


# --- Agent Tools ---

@registry.register(
    name="get_device_performance",
    description="Reads the current hardware performance metrics (CPU, RAM, Disk, Temps) of the host device. Requires user permission.",
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "type": "object",
        "properties": {}
    }
)
def get_device_performance() -> Dict[str, Any]:
    """Retrieve detailed system performance utilizing psutil."""
    SecurityGateway.verify()
    logger.info("📊 Fetching Host Device Performance Metrics...")
    
    metrics = {}
    
    # CPU
    metrics["cpu_percent"] = psutil.cpu_percent(interval=0.5)
    metrics["cpu_cores"] = psutil.cpu_count(logical=False)
    metrics["cpu_threads"] = psutil.cpu_count(logical=True)
    
    # RAM
    mem = psutil.virtual_memory()
    metrics["ram_total_gb"] = round(mem.total / (1024**3), 2)
    metrics["ram_used_gb"] = round(mem.used / (1024**3), 2)
    metrics["ram_percent"] = mem.percent
    
    # Disk
    disk = psutil.disk_usage('/')
    metrics["disk_total_gb"] = round(disk.total / (1024**3), 2)
    metrics["disk_used_gb"] = round(disk.used / (1024**3), 2)
    metrics["disk_percent"] = disk.percent
    
    # Battery (if laptop)
    if hasattr(psutil, "sensors_battery"):
        batt = psutil.sensors_battery()
        if batt:
            metrics["battery_percent"] = batt.percent
            metrics["power_plugged"] = batt.power_plugged
            
    return metrics


@registry.register(
    name="manage_processes",
    description="View, kill, or suspend processes running on the host device. Use cautiously to free up metrics. 'action' can be 'list_top', 'kill', or 'suspend'. Provide 'pid' if taking direct action.",
    risk_level=ToolRiskLevel.CRITICAL,
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_top", "kill", "suspend"],
                "description": "What operation to perform on the host's process tree."
            },
            "pid": {
                "type": "integer",
                "description": "The Process ID to target (required for kill/suspend).",
                "default": 0
            }
        },
        "required": ["action"]
    }
)
def manage_processes(action: str, pid: int = 0) -> str:
    """Control the process tree of the operating system."""
    SecurityGateway.verify()
    
    # Validate action against allowlist
    if action not in ("list_top", "kill", "suspend"):
        return "Invalid action. Must be one of: list_top, kill, suspend"
    
    if action == "list_top":
        # Return top 10 memory consuming processes
        procs = []
        for p in psutil.process_iter(['pid', 'name', 'memory_percent']):
            try:
                if p.info['memory_percent'] is not None:
                    procs.append(p.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by memory usage
        procs = sorted(procs, key=lambda x: x['memory_percent'], reverse=True)[:10]
        
        output = "Top 10 Memory Consuming Processes:\n"
        for p in procs:
            output += f"PID: {p['pid']} | Name: {p['name']} | Mem: {p['memory_percent']:.1f}%\n"
        return output
        
    elif action == "kill":
        if not pid:
            return "Error: Must specify a 'pid' to kill."
        try:
            p = psutil.Process(pid)
            p_name = p.name()
            p.kill()
            return f"Successfully killed process {p_name} (PID: {pid})."
        except psutil.NoSuchProcess:
            return f"Process with PID {pid} not found."
        except psutil.AccessDenied:
            return f"Access denied when trying to kill PID {pid}."
        except Exception:
            return f"Failed to kill PID {pid}."
            
    elif action == "suspend":
        if not pid:
            return "Error: Must specify a 'pid' to suspend."
        try:
            p = psutil.Process(pid)
            p_name = p.name()
            p.suspend()
            return f"Successfully suspended process {p_name} (PID: {pid})."
        except psutil.NoSuchProcess:
            return f"Process with PID {pid} not found."
        except psutil.AccessDenied:
            return f"Access denied when trying to suspend PID {pid}."
        except AttributeError:
            return f"Suspend not supported on this OS for PID {pid}."
        except Exception:
            return f"Failed to suspend PID {pid}."
            
    return "Invalid action."


@registry.register(
    name="manage_power_state",
    description="Control the host device's power state. Use 'sleep' to suspend the machine.",
    risk_level=ToolRiskLevel.CRITICAL,
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["sleep"],
                "description": "The power state action to execute."
            }
        },
        "required": ["action"]
    }
)
def manage_power_state(action: str) -> str:
    """Executes OS-specific power instructions using allowlisted commands only."""
    SecurityGateway.verify()
    
    # Validate action against strict allowlist
    if action not in ("sleep",):
        return f"Unsupported power action: {action}"
    
    logger.warning(f"🔋 Agent attempting to change device power state -> {action}")
    return _execute_power_command(action)
