"""
Project Intelligence — Codebase Understanding Engine
════════════════════════════════════════════════════
Parses and indexes the user's project structure, understanding
file relationships, coding patterns, dependencies, and conventions.

Capabilities:
  1. Project Scanning      — Recursively scans directory trees
  2. Dependency Mapping    — Import/require graph analysis
  3. Pattern Detection     — Identifies coding conventions
  4. File Relationship Map — Which files depend on which
  5. Tech Stack Detection  — Auto-detect languages/frameworks
  6. Code Style Profile    — Naming conventions, formatting
"""

import hashlib
import json
import logging
import os
import re
import time
from collections import defaultdict, Counter
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class Language(Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    HTML = "html"
    CSS = "css"
    JSON_LANG = "json"
    MARKDOWN = "markdown"
    YAML = "yaml"
    UNKNOWN = "unknown"


EXTENSION_MAP = {
    ".py": Language.PYTHON, ".pyw": Language.PYTHON,
    ".js": Language.JAVASCRIPT, ".jsx": Language.JAVASCRIPT, ".mjs": Language.JAVASCRIPT,
    ".ts": Language.TYPESCRIPT, ".tsx": Language.TYPESCRIPT,
    ".html": Language.HTML, ".htm": Language.HTML,
    ".css": Language.CSS, ".scss": Language.CSS,
    ".json": Language.JSON_LANG,
    ".md": Language.MARKDOWN, ".mdx": Language.MARKDOWN,
    ".yaml": Language.YAML, ".yml": Language.YAML,
}

FRAMEWORK_INDICATORS = {
    "fastapi": (["fastapi"], Language.PYTHON),
    "flask": (["flask"], Language.PYTHON),
    "django": (["django"], Language.PYTHON),
    "react": (["react", "react-dom"], Language.JAVASCRIPT),
    "next.js": (["next"], Language.JAVASCRIPT),
    "vue": (["vue"], Language.JAVASCRIPT),
    "express": (["express"], Language.JAVASCRIPT),
    "vite": (["vite"], Language.JAVASCRIPT),
    "tailwind": (["tailwindcss"], Language.CSS),
}


@dataclass
class FileInfo:
    """Information about a single file in the project."""
    path: str = ""
    relative_path: str = ""
    language: Language = Language.UNKNOWN
    size_bytes: int = 0
    line_count: int = 0
    imports: List[str] = field(default_factory=list)
    exports: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)  # Files that this file imports
    last_modified: float = 0.0


@dataclass
class ProjectProfile:
    """Complete profile of a project."""
    project_path: str = ""
    name: str = ""
    primary_language: Language = Language.UNKNOWN
    languages: Dict[str, int] = field(default_factory=dict)  # lang → file count
    frameworks: List[str] = field(default_factory=list)
    total_files: int = 0
    total_lines: int = 0
    file_map: Dict[str, FileInfo] = field(default_factory=dict)
    dependency_graph: Dict[str, List[str]] = field(default_factory=dict)
    naming_convention: str = "unknown"  # snake_case, camelCase, PascalCase
    indent_style: str = "spaces"
    indent_size: int = 4
    has_tests: bool = False
    has_ci: bool = False
    structure_type: str = ""  # monorepo, standard, flat
    scanned_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "primary_language": self.primary_language.value,
            "languages": self.languages,
            "frameworks": self.frameworks,
            "total_files": self.total_files,
            "total_lines": self.total_lines,
            "naming_convention": self.naming_convention,
            "indent_style": self.indent_style,
            "indent_size": self.indent_size,
            "has_tests": self.has_tests,
            "has_ci": self.has_ci,
            "structure_type": self.structure_type,
        }


IGNORE_DIRS = {
    ".git", "__pycache__", "node_modules", ".next", "dist", "build",
    ".venv", "venv", "env", ".env", ".idea", ".vscode", ".mypy_cache",
    "egg-info", ".eggs", ".tox", "coverage", ".pytest_cache",
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib", ".o",
    ".class", ".jar", ".war", ".zip", ".tar", ".gz", ".png",
    ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".ttf",
    ".mp3", ".mp4", ".avi", ".mov", ".pdf", ".lock",
}


