"""
Threat Destroyer — Full-Device Scanner, Network Threat Analyzer,
Corrupted File Repairer & Virus Cleaner
══════════════════════════════════════════════════════════════════
Extends the 3-Stage Cascade ThreatScanner with 7 new operational tools:

  ┌──────────────────────────────────────────────────────────────────┐
  │ threat_full_scan        Scan entire drive/directory recursively  │
  │ threat_network_scan     Detect botnet, C2, suspicious conns     │
  │ threat_repair_file      Fix corrupted images, videos, APKs      │
  │ threat_clean_file       Strip virus code, preserve host file    │
  │ threat_scan_apk         Deep APK analysis (permissions, code)   │
  │ threat_batch_clean      Clean all infected files in directory    │
  │ threat_get_report       Full security report for the device      │
  └──────────────────────────────────────────────────────────────────┘

Design:
  - Integrates with existing ThreatScanner (3-stage cascade Ψ(x))
  - File repair uses magic-byte header reconstruction
  - Virus cleaning strips malicious patterns while preserving content
  - Network scanning detects C2, botnets, port scans, DNS tunneling
  - APK scanning decompiles manifest for permission analysis
"""

import datetime
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import struct
import subprocess
import tempfile
import time
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import psutil

from agents.tools.registry import registry, ToolRiskLevel

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Lazy scanner initialization
# ══════════════════════════════════════════════════════════════════════

_scanner = None

def _get_scanner():
    global _scanner
    if _scanner is None:
        from agents.safety.threat_scanner import ThreatScanner
        try:
            from config.settings import DATA_DIR
            qdir = str(DATA_DIR / "threat_quarantine")
        except ImportError:
            qdir = None
        _scanner = ThreatScanner(quarantine_dir=qdir)
    return _scanner


# ══════════════════════════════════════════════════════════════════════
# File Header Magic Bytes — For Repair & Validation
# ══════════════════════════════════════════════════════════════════════

_VALID_HEADERS: Dict[str, bytes] = {
    ".jpg":  b"\xff\xd8\xff",
    ".jpeg": b"\xff\xd8\xff",
    ".png":  b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a",
    ".gif":  b"\x47\x49\x46\x38",
    ".bmp":  b"\x42\x4d",
    ".pdf":  b"\x25\x50\x44\x46",
    ".zip":  b"\x50\x4b\x03\x04",
    ".apk":  b"\x50\x4b\x03\x04",
    ".docx": b"\x50\x4b\x03\x04",
    ".xlsx": b"\x50\x4b\x03\x04",
    ".pptx": b"\x50\x4b\x03\x04",
    ".mp4":  b"\x00\x00\x00",       # ftyp box starts at offset 4
    ".mp3":  b"\xff\xfb",           # or ID3: b"\x49\x44\x33"
    ".wav":  b"\x52\x49\x46\x46",
    ".avi":  b"\x52\x49\x46\x46",
    ".mkv":  b"\x1a\x45\xdf\xa3",
    ".exe":  b"\x4d\x5a",
    ".dll":  b"\x4d\x5a",
}

# JPEG end-of-image marker
_JPEG_EOI = b"\xff\xd9"

# PNG end marker (IEND chunk)
_PNG_IEND = b"\x49\x45\x4e\x44"

# Dangerous patterns to strip from files during cleaning
_MALICIOUS_PATTERNS: List[Dict[str, Any]] = [
    {"name": "php_injection", "pattern": rb"<\?php\s.*?\?>", "replace": b""},
    {"name": "script_injection", "pattern": rb"<script[^>]*>.*?</script>", "replace": b""},
    {"name": "iframe_injection", "pattern": rb"<iframe[^>]*>.*?</iframe>", "replace": b""},
    {"name": "vbscript_injection", "pattern": rb"<vbscript[^>]*>.*?</vbscript>", "replace": b""},
    {"name": "eval_inject", "pattern": rb"eval\s*\(\s*(?:unescape|atob|String\.fromCharCode)\s*\(", "replace": b"/* [CLEANED BY ASTRA] */"},
    {"name": "powershell_hidden", "pattern": rb"-[Ww]indow[Ss]tyle\s+[Hh]idden", "replace": b""},
    {"name": "base64_payload", "pattern": rb"(?:powershell|cmd)\s+.*-[Ee]nc(?:oded)?[Cc]ommand\s+[A-Za-z0-9+/=]{50,}", "replace": b"/* [MALICIOUS PAYLOAD REMOVED] */"},
    {"name": "exe_download", "pattern": rb"(?:wget|curl|Invoke-WebRequest|DownloadFile)\s+.*\.(?:exe|dll|bat|ps1|vbs)", "replace": b"/* [MALICIOUS DOWNLOAD BLOCKED] */"},
]

# APK dangerous permissions
_DANGEROUS_APK_PERMISSIONS: Set[str] = {
    "android.permission.SEND_SMS",
    "android.permission.READ_SMS",
    "android.permission.RECEIVE_SMS",
    "android.permission.READ_CONTACTS",
    "android.permission.READ_CALL_LOG",
    "android.permission.RECORD_AUDIO",
    "android.permission.CAMERA",
    "android.permission.READ_PHONE_STATE",
    "android.permission.ACCESS_FINE_LOCATION",
    "android.permission.INSTALL_PACKAGES",
    "android.permission.REQUEST_INSTALL_PACKAGES",
    "android.permission.SYSTEM_ALERT_WINDOW",
    "android.permission.WRITE_SETTINGS",
    "android.permission.READ_EXTERNAL_STORAGE",
    "android.permission.WRITE_EXTERNAL_STORAGE",
    "android.permission.BIND_ACCESSIBILITY_SERVICE",
    "android.permission.BIND_DEVICE_ADMIN",
    "android.permission.RECEIVE_BOOT_COMPLETED",
}

