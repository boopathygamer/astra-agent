"""
File Finder Tool — Cross-platform local file search.
Provides the ability to locate lost files by name, extension, size, and date.
"""

import os
import time
import fnmatch
from pathlib import Path
from typing import List, Dict, Optional
import datetime
import logging

from agents.tools.registry import registry, RiskLevel

logger = logging.getLogger(__name__)

# Common directories to search first for faster results
_COMMON_USER_DIRS = [
    "Desktop",
    "Documents",
    "Downloads",
    "Pictures",
    "Music",
    "Videos"
]

def _get_common_search_paths() -> List[str]:
    """Get cross-platform paths to common user directories."""
    paths = []
    user_home = Path.home()
    
    # Always include home dir root itself (non-recursive later)
    paths.append(str(user_home))
    
    # Add common subdirectories
    for d in _COMMON_USER_DIRS:
        p = user_home / d
        if p.exists() and p.is_dir():
            paths.append(str(p))
            
    # Add project root as a priority
    try:
        from config.settings import BASE_DIR
        paths.append(str(BASE_DIR))
    except Exception:
        pass
        
    return paths

def format_size(size_bytes: int) -> str:
    """Format bytes into a human readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

@registry.register(
    name="find_files",
    description="Find files on the local device by name, extension, or date. Useful for locating lost files.",
    risk_level=RiskLevel.LOW,
    parameters={
        "query": "Filename or partial name to search for (e.g. 'budget' or '*report*')",
        "extension": "Filter by file extension (e.g. '.pdf', '.py'). Optional.",
        "search_paths": "List of directories to search. If empty, searches common user folders.",
        "max_results": "Maximum number of results to return (default 20, max 100).",
        "modified_within_days": "Only find files modified in the last N days. Optional."
    },
)
def find_files(
    query: str,
    extension: Optional[str] = None,
    search_paths: Optional[List[str]] = None,
    max_results: int = 20,
    modified_within_days: Optional[int] = None
) -> dict:
    """
    Search for files on the local file system.
    """
    start_time = time.time()
    results = []
    directories_searched = 0
    timeout_seconds = 25.0  # Hard timeout to prevent endless hanging
    
    max_results = min(max(1, max_results), 100)
    
    # Normalize query for fnmatch
    if not query:
        query = "*"
    elif not ("*" in query or "?" in query):
        query = f"*{query}*"
        
    query = query.lower()
        
    if extension and not extension.startswith("."):
        extension = f".{extension}"
    if extension:
        extension = extension.lower()
        
    # Determine search paths
    paths_to_search = []
    if search_paths and len(search_paths) > 0:
        for p in search_paths:
            path_obj = Path(p)
            if path_obj.exists() and path_obj.is_dir():
                paths_to_search.append(p)
    else:
        paths_to_search = _get_common_search_paths()
        
    if not paths_to_search:
        return {
            "success": False, 
            "error": "No valid search directories found.",
            "results": []
        }

    # Cutoff timestamp for modification date filtering
    cutoff_time = 0
    if modified_within_days:
        cutoff_time = time.time() - (modified_within_days * 86400)

    try:
        for base_path in paths_to_search:
            # Check timeout
            if time.time() - start_time > timeout_seconds:
                logger.warning(f"find_files timeout reached ({timeout_seconds}s)")
                break
                
            if len(results) >= max_results:
                break
                
            try:
                for root, dirs, files in os.walk(base_path, topdown=True):
                    # Check limits
                    if time.time() - start_time > timeout_seconds or len(results) >= max_results:
                        break
                        
                    directories_searched += 1
                    
                    # Skip common heavy/system directories to speed up search
                    dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'venv', 'env', '__pycache__', 'Windows', 'Program Files', 'Program Files (x86)')]
                    
                    for filename in files:
                        filename_lower = filename.lower()
                        
                        # 1. Check extension filter
                        if extension and not filename_lower.endswith(extension):
                            continue
                            
                        # 2. Check query match
                        if query != "*" and not fnmatch.fnmatch(filename_lower, query):
                            continue
                            
                        # Build full path
                        full_path = os.path.join(root, filename)
                        
                        try:
                            # 3. Check modification date and get stats
                            stat_result = os.stat(full_path)
                            
                            if cutoff_time > 0 and stat_result.st_mtime < cutoff_time:
                                continue
                                
                            # Match found!
                            mtime_iso = datetime.datetime.fromtimestamp(stat_result.st_mtime).isoformat()
                            
                            results.append({
                                "path": full_path,
                                "name": filename,
                                "size_bytes": stat_result.st_size,
                                "size_human": format_size(stat_result.st_size),
                                "modified": mtime_iso,
                                "extension": os.path.splitext(filename)[1]
                            })
                            
                            if len(results) >= max_results:
                                break
                                
                        except (OSError, PermissionError):
                            pass # Skip files we can't access
                            
            except (OSError, PermissionError):
                pass # Skip directories we can't access

    except Exception as e:
        logger.error(f"find_files error: {e}")
        return {
            "success": False,
            "error": f"Search encountered an error: {str(e)}",
            "results": results,
            "partial_results": len(results) > 0
        }
        
    # Sort results by modification time (newest first)
    results.sort(key=lambda x: x.get("modified", ""), reverse=True)

    elapsed_ms = int((time.time() - start_time) * 1000)
    
    return {
        "success": True,
        "query": query,
        "results": results,
        "total_found": len(results),
        "search_duration_ms": elapsed_ms,
        "directories_searched": directories_searched,
        "timeout_reached": (time.time() - start_time) > timeout_seconds
    }
