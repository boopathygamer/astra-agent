"""
Cross-Platform Device Abstraction Layer
────────────────────────────────────────
Universal device support for ALL platforms: Android, iOS, Windows,
Linux, macOS, and IoT devices.

Architecture:
  ┌──────────────────────────────────────────────────┐
  │              PlatformManager (Singleton)          │
  │  Auto-detects local OS + manages remote devices  │
  ├──────────────────────────────────────────────────┤
  │ LocalPlatform   │ Runs on the host machine       │
  │ RemoteDevice    │ Connected via API (mobile/IoT) │
  ├──────────────────────────────────────────────────┤
  │ Platform Adapters:                               │
  │  WindowsAdapter │ LinuxAdapter │ DarwinAdapter   │
  │  AndroidAdapter │ IOSAdapter   │ IoTAdapter      │
  └──────────────────────────────────────────────────┘

Remote devices (Android, iOS, IoT) register via the /device/register
API and then the system can send commands to them via their callback URL.
"""

import logging
import platform
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Platform Types
# ──────────────────────────────────────────────

class PlatformType(Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    ANDROID = "android"
    IOS = "ios"
    IOT = "iot"
    UNKNOWN = "unknown"


class DeviceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    SLEEP = "sleep"


@dataclass
class DeviceInfo:
    """Information about a connected device."""
    device_id: str = ""
    device_name: str = ""
    platform: PlatformType = PlatformType.UNKNOWN
    os_version: str = ""
    architecture: str = ""  # arm64, x86_64, armv7, etc.
    capabilities: List[str] = field(default_factory=list)
    status: DeviceStatus = DeviceStatus.ONLINE
    callback_url: str = ""  # For remote command execution
    last_heartbeat: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    is_local: bool = False


@dataclass
class DeviceCommand:
    """A command to execute on a device."""
    command_id: str = ""
    device_id: str = ""
    action: str = ""  # get_info, get_battery, get_storage, etc.
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0


@dataclass
class CommandResult:
    """Result from executing a command on a device."""
    command_id: str = ""
    device_id: str = ""
    success: bool = True
    result: Any = None
    error: str = ""
    execution_ms: float = 0.0


# ──────────────────────────────────────────────
# Platform Adapters
# ──────────────────────────────────────────────

class BasePlatformAdapter:
    """Abstract base for all platform adapters."""
    platform_type: PlatformType = PlatformType.UNKNOWN
    supported_actions: List[str] = []

    def get_device_info(self) -> Dict[str, Any]:
        raise NotImplementedError

    def get_battery(self) -> Dict[str, Any]:
        return {"supported": False}

    def get_storage(self) -> Dict[str, Any]:
        raise NotImplementedError

    def get_network(self) -> Dict[str, Any]:
        raise NotImplementedError

    def get_performance(self) -> Dict[str, Any]:
        raise NotImplementedError

    def execute_action(self, action: str, params: Dict) -> Any:
        raise NotImplementedError


class WindowsAdapter(BasePlatformAdapter):
    """Windows platform adapter (7/10/11/Server)."""
    platform_type = PlatformType.WINDOWS
    supported_actions = [
        "get_info", "get_battery", "get_storage", "get_network",
        "get_performance", "list_processes", "sleep",
    ]

    def get_device_info(self) -> Dict[str, Any]:
        import psutil
        uname = platform.uname()
        return {
            "platform": "windows",
            "os": f"Windows {platform.version()}",
            "hostname": uname.node,
            "architecture": uname.machine,
            "processor": uname.processor,
            "python": platform.python_version(),
            "boot_time": psutil.boot_time(),
        }

    def get_battery(self) -> Dict[str, Any]:
        try:
            import psutil
            batt = psutil.sensors_battery()
            if batt:
                return {
                    "percent": batt.percent,
                    "plugged_in": batt.power_plugged,
                    "seconds_left": batt.secsleft if batt.secsleft > 0 else None,
                }
        except Exception:
            pass
        return {"supported": False}

    def get_storage(self) -> Dict[str, Any]:
        import psutil
        partitions = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                partitions.append({
                    "device": part.device,
                    "mountpoint": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(usage.total / (1024**3), 2),
                    "used_gb": round(usage.used / (1024**3), 2),
                    "free_gb": round(usage.free / (1024**3), 2),
                    "percent": usage.percent,
                })
            except (PermissionError, OSError):
                pass
        return {"partitions": partitions}

    def get_network(self) -> Dict[str, Any]:
        import psutil
        interfaces = {}
        for name, addrs in psutil.net_if_addrs().items():
            interfaces[name] = [
                {"address": a.address, "family": str(a.family)}
                for a in addrs[:3]
            ]
        counters = psutil.net_io_counters()
        return {
            "interfaces": interfaces,
            "bytes_sent": counters.bytes_sent,
            "bytes_recv": counters.bytes_recv,
        }

    def get_performance(self) -> Dict[str, Any]:
        import psutil
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "cpu_cores": psutil.cpu_count(logical=False),
            "cpu_threads": psutil.cpu_count(logical=True),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "ram_used_percent": psutil.virtual_memory().percent,
            "disk_read_bytes": psutil.disk_io_counters().read_bytes if psutil.disk_io_counters() else 0,
            "disk_write_bytes": psutil.disk_io_counters().write_bytes if psutil.disk_io_counters() else 0,
        }

    def execute_action(self, action: str, params: Dict) -> Any:
        handler = {
            "get_info": self.get_device_info,
            "get_battery": self.get_battery,
            "get_storage": self.get_storage,
            "get_network": self.get_network,
            "get_performance": self.get_performance,
        }.get(action)
        if handler:
            return handler()
        return {"error": f"Unsupported action: {action}"}