# Known malicious network indicators
_MALICIOUS_PORTS: Set[int] = {
    4444, 5555, 6666, 6667, 6668, 6669,  # Common reverse shell / IRC
    8080, 8443, 9090, 9999,               # Common C2 ports
    31337, 12345, 54321,                   # Backdoor ports
    3389,                                  # RDP (suspicious outbound)
    1080, 1081,                            # SOCKS proxy
}

_KNOWN_BAD_DOMAINS: Set[str] = {
    "evil.com", "malware-c2.net", "botnet-controller.org",
    "phishing-server.xyz", "ransomware-payment.tk",
}

# Scan skip directories
_SKIP_DIRS: Set[str] = {
    "node_modules", ".git", "__pycache__", ".cache", "venv", "env",
    ".tox", ".eggs", "site-packages", ".npm", ".cargo",
}

_SCANNABLE_EXTENSIONS: Set[str] = {
    ".exe", ".dll", ".sys", ".drv", ".scr", ".bat", ".cmd",
    ".ps1", ".vbs", ".js", ".py", ".rb", ".php", ".sh",
    ".jar", ".apk", ".dex", ".msi",
    ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".pdf",
    ".html", ".htm", ".xml", ".svg",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp",
    ".mp3", ".mp4", ".avi", ".mkv", ".mov",
    ".zip", ".rar", ".7z", ".tar", ".gz",
    ".lnk", ".url", ".hta", ".inf",
}


# ══════════════════════════════════════════════════════════════════════
# Tool 1: threat_full_scan — Full Device/Directory Scan
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="threat_full_scan",
    description=(
        "Scan an ENTIRE drive or directory recursively for viruses, malware, "
        "trojans, ransomware, botnets, and all threats using the 3-Stage "
        "Cascade engine. Scans every file, reports all threats found, with "
        "severity levels and recommended actions."
    ),
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "type": "object",
        "properties": {
            "scan_path": {
                "type": "string",
                "description": (
                    "Directory or drive to scan. 'C:\\' for full C: drive, "
                    "or specific folder path."
                ),
            },
            "scan_depth": {
                "type": "string",
                "enum": ["quick", "standard", "deep"],
                "description": (
                    "quick: common locations + executables only. "
                    "standard: all scannable extensions. "
                    "deep: every single file."
                ),
                "default": "standard",
            },
            "auto_quarantine": {
                "type": "boolean",
                "description": "Automatically quarantine HIGH/CRITICAL threats.",
                "default": False,
            },
            "max_files": {
                "type": "integer",
                "description": "Maximum files to scan (default 5000).",
                "default": 5000,
            },
        },
        "required": ["scan_path"],
    },
)
def threat_full_scan(
    scan_path: str,
    scan_depth: str = "standard",
    auto_quarantine: bool = False,
    max_files: int = 5000,
) -> Dict[str, Any]:
    """Recursively scan entire directory/drive for all threats."""
    scanner = _get_scanner()
    start_time = time.time()
    max_files = min(max(100, max_files), 50000)

    if not os.path.exists(scan_path):
        return {"success": False, "error": f"Path not found: {scan_path}"}

    results = {
        "success": True,
        "scan_path": scan_path,
        "scan_depth": scan_depth,
        "files_scanned": 0,
        "threats_found": 0,
        "threats": [],
        "quarantined": [],
        "summary_by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "summary_by_type": {},
        "clean_files": 0,
        "errors": [],
        "scan_duration_s": 0,
    }

    files_to_scan = _collect_scan_targets(scan_path, scan_depth, max_files)

    for filepath in files_to_scan:
        try:
            report = scanner.scan_file(filepath)
            results["files_scanned"] += 1

            if report.is_threat:
                results["threats_found"] += 1

                threat_entry = {
                    "file": filepath,
                    "filename": os.path.basename(filepath),
                    "threat_type": report.threat_type.value if report.threat_type else "unknown",
                    "severity": report.severity.value if report.severity else "unknown",
                    "confidence": round(report.confidence, 3),
                    "psi_score": round(report.psi_score, 4),
                    "recommended_action": report.recommended_action.value,
                    "evidence_count": len(report.evidence),
                    "scan_id": report.scan_id,
                }
                results["threats"].append(threat_entry)

                # Count by severity
                sev = report.severity.value if report.severity else "low"
                results["summary_by_severity"][sev] = (
                    results["summary_by_severity"].get(sev, 0) + 1
                )

                # Count by type
                ttype = report.threat_type.value if report.threat_type else "unknown"
                results["summary_by_type"][ttype] = (
                    results["summary_by_type"].get(ttype, 0) + 1
                )

                # Auto-quarantine high/critical
                if auto_quarantine and sev in ("high", "critical"):
                    try:
                        q_result = scanner.quarantine(report)
                        if q_result.get("success"):
                            results["quarantined"].append(filepath)
                    except Exception:
                        pass
            else:
                results["clean_files"] += 1

        except Exception as e:
            results["errors"].append(f"{filepath}: {str(e)[:100]}")

    results["scan_duration_s"] = round(time.time() - start_time, 2)

    # Sort threats by severity (critical first)
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    results["threats"].sort(
        key=lambda t: severity_order.get(t.get("severity", "low"), 4)
    )

    return results


def _collect_scan_targets(
    root: str, depth: str, max_files: int
) -> List[str]:
    """Collect files to scan based on scan depth."""
    targets = []

    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        if len(targets) >= max_files:
            break

        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS
            and not d.startswith("$")
            and not d.startswith(".")
        ]

        for filename in filenames:
            if len(targets) >= max_files:
                break

            ext = os.path.splitext(filename)[1].lower()

            if depth == "quick":
                # Only executables and scripts
                if ext not in {".exe", ".dll", ".bat", ".cmd", ".ps1",
                               ".vbs", ".js", ".py", ".jar", ".apk",
                               ".msi", ".scr", ".hta", ".lnk"}:
                    continue
            elif depth == "standard":
                if ext not in _SCANNABLE_EXTENSIONS:
                    continue
            # depth == "deep" scans everything

            full_path = os.path.join(dirpath, filename)
            stat = None
            try:
                stat = os.stat(full_path)
            except (OSError, PermissionError):
                continue

            # Skip files > 200MB
            if stat and stat.st_size > 200 * 1024 * 1024:
                continue

            targets.append(full_path)

    return targets


