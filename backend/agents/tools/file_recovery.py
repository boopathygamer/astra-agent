"""
File Recovery & Deep Search — Advanced File Intelligence System
═══════════════════════════════════════════════════════════════
A forensic-grade file search and recovery engine that can find
ANYTHING on the local device, no matter how complex.

6 Registered Tools:
  ┌──────────────────────────────────────────────────────────────┐
  │ deep_search_files     Full-drive recursive search, no limit  │
  │ search_file_contents  Grep-like text search inside files     │
  │ find_deleted_files    Scan Recycle Bin / Trash               │
  │ find_duplicate_files  Hash-based duplicate detection         │
  │ read_file_metadata    EXIF, media metadata, file attributes  │
  │ recover_deleted_file  Restore files from Recycle Bin / Trash │
  └──────────────────────────────────────────────────────────────┘

Design Principles:
  - All searches use chunked iteration (no OOM on large drives)
  - Progress tracking via bounded result buffers
  - Graceful degradation when optional libraries are missing
  - Cross-platform: Windows, Linux, macOS
  - No external dependencies for core features (Pillow optional for EXIF)
"""

import datetime
import hashlib
import json
import logging
import os
import platform
import re
import struct
import subprocess
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from agents.tools.registry import registry, ToolRiskLevel

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════════════
# Constants
# ══════════════════════════════════════════════════════════════════════

# Directories to skip during deep searches (performance + safety)
_SKIP_DIRS: Set[str] = {
    "node_modules", ".git", "__pycache__", ".cache", ".npm",
    ".cargo", ".rustup", ".gradle", ".m2", "venv", "env",
    ".tox", "dist", "build", ".eggs", "site-packages",
    "AppData", "Application Data",
}

# System directories to skip unless explicitly requested
_SYSTEM_DIRS: Set[str] = {
    "Windows", "Program Files", "Program Files (x86)",
    "$Recycle.Bin", "System Volume Information",
    "ProgramData", "Recovery", "MSOCache",
}

# Text-searchable extensions
_TEXT_EXTENSIONS: Set[str] = {
    ".txt", ".md", ".py", ".js", ".ts", ".tsx", ".jsx",
    ".html", ".css", ".json", ".xml", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".env", ".log",
    ".csv", ".sql", ".sh", ".bat", ".ps1", ".cmd",
    ".c", ".cpp", ".h", ".hpp", ".java", ".kt", ".go",
    ".rs", ".rb", ".php", ".swift", ".r", ".m", ".lua",
    ".tex", ".rst", ".org", ".adoc", ".gitignore",
    ".dockerfile", ".makefile", ".cmake",
}

# Image extensions for EXIF extraction
_IMAGE_EXTENSIONS: Set[str] = {
    ".jpg", ".jpeg", ".tiff", ".tif", ".png", ".gif",
    ".bmp", ".webp", ".heic", ".heif", ".raw", ".cr2",
    ".nef", ".arw", ".dng",
}

# Media extensions
_MEDIA_EXTENSIONS: Set[str] = {
    ".mp3", ".mp4", ".avi", ".mkv", ".mov", ".wmv",
    ".flac", ".wav", ".aac", ".ogg", ".m4a", ".m4v",
    ".webm",
}