class ProjectIntelligence:
    """
    Codebase understanding engine that scans, indexes, and profiles
    a project to generate context-aware code.
    """

    MAX_FILE_SIZE = 500_000  # 500KB max per file
    MAX_FILES = 5000

    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = Path(data_dir) if data_dir else Path("data/project_intelligence")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._profiles: Dict[str, ProjectProfile] = {}
        logger.info("[PROJECT] Project Intelligence engine initialized")

    def scan_project(self, project_path: str) -> ProjectProfile:
        """Scan and profile an entire project."""
        root = Path(project_path)
        if not root.exists():
            raise ValueError(f"Project path does not exist: {project_path}")

        profile = ProjectProfile(
            project_path=project_path,
            name=root.name,
        )

        # Walk the directory tree
        lang_counter: Counter = Counter()
        files_scanned = 0

        for item in self._walk_filtered(root):
            if files_scanned >= self.MAX_FILES:
                break
            if item.is_file():
                ext = item.suffix.lower()
                if ext in IGNORE_EXTENSIONS:
                    continue

                lang = EXTENSION_MAP.get(ext, Language.UNKNOWN)
                if lang == Language.UNKNOWN:
                    continue

                finfo = self._analyze_file(item, root, lang)
                if finfo:
                    rel = finfo.relative_path
                    profile.file_map[rel] = finfo
                    lang_counter[lang.value] += 1
                    profile.total_lines += finfo.line_count
                    files_scanned += 1

        profile.total_files = files_scanned
        profile.languages = dict(lang_counter)

        # Determine primary language
        if lang_counter:
            primary = lang_counter.most_common(1)[0][0]
            for lang in Language:
                if lang.value == primary:
                    profile.primary_language = lang
                    break

        # Detect frameworks
        profile.frameworks = self._detect_frameworks(root, profile)

        # Build dependency graph
        profile.dependency_graph = self._build_dependency_graph(profile)

        # Detect conventions
        profile.naming_convention = self._detect_naming(profile)
        profile.indent_style, profile.indent_size = self._detect_indent(root, profile)

        # Detect structure
        profile.has_tests = any(
            "test" in f.lower() for f in profile.file_map.keys()
        )
        profile.has_ci = any(
            root.glob(p) for p in [".github/workflows/*.yml", ".gitlab-ci.yml",
                                    "Jenkinsfile", ".circleci/config.yml"]
        )
        profile.structure_type = self._detect_structure(profile)

        self._profiles[project_path] = profile
        self._save_profile(profile)

        logger.info(
            f"[PROJECT] Scanned '{profile.name}': {profile.total_files} files, "
            f"{profile.total_lines} lines, {profile.primary_language.value}, "
            f"frameworks={profile.frameworks}"
        )
        return profile

    def _walk_filtered(self, root: Path):
        """Walk directory tree, skipping ignored dirs."""
        try:
            for entry in sorted(root.iterdir()):
                if entry.name.startswith(".") and entry.is_dir():
                    if entry.name not in {".github", ".circleci"}:
                        continue
                if entry.is_dir():
                    if entry.name in IGNORE_DIRS:
                        continue
                    yield from self._walk_filtered(entry)
                else:
                    yield entry
        except PermissionError:
            pass

    def _analyze_file(self, filepath: Path, root: Path, lang: Language) -> Optional[FileInfo]:
        """Analyze a single file for structure information."""
        try:
            stats = filepath.stat()
            if stats.st_size > self.MAX_FILE_SIZE:
                return None

            content = filepath.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")

            finfo = FileInfo(
                path=str(filepath),
                relative_path=str(filepath.relative_to(root)),
                language=lang,
                size_bytes=stats.st_size,
                line_count=len(lines),
                last_modified=stats.st_mtime,
            )

            if lang == Language.PYTHON:
                finfo.imports = self._extract_python_imports(content)
                finfo.classes = re.findall(r'^class\s+(\w+)', content, re.MULTILINE)
                finfo.functions = re.findall(r'^def\s+(\w+)', content, re.MULTILINE)
            elif lang in (Language.JAVASCRIPT, Language.TYPESCRIPT):
                finfo.imports = self._extract_js_imports(content)
                finfo.classes = re.findall(r'class\s+(\w+)', content)
                finfo.functions = re.findall(
                    r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\(|function))',
                    content,
                )
                finfo.functions = [f[0] or f[1] for f in finfo.functions]

            return finfo
        except Exception:
            return None

    def _extract_python_imports(self, content: str) -> List[str]:
        imports = []
        for line in content.split("\n"):
            line = line.strip()
            m = re.match(r'^(?:from\s+(\S+)\s+)?import\s+(.+)', line)
            if m:
                module = m.group(1) or m.group(2).split(",")[0].strip().split(" as ")[0]
                imports.append(module)
        return imports[:50]

    def _extract_js_imports(self, content: str) -> List[str]:
        imports = []
        for m in re.finditer(r"(?:import|require)\s*\(?['\"]([^'\"]+)['\"]", content):
            imports.append(m.group(1))
        return imports[:50]

    def _detect_frameworks(self, root: Path, profile: ProjectProfile) -> List[str]:
        detected = []

        # Check package.json
        pkg_json = root / "package.json"
        if pkg_json.exists():
            try:
                pkg = json.loads(pkg_json.read_text(encoding="utf-8"))
                all_deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                for fw_name, (indicators, _) in FRAMEWORK_INDICATORS.items():
                    if any(ind in all_deps for ind in indicators):
                        detected.append(fw_name)
            except Exception:
                pass

        # Check requirements.txt / pyproject.toml
        for req_file in ["requirements.txt", "pyproject.toml", "setup.py"]:
            req_path = root / req_file
            if req_path.exists():
                try:
                    content = req_path.read_text(encoding="utf-8").lower()
                    for fw_name, (indicators, lang) in FRAMEWORK_INDICATORS.items():
                        if lang == Language.PYTHON and any(ind in content for ind in indicators):
                            detected.append(fw_name)
                except Exception:
                    pass

        return list(set(detected))

    def _build_dependency_graph(self, profile: ProjectProfile) -> Dict[str, List[str]]:
        graph = {}
        for rel_path, finfo in profile.file_map.items():
            deps = []
            for imp in finfo.imports:
                # Try to match import to a file in the project
                for other_path in profile.file_map:
                    if imp.replace(".", "/") in other_path or imp.replace(".", "\\") in other_path:
                        deps.append(other_path)
                        break
            if deps:
                graph[rel_path] = deps
        return graph

    def _detect_naming(self, profile: ProjectProfile) -> str:
        all_names = []
        for finfo in profile.file_map.values():
            all_names.extend(finfo.functions)
            all_names.extend(finfo.classes)

        if not all_names:
            return "unknown"

        snake = sum(1 for n in all_names if "_" in n and n == n.lower())
        camel = sum(1 for n in all_names if n[0].islower() and any(c.isupper() for c in n[1:]))
        pascal = sum(1 for n in all_names if n[0].isupper() and any(c.islower() for c in n[1:]))

        scores = {"snake_case": snake, "camelCase": camel, "PascalCase": pascal}
        return max(scores, key=scores.get)

    def _detect_indent(self, root: Path, profile: ProjectProfile) -> Tuple[str, int]:
        indent_counts: Counter = Counter()
        samples = list(profile.file_map.values())[:20]

        for finfo in samples:
            try:
                content = Path(finfo.path).read_text(encoding="utf-8", errors="ignore")
                for line in content.split("\n")[:100]:
                    if line and line[0] == " ":
                        spaces = len(line) - len(line.lstrip(" "))
                        if spaces in (2, 4, 8):
                            indent_counts[spaces] += 1
                    elif line and line[0] == "\t":
                        indent_counts[-1] += 1  # -1 = tabs
            except Exception:
                pass

        if not indent_counts:
            return "spaces", 4

        most_common = indent_counts.most_common(1)[0][0]
        if most_common == -1:
            return "tabs", 1
        return "spaces", most_common

    def _detect_structure(self, profile: ProjectProfile) -> str:
        paths = list(profile.file_map.keys())
        depths = [p.count("/") + p.count("\\") for p in paths]
        avg_depth = sum(depths) / max(len(depths), 1)

        if avg_depth < 1.5:
            return "flat"
        elif any("packages/" in p or "apps/" in p for p in paths):
            return "monorepo"
        return "standard"

    # ── Query ──

    def get_context_for_file(self, project_path: str, file_path: str) -> Dict[str, Any]:
        """Get relevant context when editing a file."""
        profile = self._profiles.get(project_path)
        if not profile:
            return {}

        finfo = profile.file_map.get(file_path)
        if not finfo:
            return {}

        # Find related files
        related = []
        for dep in profile.dependency_graph.get(file_path, []):
            if dep in profile.file_map:
                related.append({"path": dep, "relationship": "imports"})
        for other, deps in profile.dependency_graph.items():
            if file_path in deps:
                related.append({"path": other, "relationship": "imported_by"})

        return {
            "file": file_path,
            "language": finfo.language.value,
            "classes": finfo.classes,
            "functions": finfo.functions,
            "imports": finfo.imports,
            "related_files": related[:10],
            "project_conventions": {
                "naming": profile.naming_convention,
                "indent": f"{profile.indent_size} {profile.indent_style}",
                "frameworks": profile.frameworks,
            },
        }

    def get_project_summary(self, project_path: str) -> Dict[str, Any]:
        profile = self._profiles.get(project_path)
        if not profile:
            return {"error": "Project not scanned. Call scan_project first."}
        return profile.to_dict()

    # ── Persistence ──

    def _save_profile(self, profile: ProjectProfile) -> None:
        path = self.data_dir / f"{profile.name}_profile.json"
        try:
            path.write_text(json.dumps(profile.to_dict(), indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"[PROJECT] Save failed: {e}")

    def get_status(self) -> Dict[str, Any]:
        return {
            "projects_scanned": len(self._profiles),
            "projects": {
                name: p.to_dict() for name, p in self._profiles.items()
            },
        }