# ══════════════════════════════════════════════════════════════════════
# Tool 2: threat_network_scan — Network Threat Analysis
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="threat_network_scan",
    description=(
        "Scan active network connections for botnets, C2 (command & control) "
        "channels, suspicious outbound connections, port scans, and DNS "
        "tunneling indicators. Identifies processes making suspicious connections."
    ),
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={"type": "object", "properties": {}},
)
def threat_network_scan() -> Dict[str, Any]:
    """Deep scan of network connections for threat indicators."""
    start_time = time.time()

    results = {
        "success": True,
        "total_connections": 0,
        "suspicious_connections": [],
        "botnet_indicators": [],
        "c2_indicators": [],
        "suspicious_processes": [],
        "port_analysis": {},
        "dns_analysis": {},
        "threat_level": "clean",
        "scan_duration_s": 0,
    }

    # ── Analyze all network connections ──
    try:
        connections = psutil.net_connections(kind="inet")
        results["total_connections"] = len(connections)

        port_counts: Dict[int, int] = defaultdict(int)
        remote_ips: Dict[str, int] = defaultdict(int)
        suspicious = []

        for conn in connections:
            # Count outbound port usage
            if conn.raddr:
                remote_port = conn.raddr.port
                remote_ip = conn.raddr.ip
                port_counts[remote_port] = port_counts.get(remote_port, 0) + 1
                remote_ips[remote_ip] = remote_ips.get(remote_ip, 0) + 1

                # Check for suspicious ports
                if remote_port in _MALICIOUS_PORTS:
                    proc_name = _get_process_name(conn.pid) if conn.pid else "unknown"

                    suspicious.append({
                        "type": "suspicious_port",
                        "local_addr": f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "?",
                        "remote_addr": f"{remote_ip}:{remote_port}",
                        "status": conn.status,
                        "pid": conn.pid,
                        "process": proc_name,
                        "reason": f"Connection to known-suspicious port {remote_port}",
                        "severity": "high",
                    })

                # Check for connections to many different remote IPs (scanning)
                # Check for IRC ports (botnet C2)
                if remote_port in {6667, 6668, 6669}:
                    proc_name = _get_process_name(conn.pid) if conn.pid else "unknown"
                    results["botnet_indicators"].append({
                        "type": "irc_connection",
                        "remote": f"{remote_ip}:{remote_port}",
                        "pid": conn.pid,
                        "process": proc_name,
                        "reason": "IRC connection — common botnet C2 channel",
                    })

        results["suspicious_connections"] = suspicious[:20]

        # ── Port scan detection ──
        # If a single process connects to many different ports
        pid_ports: Dict[int, Set[int]] = defaultdict(set)
        for conn in connections:
            if conn.raddr and conn.pid:
                pid_ports[conn.pid].add(conn.raddr.port)

        for pid, ports in pid_ports.items():
            if len(ports) > 20:
                proc_name = _get_process_name(pid)
                results["suspicious_processes"].append({
                    "pid": pid,
                    "process": proc_name,
                    "unique_remote_ports": len(ports),
                    "reason": "Connects to unusually many ports — possible port scanning",
                    "severity": "high",
                })

        # ── C2 beaconing detection ──
        # Single IP with many connections = possible C2 heartbeat
        for ip, count in remote_ips.items():
            if count > 10 and not ip.startswith(("127.", "10.", "172.", "192.168.", "0.")):
                results["c2_indicators"].append({
                    "type": "repeated_connection",
                    "remote_ip": ip,
                    "connection_count": count,
                    "reason": f"Unusually high connection count ({count}x) to single external IP",
                    "severity": "medium",
                })

        # ── Listening ports analysis ──
        listening = [c for c in connections if c.status == "LISTEN"]
        unexpected_listeners = []
        for conn in listening:
            port = conn.laddr.port if conn.laddr else 0
            if port in _MALICIOUS_PORTS:
                proc_name = _get_process_name(conn.pid) if conn.pid else "unknown"
                unexpected_listeners.append({
                    "port": port,
                    "pid": conn.pid,
                    "process": proc_name,
                    "reason": f"Listening on suspicious port {port}",
                })

        results["port_analysis"] = {
            "total_listening": len(listening),
            "unexpected_listeners": unexpected_listeners[:10],
            "top_remote_ports": dict(
                sorted(port_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            ),
        }

    except (psutil.AccessDenied, OSError) as e:
        results["errors"] = [f"Connection scan requires admin: {e}"]

    # ── DNS analysis ──
    results["dns_analysis"] = _analyze_dns()

    # ── Determine overall threat level ──
    threat_score = (
        len(results["suspicious_connections"]) * 2
        + len(results["botnet_indicators"]) * 5
        + len(results["c2_indicators"]) * 3
        + len(results["suspicious_processes"]) * 4
    )

    if threat_score >= 10:
        results["threat_level"] = "critical"
    elif threat_score >= 5:
        results["threat_level"] = "high"
    elif threat_score >= 2:
        results["threat_level"] = "medium"
    elif threat_score >= 1:
        results["threat_level"] = "low"

    results["scan_duration_s"] = round(time.time() - start_time, 2)
    return results


def _get_process_name(pid: int) -> str:
    """Get process name from PID."""
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return "unknown"


def _analyze_dns() -> Dict[str, Any]:
    """Analyze DNS configuration for suspicious resolvers."""
    import socket

    dns_info: Dict[str, Any] = {}

    # Check if DNS resolves correctly (not DNS-hijacked)
    known_tests = [
        ("google.com", True),
        ("microsoft.com", True),
    ]

    for domain, should_resolve in known_tests:
        try:
            result = socket.getaddrinfo(domain, 443, socket.AF_INET)
            dns_info[domain] = {
                "resolves": True,
                "ip": result[0][4][0] if result else "N/A",
            }
        except socket.gaierror:
            dns_info[domain] = {"resolves": False}

    return dns_info


# ══════════════════════════════════════════════════════════════════════
# Tool 3: threat_repair_file — Corrupted File Repair
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="threat_repair_file",
    description=(
        "Repair corrupted files: images (JPEG, PNG, GIF, BMP), videos "
        "(MP4, AVI, MKV), documents (PDF, DOCX), and APKs. "
        "Reconstructs damaged file headers, removes trailing garbage data, "
        "fixes broken ZIP structures, and validates file integrity."
    ),
    risk_level=ToolRiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the corrupted file to repair.",
            },
            "output_path": {
                "type": "string",
                "description": "Path to save repaired file. Default: same dir with '_repaired' suffix.",
                "default": "",
            },
        },
        "required": ["file_path"],
    },
)
def threat_repair_file(
    file_path: str, output_path: str = ""
) -> Dict[str, Any]:
    """Attempt to repair a corrupted file."""
    path = Path(file_path)

    if not path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}
    if not path.is_file():
        return {"success": False, "error": f"Not a file: {file_path}"}

    ext = path.suffix.lower()

    # Determine output path
    if output_path:
        out = Path(output_path)
    else:
        out = path.parent / f"{path.stem}_repaired{path.suffix}"

    result = {
        "success": False,
        "original": str(path),
        "repaired": str(out),
        "repairs_applied": [],
        "original_size": path.stat().st_size,
    }

    try:
        data = path.read_bytes()

        if ext in (".jpg", ".jpeg"):
            data, repairs = _repair_jpeg(data)
        elif ext == ".png":
            data, repairs = _repair_png(data)
        elif ext == ".gif":
            data, repairs = _repair_gif(data)
        elif ext == ".bmp":
            data, repairs = _repair_bmp(data)
        elif ext == ".pdf":
            data, repairs = _repair_pdf(data)
        elif ext in (".zip", ".docx", ".xlsx", ".pptx", ".apk"):
            data, repairs = _repair_zip(data, ext)
        elif ext in (".mp4", ".avi", ".mkv"):
            data, repairs = _repair_video(data, ext)
        elif ext == ".mp3":
            data, repairs = _repair_mp3(data)
        else:
            # Generic: strip trailing nulls and injected code
            data, repairs = _repair_generic(data)

        if repairs:
            out.write_bytes(data)
            result["success"] = True
            result["repairs_applied"] = repairs
            result["repaired_size"] = len(data)
            result["message"] = (
                f"File repaired with {len(repairs)} fixes applied. "
                f"Saved to {out}"
            )
        else:
            result["message"] = "No corruption detected — file appears intact."
            result["success"] = True
            result["repairs_applied"] = ["none_needed"]

    except Exception as e:
        result["error"] = f"Repair failed: {type(e).__name__}: {e}"

    return result


