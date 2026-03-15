"""
Git & Version Control Tools — Expert-Level Repository Management.
================================================================
6 registered tools for professional Git workflow:

  git_status      — Repository status (branch, changes, ahead/behind)
  git_commit      — Stage and commit changes with conventional commits
  git_branch      — Create, switch, list, and delete branches
  git_diff        — Show file diffs (staged, unstaged, between commits)
  git_log         — Commit history with filtering and formatting
  git_stash       — Stash and restore working changes
"""

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List

from agents.tools.registry import registry, ToolRiskLevel

logger = logging.getLogger(__name__)


def _run_git(args: List[str], cwd: str, timeout: int = 30) -> Dict[str, Any]:
    """Execute a git command and return structured result."""
    if not os.path.isdir(cwd):
        return {"success": False, "error": f"Directory not found: {cwd}"}
    try:
        proc = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True,
            text=True, timeout=timeout, shell=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        return {
            "success": proc.returncode == 0,
            "stdout": proc.stdout.strip(),
            "stderr": proc.stderr.strip(),
            "exit_code": proc.returncode,
        }
    except FileNotFoundError:
        return {"success": False, "error": "Git not installed"}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Git command timed out after {timeout}s"}


@registry.register(
    name="git_status",
    description="Get repository status: branch, staged/unstaged changes, ahead/behind remote.",
    risk_level=ToolRiskLevel.LOW,
    parameters={"repo_path": "Path to git repository"},
)
def git_status(repo_path: str = ".") -> Dict[str, Any]:
    """Get comprehensive git status."""
    branch = _run_git(["branch", "--show-current"], repo_path)
    status = _run_git(["status", "--porcelain=v1"], repo_path)
    remote = _run_git(["rev-list", "--left-right", "--count", "HEAD...@{upstream}"], repo_path)

    if not status["success"]:
        return {"success": False, "error": status.get("error") or status.get("stderr", "Not a git repo")}

    changes = {"staged": [], "unstaged": [], "untracked": []}
    for line in status["stdout"].split("\n"):
        if not line.strip():
            continue
        code = line[:2]
        filepath = line[3:]
        if code[0] in "MADRC":
            changes["staged"].append(filepath)
        if code[1] in "MDRC":
            changes["unstaged"].append(filepath)
        if code == "??":
            changes["untracked"].append(filepath)

    ahead, behind = 0, 0
    if remote["success"] and remote["stdout"]:
        parts = remote["stdout"].split("\t")
        if len(parts) == 2:
            ahead, behind = int(parts[0]), int(parts[1])

    return {
        "success": True,
        "branch": branch.get("stdout", "unknown"),
        "staged": changes["staged"],
        "unstaged": changes["unstaged"],
        "untracked": changes["untracked"],
        "total_changes": sum(len(v) for v in changes.values()),
        "ahead": ahead,
        "behind": behind,
        "clean": sum(len(v) for v in changes.values()) == 0,
    }


@registry.register(
    name="git_commit",
    description="Stage files and create a commit with conventional commit message format.",
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "repo_path": "Path to git repository",
        "message": "Commit message (conventional: feat/fix/docs/refactor/test: description)",
        "files": "Files to stage (empty = all changed files)",
        "push": "Push after commit (default false)",
    },
)
def git_commit(
    repo_path: str = ".",
    message: str = "",
    files: list = None,
    push: bool = False,
) -> Dict[str, Any]:
    """Stage and commit changes."""
    if not message:
        return {"success": False, "error": "Commit message required"}

    # Stage files
    if files:
        for f in files:
            r = _run_git(["add", f], repo_path)
            if not r["success"]:
                return {"success": False, "error": f"Failed to stage {f}: {r.get('stderr', '')}"}
    else:
        r = _run_git(["add", "-A"], repo_path)
        if not r["success"]:
            return {"success": False, "error": f"Failed to stage: {r.get('stderr', '')}"}

    # Commit
    result = _run_git(["commit", "-m", message], repo_path)
    if not result["success"]:
        return {"success": False, "error": result.get("stderr", "Commit failed")}

    response = {
        "success": True,
        "message": message,
        "output": result["stdout"],
    }

    # Push if requested
    if push:
        push_result = _run_git(["push"], repo_path, timeout=60)
        response["pushed"] = push_result["success"]
        if not push_result["success"]:
            response["push_error"] = push_result.get("stderr", "")

    return response