class LinuxAdapter(WindowsAdapter):
    """Linux platform adapter (Ubuntu, Debian, CentOS, Arch, etc.)."""
    platform_type = PlatformType.LINUX

    def get_device_info(self) -> Dict[str, Any]:
        info = super().get_device_info()
        info["platform"] = "linux"
        # Get distro info
        try:
            with open("/etc/os-release", "r") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        info["distro"] = line.split("=", 1)[1].strip().strip('"')
                        break
        except FileNotFoundError:
            info["distro"] = "Unknown Linux"
        return info


class DarwinAdapter(WindowsAdapter):
    """macOS platform adapter."""
    platform_type = PlatformType.MACOS

    def get_device_info(self) -> Dict[str, Any]:
        info = super().get_device_info()
        info["platform"] = "macos"
        info["os"] = f"macOS {platform.mac_ver()[0]}"
        return info


class AndroidAdapter(BasePlatformAdapter):
    """
    Android device adapter.
    Executes via callback URL to the Android app's local API.
    """
    platform_type = PlatformType.ANDROID
    supported_actions = [
        "get_info", "get_battery", "get_storage", "get_location",
        "get_contacts", "get_apps", "send_notification",
        "get_sensors", "take_screenshot", "get_clipboard",
    ]

    def __init__(self, callback_url: str = ""):
        self.callback_url = callback_url

    def execute_action(self, action: str, params: Dict) -> Any:
        """Send command to Android device via callback URL."""
        if not self.callback_url:
            return {"error": "No callback URL configured for this Android device"}

        if not self.callback_url.startswith(("http://", "https://")):
            return {"error": "Invalid callback URL scheme; only http/https allowed"}

        import json
        try:
            import urllib.request
            payload = json.dumps({
                "action": action,
                "params": params,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.callback_url}/agent/command",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:  # nosec B310
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": f"Android command failed: {type(e).__name__}: {e}"}

    def get_device_info(self) -> Dict[str, Any]:
        return self.execute_action("get_info", {})

    def get_battery(self) -> Dict[str, Any]:
        return self.execute_action("get_battery", {})

    def get_storage(self) -> Dict[str, Any]:
        return self.execute_action("get_storage", {})


class IOSAdapter(AndroidAdapter):
    """
    iOS device adapter.
    Same callback pattern as Android — communicates with the iOS app.
    """
    platform_type = PlatformType.IOS
    supported_actions = [
        "get_info", "get_battery", "get_storage",
        "get_health_data", "send_notification",
        "get_clipboard", "get_screen_time",
    ]


class IoTAdapter(BasePlatformAdapter):
    """
    IoT device adapter — supports lightweight protocols.
    Communicates via simple HTTP REST or MQTT-style callbacks.
    """
    platform_type = PlatformType.IOT
    supported_actions = [
        "get_info", "get_sensors", "set_state",
        "get_telemetry", "reboot", "update_firmware",
    ]

    def __init__(self, callback_url: str = "", device_type: str = "generic"):
        self.callback_url = callback_url
        self.device_type = device_type

    def execute_action(self, action: str, params: Dict) -> Any:
        """Send command to IoT device."""
        if not self.callback_url:
            return {"error": "No callback URL for this IoT device"}

        if not self.callback_url.startswith(("http://", "https://")):
            return {"error": "Invalid callback URL scheme; only http/https allowed"}

        import json
        try:
            import urllib.request
            payload = json.dumps({
                "action": action,
                "params": params,
                "device_type": self.device_type,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self.callback_url}/command",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"error": f"IoT command failed: {type(e).__name__}: {e}"}

    def get_device_info(self) -> Dict[str, Any]:
        return self.execute_action("get_info", {})


# ──────────────────────────────────────────────
# Platform Manager (Central Registry)
# ──────────────────────────────────────────────

class PlatformManager:
    """
    Central manager for all connected devices.
    
    - Auto-detects the local platform on startup
    - Maintains a registry of remote devices (Android, iOS, IoT)
    - Routes commands to the correct platform adapter
    - Provides a unified API for device operations
    """

    def __init__(self):
        self._devices: Dict[str, DeviceInfo] = {}
        self._adapters: Dict[str, BasePlatformAdapter] = {}
        self._heartbeat_timeout = 300  # 5 minutes

        # Auto-detect and register local platform
        self._register_local_platform()
        logger.info(
            f"🌐 PlatformManager initialized — local: {self._local_platform.value}"
        )

    @property
    def _local_platform(self) -> PlatformType:
        os_name = platform.system().lower()
        if os_name == "windows":
            return PlatformType.WINDOWS
        elif os_name == "linux":
            return PlatformType.LINUX
        elif os_name == "darwin":
            return PlatformType.MACOS
        return PlatformType.UNKNOWN

    def _register_local_platform(self):
        """Register the local machine as a device."""
        local_id = "local_host"
        adapter = self._create_local_adapter()

        device = DeviceInfo(
            device_id=local_id,
            device_name=platform.node(),
            platform=self._local_platform,
            os_version=platform.version(),
            architecture=platform.machine(),
            capabilities=adapter.supported_actions,
            status=DeviceStatus.ONLINE,
            is_local=True,
            last_heartbeat=time.time(),
        )

        self._devices[local_id] = device
        self._adapters[local_id] = adapter

    def _create_local_adapter(self) -> BasePlatformAdapter:
        """Create adapter for the local platform."""
        mapping = {
            PlatformType.WINDOWS: WindowsAdapter,
            PlatformType.LINUX: LinuxAdapter,
            PlatformType.MACOS: DarwinAdapter,
        }
        adapter_class = mapping.get(self._local_platform, WindowsAdapter)
        return adapter_class()

    # ──────────────────────────────────────
    # Device Registration (for remote devices)
    # ──────────────────────────────────────

    def register_device(
        self,
        device_name: str,
        platform_type: str,
        callback_url: str,
        os_version: str = "",
        architecture: str = "",
        capabilities: List[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> DeviceInfo:
        """
        Register a remote device (Android, iOS, IoT).
        Called when a mobile app or IoT device connects to the backend.
        """
        device_id = f"dev_{uuid.uuid4().hex[:8]}"

        # Map platform string to enum
        platform_map = {
            "android": PlatformType.ANDROID,
            "ios": PlatformType.IOS,
            "iot": PlatformType.IOT,
            "windows": PlatformType.WINDOWS,
            "linux": PlatformType.LINUX,
            "macos": PlatformType.MACOS,
        }
        plat = platform_map.get(platform_type.lower(), PlatformType.UNKNOWN)

        # Create appropriate adapter
        if plat == PlatformType.ANDROID:
            adapter = AndroidAdapter(callback_url)
        elif plat == PlatformType.IOS:
            adapter = IOSAdapter(callback_url)
        elif plat == PlatformType.IOT:
            device_type = (metadata or {}).get("device_type", "generic")
            adapter = IoTAdapter(callback_url, device_type)
        else:
            adapter = BasePlatformAdapter()

        device = DeviceInfo(
            device_id=device_id,
            device_name=device_name,
            platform=plat,
            os_version=os_version,
            architecture=architecture,
            capabilities=capabilities or adapter.supported_actions,
            status=DeviceStatus.ONLINE,
            callback_url=callback_url,
            last_heartbeat=time.time(),
            metadata=metadata or {},
            is_local=False,
        )

        self._devices[device_id] = device
        self._adapters[device_id] = adapter

        logger.info(
            f"📱 Device registered: {device_name} ({plat.value}) "
            f"id={device_id} callback={callback_url[:50]}"
        )

        return device

    def unregister_device(self, device_id: str) -> bool:
        """Remove a device from the registry."""
        if device_id in self._devices and not self._devices[device_id].is_local:
            del self._devices[device_id]
            self._adapters.pop(device_id, None)
            logger.info(f"📱 Device unregistered: {device_id}")
            return True
        return False

    def heartbeat(self, device_id: str) -> bool:
        """Update device heartbeat timestamp."""
        if device_id in self._devices:
            self._devices[device_id].last_heartbeat = time.time()
            self._devices[device_id].status = DeviceStatus.ONLINE
            return True
        return False

    # ──────────────────────────────────────
    # Command Execution
    # ──────────────────────────────────────

    def execute_command(
        self, device_id: str, action: str,
        parameters: Dict[str, Any] = None,
    ) -> CommandResult:
        """Execute a command on any registered device."""
        start = time.time()
        cmd_id = uuid.uuid4().hex[:8]

        if device_id not in self._devices:
            return CommandResult(
                command_id=cmd_id, device_id=device_id,
                success=False, error=f"Device not found: {device_id}"
            )

        device = self._devices[device_id]
        adapter = self._adapters.get(device_id)

        if not adapter:
            return CommandResult(
                command_id=cmd_id, device_id=device_id,
                success=False, error="No adapter for this device"
            )

        # Check if action is supported
        if action not in device.capabilities:
            return CommandResult(
                command_id=cmd_id, device_id=device_id,
                success=False,
                error=f"Action '{action}' not supported on {device.platform.value}"
            )

        try:
            result = adapter.execute_action(action, parameters or {})
            return CommandResult(
                command_id=cmd_id, device_id=device_id,
                success=True, result=result,
                execution_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            return CommandResult(
                command_id=cmd_id, device_id=device_id,
                success=False, error=str(e),
                execution_ms=(time.time() - start) * 1000,
            )

    def execute_on_all(
        self, action: str, parameters: Dict[str, Any] = None,
        platform_filter: PlatformType = None,
    ) -> List[CommandResult]:
        """Execute a command on all matching devices."""
        results = []
        for device_id, device in self._devices.items():
            if platform_filter and device.platform != platform_filter:
                continue
            if action in device.capabilities:
                result = self.execute_command(device_id, action, parameters)
                results.append(result)
        return results

    # ──────────────────────────────────────
    # Query
    # ──────────────────────────────────────

    def list_devices(self) -> List[Dict[str, Any]]:
        """List all registered devices."""
        self._cleanup_stale()
        return [
            {
                "device_id": d.device_id,
                "name": d.device_name,
                "platform": d.platform.value,
                "os_version": d.os_version,
                "architecture": d.architecture,
                "status": d.status.value,
                "capabilities": d.capabilities,
                "is_local": d.is_local,
                "last_heartbeat": d.last_heartbeat,
            }
            for d in self._devices.values()
        ]

    def get_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Get details of a specific device."""
        d = self._devices.get(device_id)
        if not d:
            return None
        return {
            "device_id": d.device_id,
            "name": d.device_name,
            "platform": d.platform.value,
            "os_version": d.os_version,
            "architecture": d.architecture,
            "status": d.status.value,
            "capabilities": d.capabilities,
            "is_local": d.is_local,
            "callback_url": d.callback_url if not d.is_local else "",
            "metadata": d.metadata,
        }

    def get_supported_platforms(self) -> List[Dict[str, Any]]:
        """List all supported platforms and their capabilities."""
        return [
            {
                "platform": PlatformType.WINDOWS.value,
                "description": "Windows 7/10/11/Server",
                "capabilities": WindowsAdapter.supported_actions,
            },
            {
                "platform": PlatformType.LINUX.value,
                "description": "Ubuntu, Debian, CentOS, Arch, etc.",
                "capabilities": LinuxAdapter.supported_actions,
            },
            {
                "platform": PlatformType.MACOS.value,
                "description": "macOS 10.x - 14.x",
                "capabilities": DarwinAdapter.supported_actions,
            },
            {
                "platform": PlatformType.ANDROID.value,
                "description": "Android 8+ (via companion app)",
                "capabilities": AndroidAdapter.supported_actions,
            },
            {
                "platform": PlatformType.IOS.value,
                "description": "iOS 14+ (via companion app)",
                "capabilities": IOSAdapter.supported_actions,
            },
            {
                "platform": PlatformType.IOT.value,
                "description": "IoT devices (ESP32, Raspberry Pi, sensors)",
                "capabilities": IoTAdapter.supported_actions,
            },
        ]

    def _cleanup_stale(self):
        """Mark stale devices as offline."""
        now = time.time()
        for d in self._devices.values():
            if not d.is_local and now - d.last_heartbeat > self._heartbeat_timeout:
                d.status = DeviceStatus.OFFLINE


# ──────────────────────────────────────────────
# Global Instance
# ──────────────────────────────────────────────

_platform_manager: Optional[PlatformManager] = None


def get_platform_manager() -> PlatformManager:
    """Get or create the global PlatformManager singleton."""
    global _platform_manager
    if _platform_manager is None:
        _platform_manager = PlatformManager()
    return _platform_manager