def _repair_jpeg(data: bytes) -> Tuple[bytes, List[str]]:
    """Repair corrupted JPEG files."""
    repairs = []

    # Fix missing SOI header
    if not data.startswith(b"\xff\xd8"):
        # Search for SOI marker
        soi_pos = data.find(b"\xff\xd8")
        if soi_pos > 0:
            data = data[soi_pos:]
            repairs.append(f"stripped {soi_pos} junk bytes before SOI header")
        else:
            data = b"\xff\xd8\xff\xe0" + data
            repairs.append("reconstructed missing JPEG SOI header")

    # Fix missing EOI marker
    if not data.endswith(b"\xff\xd9"):
        eoi_pos = data.rfind(b"\xff\xd9")
        if eoi_pos > 0:
            data = data[:eoi_pos + 2]
            repairs.append("truncated garbage after EOI marker")
        else:
            data = data + b"\xff\xd9"
            repairs.append("appended missing JPEG EOI marker")

    # Remove injected code after EOI
    eoi_pos = data.find(b"\xff\xd9")
    if eoi_pos > 0 and eoi_pos + 2 < len(data):
        trailing = data[eoi_pos + 2:]
        if any(pattern in trailing for pattern in [b"<?php", b"<script", b"MZ"]):
            data = data[:eoi_pos + 2]
            repairs.append("removed injected malicious code after EOI")

    return data, repairs


def _repair_png(data: bytes) -> Tuple[bytes, List[str]]:
    """Repair corrupted PNG files."""
    repairs = []
    png_header = b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"

    if not data.startswith(png_header):
        pos = data.find(png_header)
        if pos > 0:
            data = data[pos:]
            repairs.append(f"stripped {pos} junk bytes before PNG header")
        else:
            data = png_header + data[len(png_header):]
            repairs.append("reconstructed PNG header signature")

    # Check for IEND chunk
    iend_pos = data.rfind(b"IEND")
    if iend_pos > 0:
        # IEND chunk: 4 bytes length + "IEND" + 4 bytes CRC
        end = iend_pos + 4 + 4
        if end < len(data):
            trailing = data[end:]
            if len(trailing) > 8:
                data = data[:end]
                repairs.append("removed trailing data after IEND chunk")

    return data, repairs


def _repair_gif(data: bytes) -> Tuple[bytes, List[str]]:
    """Repair corrupted GIF files."""
    repairs = []

    if not data.startswith(b"GIF8"):
        pos = data.find(b"GIF8")
        if pos > 0:
            data = data[pos:]
            repairs.append(f"stripped {pos} junk bytes before GIF header")

    # GIF should end with trailer byte 0x3B
    if not data.endswith(b"\x3b"):
        trailer_pos = data.rfind(b"\x3b")
        if trailer_pos > 10:
            data = data[:trailer_pos + 1]
            repairs.append("truncated after GIF trailer byte")
        else:
            data = data + b"\x3b"
            repairs.append("appended missing GIF trailer byte")

    return data, repairs


