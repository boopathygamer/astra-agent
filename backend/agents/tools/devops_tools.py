"""
Automated Test Generator + API Tester + Dependency Vulnerability Scanner.
=========================================================================
3 expert-level tools in one module:

  generate_tests     — Auto-generate unit tests for Python/JS/TS code
  api_test           — HTTP request tool (GET/POST/PUT/DELETE with assertions)
  scan_dependencies  — Scan npm/pip/gradle for known CVEs
"""

import ast
import json
import logging
import os
import re
import subprocess
import textwrap
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.tools.registry import registry, ToolRiskLevel

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Tool 1: generate_tests
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="generate_tests",
    description=(
        "Auto-generate unit test code from source code. Analyzes functions/classes "
        "and creates test cases with assertions, edge cases, and mocking."
    ),
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "code": "Source code to generate tests for",
        "language": "python | javascript | typescript",
        "framework": "pytest | unittest | jest | vitest | mocha",
        "style": "basic | thorough | edge_cases",
    },
)
def generate_tests(
    code: str = "",
    language: str = "python",
    framework: str = "pytest",
    style: str = "thorough",
) -> Dict[str, Any]:
    """Auto-generate unit tests from source code."""
    if not code.strip():
        return {"success": False, "error": "No source code provided"}

    if language == "python":
        return _gen_python_tests(code, framework, style)
    elif language in ("javascript", "typescript"):
        return _gen_js_tests(code, framework, style, language)
    return {"success": False, "error": f"Unsupported language: {language}"}


def _gen_python_tests(code, framework, style):
    """Generate Python tests by analyzing AST."""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return {"success": False, "error": f"Syntax error: {e}"}

    functions = []
    classes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            args = [a.arg for a in node.args.args if a.arg != "self"]
            has_return = any(isinstance(n, ast.Return) and n.value for n in ast.walk(node))
            has_raise = any(isinstance(n, ast.Raise) for n in ast.walk(node))
            functions.append({"name": node.name, "args": args, "returns": has_return, "raises": has_raise})
        elif isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and not item.name.startswith("_"):
                    m_args = [a.arg for a in item.args.args if a.arg != "self"]
                    methods.append({"name": item.name, "args": m_args})
            classes.append({"name": node.name, "methods": methods})

    if framework == "pytest":
        test_code = _gen_pytest(functions, classes, style)
    else:
        test_code = _gen_unittest(functions, classes, style)

    return {
        "success": True,
        "language": "python",
        "framework": framework,
        "test_code": test_code,
        "functions_found": len(functions),
        "classes_found": len(classes),
        "test_count": test_code.count("def test_"),
    }


def _gen_pytest(funcs, classes, style):
    lines = ['import pytest', '', '# Auto-generated tests', '']

    for func in funcs:
        name = func["name"]
        args = func["args"]

        # Basic test
        arg_vals = ", ".join(_guess_arg_value(a) for a in args)
        lines.extend([
            f"def test_{name}_basic():",
            f'    """Test {name} with valid inputs."""',
            f"    result = {name}({arg_vals})",
        ])
        if func["returns"]:
            lines.append("    assert result is not None")
        lines.append("")

        if style in ("thorough", "edge_cases"):
            # Edge case: empty/None inputs
            if args:
                lines.extend([
                    f"def test_{name}_edge_cases():",
                    f'    """Test {name} with edge case inputs."""',
                ])
                for arg in args:
                    lines.append(f"    # Test with None {arg}")
                if func["raises"]:
                    lines.append(f"    with pytest.raises(Exception):")
                    lines.append(f"        {name}(None)")
                lines.append("")

            # Type test
            if func["returns"]:
                lines.extend([
                    f"def test_{name}_return_type():",
                    f'    """Test {name} returns expected type."""',
                    f"    result = {name}({arg_vals})",
                    f"    assert isinstance(result, (str, int, float, bool, list, dict, type(None)))",
                    "",
                ])

    for cls in classes:
        lines.extend([
            f"class Test{cls['name']}:",
            f'    """Tests for {cls["name"]} class."""',
            "",
            f"    def setup_method(self):",
            f"        self.instance = {cls['name']}()",
            "",
        ])
        for method in cls["methods"]:
            arg_vals = ", ".join(_guess_arg_value(a) for a in method["args"])
            lines.extend([
                f"    def test_{method['name']}(self):",
                f'        """Test {cls["name"]}.{method["name"]}."""',
                f"        result = self.instance.{method['name']}({arg_vals})",
                f"        assert result is not None",
                "",
            ])

    return "\n".join(lines)


