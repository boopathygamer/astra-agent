"""
File Operations Tool — Read/write files with permission controls.
Hardened: case-insensitive path validation, symlink protection.
"""

import logging
from pathlib import Path

from agents.tools.registry import registry, RiskLevel
from config.settings import BASE_DIR

logger = logging.getLogger(__name__)

# Resolve once at module load for consistent comparison
_SAFE_BASE = BASE_DIR.resolve()


def _is_safe_path(path: Path) -> bool:
    """Check if a resolved path is within the project directory.

    Handles Windows case-insensitivity, symlinks, and junction points.
    Uses is_relative_to (Python 3.9+) which is case-aware on Windows.
    """
    resolved = path.resolve()
    try:
        # Python 3.9+ — handles case-insensitive Windows paths correctly
        return resolved.is_relative_to(_SAFE_BASE)
    except AttributeError:
        # Fallback for Python < 3.9
        try:
            resolved.relative_to(_SAFE_BASE)
            return True
        except ValueError:
            return False


@registry.register(
    name="read_file",
    description="Read the contents of a file. Only files within the project directory are accessible.",
    risk_level=RiskLevel.LOW,
    parameters={"file_path": "Path to the file to read", "max_lines": "Max lines to read (default 200)"},
)
def read_file(file_path: str, max_lines: int = 200) -> dict:
    """Read a file safely."""
    path = Path(file_path).resolve()

    # Security: only allow reading within project (case-insensitive on Windows)
    if not _is_safe_path(path):
        return {"success": False, "content": None, "error": "Access denied: path outside project"}

    # Block symlinks pointing outside project
    if path.is_symlink():
        real_target = path.resolve()
        if not _is_safe_path(real_target):
            return {"success": False, "content": None, "error": "Access denied: symlink target outside project"}

    if not path.exists():
        return {"success": False, "content": None, "error": f"File not found: {path.name}"}

    if not path.is_file():
        return {"success": False, "content": None, "error": f"Not a file: {path.name}"}

    try:
        content = path.read_text(encoding="utf-8")
        lines = content.split("\n")
        truncated = len(lines) > max_lines
        if truncated:
            lines = lines[:max_lines]
            content = "\n".join(lines)

        return {
            "success": True,
            "content": content,
            "lines": len(lines),
            "truncated": truncated,
        }
    except UnicodeDecodeError:
        return {"success": False, "content": None, "error": "File is not valid UTF-8 text"}
    except Exception as e:
        logger.error(f"read_file error: {e}")
        return {"success": False, "content": None, "error": "Failed to read file"}


@registry.register(
    name="write_file",
    description="Write content to a file. Creates parent directories if needed.",
    risk_level=RiskLevel.HIGH,
    parameters={"file_path": "Path to write to", "content": "Content to write"},
)
def write_file(file_path: str, content: str) -> dict:
    """Write to a file safely."""
    path = Path(file_path).resolve()

    # Security check (case-insensitive on Windows)
    if not _is_safe_path(path):
        return {"success": False, "error": "Access denied: path outside project"}

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return {"success": True, "path": str(path), "bytes_written": len(content)}
    except Exception as e:
        logger.error(f"write_file error: {e}")
        return {"success": False, "error": "Failed to write file"}


@registry.register(
    name="list_directory",
    description="List contents of a directory.",
    risk_level=RiskLevel.LOW,
    parameters={"dir_path": "Path to directory list"},
)
def list_directory(dir_path: str) -> dict:
    """List directory contents."""
    path = Path(dir_path).resolve()

    if not _is_safe_path(path):
        return {"success": False, "error": "Access denied: path outside project"}

    if not path.is_dir():
        return {"success": False, "error": f"Not a directory: {path.name}"}

    try:
        entries = []
        for item in sorted(path.iterdir()):
            entries.append({
                "name": item.name,
                "type": "dir" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None,
            })
        return {"success": True, "entries": entries, "count": len(entries)}
    except Exception as e:
        logger.error(f"list_directory error: {e}")
        return {"success": False, "error": "Failed to list directory"}