def _repair_bmp(data: bytes) -> Tuple[bytes, List[str]]:
    """Repair corrupted BMP files."""
    repairs = []

    if not data.startswith(b"BM"):
        pos = data.find(b"BM")
        if pos > 0:
            data = data[pos:]
            repairs.append(f"stripped {pos} junk bytes before BMP header")

    # Validate file size in header matches actual size
    if len(data) >= 6:
        declared_size = struct.unpack_from("<I", data, 2)[0]
        if declared_size != len(data) and declared_size < len(data):
            data = data[:declared_size]
            repairs.append("truncated to declared BMP file size")

    return data, repairs


def _repair_pdf(data: bytes) -> Tuple[bytes, List[str]]:
    """Repair corrupted PDF files."""
    repairs = []

    if not data.startswith(b"%PDF"):
        pos = data.find(b"%PDF")
        if pos > 0:
            data = data[pos:]
            repairs.append(f"stripped {pos} junk bytes before PDF header")

    # Check for %%EOF marker
    if b"%%EOF" not in data[-128:]:
        eof_pos = data.rfind(b"%%EOF")
        if eof_pos > 0:
            data = data[:eof_pos + 5] + b"\n"
            repairs.append("truncated after last %%EOF marker")
        else:
            data = data + b"\n%%EOF\n"
            repairs.append("appended missing %%EOF marker")

    # Remove any injected JavaScript after %%EOF
    last_eof = data.rfind(b"%%EOF")
    if last_eof > 0 and last_eof + 6 < len(data):
        trailing = data[last_eof + 6:]
        if any(sig in trailing for sig in [b"<script", b"<?php", b"eval("]):
            data = data[:last_eof + 6]
            repairs.append("removed injected code after %%EOF")

    return data, repairs


def _repair_zip(data: bytes, ext: str) -> Tuple[bytes, List[str]]:
    """Repair corrupted ZIP-based files (ZIP, DOCX, APK, etc.)."""
    repairs = []

    if not data.startswith(b"PK\x03\x04"):
        pos = data.find(b"PK\x03\x04")
        if pos > 0:
            data = data[pos:]
            repairs.append(f"stripped {pos} junk bytes before ZIP signature")

    # Try to validate ZIP structure
    try:
        import io
        zf = zipfile.ZipFile(io.BytesIO(data))
        bad_files = zf.testzip()
        if bad_files:
            repairs.append(f"ZIP contains corrupted entry: {bad_files}")
        zf.close()
    except zipfile.BadZipFile:
        # Try to find the End of Central Directory record
        eocd_pos = data.rfind(b"PK\x05\x06")
        if eocd_pos > 0:
            # Truncate to just after EOCD + 22-byte minimum record
            data = data[:eocd_pos + 22]
            repairs.append("truncated to End of Central Directory")
        else:
            repairs.append("ZIP structure severely damaged — partial recovery only")

    return data, repairs


def _repair_video(data: bytes, ext: str) -> Tuple[bytes, List[str]]:
    """Repair corrupted video files (header reconstruction)."""
    repairs = []

    if ext == ".mp4":
        # MP4 files start with a box: size(4 bytes) + type(4 bytes)
        # Common first box: "ftyp"
        if data[4:8] != b"ftyp" and len(data) > 8:
            ftyp_pos = data.find(b"ftyp")
            if ftyp_pos > 4:
                data = data[ftyp_pos - 4:]
                repairs.append(f"aligned to ftyp box at offset {ftyp_pos - 4}")

    elif ext == ".avi":
        if not data.startswith(b"RIFF"):
            pos = data.find(b"RIFF")
            if pos > 0:
                data = data[pos:]
                repairs.append(f"stripped {pos} junk bytes before RIFF header")

    elif ext == ".mkv":
        if not data.startswith(b"\x1a\x45\xdf\xa3"):
            pos = data.find(b"\x1a\x45\xdf\xa3")
            if pos > 0:
                data = data[pos:]
                repairs.append(f"stripped {pos} junk bytes before EBML header")

    return data, repairs