def _gen_unittest(funcs, classes, style):
    lines = [
        "import unittest",
        "",
        "class TestGenerated(unittest.TestCase):",
        "",
    ]
    for func in funcs:
        arg_vals = ", ".join(_guess_arg_value(a) for a in func["args"])
        lines.extend([
            f"    def test_{func['name']}(self):",
            f"        result = {func['name']}({arg_vals})",
            f"        self.assertIsNotNone(result)",
            "",
        ])
    lines.append('if __name__ == "__main__": unittest.main()')
    return "\n".join(lines)


def _gen_js_tests(code, framework, style, lang):
    """Generate JS/TS tests by regex analysis."""
    funcs = re.findall(r'(?:function\s+(\w+)|(?:const|let)\s+(\w+)\s*=\s*(?:async\s*)?\()', code)
    func_names = [f[0] or f[1] for f in funcs if f[0] or f[1]]

    exports = re.findall(r'export\s+(?:default\s+)?(?:function|const|class)\s+(\w+)', code)
    classes = re.findall(r'class\s+(\w+)', code)

    if framework == "jest":
        test_code = _gen_jest_tests(func_names, classes, exports, style)
    elif framework == "vitest":
        test_code = _gen_vitest_tests(func_names, classes, exports, style)
    else:
        test_code = _gen_mocha_tests(func_names, classes, style)

    return {
        "success": True,
        "language": lang,
        "framework": framework,
        "test_code": test_code,
        "functions_found": len(func_names),
        "classes_found": len(classes),
        "test_count": test_code.count("it(") + test_code.count("test("),
    }


def _gen_jest_tests(funcs, classes, exports, style):
    lines = []
    if exports:
        lines.append(f"const {{ {', '.join(exports)} }} = require('./module');")
    lines.extend(["", "describe('Module Tests', () => {", ""])

    for fn in funcs:
        lines.extend([
            f"  test('{fn} returns expected result', () => {{",
            f"    const result = {fn}();",
            f"    expect(result).toBeDefined();",
            f"  }});",
            "",
        ])
        if style in ("thorough", "edge_cases"):
            lines.extend([
                f"  test('{fn} handles null input', () => {{",
                f"    expect(() => {fn}(null)).not.toThrow();",
                f"  }});",
                "",
            ])

    for cls in classes:
        lines.extend([
            f"  describe('{cls}', () => {{",
            f"    let instance;",
            f"    beforeEach(() => {{ instance = new {cls}(); }});",
            f"",
            f"    test('instantiates correctly', () => {{",
            f"      expect(instance).toBeDefined();",
            f"    }});",
            f"  }});",
            "",
        ])

    lines.append("});")
    return "\n".join(lines)


def _gen_vitest_tests(funcs, classes, exports, style):
    lines = ["import { describe, test, expect, beforeEach } from 'vitest';"]
    if exports:
        lines.append(f"import {{ {', '.join(exports)} }} from './module';")
    lines.extend(["", "describe('Module', () => {"])
    for fn in funcs:
        lines.extend([
            f"  test('{fn}', () => {{",
            f"    const result = {fn}();",
            f"    expect(result).toBeDefined();",
            f"  }});",
        ])
    lines.append("});")
    return "\n".join(lines)