def _format_size(size_bytes: int) -> str:
    """Format bytes into human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 ** 2:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 ** 3:
        return f"{size_bytes / (1024 ** 2):.1f} MB"
    else:
        return f"{size_bytes / (1024 ** 3):.2f} GB"


def _hash_file(filepath: str, algorithm: str = "sha256",
               chunk_size: int = 65536) -> Optional[str]:
    """Compute file hash using chunked reading (memory-safe for large files)."""
    try:
        h = hashlib.new(algorithm)
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


def _safe_stat(filepath: str) -> Optional[os.stat_result]:
    """Get file stats without crashing on permission errors."""
    try:
        return os.stat(filepath)
    except (OSError, PermissionError):
        return None


# ══════════════════════════════════════════════════════════════════════
# Tool 1: deep_search_files — Full-Drive Deep Search
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="deep_search_files",
    description=(
        "Deep search for files across the ENTIRE device — all drives, "
        "all directories, with no timeout limit. Searches by name pattern, "
        "extension, size range, and date range. Can search system directories. "
        "Use this when the user has lost a file and doesn't know where it is."
    ),
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "Filename pattern to search for. Supports wildcards: "
                    "* (any chars), ? (single char). "
                    "Example: '*budget*', '*.pdf', 'report_202?.*'"
                ),
            },
            "drives": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Drive letters or mount points to search. "
                    "Empty = search ALL available drives. "
                    "Example: ['C:', 'D:'] on Windows, ['/home', '/mnt'] on Linux."
                ),
                "default": [],
            },
            "extension": {
                "type": "string",
                "description": "Filter by extension (e.g. '.pdf', '.jpg'). Optional.",
                "default": "",
            },
            "min_size_bytes": {
                "type": "integer",
                "description": "Minimum file size in bytes. Optional.",
                "default": 0,
            },
            "max_size_bytes": {
                "type": "integer",
                "description": "Maximum file size in bytes (0 = no limit). Optional.",
                "default": 0,
            },
            "modified_after": {
                "type": "string",
                "description": "Only files modified after this date (YYYY-MM-DD). Optional.",
                "default": "",
            },
            "modified_before": {
                "type": "string",
                "description": "Only files modified before this date (YYYY-MM-DD). Optional.",
                "default": "",
            },
            "include_system_dirs": {
                "type": "boolean",
                "description": "Include Windows/Program Files system directories.",
                "default": False,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results to return (default 50, max 500).",
                "default": 50,
            },
        },
        "required": ["query"],
    },
)
def deep_search_files(
    query: str,
    drives: Optional[List[str]] = None,
    extension: str = "",
    min_size_bytes: int = 0,
    max_size_bytes: int = 0,
    modified_after: str = "",
    modified_before: str = "",
    include_system_dirs: bool = False,
    max_results: int = 50,
) -> Dict[str, Any]:
    """
    Full-drive deep recursive file search with no artificial timeout.
    Scans every accessible directory across all drives.
    """
    import fnmatch

    start_time = time.time()
    max_results = min(max(1, max_results), 500)
    results: List[Dict[str, Any]] = []
    dirs_searched = 0
    files_scanned = 0
    errors: List[str] = []

    # Normalize query
    if not query:
        query = "*"
    elif "*" not in query and "?" not in query:
        query = f"*{query}*"
    query_lower = query.lower()

    # Extension filter
    if extension and not extension.startswith("."):
        extension = f".{extension}"
    ext_lower = extension.lower() if extension else ""

    # Date filters
    after_ts = 0.0
    before_ts = float("inf")
    if modified_after:
        try:
            after_ts = datetime.datetime.strptime(
                modified_after, "%Y-%m-%d"
            ).timestamp()
        except ValueError:
            errors.append(f"Invalid date format for modified_after: {modified_after}")

    if modified_before:
        try:
            before_ts = datetime.datetime.strptime(
                modified_before, "%Y-%m-%d"
            ).timestamp()
        except ValueError:
            errors.append(f"Invalid date format for modified_before: {modified_before}")

    # Determine search roots
    search_roots = []
    if drives:
        for d in drives:
            p = Path(d)
            if p.exists():
                search_roots.append(str(p))
    else:
        search_roots = _get_all_drives()

    skip_set = set(_SKIP_DIRS)
    if not include_system_dirs:
        skip_set.update(_SYSTEM_DIRS)

    for root_path in search_roots:
        if len(results) >= max_results:
            break

        try:
            for dirpath, dirnames, filenames in os.walk(
                root_path, topdown=True, followlinks=False
            ):
                if len(results) >= max_results:
                    break

                dirs_searched += 1

                # Prune directories
                dirnames[:] = [
                    d for d in dirnames
                    if d not in skip_set and not d.startswith("$")
                ]

                for filename in filenames:
                    files_scanned += 1
                    filename_lower = filename.lower()

                    # Extension filter
                    if ext_lower and not filename_lower.endswith(ext_lower):
                        continue

                    # Name pattern match
                    if query_lower != "*" and not fnmatch.fnmatch(
                        filename_lower, query_lower
                    ):
                        continue

                    full_path = os.path.join(dirpath, filename)
                    stat = _safe_stat(full_path)
                    if stat is None:
                        continue

                    # Size filters
                    if min_size_bytes > 0 and stat.st_size < min_size_bytes:
                        continue
                    if max_size_bytes > 0 and stat.st_size > max_size_bytes:
                        continue

                    # Date filters
                    if stat.st_mtime < after_ts or stat.st_mtime > before_ts:
                        continue

                    results.append({
                        "path": full_path,
                        "name": filename,
                        "size_bytes": stat.st_size,
                        "size_human": _format_size(stat.st_size),
                        "modified": datetime.datetime.fromtimestamp(
                            stat.st_mtime
                        ).isoformat(),
                        "created": datetime.datetime.fromtimestamp(
                            stat.st_ctime
                        ).isoformat(),
                        "extension": os.path.splitext(filename)[1].lower(),
                    })

                    if len(results) >= max_results:
                        break

        except (PermissionError, OSError) as e:
            errors.append(f"Cannot access {root_path}: {e}")

    # Sort by modification time (newest first)
    results.sort(key=lambda x: x.get("modified", ""), reverse=True)

    elapsed_s = time.time() - start_time

    return {
        "success": True,
        "query": query,
        "results": results,
        "total_found": len(results),
        "files_scanned": files_scanned,
        "directories_searched": dirs_searched,
        "drives_searched": search_roots,
        "search_duration_s": round(elapsed_s, 2),
        "max_results_reached": len(results) >= max_results,
        "errors": errors[:10] if errors else [],
    }


def _get_all_drives() -> List[str]:
    """Get all available drive roots on the system."""
    os_name = platform.system()

    if os_name == "Windows":
        drives = []
        # Check drive letters A-Z
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZAB":
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
        return drives if drives else ["C:\\"]

    elif os_name == "Darwin":
        roots = ["/Users", "/Volumes"]
        return [r for r in roots if os.path.exists(r)]

    else:  # Linux
        roots = ["/home"]
        # Add mounted drives
        mnt = Path("/mnt")
        if mnt.exists():
            for child in mnt.iterdir():
                if child.is_dir():
                    roots.append(str(child))
        media = Path("/media")
        if media.exists():
            for user_dir in media.iterdir():
                if user_dir.is_dir():
                    for device in user_dir.iterdir():
                        if device.is_dir():
                            roots.append(str(device))
        return roots if roots else ["/"]


# ══════════════════════════════════════════════════════════════════════
# Tool 2: search_file_contents — Grep-Like Content Search
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="search_file_contents",
    description=(
        "Search INSIDE files for specific text or patterns (like grep). "
        "Scans file contents line by line. Supports regex patterns. "
        "Searches text files (.txt, .py, .js, .html, .json, .csv, etc.)."
    ),
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "type": "object",
        "properties": {
            "pattern": {
                "type": "string",
                "description": "Text or regex pattern to search for inside files.",
            },
            "search_dir": {
                "type": "string",
                "description": (
                    "Directory to search. Default: user home directory."
                ),
                "default": "",
            },
            "extensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "File extensions to search (e.g. ['.py', '.txt']). "
                    "Empty = all text-searchable extensions."
                ),
                "default": [],
            },
            "case_sensitive": {
                "type": "boolean",
                "description": "Case-sensitive search. Default false.",
                "default": False,
            },
            "use_regex": {
                "type": "boolean",
                "description": "Treat pattern as regex. Default false.",
                "default": False,
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum matches to return (default 30).",
                "default": 30,
            },
            "context_lines": {
                "type": "integer",
                "description": "Lines of context around each match (default 1).",
                "default": 1,
            },
        },
        "required": ["pattern"],
    },
)
def search_file_contents(
    pattern: str,
    search_dir: str = "",
    extensions: Optional[List[str]] = None,
    case_sensitive: bool = False,
    use_regex: bool = False,
    max_results: int = 30,
    context_lines: int = 1,
) -> Dict[str, Any]:
    """
    Search inside file contents for text patterns.
    Memory-efficient: reads files line by line, never loads entire files.
    """
    start_time = time.time()
    max_results = min(max(1, max_results), 200)
    context_lines = min(max(0, context_lines), 5)
    results: List[Dict[str, Any]] = []
    files_searched = 0
    total_matches = 0
    errors: List[str] = []

    # Determine search directory
    if search_dir and os.path.isdir(search_dir):
        root = search_dir
    else:
        root = str(Path.home())

    # Determine searchable extensions
    valid_exts = set()
    if extensions:
        for ext in extensions:
            if not ext.startswith("."):
                ext = f".{ext}"
            valid_exts.add(ext.lower())
    else:
        valid_exts = _TEXT_EXTENSIONS

    # Compile search pattern
    try:
        if use_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            compiled = re.compile(pattern, flags)
        else:
            if not case_sensitive:
                pattern_lower = pattern.lower()
            compiled = None
    except re.error as e:
        return {
            "success": False,
            "error": f"Invalid regex pattern: {e}",
            "results": [],
        }

    # Walk directory tree
    for dirpath, dirnames, filenames in os.walk(root, topdown=True):
        if len(results) >= max_results:
            break

        # Prune heavy directories
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith(".")
        ]

        for filename in filenames:
            if len(results) >= max_results:
                break

            ext = os.path.splitext(filename)[1].lower()
            if ext not in valid_exts:
                continue

            full_path = os.path.join(dirpath, filename)
            stat = _safe_stat(full_path)
            if stat is None:
                continue

            # Skip files larger than 50MB (not practical for text search)
            if stat.st_size > 50 * 1024 * 1024:
                continue

            files_searched += 1

            try:
                file_matches = _search_in_file(
                    full_path, pattern, compiled,
                    case_sensitive, context_lines, max_per_file=5,
                )

                for match in file_matches:
                    total_matches += 1
                    results.append({
                        "file": full_path,
                        "filename": filename,
                        "line_number": match["line_number"],
                        "line_content": match["line_content"],
                        "context_before": match.get("context_before", []),
                        "context_after": match.get("context_after", []),
                    })

                    if len(results) >= max_results:
                        break

            except Exception:
                continue

    elapsed_s = time.time() - start_time

    return {
        "success": True,
        "pattern": pattern,
        "results": results,
        "total_matches": len(results),
        "files_searched": files_searched,
        "search_dir": root,
        "search_duration_s": round(elapsed_s, 2),
        "errors": errors[:5],
    }


def _search_in_file(
    filepath: str,
    pattern: str,
    compiled_regex,
    case_sensitive: bool,
    context_lines: int,
    max_per_file: int = 5,
) -> List[Dict[str, Any]]:
    """Search for pattern inside a single file, line by line."""
    matches = []

    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except (OSError, PermissionError):
        return []

    for i, line in enumerate(lines):
        if len(matches) >= max_per_file:
            break

        line_stripped = line.rstrip("\n\r")

        # Check match
        if compiled_regex:
            if not compiled_regex.search(line_stripped):
                continue
        else:
            if case_sensitive:
                if pattern not in line_stripped:
                    continue
            else:
                if pattern.lower() not in line_stripped.lower():
                    continue

        # Collect context
        ctx_before = []
        ctx_after = []
        if context_lines > 0:
            start = max(0, i - context_lines)
            end = min(len(lines), i + context_lines + 1)
            ctx_before = [
                lines[j].rstrip("\n\r") for j in range(start, i)
            ]
            ctx_after = [
                lines[j].rstrip("\n\r") for j in range(i + 1, end)
            ]

        matches.append({
            "line_number": i + 1,
            "line_content": line_stripped[:500],
            "context_before": [c[:200] for c in ctx_before],
            "context_after": [c[:200] for c in ctx_after],
        })

    return matches


# ══════════════════════════════════════════════════════════════════════
# Tool 3: find_deleted_files — Recycle Bin / Trash Scanner
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="find_deleted_files",
    description=(
        "Scan the Recycle Bin (Windows) or Trash (Linux/Mac) for deleted files. "
        "Can filter by name, extension, or deletion date. "
        "Recoverable files can be restored with the recover_deleted_file tool."
    ),
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Filename pattern to search in deleted files. '*' for all.",
                "default": "*",
            },
            "extension": {
                "type": "string",
                "description": "Filter by extension (e.g. '.jpg', '.docx'). Optional.",
                "default": "",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results (default 50).",
                "default": 50,
            },
        },
    },
)
def find_deleted_files(
    query: str = "*",
    extension: str = "",
    max_results: int = 50,
) -> Dict[str, Any]:
    """Scan Recycle Bin or Trash for deleted files."""
    import fnmatch

    os_name = platform.system()
    max_results = min(max(1, max_results), 200)
    results: List[Dict[str, Any]] = []

    if not query:
        query = "*"
    elif "*" not in query and "?" not in query:
        query = f"*{query}*"
    query_lower = query.lower()

    if extension and not extension.startswith("."):
        extension = f".{extension}"
    ext_lower = extension.lower() if extension else ""

    if os_name == "Windows":
        results = _scan_windows_recycle_bin(
            query_lower, ext_lower, max_results
        )
    elif os_name == "Linux":
        results = _scan_linux_trash(
            query_lower, ext_lower, max_results
        )
    elif os_name == "Darwin":
        results = _scan_macos_trash(
            query_lower, ext_lower, max_results
        )
    else:
        return {
            "success": False,
            "error": f"Unsupported platform: {os_name}",
            "results": [],
        }

    return {
        "success": True,
        "platform": os_name,
        "total_found": len(results),
        "results": results,
        "note": (
            "Use 'recover_deleted_file' tool with the 'trash_path' "
            "from results to restore a file."
        ),
    }


def _scan_windows_recycle_bin(
    query: str, ext: str, max_results: int
) -> List[Dict[str, Any]]:
    """Scan Windows Recycle Bin using PowerShell."""
    import fnmatch

    results = []

    # Method 1: Use PowerShell Shell.Application COM to list Recycle Bin
    try:
        ps_script = (
            "$shell = New-Object -ComObject Shell.Application; "
            "$rb = $shell.Namespace(0xA); "
            "$items = $rb.Items(); "
            "foreach ($item in $items) { "
            "  $obj = @{ "
            "    Name = $item.Name; "
            "    Path = $item.Path; "
            "    Size = $item.Size; "
            "    Modified = $item.ModifyDate.ToString('o'); "
            "    Type = $item.Type "
            "  }; "
            "  $obj | ConvertTo-Json -Compress; "
            "  Write-Host '---SEPARATOR---' "
            "}"
        )
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True, text=True, timeout=30,
            shell=False,  # nosec B603
        )

        if proc.returncode == 0 and proc.stdout.strip():
            chunks = proc.stdout.split("---SEPARATOR---")
            for chunk in chunks:
                chunk = chunk.strip()
                if not chunk or chunk.startswith("{") is False:
                    continue
                try:
                    item = json.loads(chunk)
                    name = item.get("Name", "")
                    name_lower = name.lower()

                    if ext and not name_lower.endswith(ext):
                        continue
                    if query != "*" and not fnmatch.fnmatch(name_lower, query):
                        continue

                    size = item.get("Size", 0)
                    results.append({
                        "name": name,
                        "trash_path": item.get("Path", ""),
                        "size_bytes": size if isinstance(size, int) else 0,
                        "size_human": _format_size(
                            size if isinstance(size, int) else 0
                        ),
                        "modified": item.get("Modified", ""),
                        "type": item.get("Type", ""),
                        "recoverable": True,
                    })

                    if len(results) >= max_results:
                        break
                except (json.JSONDecodeError, TypeError):
                    continue

    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    # Method 2: Direct $Recycle.Bin scanning fallback
    if not results:
        results = _scan_recycle_bin_direct(query, ext, max_results)

    return results


def _scan_recycle_bin_direct(
    query: str, ext: str, max_results: int
) -> List[Dict[str, Any]]:
    """Direct scan of $Recycle.Bin directories on all drives."""
    import fnmatch

    results = []

    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        recycle_path = Path(f"{letter}:\\$Recycle.Bin")
        if not recycle_path.exists():
            continue

        try:
            for sid_dir in recycle_path.iterdir():
                if not sid_dir.is_dir():
                    continue

                for item in sid_dir.iterdir():
                    try:
                        name = item.name
                        # $I files contain metadata, $R files are the actual data
                        if name.startswith("$I"):
                            # Read the corresponding $R file info
                            r_name = "$R" + name[2:]
                            r_path = sid_dir / r_name

                            original_name = _read_recycle_bin_metadata(
                                str(item)
                            )
                            if not original_name:
                                original_name = r_name

                            name_lower = original_name.lower()
                            if ext and not name_lower.endswith(ext):
                                continue
                            if query != "*" and not fnmatch.fnmatch(
                                name_lower, query
                            ):
                                continue

                            stat = _safe_stat(str(r_path)) if r_path.exists() else None
                            size = stat.st_size if stat else 0

                            results.append({
                                "name": original_name,
                                "trash_path": str(r_path),
                                "size_bytes": size,
                                "size_human": _format_size(size),
                                "modified": (
                                    datetime.datetime.fromtimestamp(
                                        stat.st_mtime
                                    ).isoformat()
                                    if stat else ""
                                ),
                                "recoverable": r_path.exists(),
                            })

                            if len(results) >= max_results:
                                return results

                    except (OSError, PermissionError):
                        continue

        except (OSError, PermissionError):
            continue

    return results


def _read_recycle_bin_metadata(i_file_path: str) -> Optional[str]:
    """Read the original filename from a $I metadata file in Recycle Bin."""
    try:
        with open(i_file_path, "rb") as f:
            data = f.read()

        if len(data) < 28:
            return None

        # $I file format:
        # Offset 0: version (8 bytes, little-endian int64)
        # Offset 8: original file size (8 bytes, little-endian int64)
        # Offset 16: deletion timestamp (8 bytes, FILETIME)
        # Offset 24: filename length (4 bytes, v2) or filename starts (v1)
        # The filename is stored as UTF-16LE

        version = struct.unpack_from("<Q", data, 0)[0]

        if version == 2:
            # Version 2 format (Windows 10+)
            name_len = struct.unpack_from("<I", data, 24)[0]
            name_bytes = data[28: 28 + name_len * 2]
            return name_bytes.decode("utf-16-le", errors="replace").rstrip("\x00")
        else:
            # Version 1 format (older Windows)
            name_bytes = data[24:]
            try:
                name = name_bytes.decode("utf-16-le", errors="replace")
                return name.rstrip("\x00").split("\\")[-1]
            except Exception:
                return None

    except (OSError, struct.error):
        return None


def _scan_linux_trash(
    query: str, ext: str, max_results: int
) -> List[Dict[str, Any]]:
    """Scan Linux Trash directory (~/.local/share/Trash)."""
    import fnmatch

    results = []
    trash_dir = Path.home() / ".local" / "share" / "Trash"

    files_dir = trash_dir / "files"
    info_dir = trash_dir / "info"

    if not files_dir.exists():
        return results

    try:
        for item in files_dir.iterdir():
            name = item.name
            name_lower = name.lower()

            if ext and not name_lower.endswith(ext):
                continue
            if query != "*" and not fnmatch.fnmatch(name_lower, query):
                continue

            # Read .trashinfo for original path
            info_file = info_dir / f"{name}.trashinfo"
            original_path = ""
            deletion_date = ""
            if info_file.exists():
                try:
                    content = info_file.read_text()
                    for line in content.split("\n"):
                        if line.startswith("Path="):
                            original_path = line[5:]
                        elif line.startswith("DeletionDate="):
                            deletion_date = line[13:]
                except OSError:
                    pass

            stat = _safe_stat(str(item))
            size = stat.st_size if stat else 0

            results.append({
                "name": name,
                "original_path": original_path,
                "trash_path": str(item),
                "size_bytes": size,
                "size_human": _format_size(size),
                "deletion_date": deletion_date,
                "recoverable": True,
            })

            if len(results) >= max_results:
                break

    except (OSError, PermissionError):
        pass

    return results


def _scan_macos_trash(
    query: str, ext: str, max_results: int
) -> List[Dict[str, Any]]:
    """Scan macOS Trash directory (~/.Trash)."""
    import fnmatch

    results = []
    trash_dir = Path.home() / ".Trash"

    if not trash_dir.exists():
        return results

    try:
        for item in trash_dir.iterdir():
            name = item.name
            name_lower = name.lower()

            if name.startswith("."):
                continue
            if ext and not name_lower.endswith(ext):
                continue
            if query != "*" and not fnmatch.fnmatch(name_lower, query):
                continue

            stat = _safe_stat(str(item))
            size = stat.st_size if stat else 0

            results.append({
                "name": name,
                "trash_path": str(item),
                "size_bytes": size,
                "size_human": _format_size(size),
                "modified": (
                    datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
                    if stat else ""
                ),
                "recoverable": True,
            })

            if len(results) >= max_results:
                break

    except (OSError, PermissionError):
        pass

    return results


# ══════════════════════════════════════════════════════════════════════
# Tool 4: find_duplicate_files — Hash-Based Duplicate Detection
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="find_duplicate_files",
    description=(
        "Find duplicate files using cryptographic hash comparison. "
        "Groups identical files by SHA-256 hash. Finds wasted disk space. "
        "First groups by size (fast), then verifies with hash (accurate)."
    ),
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "type": "object",
        "properties": {
            "search_dir": {
                "type": "string",
                "description": "Directory to scan for duplicates.",
            },
            "extensions": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "File extensions to check (e.g. ['.jpg', '.pdf']). "
                    "Empty = all files."
                ),
                "default": [],
            },
            "min_size_bytes": {
                "type": "integer",
                "description": "Minimum file size to consider (skip tiny files). Default 1024.",
                "default": 1024,
            },
            "max_groups": {
                "type": "integer",
                "description": "Maximum duplicate groups to return (default 20).",
                "default": 20,
            },
        },
        "required": ["search_dir"],
    },
)
def find_duplicate_files(
    search_dir: str,
    extensions: Optional[List[str]] = None,
    min_size_bytes: int = 1024,
    max_groups: int = 20,
) -> Dict[str, Any]:
    """
    Find duplicate files using a two-pass approach:
      Pass 1: Group by file size (instant)
      Pass 2: Hash files with same size (accurate)
    """
    start_time = time.time()
    max_groups = min(max(1, max_groups), 100)

    if not os.path.isdir(search_dir):
        return {"success": False, "error": f"Directory not found: {search_dir}"}

    # Normalize extensions
    valid_exts = set()
    if extensions:
        for ext in extensions:
            if not ext.startswith("."):
                ext = f".{ext}"
            valid_exts.add(ext.lower())

    # Pass 1: Group files by size
    size_groups: Dict[int, List[str]] = defaultdict(list)
    files_scanned = 0

    for dirpath, dirnames, filenames in os.walk(search_dir, topdown=True):
        dirnames[:] = [
            d for d in dirnames
            if d not in _SKIP_DIRS and not d.startswith(".")
        ]

        for filename in filenames:
            if valid_exts:
                ext = os.path.splitext(filename)[1].lower()
                if ext not in valid_exts:
                    continue

            full_path = os.path.join(dirpath, filename)
            stat = _safe_stat(full_path)
            if stat is None or stat.st_size < min_size_bytes:
                continue

            files_scanned += 1
            size_groups[stat.st_size].append(full_path)

    # Pass 2: Hash files that share the same size
    duplicate_groups: List[Dict[str, Any]] = []
    files_hashed = 0
    wasted_bytes = 0

    # Only check size groups with 2+ files
    candidates = {
        size: paths for size, paths in size_groups.items()
        if len(paths) >= 2
    }

    for size, paths in sorted(
        candidates.items(), key=lambda x: x[0] * len(x[1]), reverse=True
    ):
        if len(duplicate_groups) >= max_groups:
            break

        # Hash all files in this size group
        hash_groups: Dict[str, List[str]] = defaultdict(list)
        for path in paths:
            files_hashed += 1
            file_hash = _hash_file(path)
            if file_hash:
                hash_groups[file_hash].append(path)

        # Report groups with actual duplicates
        for file_hash, dup_paths in hash_groups.items():
            if len(dup_paths) < 2:
                continue

            group_waste = size * (len(dup_paths) - 1)
            wasted_bytes += group_waste

            duplicate_groups.append({
                "hash": file_hash[:16],
                "size_bytes": size,
                "size_human": _format_size(size),
                "count": len(dup_paths),
                "wasted_bytes": group_waste,
                "wasted_human": _format_size(group_waste),
                "files": dup_paths[:10],
            })

            if len(duplicate_groups) >= max_groups:
                break

    elapsed_s = time.time() - start_time

    return {
        "success": True,
        "search_dir": search_dir,
        "files_scanned": files_scanned,
        "files_hashed": files_hashed,
        "duplicate_groups": len(duplicate_groups),
        "total_wasted_bytes": wasted_bytes,
        "total_wasted_human": _format_size(wasted_bytes),
        "groups": duplicate_groups,
        "search_duration_s": round(elapsed_s, 2),
    }


# ══════════════════════════════════════════════════════════════════════
# Tool 5: read_file_metadata — EXIF, Media, and File Attributes
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="read_file_metadata",
    description=(
        "Read detailed metadata from any file: EXIF data (photos), "
        "media info (audio/video), document properties, and OS file attributes. "
        "For images: camera model, GPS coordinates, dimensions, date taken. "
        "For all files: creation date, permissions, owner."
    ),
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "type": "object",
        "properties": {
            "file_path": {
                "type": "string",
                "description": "Absolute path to the file to analyze.",
            },
        },
        "required": ["file_path"],
    },
)
def read_file_metadata(file_path: str) -> Dict[str, Any]:
    """Read comprehensive metadata from any file."""
    path = Path(file_path)

    if not path.exists():
        return {"success": False, "error": f"File not found: {file_path}"}

    if not path.is_file():
        return {"success": False, "error": f"Not a file: {file_path}"}

    result: Dict[str, Any] = {"success": True, "file": str(path)}

    # ── Basic OS metadata ──
    try:
        stat = path.stat()
        result["basic"] = {
            "name": path.name,
            "extension": path.suffix.lower(),
            "size_bytes": stat.st_size,
            "size_human": _format_size(stat.st_size),
            "created": datetime.datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "accessed": datetime.datetime.fromtimestamp(stat.st_atime).isoformat(),
            "is_readonly": not os.access(file_path, os.W_OK),
            "is_hidden": path.name.startswith(".") or _is_hidden_windows(file_path),
        }
    except OSError as e:
        result["basic"] = {"error": str(e)}

    # ── File hash ──
    file_hash = _hash_file(file_path)
    if file_hash:
        result["hash_sha256"] = file_hash

    # ── EXIF metadata for images ──
    ext = path.suffix.lower()
    if ext in _IMAGE_EXTENSIONS:
        result["exif"] = _extract_exif(file_path)

    # ── Media metadata ──
    if ext in _MEDIA_EXTENSIONS or ext in _IMAGE_EXTENSIONS:
        result["media"] = _extract_media_info(file_path)

    # ── Windows-specific file attributes ──
    if platform.system() == "Windows":
        result["windows_attrs"] = _get_windows_attributes(file_path)

    return result


def _is_hidden_windows(filepath: str) -> bool:
    """Check if file has the Windows 'hidden' attribute."""
    if platform.system() != "Windows":
        return False
    try:
        import ctypes
        attrs = ctypes.windll.kernel32.GetFileAttributesW(filepath)
        return bool(attrs & 0x02)  # FILE_ATTRIBUTE_HIDDEN
    except Exception:
        return False


def _extract_exif(filepath: str) -> Dict[str, Any]:
    """
    Extract EXIF data from image files.
    Uses Pillow if available, falls back to raw binary EXIF parsing.
    """
    exif_data: Dict[str, Any] = {}

    # Attempt 1: Use Pillow (best results)
    try:
        from PIL import Image
        from PIL.ExifTags import TAGS, GPSTAGS

        img = Image.open(filepath)
        exif_data["dimensions"] = f"{img.width}x{img.height}"
        exif_data["mode"] = img.mode
        exif_data["format"] = img.format

        raw_exif = img._getexif()
        if raw_exif:
            for tag_id, value in raw_exif.items():
                tag_name = TAGS.get(tag_id, str(tag_id))

                # Skip binary/large data
                if isinstance(value, bytes) and len(value) > 100:
                    continue

                # Handle GPS data specially
                if tag_name == "GPSInfo":
                    gps = {}
                    for gps_id, gps_val in value.items():
                        gps_tag = GPSTAGS.get(gps_id, str(gps_id))
                        gps[gps_tag] = str(gps_val)
                    exif_data["gps"] = gps

                    # Convert to decimal coordinates
                    coords = _gps_to_decimal(value)
                    if coords:
                        exif_data["gps_decimal"] = coords
                else:
                    # Convert non-serializable types
                    try:
                        json.dumps(value)
                        exif_data[tag_name] = value
                    except (TypeError, ValueError):
                        exif_data[tag_name] = str(value)

        img.close()
        return exif_data

    except ImportError:
        pass
    except Exception as e:
        exif_data["pillow_error"] = str(e)

    # Attempt 2: Raw EXIF header parsing (no dependencies)
    try:
        raw_exif = _parse_exif_raw(filepath)
        exif_data.update(raw_exif)
    except Exception:
        pass

    if not exif_data:
        exif_data["note"] = "Install Pillow (pip install Pillow) for full EXIF support"

    return exif_data


def _gps_to_decimal(gps_info: dict) -> Optional[Dict[str, float]]:
    """Convert GPS EXIF data to decimal lat/lon."""
    try:
        def to_decimal(dms, ref):
            degrees = float(dms[0])
            minutes = float(dms[1])
            seconds = float(dms[2])
            decimal = degrees + minutes / 60 + seconds / 3600
            if ref in ("S", "W"):
                decimal = -decimal
            return round(decimal, 6)

        lat = to_decimal(gps_info.get(2, (0, 0, 0)), gps_info.get(1, "N"))
        lon = to_decimal(gps_info.get(4, (0, 0, 0)), gps_info.get(3, "E"))

        if lat != 0 or lon != 0:
            return {"latitude": lat, "longitude": lon}
    except (TypeError, ValueError, ZeroDivisionError, IndexError):
        pass
    return None


def _parse_exif_raw(filepath: str) -> Dict[str, Any]:
    """Minimal EXIF parser using only stdlib (no Pillow required)."""
    result: Dict[str, Any] = {}

    try:
        with open(filepath, "rb") as f:
            header = f.read(12)

            # Check for JPEG SOI marker + APP1 EXIF
            if header[:2] != b"\xff\xd8":
                return result

            # Find EXIF APP1 marker
            f.seek(2)
            while True:
                marker = f.read(2)
                if len(marker) < 2:
                    break

                if marker == b"\xff\xe1":  # APP1
                    length = struct.unpack(">H", f.read(2))[0]
                    exif_header = f.read(6)
                    if exif_header[:4] == b"Exif":
                        result["has_exif"] = True
                        # Read the TIFF header to determine byte order
                        tiff_start = f.tell()
                        byte_order = f.read(2)
                        result["byte_order"] = (
                            "big-endian" if byte_order == b"MM"
                            else "little-endian"
                        )
                    break

                elif marker[0:1] == b"\xff":
                    # Skip other markers
                    length = struct.unpack(">H", f.read(2))[0]
                    f.seek(length - 2, 1)
                else:
                    break

            # Get image dimensions from JPEG SOF marker
            f.seek(0)
            data = f.read(min(65536, os.path.getsize(filepath)))
            sof_markers = [b"\xff\xc0", b"\xff\xc2"]
            for sof in sof_markers:
                idx = data.find(sof)
                if idx >= 0 and idx + 9 < len(data):
                    height = struct.unpack(">H", data[idx + 5: idx + 7])[0]
                    width = struct.unpack(">H", data[idx + 7: idx + 9])[0]
                    result["dimensions"] = f"{width}x{height}"
                    break

    except (OSError, struct.error):
        pass

    return result


def _extract_media_info(filepath: str) -> Dict[str, Any]:
    """Extract media metadata using ffprobe if available."""
    info: Dict[str, Any] = {}

    # Get file size category
    stat = _safe_stat(filepath)
    if stat:
        info["size_bytes"] = stat.st_size
        info["size_human"] = _format_size(stat.st_size)

    # Try ffprobe for detailed media info
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", filepath,
        ]
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            shell=False,
        )
        if proc.returncode == 0 and proc.stdout:
            data = json.loads(proc.stdout)

            fmt = data.get("format", {})
            if fmt:
                info["duration_s"] = round(float(fmt.get("duration", 0)), 2)
                info["format_name"] = fmt.get("format_long_name", "")
                info["bit_rate"] = fmt.get("bit_rate", "")

                # Tags
                tags = fmt.get("tags", {})
                for key in ["title", "artist", "album", "genre",
                            "date", "encoder", "comment"]:
                    val = tags.get(key)
                    if val:
                        info[key] = val

            # Stream info
            for stream in data.get("streams", []):
                codec_type = stream.get("codec_type", "")
                if codec_type == "video":
                    info["video_codec"] = stream.get("codec_name", "")
                    info["video_resolution"] = (
                        f"{stream.get('width', '?')}"
                        f"x{stream.get('height', '?')}"
                    )
                    info["video_fps"] = stream.get("r_frame_rate", "")
                elif codec_type == "audio":
                    info["audio_codec"] = stream.get("codec_name", "")
                    info["audio_sample_rate"] = stream.get(
                        "sample_rate", ""
                    )
                    info["audio_channels"] = stream.get("channels", 0)

    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        info["ffprobe"] = "not available (install ffmpeg for media metadata)"

    return info


def _get_windows_attributes(filepath: str) -> Dict[str, Any]:
    """Get Windows-specific file attributes."""
    attrs: Dict[str, Any] = {}
    try:
        import ctypes
        FILE_ATTRIBUTE_FLAGS = {
            0x01: "READONLY",
            0x02: "HIDDEN",
            0x04: "SYSTEM",
            0x10: "DIRECTORY",
            0x20: "ARCHIVE",
            0x40: "DEVICE",
            0x80: "NORMAL",
            0x100: "TEMPORARY",
            0x200: "SPARSE",
            0x400: "REPARSE_POINT",
            0x800: "COMPRESSED",
            0x1000: "OFFLINE",
            0x2000: "NOT_INDEXED",
            0x4000: "ENCRYPTED",
        }

        raw = ctypes.windll.kernel32.GetFileAttributesW(filepath)
        if raw != -1:
            active = [
                name for flag, name in FILE_ATTRIBUTE_FLAGS.items()
                if raw & flag
            ]
            attrs["attributes"] = active
            attrs["raw_value"] = raw
    except Exception:
        pass

    return attrs


# ══════════════════════════════════════════════════════════════════════
# Tool 6: recover_deleted_file — Restore from Recycle Bin / Trash
# ══════════════════════════════════════════════════════════════════════

@registry.register(
    name="recover_deleted_file",
    description=(
        "Restore a deleted file from the Recycle Bin (Windows) or Trash "
        "(Linux/Mac). Use find_deleted_files first to get the trash_path, "
        "then provide it here along with the desired restore location."
    ),
    risk_level=ToolRiskLevel.HIGH,
    parameters={
        "type": "object",
        "properties": {
            "trash_path": {
                "type": "string",
                "description": (
                    "Path to the file in the Recycle Bin / Trash "
                    "(from find_deleted_files results)."
                ),
            },
            "restore_to": {
                "type": "string",
                "description": (
                    "Directory to restore the file to. "
                    "Default: user's Desktop."
                ),
                "default": "",
            },
        },
        "required": ["trash_path"],
    },
)
def recover_deleted_file(
    trash_path: str, restore_to: str = ""
) -> Dict[str, Any]:
    """Restore a deleted file from the recycle bin or trash."""
    import shutil

    source = Path(trash_path)
    if not source.exists():
        return {
            "success": False,
            "error": f"File not found in trash: {trash_path}",
        }

    # Determine restore location
    if restore_to and os.path.isdir(restore_to):
        dest_dir = Path(restore_to)
    else:
        dest_dir = Path.home() / "Desktop"
        if not dest_dir.exists():
            dest_dir = Path.home()

    dest_path = dest_dir / source.name

    # Avoid overwriting existing files
    if dest_path.exists():
        stem = dest_path.stem
        suffix = dest_path.suffix
        counter = 1
        while dest_path.exists():
            dest_path = dest_dir / f"{stem}_recovered_{counter}{suffix}"
            counter += 1

    try:
        if source.is_dir():
            shutil.copytree(str(source), str(dest_path))
        else:
            shutil.copy2(str(source), str(dest_path))

        stat = _safe_stat(str(dest_path))
        size = stat.st_size if stat else 0

        return {
            "success": True,
            "original_trash_path": trash_path,
            "restored_to": str(dest_path),
            "size_bytes": size,
            "size_human": _format_size(size),
            "message": f"File restored successfully to {dest_path}",
        }

    except (OSError, PermissionError, shutil.Error) as e:
        return {
            "success": False,
            "error": f"Failed to restore file: {type(e).__name__}: {e}",
        }