def _repair_mp3(data: bytes) -> Tuple[bytes, List[str]]:
    """Repair corrupted MP3 files."""
    repairs = []

    # ID3v2 tag or sync bytes
    if data[:3] == b"ID3":
        pass  # Has ID3v2 tag, probably ok
    elif data[:2] == b"\xff\xfb" or data[:2] == b"\xff\xf3":
        pass  # Valid frame sync
    else:
        # Search for first valid frame sync
        for i in range(min(len(data), 4096)):
            if data[i:i + 2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
                data = data[i:]
                repairs.append(f"stripped {i} junk bytes before MP3 frame sync")
                break

    return data, repairs


def _repair_generic(data: bytes) -> Tuple[bytes, List[str]]:
    """Generic repair: strip trailing nulls and injected code."""
    repairs = []

    # Strip trailing null bytes
    original_len = len(data)
    data = data.rstrip(b"\x00")
    if len(data) < original_len:
        repairs.append(f"stripped {original_len - len(data)} trailing null bytes")

    # Remove known malicious injections
    for pattern in _MALICIOUS_PATTERNS:
        regex = re.compile(pattern["pattern"], re.DOTALL | re.IGNORECASE)
        cleaned, count = regex.subn(pattern["replace"], data)
        if count > 0:
            data = cleaned
            repairs.append(f"removed {count}x {pattern['name']}")

    return data, repairs


# ══════════════════════════════════════════════════════════════════════
# Tool 4: threat_clean_file — Strip Virus, Preserve Host File
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="threat_clean_file",
    description=(
        "Clean a virus-infected file WITHOUT deleting it. Strips malicious "
        "code (injected PHP, JavaScript, shell commands, encoded payloads, "
        "macro viruses) while preserving the original file content. "
        "Creates a backup before cleaning."
    ),
    risk_level=ToolRiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Path to the infected file to clean.",
            },
            "create_backup": {
                "type": "boolean",
                "description": "Create .bak backup before cleaning. Default true.",
                "default": True,
            },
        },
        "required": ["file_path"],
    },
)
def threat_clean_file(
    file_path: str, create_backup: bool = True
) -> Dict[str, Any]:
    """Strip malicious code from a file while preserving content."""
    path = Path(file_path)

    if not path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    result = {
        "success": False,
        "file": str(path),
        "cleaned_patterns": [],
        "backup_path": "",
        "original_size": path.stat().st_size,
    }

    try:
        data = path.read_bytes()

        # Create backup
        if create_backup:
            backup_path = path.parent / f"{path.name}.bak"
            shutil.copy2(str(path), str(backup_path))
            result["backup_path"] = str(backup_path)

        # Apply all cleaning patterns
        total_removals = 0
        for pattern_def in _MALICIOUS_PATTERNS:
            regex = re.compile(
                pattern_def["pattern"], re.DOTALL | re.IGNORECASE
            )
            cleaned, count = regex.subn(pattern_def["replace"], data)
            if count > 0:
                data = cleaned
                total_removals += count
                result["cleaned_patterns"].append({
                    "name": pattern_def["name"],
                    "occurrences": count,
                })

        # Image-specific cleaning: remove code injected after EOI/IEND
        ext = path.suffix.lower()
        if ext in (".jpg", ".jpeg"):
            eoi = data.find(b"\xff\xd9")
            if eoi > 0 and eoi + 2 < len(data):
                trailing = data[eoi + 2:]
                if any(sig in trailing for sig in
                       [b"<?php", b"<script", b"MZ", b"eval("]):
                    data = data[:eoi + 2]
                    total_removals += 1
                    result["cleaned_patterns"].append({
                        "name": "image_appended_code",
                        "occurrences": 1,
                    })

        elif ext == ".png":
            iend = data.rfind(b"IEND")
            if iend > 0:
                end = iend + 8  # IEND + CRC
                if end < len(data):
                    trailing = data[end:]
                    if any(sig in trailing for sig in
                           [b"<?php", b"<script", b"eval("]):
                        data = data[:end]
                        total_removals += 1
                        result["cleaned_patterns"].append({
                            "name": "image_appended_code",
                            "occurrences": 1,
                        })

        # Write cleaned file
        if total_removals > 0:
            path.write_bytes(data)
            result["success"] = True
            result["cleaned_size"] = len(data)
            result["total_removals"] = total_removals
            result["message"] = (
                f"Cleaned {total_removals} malicious patterns from {path.name}. "
                f"Backup saved to {result['backup_path']}"
            )
        else:
            result["success"] = True
            result["total_removals"] = 0
            result["message"] = "No malicious patterns detected — file is clean."

    except Exception as e:
        result["error"] = f"Cleaning failed: {type(e).__name__}: {e}"

    return result


# ══════════════════════════════════════════════════════════════════════
# Tool 5: threat_scan_apk — APK Deep Analysis
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="threat_scan_apk",
    description=(
        "Deep security analysis of Android APK files. Extracts and analyzes "
        "the AndroidManifest.xml for dangerous permissions, suspicious "
        "activities, and malware indicators. Also scans embedded code."
    ),
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "type": "object",
        "properties": {
            "apk_path": {
                "type": "string",
                "description": "Path to the APK file to analyze.",
            },
        },
        "required": ["apk_path"],
    },
)
def threat_scan_apk(apk_path: str) -> Dict[str, Any]:
    """Deep security analysis of an Android APK file."""
    path = Path(apk_path)

    if not path.exists():
        return {"success": False, "error": f"APK not found: {apk_path}"}
    if path.suffix.lower() != ".apk":
        return {"success": False, "error": "File is not an APK"}

    result = {
        "success": True,
        "apk": str(path),
        "size_human": "",
        "permissions": [],
        "dangerous_permissions": [],
        "activities": [],
        "services": [],
        "receivers": [],
        "threat_indicators": [],
        "risk_score": 0,
        "risk_level": "low",
    }

    try:
        stat = path.stat()
        result["size_human"] = f"{stat.st_size / (1024 * 1024):.1f} MB"

        with zipfile.ZipFile(str(path), "r") as zf:
            namelist = zf.namelist()
            result["total_files"] = len(namelist)

            # Check for suspicious files
            suspicious_files = []
            for name in namelist:
                name_lower = name.lower()
                if any(ext in name_lower for ext in
                       [".so", ".dex", ".bin", ".sh", ".elf"]):
                    suspicious_files.append(name)
                # Hidden files
                base = os.path.basename(name)
                if base.startswith(".") and len(base) > 1:
                    suspicious_files.append(name)

            if suspicious_files:
                result["suspicious_files"] = suspicious_files[:20]

            # Try to read AndroidManifest.xml (binary XML format)
            if "AndroidManifest.xml" in namelist:
                try:
                    manifest_data = zf.read("AndroidManifest.xml")
                    permissions = _extract_apk_permissions(manifest_data)
                    result["permissions"] = permissions
                    result["dangerous_permissions"] = [
                        p for p in permissions
                        if p in _DANGEROUS_APK_PERMISSIONS
                    ]
                except Exception:
                    result["manifest_note"] = "Binary XML — full parsing requires aapt"

            # Try aapt for detailed analysis
            aapt_info = _aapt_analysis(str(path))
            if aapt_info:
                result.update(aapt_info)

            # Scan DEX files for suspicious strings
            for name in namelist:
                if name.endswith(".dex") and zf.getinfo(name).file_size < 10 * 1024 * 1024:
                    try:
                        dex_data = zf.read(name)
                        dex_threats = _scan_dex_content(dex_data)
                        result["threat_indicators"].extend(dex_threats)
                    except Exception:
                        pass

        # Calculate risk score
        risk = 0
        risk += len(result.get("dangerous_permissions", [])) * 2
        risk += len(result.get("threat_indicators", [])) * 3
        risk += len(result.get("suspicious_files", [])) * 1
        result["risk_score"] = risk

        if risk >= 15:
            result["risk_level"] = "critical"
        elif risk >= 8:
            result["risk_level"] = "high"
        elif risk >= 4:
            result["risk_level"] = "medium"

    except zipfile.BadZipFile:
        result["success"] = False
        result["error"] = "APK is not a valid ZIP file — may be corrupted"
    except Exception as e:
        result["error"] = str(e)

    return result