@registry.register(
    name="git_branch",
    description="Create, switch, list, or delete git branches.",
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "repo_path": "Path to git repository",
        "action": "list | create | switch | delete | rename",
        "branch_name": "Branch name for create/switch/delete",
        "new_name": "New name for rename action",
    },
)
def git_branch(
    repo_path: str = ".",
    action: str = "list",
    branch_name: str = "",
    new_name: str = "",
) -> Dict[str, Any]:
    """Manage git branches."""
    if action == "list":
        r = _run_git(["branch", "-a", "--format=%(refname:short) %(upstream:short) %(objectname:short)"], repo_path)
        branches = []
        for line in r.get("stdout", "").split("\n"):
            if line.strip():
                parts = line.strip().split()
                branches.append({"name": parts[0], "remote": parts[1] if len(parts) > 1 else ""})
        current = _run_git(["branch", "--show-current"], repo_path)
        return {"success": True, "branches": branches, "current": current.get("stdout", ""),
                "total": len(branches)}

    elif action == "create":
        if not branch_name:
            return {"success": False, "error": "Branch name required"}
        r = _run_git(["checkout", "-b", branch_name], repo_path)
        return {"success": r["success"], "branch": branch_name,
                "output": r.get("stdout", "") or r.get("stderr", "")}

    elif action == "switch":
        if not branch_name:
            return {"success": False, "error": "Branch name required"}
        r = _run_git(["checkout", branch_name], repo_path)
        return {"success": r["success"], "branch": branch_name,
                "output": r.get("stdout", "") or r.get("stderr", "")}

    elif action == "delete":
        if not branch_name:
            return {"success": False, "error": "Branch name required"}
        r = _run_git(["branch", "-d", branch_name], repo_path)
        return {"success": r["success"], "deleted": branch_name,
                "output": r.get("stdout", "") or r.get("stderr", "")}

    elif action == "rename":
        if not branch_name or not new_name:
            return {"success": False, "error": "Both branch_name and new_name required"}
        r = _run_git(["branch", "-m", branch_name, new_name], repo_path)
        return {"success": r["success"], "renamed": f"{branch_name} -> {new_name}"}

    return {"success": False, "error": f"Unknown action: {action}"}


@registry.register(
    name="git_diff",
    description="Show file diffs: staged, unstaged, or between commits/branches.",
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "repo_path": "Path to git repository",
        "target": "staged | unstaged | commit_hash | branch_name",
        "file_path": "Optional specific file to diff",
    },
)
def git_diff(
    repo_path: str = ".",
    target: str = "unstaged",
    file_path: str = "",
) -> Dict[str, Any]:
    """Show diffs."""
    args = ["diff"]
    if target == "staged":
        args.append("--cached")
    elif target == "unstaged":
        pass
    else:
        args.append(target)

    args.extend(["--stat"])
    if file_path:
        args.extend(["--", file_path])

    stat_result = _run_git(args, repo_path)

    # Full diff (limited)
    full_args = ["diff"]
    if target == "staged":
        full_args.append("--cached")
    elif target != "unstaged":
        full_args.append(target)
    if file_path:
        full_args.extend(["--", file_path])

    full_result = _run_git(full_args, repo_path)

    return {
        "success": stat_result["success"],
        "target": target,
        "stat": stat_result.get("stdout", ""),
        "diff": full_result.get("stdout", "")[:10000],  # Cap at 10k chars
        "truncated": len(full_result.get("stdout", "")) > 10000,
    }


@registry.register(
    name="git_log",
    description="Show commit history with filtering and formatting options.",
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "repo_path": "Path to git repository",
        "count": "Number of commits to show (default 10)",
        "author": "Filter by author",
        "since": "Filter commits since date (e.g. '2024-01-01')",
        "search": "Search commit messages",
    },
)
def git_log(
    repo_path: str = ".",
    count: int = 10,
    author: str = "",
    since: str = "",
    search: str = "",
) -> Dict[str, Any]:
    """Show commit history."""
    args = ["log", f"-{count}", "--format=%H|%an|%ae|%aI|%s"]
    if author:
        args.append(f"--author={author}")
    if since:
        args.append(f"--since={since}")
    if search:
        args.append(f"--grep={search}")

    r = _run_git(args, repo_path)
    if not r["success"]:
        return {"success": False, "error": r.get("stderr", "")}

    commits = []
    for line in r["stdout"].split("\n"):
        if "|" in line:
            parts = line.split("|", 4)
            if len(parts) >= 5:
                commits.append({
                    "hash": parts[0][:8],
                    "full_hash": parts[0],
                    "author": parts[1],
                    "email": parts[2],
                    "date": parts[3],
                    "message": parts[4],
                })

    return {"success": True, "commits": commits, "total": len(commits)}


@registry.register(
    name="git_stash",
    description="Stash working changes or restore stashed changes.",
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "repo_path": "Path to git repository",
        "action": "save | pop | list | drop | apply",
        "message": "Stash message (for save)",
        "index": "Stash index (for pop/drop/apply)",
    },
)
def git_stash(
    repo_path: str = ".",
    action: str = "list",
    message: str = "",
    index: int = 0,
) -> Dict[str, Any]:
    """Manage git stash."""
    if action == "save":
        args = ["stash", "push"]
        if message:
            args.extend(["-m", message])
        r = _run_git(args, repo_path)
    elif action == "pop":
        r = _run_git(["stash", "pop", f"stash@{{{index}}}"], repo_path)
    elif action == "apply":
        r = _run_git(["stash", "apply", f"stash@{{{index}}}"], repo_path)
    elif action == "drop":
        r = _run_git(["stash", "drop", f"stash@{{{index}}}"], repo_path)
    elif action == "list":
        r = _run_git(["stash", "list"], repo_path)
        stashes = []
        for line in r.get("stdout", "").split("\n"):
            if line.strip():
                stashes.append(line.strip())
        return {"success": True, "stashes": stashes, "total": len(stashes)}
    else:
        return {"success": False, "error": f"Unknown action: {action}"}

    return {"success": r["success"], "action": action,
            "output": r.get("stdout", "") or r.get("stderr", "")}
