"""
Environment Observer — 7-Sensor Autonomous Perception Engine
═════════════════════════════════════════════════════════════
Gives the agent real-time awareness of its host operating environment
through 7 independent sensor subsystems. Each sensor is fail-isolated:
if one crashes, the rest continue operating.

Sensors:
  ┌───────────────────────────────────────────────────────────────────┐
  │ 1. SystemVitals      CPU, RAM, disk, battery, uptime             │
  │ 2. NetworkProbe      Connections, bandwidth, latency, public IP  │
  │ 3. ProcessRadar      Running processes, resource hogs, children  │
  │ 4. FileSystemWatch   Partitions, mounts, workspace file changes  │
  │ 5. PeripheralScanner USB, display, audio device enumeration      │
  │ 6. EnvironmentContext OS, Python, env vars, locale, timezone     │
  │ 7. ThermalSentinel   CPU/GPU temps, fan speeds, throttle state   │
  └───────────────────────────────────────────────────────────────────┘

Architecture:
  EnvironmentObserver
    ├── 7 Sensor instances (each with .scan() → dict)
    ├── AnomalyDetector (z-score against rolling baseline)
    ├── SnapshotHistory (bounded deque of past observations)
    └── ContextGenerator (LLM-injectable environment summary)
"""

import logging
import math
import os
import platform
import socket
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

import psutil

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════════════