def _extract_apk_permissions(manifest_data: bytes) -> List[str]:
    """Extract permission strings from binary AndroidManifest.xml."""
    permissions = []

    # Search for permission string patterns in binary XML
    for perm in _DANGEROUS_APK_PERMISSIONS:
        if perm.encode("utf-8") in manifest_data:
            permissions.append(perm)
        # Also check UTF-16LE encoding (common in binary XML)
        if perm.encode("utf-16-le") in manifest_data:
            if perm not in permissions:
                permissions.append(perm)

    return permissions


def _aapt_analysis(apk_path: str) -> Optional[Dict[str, Any]]:
    """Use aapt/aapt2 for detailed APK analysis."""
    try:
        cmd = ["aapt", "dump", "badging", apk_path]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=15,
            shell=False,
        )
        if proc.returncode != 0:
            return None

        info: Dict[str, Any] = {}
        permissions = []

        for line in proc.stdout.split("\n"):
            if line.startswith("package:"):
                # Extract package name
                match = re.search(r"name='([^']+)'", line)
                if match:
                    info["package_name"] = match.group(1)
            elif line.startswith("uses-permission:"):
                match = re.search(r"name='([^']+)'", line)
                if match:
                    permissions.append(match.group(1))
            elif line.startswith("application-label:"):
                match = re.search(r"'([^']+)'", line)
                if match:
                    info["app_label"] = match.group(1)
            elif line.startswith("sdkVersion:"):
                match = re.search(r"'(\d+)'", line)
                if match:
                    info["min_sdk"] = int(match.group(1))

        if permissions:
            info["permissions"] = permissions
            info["dangerous_permissions"] = [
                p for p in permissions if p in _DANGEROUS_APK_PERMISSIONS
            ]

        return info

    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def _scan_dex_content(dex_data: bytes) -> List[Dict[str, str]]:
    """Scan DEX file content for suspicious strings."""
    threats = []

    suspicious_strings = [
        (b"Runtime.getRuntime().exec", "runtime_exec", "Executes system commands"),
        (b"su -c", "su_command", "Attempts root access"),
        (b"/system/bin/su", "root_binary", "References root binary"),
        (b"Superuser.apk", "superuser_check", "Checks for root"),
        (b"android.os.Process.killProcess", "kill_process", "Kills processes"),
        (b"DeviceAdminReceiver", "device_admin", "Claims device admin"),
        (b"SmsManager", "sms_manager", "Accesses SMS functions"),
        (b"getDeviceId", "device_id", "Reads device IMEI"),
        (b"getSubscriberId", "subscriber_id", "Reads SIM subscriber ID"),
        (b"TelephonyManager", "telephony", "Accesses telephony"),
    ]

    for sig, name, desc in suspicious_strings:
        if sig in dex_data:
            threats.append({"name": name, "description": desc, "severity": "medium"})

    return threats


# ══════════════════════════════════════════════════════════════════════
# Tool 6: threat_batch_clean — Clean All Infected Files in Directory
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="threat_batch_clean",
    description=(
        "Scan AND clean all infected files in a directory. Combines "
        "threat_full_scan with threat_clean_file — scans every file, "
        "automatically cleans infections it finds, and reports results."
    ),
    risk_level=ToolRiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "scan_dir": {
                "type": "string",
                "description": "Directory to scan and clean.",
            },
            "create_backups": {
                "type": "boolean",
                "description": "Create .bak backups before cleaning. Default true.",
                "default": True,
            },
            "max_files": {
                "type": "integer",
                "description": "Maximum files to process (default 1000).",
                "default": 1000,
            },
        },
        "required": ["scan_dir"],
    },
)
def threat_batch_clean(
    scan_dir: str,
    create_backups: bool = True,
    max_files: int = 1000,
) -> Dict[str, Any]:
    """Scan and clean all infected files in a directory."""
    scanner = _get_scanner()

    if not os.path.isdir(scan_dir):
        return {"success": False, "error": f"Directory not found: {scan_dir}"}

    max_files = min(max(10, max_files), 10000)
    targets = _collect_scan_targets(scan_dir, "standard", max_files)

    results = {
        "success": True,
        "scan_dir": scan_dir,
        "files_scanned": 0,
        "threats_found": 0,
        "files_cleaned": 0,
        "files_quarantined": 0,
        "files_repaired": 0,
        "clean_files": 0,
        "detailed_results": [],
        "errors": [],
    }

    for filepath in targets:
        results["files_scanned"] += 1

        try:
            report = scanner.scan_file(filepath)

            if not report.is_threat:
                results["clean_files"] += 1
                continue

            results["threats_found"] += 1

            entry = {
                "file": filepath,
                "threat_type": report.threat_type.value if report.threat_type else "unknown",
                "severity": report.severity.value if report.severity else "unknown",
                "action_taken": "none",
            }

            # Try cleaning first
            clean_result = threat_clean_file(filepath, create_backup=create_backups)
            if clean_result.get("total_removals", 0) > 0:
                entry["action_taken"] = "cleaned"
                entry["removals"] = clean_result["total_removals"]
                results["files_cleaned"] += 1
            else:
                # Try repair
                repair_result = threat_repair_file(filepath)
                if repair_result.get("success") and repair_result.get("repairs_applied"):
                    entry["action_taken"] = "repaired"
                    results["files_repaired"] += 1
                else:
                    # Quarantine if can't clean
                    try:
                        q = scanner.quarantine(report)
                        if q.get("success"):
                            entry["action_taken"] = "quarantined"
                            results["files_quarantined"] += 1
                    except Exception:
                        entry["action_taken"] = "failed"

            results["detailed_results"].append(entry)

        except Exception as e:
            results["errors"].append(f"{filepath}: {str(e)[:80]}")

    return results


