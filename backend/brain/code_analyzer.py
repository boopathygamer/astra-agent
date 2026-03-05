"""
Code Analyzer — AST Parsing + 15 Vulnerability Detectors + Quality Scoring.
────────────────────────────────────────────────────────────────────────────
Deep code intelligence for the brain:
  - AST-based structural analysis
  - 15 security vulnerability detectors (OWASP Top 10+)
  - Code quality scoring (complexity, nesting, duplication)
  - Auto-fix suggestions for each vulnerability
"""

import ast
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

NL = "\n"


class VulnSeverity(Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Vulnerability:
    id: str = ""
    name: str = ""
    severity: VulnSeverity = VulnSeverity.LOW
    description: str = ""
    line: int = 0
    code_snippet: str = ""
    fix_suggestion: str = ""
    cwe_id: str = ""

    def summary(self):
        sev = self.severity.value.upper()
        return f"[{sev}] {self.name} (line {self.line}): {self.description}"


@dataclass
class CodeStructure:
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    global_vars: List[str] = field(default_factory=list)
    total_lines: int = 0
    blank_lines: int = 0
    comment_lines: int = 0
    code_lines: int = 0


@dataclass
class QualityScore:
    cyclomatic_complexity: float = 0.0
    max_nesting_depth: int = 0
    avg_function_length: float = 0.0
    longest_function: int = 0
    dead_code_count: int = 0
    duplication_ratio: float = 0.0
    overall_score: float = 0.0  # 0-100

    def grade(self):
        if self.overall_score >= 90:
            return "A"
        elif self.overall_score >= 80:
            return "B"
        elif self.overall_score >= 70:
            return "C"
        elif self.overall_score >= 60:
            return "D"
        return "F"


@dataclass
class CodeAnalysisReport:
    structure: CodeStructure = field(default_factory=CodeStructure)
    vulnerabilities: List[Vulnerability] = field(default_factory=list)
    quality: QualityScore = field(default_factory=QualityScore)
    language: str = "python"
    is_parseable: bool = True
    parse_error: str = ""

    @property
    def critical_vulns(self):
        return [v for v in self.vulnerabilities
                if v.severity in (VulnSeverity.CRITICAL, VulnSeverity.HIGH)]

    @property
    def security_score(self):
        if not self.vulnerabilities:
            return 1.0
        weights = {
            VulnSeverity.CRITICAL: 0.0,
            VulnSeverity.HIGH: 0.15,
            VulnSeverity.MEDIUM: 0.4,
            VulnSeverity.LOW: 0.7,
            VulnSeverity.INFO: 0.9,
        }
        scores = [weights.get(v.severity, 0.5) for v in self.vulnerabilities]
        return min(scores) if scores else 1.0

    def summary(self):
        crit = len(self.critical_vulns)
        total_v = len(self.vulnerabilities)
        grade = self.quality.grade()
        lines = [
            f"Code Analysis Report ({self.language})",
            f"  Structure: {len(self.structure.functions)} funcs, "
            f"{len(self.structure.classes)} classes, "
            f"{self.structure.code_lines} lines",
            f"  Quality: {grade} ({self.quality.overall_score:.0f}/100)",
            f"  Security: {total_v} vulns ({crit} critical/high)",
            f"  Score: {self.security_score:.2f}",
        ]
        return NL.join(lines)


class CodeAnalyzer:
    """
    Deep code analysis with AST parsing and security scanning.

    15 vulnerability detectors covering OWASP Top 10+:
    1. SQL Injection          9. Open Redirect
    2. XSS                   10. Weak Crypto
    3. Path Traversal        11. Info Leakage
    4. Command Injection     12. Race Condition
    5. Hardcoded Secrets     13. Buffer Issues
    6. Insecure Deserialize  14. Privilege Escalation
    7. SSRF                  15. Insecure Defaults
    8. CSRF
    """

    def __init__(self):
        self._detectors = [
            self._detect_sql_injection,
            self._detect_xss,
            self._detect_path_traversal,
            self._detect_command_injection,
            self._detect_hardcoded_secrets,
            self._detect_insecure_deserialization,
            self._detect_ssrf,
            self._detect_csrf_missing,
            self._detect_open_redirect,
            self._detect_weak_crypto,
            self._detect_info_leakage,
            self._detect_race_condition,
            self._detect_buffer_issues,
            self._detect_privilege_escalation,
            self._detect_insecure_defaults,
        ]

    def analyze(self, code: str, language: str = "python") -> CodeAnalysisReport:
        report = CodeAnalysisReport(language=language)

        # Parse structure
        if language == "python":
            report.structure = self._parse_python_structure(code)
            report.is_parseable = True
        else:
            report.structure = self._parse_generic_structure(code)

        # Run vulnerability detectors
        for detector in self._detectors:
            try:
                vulns = detector(code, language)
                report.vulnerabilities.extend(vulns)
            except Exception as e:
                logger.warning(f"Detector {detector.__name__} failed: {e}")

        # Calculate quality score
        report.quality = self._calculate_quality(code, report.structure)

        logger.info(report.summary())
        return report

    # ─── Structure Parsing ───

    def _parse_python_structure(self, code: str) -> CodeStructure:
        struct = CodeStructure()
        lines = code.split(NL)
        struct.total_lines = len(lines)
        struct.blank_lines = sum(1 for l in lines if not l.strip())
        struct.comment_lines = sum(1 for l in lines if l.strip().startswith("#"))
        struct.code_lines = struct.total_lines - struct.blank_lines

        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    struct.functions.append(node.name)
                elif isinstance(node, ast.AsyncFunctionDef):
                    struct.functions.append(f"async:{node.name}")
                elif isinstance(node, ast.ClassDef):
                    struct.classes.append(node.name)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        struct.imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    for alias in node.names:
                        struct.imports.append(f"{mod}.{alias.name}")
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            struct.global_vars.append(target.id)
        except SyntaxError:
            pass

        return struct

    def _parse_generic_structure(self, code: str) -> CodeStructure:
        struct = CodeStructure()
        lines = code.split(NL)
        struct.total_lines = len(lines)
        struct.blank_lines = sum(1 for l in lines if not l.strip())
        struct.code_lines = struct.total_lines - struct.blank_lines

        # Regex-based detection for JS/TS
        func_pattern = re.compile(
            r'(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\()')
        class_pattern = re.compile(r'class\s+(\w+)')
        import_pattern = re.compile(r'import\s+.*?from\s+["\'](.+?)["\']')

        for line in lines:
            fm = func_pattern.search(line)
            if fm:
                name = fm.group(1) or fm.group(2)
                if name:
                    struct.functions.append(name)
            cm = class_pattern.search(line)
            if cm:
                struct.classes.append(cm.group(1))
            im = import_pattern.search(line)
            if im:
                struct.imports.append(im.group(1))

        return struct

    # ─── 15 Vulnerability Detectors ───

    def _detect_sql_injection(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'execute\s*\(\s*["\'].*?%s', "String formatting in SQL"),
            (r'execute\s*\(\s*f["\']', "F-string in SQL query"),
            (r'execute\s*\(\s*["\'].*?\+', "Concatenation in SQL"),
            (r'cursor\.\w+\(\s*["\'].*?\{', "Format string in cursor"),
            (r'raw\s*\(\s*["\'].*?%', "Raw SQL with formatting"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    vulns.append(Vulnerability(
                        id="VULN-001", name="SQL Injection",
                        severity=VulnSeverity.CRITICAL,
                        description=desc,
                        line=i, code_snippet=line.strip()[:100],
                        fix_suggestion="Use parameterized queries",
                        cwe_id="CWE-89"))
        return vulns

    def _detect_xss(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'innerHTML\s*=', "Unsafe innerHTML assignment"),
            (r'document\.write\s*\(', "document.write usage"),
            (r'\.html\s*\(.*?\+', "jQuery .html() with concat"),
            (r'dangerouslySetInnerHTML', "React dangerouslySetInnerHTML"),
            (r'Markup\s*\(', "Flask Markup with user input"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line):
                    vulns.append(Vulnerability(
                        id="VULN-002", name="XSS",
                        severity=VulnSeverity.HIGH,
                        description=desc, line=i,
                        code_snippet=line.strip()[:100],
                        fix_suggestion="Sanitize/escape output",
                        cwe_id="CWE-79"))
        return vulns

    def _detect_path_traversal(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'open\s*\(.*?\+', "File open with concatenation"),
            (r'open\s*\(.*?format', "File open with format"),
            (r'os\.path\.join\s*\(.*?request', "Path join with user input"),
            (r'send_file\s*\(.*?\+', "send_file with concatenation"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    vulns.append(Vulnerability(
                        id="VULN-003", name="Path Traversal",
                        severity=VulnSeverity.HIGH,
                        description=desc, line=i,
                        code_snippet=line.strip()[:100],
                        fix_suggestion="Validate and sanitize file paths",
                        cwe_id="CWE-22"))
        return vulns

    def _detect_command_injection(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'os\.system\s*\(', "os.system usage"),
            (r'subprocess\.call\s*\(.*?shell\s*=\s*True', "shell=True"),
            (r'subprocess\.Popen\s*\(.*?shell\s*=\s*True', "Popen shell=True"),
            (r'eval\s*\(', "eval() usage"),
            (r'exec\s*\(', "exec() usage"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line):
                    vulns.append(Vulnerability(
                        id="VULN-004", name="Command Injection",
                        severity=VulnSeverity.CRITICAL,
                        description=desc, line=i,
                        code_snippet=line.strip()[:100],
                        fix_suggestion="Use subprocess with list args, no shell",
                        cwe_id="CWE-78"))
        return vulns

    def _detect_hardcoded_secrets(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'(?:password|passwd|pwd)\s*=\s*["\'][^"\']+["\']',
             "Hardcoded password"),
            (r'(?:api_key|apikey|api_secret)\s*=\s*["\'][^"\']+["\']',
             "Hardcoded API key"),
            (r'(?:secret|token|auth)\s*=\s*["\'][A-Za-z0-9+/=]{16,}["\']',
             "Hardcoded secret/token"),
            (r'(?:aws_access|aws_secret)\s*=\s*["\']',
             "Hardcoded AWS credentials"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    vulns.append(Vulnerability(
                        id="VULN-005", name="Hardcoded Secret",
                        severity=VulnSeverity.HIGH,
                        description=desc, line=i,
                        code_snippet=line.strip()[:80] + "...",
                        fix_suggestion="Use env vars or secret manager",
                        cwe_id="CWE-798"))
        return vulns

    def _detect_insecure_deserialization(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'pickle\.loads?\s*\(', "Unsafe pickle usage"),
            (r'yaml\.load\s*\((?!.*Loader)', "yaml.load without SafeLoader"),
            (r'marshal\.loads?\s*\(', "Unsafe marshal usage"),
            (r'shelve\.open\s*\(', "Unsafe shelve usage"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line):
                    vulns.append(Vulnerability(
                        id="VULN-006", name="Insecure Deserialization",
                        severity=VulnSeverity.HIGH,
                        description=desc, line=i,
                        code_snippet=line.strip()[:100],
                        fix_suggestion="Use json or yaml.safe_load",
                        cwe_id="CWE-502"))
        return vulns

    def _detect_ssrf(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'requests\.\w+\s*\(.*?request\.\w+', "Request with user URL"),
            (r'urllib\.request\.urlopen\s*\(.*?\+', "urlopen with concat"),
            (r'http\.client\.\w+\s*\(.*?\+', "HTTP client with concat"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    vulns.append(Vulnerability(
                        id="VULN-007", name="SSRF",
                        severity=VulnSeverity.HIGH,
                        description=desc, line=i,
                        code_snippet=line.strip()[:100],
                        fix_suggestion="Validate/whitelist URLs",
                        cwe_id="CWE-918"))
        return vulns

    def _detect_csrf_missing(self, code, lang) -> List[Vulnerability]:
        vulns = []
        if lang == "python":
            has_csrf = bool(re.search(r'csrf|CSRFProtect', code))
            has_forms = bool(re.search(
                r'@app\.route.*methods.*POST|@app\.post', code))
            if has_forms and not has_csrf:
                vulns.append(Vulnerability(
                    id="VULN-008", name="Missing CSRF Protection",
                    severity=VulnSeverity.MEDIUM,
                    description="POST endpoints without CSRF tokens",
                    fix_suggestion="Add CSRFProtect or csrf_token",
                    cwe_id="CWE-352"))
        return vulns

    def _detect_open_redirect(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'redirect\s*\(.*?request\.\w+', "Redirect with user input"),
            (r'Location.*?request\.\w+', "Location header with user input"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    vulns.append(Vulnerability(
                        id="VULN-009", name="Open Redirect",
                        severity=VulnSeverity.MEDIUM,
                        description=desc, line=i,
                        code_snippet=line.strip()[:100],
                        fix_suggestion="Validate redirect URLs",
                        cwe_id="CWE-601"))
        return vulns

    def _detect_weak_crypto(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'md5\s*\(', "Weak hash: MD5"),
            (r'sha1\s*\(', "Weak hash: SHA1"),
            (r'DES\b', "Weak cipher: DES"),
            (r'RC4\b', "Weak cipher: RC4"),
            (r'random\.random\s*\(', "Non-cryptographic random"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line):
                    vulns.append(Vulnerability(
                        id="VULN-010", name="Weak Cryptography",
                        severity=VulnSeverity.MEDIUM,
                        description=desc, line=i,
                        code_snippet=line.strip()[:100],
                        fix_suggestion="Use SHA-256+, AES, secrets module",
                        cwe_id="CWE-327"))
        return vulns

    def _detect_info_leakage(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'traceback\.print_exc', "Stack trace exposure"),
            (r'print\s*\(.*?password', "Password in print"),
            (r'logging\..*?password', "Password in logs"),
            (r'debug\s*=\s*True', "Debug mode enabled"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    vulns.append(Vulnerability(
                        id="VULN-011", name="Information Leakage",
                        severity=VulnSeverity.LOW,
                        description=desc, line=i,
                        code_snippet=line.strip()[:100],
                        fix_suggestion="Remove sensitive data from output",
                        cwe_id="CWE-200"))
        return vulns

    def _detect_race_condition(self, code, lang) -> List[Vulnerability]:
        vulns = []
        has_threads = bool(re.search(r'threading|Thread|Lock', code))
        has_shared = bool(re.search(r'global\s+\w+', code))
        if has_threads and has_shared and not re.search(r'Lock\(\)', code):
            vulns.append(Vulnerability(
                id="VULN-012", name="Race Condition",
                severity=VulnSeverity.MEDIUM,
                description="Shared state without locks",
                fix_suggestion="Use threading.Lock or queue",
                cwe_id="CWE-362"))
        return vulns

    def _detect_buffer_issues(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'ctypes\.\w+\s*\(', "ctypes usage (potential buffer issue)"),
            (r'struct\.unpack\s*\(', "struct.unpack (check bounds)"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line):
                    vulns.append(Vulnerability(
                        id="VULN-013", name="Buffer Issue",
                        severity=VulnSeverity.LOW,
                        description=desc, line=i,
                        code_snippet=line.strip()[:100],
                        fix_suggestion="Validate buffer sizes",
                        cwe_id="CWE-120"))
        return vulns

    def _detect_privilege_escalation(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'os\.setuid\s*\(0\)', "Setting UID to root"),
            (r'chmod\s*\(.*?0?777', "chmod 777"),
            (r'os\.chmod\s*\(.*?0o777', "os.chmod 777"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line):
                    vulns.append(Vulnerability(
                        id="VULN-014", name="Privilege Escalation",
                        severity=VulnSeverity.CRITICAL,
                        description=desc, line=i,
                        code_snippet=line.strip()[:100],
                        fix_suggestion="Use least privilege principle",
                        cwe_id="CWE-269"))
        return vulns

    def _detect_insecure_defaults(self, code, lang) -> List[Vulnerability]:
        vulns = []
        patterns = [
            (r'verify\s*=\s*False', "SSL verification disabled"),
            (r'CORS\s*\(.*?\*', "CORS allows all origins"),
            (r'allow_all\s*=\s*True', "Allow all enabled"),
            (r'secure\s*=\s*False', "Secure flag disabled"),
        ]
        for i, line in enumerate(code.split(NL), 1):
            for pattern, desc in patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    vulns.append(Vulnerability(
                        id="VULN-015", name="Insecure Default",
                        severity=VulnSeverity.MEDIUM,
                        description=desc, line=i,
                        code_snippet=line.strip()[:100],
                        fix_suggestion="Use secure defaults",
                        cwe_id="CWE-276"))
        return vulns

    # ─── Quality Scoring ───

    def _calculate_quality(self, code, structure) -> QualityScore:
        q = QualityScore()
        lines = code.split(NL)

        # Cyclomatic complexity (branches per 100 lines)
        branches = sum(1 for l in lines if re.search(
            r'\b(if|elif|for|while|except|and|or)\b', l))
        q.cyclomatic_complexity = (
            branches / max(structure.code_lines, 1)) * 100

        # Nesting depth
        max_indent = 0
        for line in lines:
            if line.strip():
                indent = len(line) - len(line.lstrip())
                spaces = indent if line[0:1] == ' ' else indent * 4
                max_indent = max(max_indent, spaces // 4)
        q.max_nesting_depth = max_indent

        # Function lengths (heuristic)
        func_lengths = []
        in_func = False
        func_lines = 0
        base_indent = 0
        for line in lines:
            stripped = line.strip()
            indent = len(line) - len(line.lstrip()) if stripped else 0
            if re.match(r'\s*def\s+', line) or re.match(r'\s*async\s+def\s+', line):
                if in_func and func_lines > 0:
                    func_lengths.append(func_lines)
                in_func = True
                func_lines = 0
                base_indent = indent
            elif in_func:
                if stripped and indent <= base_indent and not stripped.startswith('#'):
                    func_lengths.append(func_lines)
                    in_func = False
                    func_lines = 0
                else:
                    func_lines += 1
        if in_func and func_lines > 0:
            func_lengths.append(func_lines)

        if func_lengths:
            q.avg_function_length = sum(func_lengths) / len(func_lengths)
            q.longest_function = max(func_lengths)

        # Duplication (simple check: identical non-trivial lines)
        non_trivial = [l.strip() for l in lines
                       if l.strip() and len(l.strip()) > 20]
        if non_trivial:
            unique = set(non_trivial)
            q.duplication_ratio = 1.0 - len(unique) / len(non_trivial)

        # Overall score (100-point scale)
        score = 100.0
        score -= min(q.cyclomatic_complexity, 30)
        score -= min(q.max_nesting_depth * 3, 15)
        if q.avg_function_length > 50:
            score -= 10
        if q.longest_function > 100:
            score -= 10
        score -= min(q.duplication_ratio * 20, 15)
        q.overall_score = max(0, min(100, score))

        return q