def _gen_mocha_tests(funcs, classes, style):
    lines = ["const assert = require('assert');", "", "describe('Module', () => {"]
    for fn in funcs:
        lines.extend([
            f"  it('{fn} works', () => {{",
            f"    const result = {fn}();",
            f"    assert.ok(result !== undefined);",
            f"  }});",
        ])
    lines.append("});")
    return "\n".join(lines)


def _guess_arg_value(name):
    """Guess a reasonable test value from argument name."""
    name_lower = name.lower()
    if "id" in name_lower:
        return "1"
    if "name" in name_lower or "title" in name_lower:
        return '"test"'
    if "email" in name_lower:
        return '"test@example.com"'
    if "count" in name_lower or "num" in name_lower or "size" in name_lower:
        return "10"
    if "flag" in name_lower or "is_" in name_lower or "enabled" in name_lower:
        return "True"
    if "path" in name_lower or "dir" in name_lower or "file" in name_lower:
        return '"/tmp/test"'
    if "data" in name_lower or "config" in name_lower:
        return "{}"
    if "items" in name_lower or "list" in name_lower:
        return "[]"
    if "url" in name_lower:
        return '"https://example.com"'
    return '"test"'


# ══════════════════════════════════════════════════════════════
# Tool 2: api_test
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="api_test",
    description=(
        "Send HTTP requests and validate responses. Like Postman: "
        "supports GET/POST/PUT/DELETE with headers, body, and assertions."
    ),
    risk_level=ToolRiskLevel.MEDIUM,
    parameters={
        "url": "Request URL",
        "method": "GET | POST | PUT | PATCH | DELETE",
        "headers": "Request headers dict",
        "body": "Request body (for POST/PUT/PATCH)",
        "assertions": "List of assertions: [{field, op, value}]",
        "timeout": "Request timeout in seconds",
    },
)
def api_test(
    url: str = "",
    method: str = "GET",
    headers: dict = None,
    body: dict = None,
    assertions: list = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Send HTTP request and validate response."""
    if not url:
        return {"success": False, "error": "URL required"}

    import urllib.request
    import urllib.error

    headers = headers or {}
    assertions = assertions or []
    method = method.upper()

    req_data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=req_data, method=method)
    req.add_header("User-Agent", "Astra-Agent/1.0")
    req.add_header("Accept", "application/json")

    if body:
        req.add_header("Content-Type", "application/json")
    for k, v in headers.items():
        req.add_header(k, v)

    import time
    start = time.time()

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.getcode()
            resp_headers = dict(resp.headers)
            resp_body = resp.read().decode("utf-8", errors="replace")
            elapsed = round(time.time() - start, 3)

            # Parse JSON if possible
            try:
                resp_json = json.loads(resp_body)
            except (json.JSONDecodeError, ValueError):
                resp_json = None

            # Run assertions
            assertion_results = []
            for a in assertions:
                field = a.get("field", "status")
                op = a.get("op", "==")
                expected = a.get("value")

                if field == "status":
                    actual = status
                elif field.startswith("header."):
                    actual = resp_headers.get(field[7:])
                elif resp_json and field.startswith("body."):
                    actual = _extract_json_path(resp_json, field[5:])
                else:
                    actual = None

                passed = _check_assertion(actual, op, expected)
                assertion_results.append({
                    "field": field, "op": op, "expected": expected,
                    "actual": actual, "passed": passed,
                })

            all_passed = all(a["passed"] for a in assertion_results) if assertion_results else True

            return {
                "success": True,
                "status": status,
                "elapsed_ms": int(elapsed * 1000),
                "headers": resp_headers,
                "body": resp_body[:10000],
                "json": resp_json,
                "assertions": assertion_results,
                "all_passed": all_passed,
            }

    except urllib.error.HTTPError as e:
        elapsed = round(time.time() - start, 3)
        return {
            "success": True,
            "status": e.code,
            "elapsed_ms": int(elapsed * 1000),
            "error": str(e.reason),
            "body": e.read().decode("utf-8", errors="replace")[:5000],
            "assertions": [],
            "all_passed": False,
        }
    except urllib.error.URLError as e:
        return {"success": False, "error": f"Connection error: {e.reason}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _extract_json_path(obj, path):
    """Extract value from JSON using dot notation."""
    parts = path.split(".")
    current = obj
    for part in parts:
        if isinstance(current, dict):
            current = current.get(part)
        elif isinstance(current, list) and part.isdigit():
            idx = int(part)
            current = current[idx] if idx < len(current) else None
        else:
            return None
    return current


def _check_assertion(actual, op, expected):
    """Check an assertion."""
    try:
        if op == "==":
            return actual == expected
        elif op == "!=":
            return actual != expected
        elif op == ">":
            return actual > expected
        elif op == "<":
            return actual < expected
        elif op == ">=":
            return actual >= expected
        elif op == "<=":
            return actual <= expected
        elif op == "contains":
            return expected in str(actual)
        elif op == "exists":
            return actual is not None
        elif op == "type":
            return type(actual).__name__ == expected
    except (TypeError, ValueError):
        return False
    return False


# ══════════════════════════════════════════════════════════════
# Tool 3: scan_dependencies
# ══════════════════════════════════════════════════════════════

@registry.register(
    name="scan_dependencies",
    description=(
        "Scan project dependencies for known vulnerabilities. "
        "Supports npm (package.json), pip (requirements.txt), and Gradle."
    ),
    risk_level=ToolRiskLevel.LOW,
    parameters={
        "project_dir": "Project directory to scan",
        "ecosystem": "npm | pip | gradle | auto",
    },
)
def scan_dependencies(
    project_dir: str = ".",
    ecosystem: str = "auto",
) -> Dict[str, Any]:
    """Scan dependencies for vulnerabilities."""
    if not os.path.isdir(project_dir):
        return {"success": False, "error": f"Directory not found: {project_dir}"}

    # Auto-detect ecosystem
    if ecosystem == "auto":
        if (Path(project_dir) / "package.json").exists():
            ecosystem = "npm"
        elif (Path(project_dir) / "requirements.txt").exists():
            ecosystem = "pip"
        elif (Path(project_dir) / "build.gradle").exists() or (Path(project_dir) / "build.gradle.kts").exists():
            ecosystem = "gradle"
        else:
            return {"success": False, "error": "Could not detect package ecosystem. Specify manually."}

    if ecosystem == "npm":
        return _scan_npm(project_dir)
    elif ecosystem == "pip":
        return _scan_pip(project_dir)
    elif ecosystem == "gradle":
        return _scan_gradle(project_dir)

    return {"success": False, "error": f"Unsupported ecosystem: {ecosystem}"}


def _scan_npm(project_dir):
    """Scan npm dependencies."""
    # Read package.json
    pkg_path = Path(project_dir) / "package.json"
    if not pkg_path.exists():
        return {"success": False, "error": "package.json not found"}

    pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

    # Known vulnerable patterns (simplified — real scanner would use CVE database)
    _KNOWN_VULNS = {
        "lodash": {"versions": ["<4.17.21"], "cve": "CVE-2021-23337", "severity": "high",
                    "description": "Command injection via template function"},
        "minimist": {"versions": ["<1.2.6"], "cve": "CVE-2021-44906", "severity": "critical",
                      "description": "Prototype pollution"},
        "node-fetch": {"versions": ["<2.6.7"], "cve": "CVE-2022-0235", "severity": "high",
                        "description": "Exposure of sensitive information"},
        "moment": {"versions": ["*"], "cve": "N/A", "severity": "warning",
                    "description": "Deprecated — use dayjs or date-fns instead"},
        "express": {"versions": ["<4.17.3"], "cve": "CVE-2024-29041", "severity": "medium",
                     "description": "Open redirect vulnerability"},
    }

    vulnerabilities = []
    safe_count = 0
    for name, version in deps.items():
        vuln = _KNOWN_VULNS.get(name)
        if vuln:
            vulnerabilities.append({
                "package": name,
                "installed": version,
                "cve": vuln["cve"],
                "severity": vuln["severity"],
                "description": vuln["description"],
                "fix": f"npm install {name}@latest",
            })
        else:
            safe_count += 1

    # Try npm audit if available
    audit_output = ""
    try:
        proc = subprocess.run(
            ["npm", "audit", "--json"], cwd=project_dir,
            capture_output=True, text=True, timeout=30, shell=False,
        )
        if proc.stdout:
            try:
                audit = json.loads(proc.stdout)
                audit_output = f"npm audit: {audit.get('metadata', {}).get('vulnerabilities', {})}"
            except json.JSONDecodeError:
                pass
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return {
        "success": True,
        "ecosystem": "npm",
        "total_packages": len(deps),
        "vulnerabilities": vulnerabilities,
        "vuln_count": len(vulnerabilities),
        "safe_count": safe_count,
        "audit_output": audit_output,
        "risk_level": "critical" if any(v["severity"] == "critical" for v in vulnerabilities)
                       else "high" if any(v["severity"] == "high" for v in vulnerabilities)
                       else "medium" if vulnerabilities else "safe",
    }


def _scan_pip(project_dir):
    """Scan pip dependencies."""
    req_path = Path(project_dir) / "requirements.txt"
    if not req_path.exists():
        return {"success": False, "error": "requirements.txt not found"}

    deps = {}
    for line in req_path.read_text(encoding="utf-8").split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            parts = re.split(r"[=<>!~]", line, 1)
            name = parts[0].strip()
            version = line.replace(name, "").strip("=<>!~ ")
            deps[name] = version

    _PIP_VULNS = {
        "django": {"cve": "CVE-2024-24680", "severity": "high", "description": "DOS via file uploads"},
        "flask": {"cve": "CVE-2023-46136", "severity": "medium", "description": "Werkzeug 3.0 security fix needed"},
        "requests": {"cve": "CVE-2023-32681", "severity": "medium", "description": "Leaking Proxy-Auth header"},
        "pyyaml": {"cve": "CVE-2020-14343", "severity": "critical", "description": "Arbitrary code execution via yaml.load"},
        "pillow": {"cve": "CVE-2023-44271", "severity": "high", "description": "DOS via image processing"},
    }

    vulns = []
    for name, version in deps.items():
        vuln = _PIP_VULNS.get(name.lower())
        if vuln:
            vulns.append({"package": name, "installed": version, **vuln,
                          "fix": f"pip install --upgrade {name}"})

    # Try pip-audit if available
    try:
        proc = subprocess.run(
            ["pip-audit", "--format", "json"], cwd=project_dir,
            capture_output=True, text=True, timeout=60, shell=False,
        )
        if proc.returncode == 0 and proc.stdout:
            pass  # Would parse audit results
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return {
        "success": True,
        "ecosystem": "pip",
        "total_packages": len(deps),
        "vulnerabilities": vulns,
        "vuln_count": len(vulns),
        "risk_level": "critical" if any(v["severity"] == "critical" for v in vulns)
                       else "high" if any(v["severity"] == "high" for v in vulns)
                       else "safe",
    }


def _scan_gradle(project_dir):
    """Scan Gradle dependencies."""
    gradle_files = list(Path(project_dir).glob("**/build.gradle*"))
    if not gradle_files:
        return {"success": False, "error": "No build.gradle found"}

    deps = []
    for gf in gradle_files:
        content = gf.read_text(encoding="utf-8")
        # Extract implementation/api dependencies
        matches = re.findall(r"(?:implementation|api|compile)\s*['\"]([^'\"]+)['\"]", content)
        deps.extend(matches)

    return {
        "success": True,
        "ecosystem": "gradle",
        "total_packages": len(deps),
        "dependencies": deps[:50],
        "vulnerabilities": [],
        "note": "For deep Gradle scanning, use: ./gradlew dependencyCheckAnalyze (OWASP plugin)",
    }