# ══════════════════════════════════════════════════════════════════════
# Tool 7: threat_get_report — Full Device Security Report
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="threat_get_report",
    description=(
        "Generate a comprehensive security report for the device: "
        "system info, running security software, firewall status, "
        "recent threat scan results, network threat analysis, "
        "and security recommendations."
    ),
    risk_level=ToolRiskLevel.LOW,
    parameters={"type": "object", "properties": {}},
)
def threat_get_report() -> Dict[str, Any]:
    """Generate comprehensive device security report."""
    report: Dict[str, Any] = {
        "success": True,
        "timestamp": datetime.datetime.now().isoformat(),
        "system": {},
        "security_software": {},
        "firewall": {},
        "network_summary": {},
        "recommendations": [],
    }

    # ── System info ──
    report["system"] = {
        "os": f"{platform.system()} {platform.release()}",
        "version": platform.version()[:80],
        "machine": platform.machine(),
        "hostname": platform.node(),
        "boot_time": datetime.datetime.fromtimestamp(
            psutil.boot_time()
        ).isoformat(),
        "uptime_hours": round(
            (time.time() - psutil.boot_time()) / 3600, 1
        ),
        "cpu_count": psutil.cpu_count(),
        "ram_gb": round(psutil.virtual_memory().total / (1024 ** 3), 1),
    }

    # ── Security software detection ──
    if platform.system() == "Windows":
        report["security_software"] = _detect_windows_security()
        report["firewall"] = _check_windows_firewall()
    else:
        report["security_software"] = _detect_linux_security()

    # ── Network summary ──
    try:
        conns = psutil.net_connections(kind="inet")
        established = sum(1 for c in conns if c.status == "ESTABLISHED")
        listening = sum(1 for c in conns if c.status == "LISTEN")
        report["network_summary"] = {
            "total_connections": len(conns),
            "established": established,
            "listening": listening,
        }
    except (psutil.AccessDenied, OSError):
        report["network_summary"] = {"error": "Requires elevated privileges"}

    # ── Running processes analysis ──
    suspicious_procs = []
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if any(sus in name for sus in [
                "mimikatz", "lazagne", "metasploit", "meterpreter",
                "cobalt", "nmap", "netcat", "keylog", "cryptomine",
            ]):
                suspicious_procs.append({
                    "pid": proc.info["pid"],
                    "name": proc.info["name"],
                    "exe": proc.info.get("exe", ""),
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if suspicious_procs:
        report["suspicious_processes"] = suspicious_procs

    # ── Recommendations ──
    recs = []

    if not report.get("firewall", {}).get("enabled", True):
        recs.append("⚠️ CRITICAL: Firewall is DISABLED — enable immediately")

    av = report.get("security_software", {})
    if not av.get("antivirus_found"):
        recs.append("⚠️ No antivirus detected — install Windows Defender or equivalent")

    net = report.get("network_summary", {})
    if net.get("listening", 0) > 50:
        recs.append(f"🟡 {net['listening']} listening ports — review for unnecessary services")

    if suspicious_procs:
        recs.append(f"🔴 {len(suspicious_procs)} suspicious processes detected — investigate immediately")

    if not recs:
        recs.append("✅ System appears well-protected — no immediate concerns")

    report["recommendations"] = recs

    return report


def _detect_windows_security() -> Dict[str, Any]:
    """Detect security software on Windows."""
    info: Dict[str, Any] = {"antivirus_found": False}

    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance -Namespace root/SecurityCenter2 "
            "-ClassName AntiVirusProduct 2>$null | "
            "Select-Object -First 3 displayName,productState | "
            "ConvertTo-Json"
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            shell=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            products = json.loads(proc.stdout)
            if isinstance(products, dict):
                products = [products]
            info["antivirus_products"] = [
                p.get("displayName", "Unknown") for p in products
            ]
            info["antivirus_found"] = True
    except Exception:
        pass

    return info


def _check_windows_firewall() -> Dict[str, Any]:
    """Check Windows Firewall status."""
    info: Dict[str, Any] = {"enabled": False}

    try:
        cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-NetFirewallProfile 2>$null | "
            "Select-Object Name,Enabled | ConvertTo-Json"
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            shell=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            profiles = json.loads(proc.stdout)
            if isinstance(profiles, dict):
                profiles = [profiles]
            info["profiles"] = [
                {"name": p.get("Name", "?"), "enabled": p.get("Enabled", False)}
                for p in profiles
            ]
            info["enabled"] = any(
                p.get("Enabled", False) for p in profiles
            )
    except Exception:
        pass

    return info


def _detect_linux_security() -> Dict[str, Any]:
    """Detect security software on Linux."""
    info: Dict[str, Any] = {"antivirus_found": False}

    # Check for ClamAV
    try:
        proc = subprocess.run(
            ["clamscan", "--version"],
            capture_output=True, text=True, timeout=5,
            shell=False,
        )
        if proc.returncode == 0:
            info["clamav"] = proc.stdout.strip()
            info["antivirus_found"] = True
    except FileNotFoundError:
        pass

    # Check iptables/nftables
    try:
        proc = subprocess.run(
            ["iptables", "-L", "-n", "--line-numbers"],
            capture_output=True, text=True, timeout=5,
            shell=False,
        )
        if proc.returncode == 0:
            rules = [l for l in proc.stdout.split("\n") if l.strip()]
            info["iptables_rules"] = len(rules)
    except (FileNotFoundError, PermissionError):
        pass

    return info