class AnomalyLevel(Enum):
    """Severity of a detected environment anomaly."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Anomaly:
    """A detected deviation from the environment baseline."""
    sensor: str
    metric: str
    current_value: float
    baseline_value: float
    z_score: float
    level: AnomalyLevel
    message: str
    timestamp: float = field(default_factory=time.time)


@dataclass
class EnvironmentSnapshot:
    """Complete environment observation at a point in time."""
    timestamp: float = field(default_factory=time.time)
    system_vitals: Dict[str, Any] = field(default_factory=dict)
    network: Dict[str, Any] = field(default_factory=dict)
    processes: Dict[str, Any] = field(default_factory=dict)
    filesystem: Dict[str, Any] = field(default_factory=dict)
    peripherals: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, Any] = field(default_factory=dict)
    thermal: Dict[str, Any] = field(default_factory=dict)
    anomalies: List[Anomaly] = field(default_factory=list)
    scan_duration_ms: float = 0.0
    sensors_failed: List[str] = field(default_factory=list)

    @property
    def sensor_count(self) -> int:
        return 7 - len(self.sensors_failed)

    def summary(self) -> str:
        lines = [
            f"═══ Environment Snapshot ═══",
            f"  Time:      {time.strftime('%H:%M:%S', time.localtime(self.timestamp))}",
            f"  Sensors:   {self.sensor_count}/7 active",
            f"  Duration:  {self.scan_duration_ms:.0f}ms",
            f"  Anomalies: {len(self.anomalies)}",
        ]
        if self.system_vitals:
            lines.append(
                f"  CPU: {self.system_vitals.get('cpu_percent', '?')}% | "
                f"RAM: {self.system_vitals.get('ram_percent', '?')}% | "
                f"Disk: {self.system_vitals.get('disk_percent', '?')}%"
            )
        if self.sensors_failed:
            lines.append(f"  ⚠ Failed: {', '.join(self.sensors_failed)}")
        return "\n".join(lines)


@dataclass
class EnvironmentDelta:
    """Changes between two consecutive environment snapshots."""
    time_elapsed_s: float = 0.0
    cpu_change: float = 0.0
    ram_change: float = 0.0
    new_processes: List[str] = field(default_factory=list)
    terminated_processes: List[str] = field(default_factory=list)
    new_connections: int = 0
    closed_connections: int = 0
    new_files: List[str] = field(default_factory=list)
    disk_change_mb: float = 0.0
    temperature_change: float = 0.0
    significant: bool = False

    def summary(self) -> str:
        parts = [f"Δt={self.time_elapsed_s:.1f}s"]
        if abs(self.cpu_change) > 5:
            parts.append(f"CPU{self.cpu_change:+.1f}%")
        if abs(self.ram_change) > 2:
            parts.append(f"RAM{self.ram_change:+.1f}%")
        if self.new_processes:
            parts.append(f"+{len(self.new_processes)} procs")
        if self.terminated_processes:
            parts.append(f"-{len(self.terminated_processes)} procs")
        if self.new_files:
            parts.append(f"+{len(self.new_files)} files")
        return " | ".join(parts)


# ══════════════════════════════════════════════════════════════════════
# Sensor 1: System Vitals
# ══════════════════════════════════════════════════════════════════════

class SystemVitals:
    """CPU, RAM, disk, battery, and system uptime."""

    def scan(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}

        # CPU — aggregate and per-core
        metrics["cpu_percent"] = psutil.cpu_percent(interval=0.3)
        metrics["cpu_per_core"] = psutil.cpu_percent(interval=0, percpu=True)
        metrics["cpu_cores_physical"] = psutil.cpu_count(logical=False) or 0
        metrics["cpu_cores_logical"] = psutil.cpu_count(logical=True) or 0

        try:
            freq = psutil.cpu_freq()
            if freq:
                metrics["cpu_freq_current_mhz"] = round(freq.current, 1)
                metrics["cpu_freq_max_mhz"] = round(freq.max, 1)
        except Exception:
            pass

        # Load averages (Unix) / queue length approximation (Windows)
        try:
            load_avg = psutil.getloadavg()
            metrics["load_avg_1m"] = round(load_avg[0], 2)
            metrics["load_avg_5m"] = round(load_avg[1], 2)
            metrics["load_avg_15m"] = round(load_avg[2], 2)
        except (AttributeError, OSError):
            pass

        # RAM
        mem = psutil.virtual_memory()
        metrics["ram_total_gb"] = round(mem.total / (1024 ** 3), 2)
        metrics["ram_used_gb"] = round(mem.used / (1024 ** 3), 2)
        metrics["ram_available_gb"] = round(mem.available / (1024 ** 3), 2)
        metrics["ram_percent"] = mem.percent

        # Swap
        swap = psutil.swap_memory()
        metrics["swap_total_gb"] = round(swap.total / (1024 ** 3), 2)
        metrics["swap_used_gb"] = round(swap.used / (1024 ** 3), 2)
        metrics["swap_percent"] = swap.percent

        # Disk — primary partition
        try:
            if platform.system() == "Windows":
                disk = psutil.disk_usage("C:\\")
            else:
                disk = psutil.disk_usage("/")
            metrics["disk_total_gb"] = round(disk.total / (1024 ** 3), 2)
            metrics["disk_used_gb"] = round(disk.used / (1024 ** 3), 2)
            metrics["disk_free_gb"] = round(disk.free / (1024 ** 3), 2)
            metrics["disk_percent"] = disk.percent
        except Exception:
            pass

        # Disk I/O counters
        try:
            dio = psutil.disk_io_counters()
            if dio:
                metrics["disk_read_mb"] = round(dio.read_bytes / (1024 ** 2), 1)
                metrics["disk_write_mb"] = round(dio.write_bytes / (1024 ** 2), 1)
                metrics["disk_read_count"] = dio.read_count
                metrics["disk_write_count"] = dio.write_count
        except Exception:
            pass

        # Battery
        try:
            batt = psutil.sensors_battery()
            if batt:
                metrics["battery_percent"] = batt.percent
                metrics["battery_plugged"] = batt.power_plugged
                if batt.secsleft > 0 and batt.secsleft != psutil.POWER_TIME_UNLIMITED:
                    metrics["battery_time_left_min"] = round(batt.secsleft / 60, 1)
        except Exception:
            pass

        # Uptime
        metrics["boot_time_epoch"] = psutil.boot_time()
        metrics["uptime_hours"] = round(
            (time.time() - psutil.boot_time()) / 3600, 2
        )

        return metrics


# ══════════════════════════════════════════════════════════════════════
# Sensor 2: Network Probe
# ══════════════════════════════════════════════════════════════════════

class NetworkProbe:
    """Active connections, bandwidth usage, latency, and network interfaces."""

    def scan(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}

        # Network I/O counters
        try:
            nio = psutil.net_io_counters()
            metrics["bytes_sent_mb"] = round(nio.bytes_sent / (1024 ** 2), 1)
            metrics["bytes_recv_mb"] = round(nio.bytes_recv / (1024 ** 2), 1)
            metrics["packets_sent"] = nio.packets_sent
            metrics["packets_recv"] = nio.packets_recv
            metrics["errors_in"] = nio.errin
            metrics["errors_out"] = nio.errout
            metrics["drops_in"] = nio.dropin
            metrics["drops_out"] = nio.dropout
        except Exception:
            pass

        # Active connections (count by state)
        try:
            connections = psutil.net_connections(kind="inet")
            state_counts: Dict[str, int] = {}
            for conn in connections:
                state = conn.status if conn.status else "NONE"
                state_counts[state] = state_counts.get(state, 0) + 1
            metrics["connection_states"] = state_counts
            metrics["total_connections"] = len(connections)
            metrics["established_count"] = state_counts.get("ESTABLISHED", 0)
            metrics["listening_count"] = state_counts.get("LISTEN", 0)
        except (psutil.AccessDenied, OSError):
            metrics["total_connections"] = -1
            metrics["connection_note"] = "Access denied — run as admin for full info"

        # Network interfaces
        try:
            addrs = psutil.net_if_addrs()
            interfaces = []
            for name, addr_list in addrs.items():
                for addr in addr_list:
                    if addr.family == socket.AF_INET:
                        interfaces.append({
                            "name": name,
                            "ipv4": addr.address,
                            "netmask": addr.netmask,
                        })
                        break
            metrics["interfaces"] = interfaces[:10]  # Cap at 10
        except Exception:
            pass

        # DNS resolution check (connectivity probe)
        try:
            start = time.time()
            socket.getaddrinfo("dns.google", 443, socket.AF_INET)
            metrics["dns_latency_ms"] = round((time.time() - start) * 1000, 1)
            metrics["internet_reachable"] = True
        except (socket.gaierror, OSError):
            metrics["dns_latency_ms"] = -1
            metrics["internet_reachable"] = False

        # Hostname
        metrics["hostname"] = socket.gethostname()

        return metrics


# ══════════════════════════════════════════════════════════════════════
# Sensor 3: Process Radar
# ══════════════════════════════════════════════════════════════════════

class ProcessRadar:
    """Running processes, resource hogs, and agent child processes."""

    def scan(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}

        # Collect process info
        proc_list = []
        for p in psutil.process_iter(
            ["pid", "name", "cpu_percent", "memory_percent", "status", "create_time"]
        ):
            try:
                info = p.info
                if info["memory_percent"] is not None:
                    proc_list.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        metrics["total_processes"] = len(proc_list)

        # Top 10 by memory
        by_memory = sorted(
            proc_list,
            key=lambda x: x.get("memory_percent", 0) or 0,
            reverse=True,
        )[:10]
        metrics["top_by_memory"] = [
            {
                "pid": p["pid"],
                "name": p["name"],
                "memory_pct": round(p.get("memory_percent", 0) or 0, 1),
                "cpu_pct": round(p.get("cpu_percent", 0) or 0, 1),
            }
            for p in by_memory
        ]

        # Top 10 by CPU
        by_cpu = sorted(
            proc_list,
            key=lambda x: x.get("cpu_percent", 0) or 0,
            reverse=True,
        )[:10]
        metrics["top_by_cpu"] = [
            {
                "pid": p["pid"],
                "name": p["name"],
                "cpu_pct": round(p.get("cpu_percent", 0) or 0, 1),
                "memory_pct": round(p.get("memory_percent", 0) or 0, 1),
            }
            for p in by_cpu
        ]

        # Agent's own resource usage
        try:
            own = psutil.Process(os.getpid())
            own_mem = own.memory_info()
            metrics["agent_pid"] = os.getpid()
            metrics["agent_memory_mb"] = round(own_mem.rss / (1024 ** 2), 1)
            metrics["agent_cpu_percent"] = own.cpu_percent(interval=0)
            metrics["agent_threads"] = own.num_threads()

            # Child processes
            children = own.children(recursive=True)
            metrics["agent_children"] = [
                {"pid": c.pid, "name": c.name()}
                for c in children[:20]
            ]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        # Process status distribution
        status_dist: Dict[str, int] = {}
        for p in proc_list:
            status = p.get("status", "unknown")
            status_dist[status] = status_dist.get(status, 0) + 1
        metrics["status_distribution"] = status_dist

        return metrics


# ══════════════════════════════════════════════════════════════════════
# Sensor 4: File System Watch
# ══════════════════════════════════════════════════════════════════════

class FileSystemWatch:
    """Disk partitions, mount points, and workspace file change detection."""

    def __init__(self, workspace_dir: Optional[str] = None):
        self._workspace = workspace_dir
        self._known_files: Dict[str, float] = {}  # path -> mtime

    def scan(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}

        # Disk partitions
        try:
            partitions = psutil.disk_partitions(all=False)
            metrics["partitions"] = [
                {
                    "device": p.device,
                    "mountpoint": p.mountpoint,
                    "fstype": p.fstype,
                    "opts": p.opts[:100],
                }
                for p in partitions[:10]
            ]

            # Per-partition usage
            partition_usage = []
            for p in partitions[:10]:
                try:
                    usage = psutil.disk_usage(p.mountpoint)
                    partition_usage.append({
                        "mountpoint": p.mountpoint,
                        "total_gb": round(usage.total / (1024 ** 3), 1),
                        "used_gb": round(usage.used / (1024 ** 3), 1),
                        "free_gb": round(usage.free / (1024 ** 3), 1),
                        "percent": usage.percent,
                    })
                except (PermissionError, OSError):
                    continue
            metrics["partition_usage"] = partition_usage
        except Exception:
            pass

        # Workspace file monitoring
        if self._workspace and os.path.isdir(self._workspace):
            metrics.update(self._scan_workspace())

        return metrics

    def _scan_workspace(self) -> Dict[str, Any]:
        """Scan workspace directory for recent file changes."""
        result: Dict[str, Any] = {
            "workspace_path": self._workspace,
            "recently_modified": [],
            "new_files": [],
            "total_files": 0,
        }

        now = time.time()
        current_files: Dict[str, float] = {}
        file_count = 0
        recent: List[Dict[str, Any]] = []

        try:
            workspace_path = Path(self._workspace)
            for item in workspace_path.rglob("*"):
                if item.is_file():
                    file_count += 1
                    if file_count > 5000:
                        break  # Safety cap

                    try:
                        mtime = item.stat().st_mtime
                        rel = str(item.relative_to(workspace_path))
                        current_files[rel] = mtime

                        # Recently modified (within last 5 minutes)
                        if now - mtime < 300:
                            recent.append({
                                "path": rel,
                                "modified_ago_s": round(now - mtime, 1),
                                "size_kb": round(item.stat().st_size / 1024, 1),
                            })
                    except (OSError, ValueError):
                        continue
        except Exception:
            pass

        # Detect new files since last scan
        if self._known_files:
            new = set(current_files.keys()) - set(self._known_files.keys())
            result["new_files"] = list(new)[:20]

        # Sort recent by modification time (newest first)
        recent.sort(key=lambda x: x["modified_ago_s"])
        result["recently_modified"] = recent[:15]
        result["total_files"] = file_count

        # Update known file cache
        self._known_files = current_files

        return result


# ══════════════════════════════════════════════════════════════════════
# Sensor 5: Peripheral Scanner
# ══════════════════════════════════════════════════════════════════════

class PeripheralScanner:
    """Enumerate connected peripherals (USB, display, audio)."""

    def scan(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}
        os_name = platform.system()

        if os_name == "Windows":
            metrics.update(self._scan_windows())
        elif os_name == "Linux":
            metrics.update(self._scan_linux())
        elif os_name == "Darwin":
            metrics.update(self._scan_darwin())
        else:
            metrics["note"] = f"Peripheral scanning not supported on {os_name}"

        return metrics

    def _scan_windows(self) -> Dict[str, Any]:
        """Scan peripherals on Windows using PowerShell/WMI."""
        result: Dict[str, Any] = {}

        # USB Devices via PowerShell
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-PnpDevice -Class USB -Status OK 2>$null | "
                "Select-Object -First 15 FriendlyName,Status | "
                "ConvertTo-Json"
            ]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10,
                shell=False,  # nosec B603
            )
            if proc.returncode == 0 and proc.stdout.strip():
                import json
                try:
                    devices = json.loads(proc.stdout)
                    if isinstance(devices, dict):
                        devices = [devices]
                    result["usb_devices"] = [
                        d.get("FriendlyName", "Unknown") for d in devices
                        if d.get("FriendlyName")
                    ]
                except (json.JSONDecodeError, TypeError):
                    result["usb_devices"] = []
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            result["usb_devices"] = []

        # Display adapters
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "Get-CimInstance Win32_VideoController 2>$null | "
                "Select-Object -First 5 Name,DriverVersion,CurrentHorizontalResolution,"
                "CurrentVerticalResolution | ConvertTo-Json"
            ]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10,
                shell=False,  # nosec B603
            )
            if proc.returncode == 0 and proc.stdout.strip():
                import json
                try:
                    displays = json.loads(proc.stdout)
                    if isinstance(displays, dict):
                        displays = [displays]
                    result["displays"] = [
                        {
                            "name": d.get("Name", "Unknown"),
                            "driver": d.get("DriverVersion", ""),
                            "resolution": (
                                f"{d.get('CurrentHorizontalResolution', '?')}"
                                f"x{d.get('CurrentVerticalResolution', '?')}"
                            ),
                        }
                        for d in displays
                    ]
                except (json.JSONDecodeError, TypeError):
                    result["displays"] = []
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            result["displays"] = []

        return result

    def _scan_linux(self) -> Dict[str, Any]:
        """Scan peripherals on Linux using /sys and lsusb."""
        result: Dict[str, Any] = {}

        # USB devices
        try:
            usb_path = Path("/sys/bus/usb/devices")
            if usb_path.exists():
                devices = []
                for dev in usb_path.iterdir():
                    product_file = dev / "product"
                    if product_file.exists():
                        try:
                            name = product_file.read_text().strip()
                            if name:
                                devices.append(name)
                        except (OSError, PermissionError):
                            continue
                result["usb_devices"] = devices[:20]
        except Exception:
            result["usb_devices"] = []

        # Display info via xrandr
        try:
            proc = subprocess.run(
                ["xrandr", "--query"],
                capture_output=True, text=True, timeout=5,
                shell=False,
            )
            if proc.returncode == 0:
                displays = []
                for line in proc.stdout.split("\n"):
                    if " connected" in line:
                        displays.append(line.split(" connected")[0].strip())
                result["displays"] = displays[:5]
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            result["displays"] = []

        return result

    def _scan_darwin(self) -> Dict[str, Any]:
        """Scan peripherals on macOS."""
        result: Dict[str, Any] = {}

        try:
            proc = subprocess.run(
                ["system_profiler", "SPUSBDataType", "-detailLevel", "mini"],
                capture_output=True, text=True, timeout=10,
                shell=False,
            )
            if proc.returncode == 0:
                devices = []
                for line in proc.stdout.split("\n"):
                    stripped = line.strip()
                    if stripped and not stripped.startswith(("USB", "Location", "Serial",
                                                           "Product", "Vendor", "Speed",
                                                           "Manufacturer")):
                        if ":" in stripped and not stripped.endswith(":"):
                            continue
                        if stripped.endswith(":"):
                            devices.append(stripped.rstrip(":"))
                result["usb_devices"] = devices[:20]
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            result["usb_devices"] = []

        return result


# ══════════════════════════════════════════════════════════════════════
# Sensor 6: Environment Context
# ══════════════════════════════════════════════════════════════════════

class EnvironmentContext:
    """OS metadata, Python version, environment variables, locale."""

    def scan(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}

        # OS info
        uname = platform.uname()
        metrics["os_system"] = uname.system
        metrics["os_release"] = uname.release
        metrics["os_version"] = uname.version[:100]
        metrics["os_machine"] = uname.machine
        metrics["os_node"] = uname.node

        # Python runtime
        metrics["python_version"] = sys.version.split()[0]
        metrics["python_executable"] = sys.executable
        metrics["python_path_count"] = len(sys.path)

        # Working directory
        metrics["cwd"] = os.getcwd()

        # Key environment variables (filtered — no secrets)
        safe_env_keys = [
            "PATH", "HOME", "USER", "USERNAME", "SHELL", "TERM",
            "LANG", "LC_ALL", "TZ", "VIRTUAL_ENV", "CONDA_DEFAULT_ENV",
            "NODE_VERSION", "JAVA_HOME", "GOPATH", "RUST_LOG",
            "COMPUTERNAME", "PROCESSOR_ARCHITECTURE",
        ]
        env_snapshot = {}
        for key in safe_env_keys:
            val = os.environ.get(key)
            if val:
                # Truncate PATH-like values
                if "PATH" in key and len(val) > 200:
                    paths = val.split(os.pathsep)
                    env_snapshot[key] = f"{len(paths)} entries"
                else:
                    env_snapshot[key] = val[:200]
        metrics["environment_vars"] = env_snapshot

        # Locale / timezone
        try:
            import locale
            metrics["locale"] = locale.getdefaultlocale()[0] or "unknown"
        except Exception:
            metrics["locale"] = "unknown"

        try:
            metrics["timezone"] = time.strftime("%Z")
            metrics["utc_offset_hours"] = round(
                -time.timezone / 3600 if time.daylight == 0
                else -time.altzone / 3600, 1
            )
        except Exception:
            pass

        # Installed packages count
        try:
            import pkg_resources
            metrics["installed_packages"] = len(
                list(pkg_resources.working_set)
            )
        except Exception:
            pass

        return metrics


# ══════════════════════════════════════════════════════════════════════
# Sensor 7: Thermal Sentinel
# ══════════════════════════════════════════════════════════════════════

class ThermalSentinel:
    """CPU/GPU temperatures, fan speeds, and thermal throttle detection."""

    def scan(self) -> Dict[str, Any]:
        metrics: Dict[str, Any] = {}

        # Temperature sensors
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                temp_data = {}
                max_temp = 0.0
                for chip_name, entries in temps.items():
                    chip_temps = []
                    for entry in entries[:10]:
                        t = {
                            "label": entry.label or chip_name,
                            "current_c": entry.current,
                        }
                        if entry.high:
                            t["high_c"] = entry.high
                        if entry.critical:
                            t["critical_c"] = entry.critical
                        chip_temps.append(t)
                        max_temp = max(max_temp, entry.current)
                    temp_data[chip_name] = chip_temps
                metrics["sensors"] = temp_data
                metrics["max_temperature_c"] = round(max_temp, 1)
                metrics["thermal_state"] = (
                    "critical" if max_temp > 85
                    else "warning" if max_temp > 75
                    else "normal"
                )
            else:
                metrics["sensors"] = {}
                metrics["thermal_state"] = "unknown"
                metrics["note"] = "No temperature sensors available"
        except (AttributeError, OSError):
            metrics["sensors"] = {}
            metrics["thermal_state"] = "unsupported"

        # Fan speeds
        try:
            fans = psutil.sensors_fans()
            if fans:
                fan_data = {}
                for chip_name, entries in fans.items():
                    fan_data[chip_name] = [
                        {"label": e.label or chip_name, "rpm": e.current}
                        for e in entries[:10]
                    ]
                metrics["fans"] = fan_data
        except (AttributeError, OSError):
            pass

        # Windows: attempt WMI temperature read via PowerShell
        if platform.system() == "Windows" and not metrics.get("sensors"):
            metrics.update(self._windows_thermal())

        return metrics

    def _windows_thermal(self) -> Dict[str, Any]:
        """Attempt to read thermal data on Windows via CIM."""
        result: Dict[str, Any] = {}
        try:
            cmd = [
                "powershell", "-NoProfile", "-Command",
                "try {"
                "  $t = Get-CimInstance MSAcpi_ThermalZoneTemperature "
                "  -Namespace root/wmi 2>$null; "
                "  if ($t) { $t[0].CurrentTemperature } else { 'N/A' }"
                "} catch { 'N/A' }"
            ]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=8,
                shell=False,  # nosec B603
            )
            raw = proc.stdout.strip()
            if raw and raw != "N/A":
                # WMI returns temp in tenths of Kelvin
                try:
                    kelvin_tenth = float(raw)
                    celsius = round((kelvin_tenth / 10.0) - 273.15, 1)
                    if 0 < celsius < 120:
                        result["sensors"] = {
                            "ACPI": [{"label": "ThermalZone", "current_c": celsius}]
                        }
                        result["max_temperature_c"] = celsius
                        result["thermal_state"] = (
                            "critical" if celsius > 85
                            else "warning" if celsius > 75
                            else "normal"
                        )
                except (ValueError, TypeError):
                    pass
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            pass

        if "thermal_state" not in result:
            result["thermal_state"] = "unavailable"
            result["note"] = "Temperature sensors not accessible (may require admin)"

        return result


# ══════════════════════════════════════════════════════════════════════
# Anomaly Detector — Z-Score Against Rolling Baseline
# ══════════════════════════════════════════════════════════════════════

class AnomalyDetector:
    """
    Detects anomalies by comparing current metrics against a rolling
    baseline using z-score analysis.

    For each tracked metric, maintains a running mean and variance
    using Welford's online algorithm. Flags deviations exceeding
    the configured z-threshold.
    """

    # Metrics to track for anomaly detection
    TRACKED_METRICS = [
        ("system_vitals", "cpu_percent"),
        ("system_vitals", "ram_percent"),
        ("system_vitals", "disk_percent"),
        ("system_vitals", "swap_percent"),
        ("network", "total_connections"),
        ("network", "established_count"),
        ("processes", "total_processes"),
        ("thermal", "max_temperature_c"),
    ]

    def __init__(self, z_threshold: float = 2.5, min_samples: int = 5):
        self.z_threshold = z_threshold
        self.min_samples = min_samples

        # Welford's running stats: {metric_key: (count, mean, M2)}
        self._stats: Dict[str, Tuple[int, float, float]] = {}

    def update_and_detect(self, snapshot: EnvironmentSnapshot) -> List[Anomaly]:
        """
        Update baseline with new snapshot data and detect anomalies.

        Uses Welford's online algorithm for numerically stable
        running mean and variance computation.
        """
        anomalies = []

        for sensor_name, metric_name in self.TRACKED_METRICS:
            sensor_data = getattr(snapshot, sensor_name, {})
            if not isinstance(sensor_data, dict):
                continue

            value = sensor_data.get(metric_name)
            if value is None or not isinstance(value, (int, float)):
                continue
            if value < 0:
                continue  # Skip sentinel values like -1

            key = f"{sensor_name}.{metric_name}"

            # Welford's online algorithm
            if key not in self._stats:
                self._stats[key] = (1, float(value), 0.0)
                continue

            count, mean, m2 = self._stats[key]
            count += 1
            delta = value - mean
            mean += delta / count
            delta2 = value - mean
            m2 += delta * delta2

            self._stats[key] = (count, mean, m2)

            # Only detect after minimum samples
            if count < self.min_samples:
                continue

            variance = m2 / (count - 1) if count > 1 else 0.0
            std_dev = math.sqrt(max(variance, 1e-10))
            z_score = abs(value - mean) / std_dev

            if z_score > self.z_threshold:
                level = (
                    AnomalyLevel.CRITICAL if z_score > self.z_threshold * 1.5
                    else AnomalyLevel.WARNING
                )
                anomalies.append(Anomaly(
                    sensor=sensor_name,
                    metric=metric_name,
                    current_value=round(value, 2),
                    baseline_value=round(mean, 2),
                    z_score=round(z_score, 2),
                    level=level,
                    message=(
                        f"{metric_name} is {value:.1f} "
                        f"(baseline: {mean:.1f}, z={z_score:.1f})"
                    ),
                ))

        return anomalies

    def get_baselines(self) -> Dict[str, Dict[str, float]]:
        """Get current baseline statistics for all tracked metrics."""
        baselines = {}
        for key, (count, mean, m2) in self._stats.items():
            variance = m2 / (count - 1) if count > 1 else 0.0
            baselines[key] = {
                "mean": round(mean, 2),
                "std_dev": round(math.sqrt(max(variance, 0)), 2),
                "samples": count,
            }
        return baselines


# ══════════════════════════════════════════════════════════════════════
# Environment Observer — Main Engine
# ══════════════════════════════════════════════════════════════════════

class EnvironmentObserver:
    """
    Continuous environment perception engine with 7 sensor subsystems.

    Provides the agent with real-time awareness of its host environment:
    system resources, network state, running processes, filesystem changes,
    connected peripherals, OS context, and thermal conditions.

    Each sensor is fail-isolated — if one crashes, the rest continue.

    Usage:
        observer = EnvironmentObserver()
        snapshot = observer.observe()
        print(snapshot.summary())

        # Get LLM-injectable context
        context = observer.build_context_prompt()

        # Detect what changed since last observation
        delta = observer.get_change_delta()
    """

    def __init__(
        self,
        workspace_dir: Optional[str] = None,
        anomaly_z_threshold: float = 2.5,
        history_size: int = 100,
    ):
        # Initialize all 7 sensors
        self._sensors = {
            "system_vitals": SystemVitals(),
            "network": NetworkProbe(),
            "processes": ProcessRadar(),
            "filesystem": FileSystemWatch(workspace_dir=workspace_dir),
            "peripherals": PeripheralScanner(),
            "environment": EnvironmentContext(),
            "thermal": ThermalSentinel(),
        }

        # Anomaly detection
        self._anomaly_detector = AnomalyDetector(z_threshold=anomaly_z_threshold)

        # Snapshot history (bounded)
        self._history: Deque[EnvironmentSnapshot] = deque(maxlen=history_size)
        self._last_snapshot: Optional[EnvironmentSnapshot] = None

        # Stats
        self._total_observations = 0
        self._total_anomalies = 0

        logger.info(
            f"🔭 EnvironmentObserver initialized — "
            f"7 sensors, z_threshold={anomaly_z_threshold}, "
            f"history_size={history_size}"
        )

    def observe(self, fast_mode: bool = False) -> EnvironmentSnapshot:
        """
        Perform a full environment scan across all sensors.

        Args:
            fast_mode: If True, skip slow sensors (peripherals, filesystem)
                       for faster response times.

        Returns:
            EnvironmentSnapshot with data from all active sensors.
        """
        start = time.time()
        snapshot = EnvironmentSnapshot()
        skip_sensors = {"peripherals", "filesystem"} if fast_mode else set()

        # Scan each sensor with fail isolation
        for name, sensor in self._sensors.items():
            if name in skip_sensors:
                continue

            try:
                data = sensor.scan()
                setattr(snapshot, name, data)
            except Exception as e:
                snapshot.sensors_failed.append(name)
                logger.warning(f"Sensor '{name}' failed: {type(e).__name__}: {e}")

        # Anomaly detection
        anomalies = self._anomaly_detector.update_and_detect(snapshot)
        snapshot.anomalies = anomalies
        self._total_anomalies += len(anomalies)

        for anomaly in anomalies:
            logger.warning(
                f"🚨 Environment anomaly [{anomaly.level.value}]: "
                f"{anomaly.message}"
            )

        # Record
        snapshot.scan_duration_ms = (time.time() - start) * 1000
        self._history.append(snapshot)
        self._last_snapshot = snapshot
        self._total_observations += 1

        logger.info(
            f"🔭 Observation #{self._total_observations}: "
            f"{snapshot.sensor_count}/7 sensors, "
            f"{len(anomalies)} anomalies, "
            f"{snapshot.scan_duration_ms:.0f}ms"
        )

        return snapshot

    def get_last_snapshot(self) -> Optional[EnvironmentSnapshot]:
        """Get the most recent observation without scanning again."""
        return self._last_snapshot

    def get_change_delta(self) -> Optional[EnvironmentDelta]:
        """
        Compute what changed between the last two observations.

        Returns None if fewer than 2 observations have been made.
        """
        if len(self._history) < 2:
            return None

        prev = self._history[-2]
        curr = self._history[-1]
        delta = EnvironmentDelta()

        delta.time_elapsed_s = curr.timestamp - prev.timestamp

        # CPU/RAM changes
        delta.cpu_change = (
            curr.system_vitals.get("cpu_percent", 0)
            - prev.system_vitals.get("cpu_percent", 0)
        )
        delta.ram_change = (
            curr.system_vitals.get("ram_percent", 0)
            - prev.system_vitals.get("ram_percent", 0)
        )

        # Process changes
        curr_procs = {
            p["name"] for p in curr.processes.get("top_by_memory", [])
        }
        prev_procs = {
            p["name"] for p in prev.processes.get("top_by_memory", [])
        }
        delta.new_processes = list(curr_procs - prev_procs)
        delta.terminated_processes = list(prev_procs - curr_procs)

        # Connection changes
        curr_conns = curr.network.get("total_connections", 0)
        prev_conns = prev.network.get("total_connections", 0)
        if curr_conns >= 0 and prev_conns >= 0:
            diff = curr_conns - prev_conns
            delta.new_connections = max(0, diff)
            delta.closed_connections = max(0, -diff)

        # File changes
        delta.new_files = curr.filesystem.get("new_files", [])

        # Temperature change
        curr_temp = curr.thermal.get("max_temperature_c", 0)
        prev_temp = prev.thermal.get("max_temperature_c", 0)
        if curr_temp > 0 and prev_temp > 0:
            delta.temperature_change = curr_temp - prev_temp

        # Significance check
        delta.significant = (
            abs(delta.cpu_change) > 15
            or abs(delta.ram_change) > 10
            or len(delta.new_processes) > 3
            or len(delta.terminated_processes) > 3
            or abs(delta.temperature_change) > 5
            or len(delta.new_files) > 0
        )

        return delta

    def detect_anomalies(self) -> List[Anomaly]:
        """Get anomalies from the most recent observation."""
        if self._last_snapshot:
            return self._last_snapshot.anomalies
        return []

    def build_context_prompt(self, max_length: int = 800) -> str:
        """
        Generate an LLM-injectable context string summarizing the
        current environment state. Focuses on actionable information.
        """
        if not self._last_snapshot:
            return ""

        snap = self._last_snapshot
        parts = ["ENVIRONMENT AWARENESS:"]

        # System vitals summary
        sv = snap.system_vitals
        if sv:
            cpu = sv.get("cpu_percent", "?")
            ram = sv.get("ram_percent", "?")
            disk = sv.get("disk_percent", "?")
            uptime = sv.get("uptime_hours", "?")
            parts.append(
                f"  System: CPU {cpu}% | RAM {ram}% | "
                f"Disk {disk}% | Uptime {uptime}h"
            )

            # Battery warning
            batt = sv.get("battery_percent")
            if batt is not None and batt < 20 and not sv.get("battery_plugged"):
                parts.append(f"  ⚠ Battery LOW: {batt}% (not plugged in)")

        # Network status
        net = snap.network
        if net:
            conns = net.get("established_count", "?")
            reachable = net.get("internet_reachable", None)
            if reachable is False:
                parts.append("  ⚠ OFFLINE — No internet connectivity")
            else:
                dns = net.get("dns_latency_ms", "?")
                parts.append(f"  Network: {conns} connections | DNS {dns}ms")

        # Thermal warnings
        thermal = snap.thermal
        if thermal:
            state = thermal.get("thermal_state", "unknown")
            if state == "critical":
                temp = thermal.get("max_temperature_c", "?")
                parts.append(f"  🔥 THERMAL CRITICAL: {temp}°C — reduce workload!")
            elif state == "warning":
                temp = thermal.get("max_temperature_c", "?")
                parts.append(f"  ⚠ Thermal warning: {temp}°C")

        # Active anomalies
        if snap.anomalies:
            parts.append(f"  🚨 Active anomalies: {len(snap.anomalies)}")
            for a in snap.anomalies[:3]:
                parts.append(f"    - [{a.level.value}] {a.message}")

        # Recent delta
        delta = self.get_change_delta()
        if delta and delta.significant:
            parts.append(f"  Δ Changes: {delta.summary()}")

        # Agent resource usage
        proc = snap.processes
        if proc:
            agent_mem = proc.get("agent_memory_mb")
            if agent_mem:
                parts.append(f"  Agent: {agent_mem}MB RAM, "
                             f"{proc.get('agent_threads', '?')} threads")

        result = "\n".join(parts)
        return result[:max_length]

    def get_stats(self) -> Dict[str, Any]:
        """Get observer statistics."""
        return {
            "total_observations": self._total_observations,
            "total_anomalies": self._total_anomalies,
            "history_size": len(self._history),
            "baselines": self._anomaly_detector.get_baselines(),
            "last_scan_ms": (
                self._last_snapshot.scan_duration_ms
                if self._last_snapshot else 0
            ),
        }
