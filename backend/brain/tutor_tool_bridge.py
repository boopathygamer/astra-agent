"""
Tutor Tool Bridge — Live Tool-Powered Teaching
═══════════════════════════════════════════════
Gives the tutor engine real-time access to system tools during lessons:

  🔬 Code Executor   → Run code snippets and show actual output
  🌐 Web Search      → Pull real-time facts and verify claims
  🧮 Calculator      → Perform math demonstrations
  📊 Data Analyzer   → Show real data patterns and visualizations
  📝 Writer          → Generate structured explanations and summaries

Each tool call is wrapped with:
  - Teaching-friendly output formatting
  - Error isolation (tool failures never crash the lesson)
  - Timing metrics for performance awareness
  - Output annotation with pedagogical context

Usage:
    bridge = TutorToolBridge(agent_controller=controller)
    demo = bridge.demonstrate_with_code("print(2 ** 10)", language="python")
    facts = bridge.live_search("what causes recursion stack overflow")
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Data Models
# ══════════════════════════════════════════════════════════════

class ToolCategory(Enum):
    """Categories of teaching tools."""
    CODE_EXECUTOR = "code_executor"
    WEB_SEARCH = "web_search"
    CALCULATOR = "calculator"
    DATA_ANALYZER = "data_analyzer"
    WRITER = "writer"
    KNOWLEDGE = "knowledge"


@dataclass
class ToolDemoResult:
    """Result of a tool demonstration during a tutoring session."""
    tool: ToolCategory
    success: bool
    raw_output: str = ""
    formatted_output: str = ""
    error_message: str = ""
    execution_ms: float = 0.0
    teaching_annotation: str = ""
    source_url: str = ""

    def to_teaching_block(self) -> str:
        """Format as a teaching-ready block for injection into prompts."""
        if not self.success:
            return (
                f"⚠️ Tool Demo ({self.tool.value}) encountered an issue:\n"
                f"   {self.error_message}\n"
                f"   (This is a teaching moment: tools can fail! Always handle errors.)\n"
            )
        parts = [f"\n🔬 LIVE DEMONSTRATION [{self.tool.value}]:"]
        if self.teaching_annotation:
            parts.append(f"📌 {self.teaching_annotation}")
        parts.append(f"```\n{self.formatted_output}\n```")
        if self.execution_ms > 0:
            parts.append(f"⏱️ Executed in {self.execution_ms:.0f}ms")
        if self.source_url:
            parts.append(f"🔗 Source: {self.source_url}")
        return "\n".join(parts)


@dataclass
class VerificationResult:
    """Result of cross-referencing a claim against multiple sources."""
    claim: str = ""
    confidence: float = 0.0
    sources: List[Dict[str, str]] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    verified: bool = False
    summary: str = ""

    def to_badge(self) -> str:
        """Return a trust badge for the claim."""
        if self.confidence >= 0.8:
            return f"✅ Verified ({self.confidence:.0%}) — {len(self.sources)} sources"
        elif self.confidence >= 0.5:
            return f"⚠️ Partially Verified ({self.confidence:.0%})"
        else:
            return f"❓ Unverified ({self.confidence:.0%}) — treat with caution"


# ══════════════════════════════════════════════════════════════
# Tutor Tool Bridge
# ══════════════════════════════════════════════════════════════

class TutorToolBridge:
    """
    Bridges the tutoring engine to real system tools for live demonstrations.

    Instead of the tutor just *saying* what code does, it can *run* the code
    and show the actual output. Instead of guessing facts, it can *search*
    and cite real sources.

    This bridge wraps each tool with:
      1. Teaching-friendly output formatting
      2. Error isolation (tool failures → teaching moments)
      3. Timing metrics
      4. Pedagogical annotations
    """

    # Maximum output length per tool to keep teaching focused
    MAX_OUTPUT_LENGTH = 2000
    # Timeout for individual tool calls (seconds)
    TOOL_TIMEOUT = 30.0

    def __init__(
        self,
        agent_controller=None,
        generate_fn: Optional[Callable] = None,
    ):
        self._agent = agent_controller
        self._generate_fn = generate_fn
        self._demo_history: List[ToolDemoResult] = []
        self._tools_available: Dict[str, bool] = {}
        self._probe_available_tools()
        logger.info(
            "🔬 TutorToolBridge initialized — available tools: %s",
            [k for k, v in self._tools_available.items() if v],
        )

    def _probe_available_tools(self) -> None:
        """Detect which tools are available in the current environment."""
        tool_checks = {
            "code_executor": "agents.tools.code_executor",
            "web_search": "agents.tools.web_search",
            "calculator": "agents.tools.calculator",
            "data_analyzer": "agents.tools.data_analyzer",
            "writer": "agents.tools.writer",
            "knowledge": "agents.tools.knowledge",
        }
        for name, module_path in tool_checks.items():
            try:
                __import__(module_path)
                self._tools_available[name] = True
            except ImportError:
                self._tools_available[name] = False

    @property
    def available_tools(self) -> List[str]:
        """List of tool names currently available."""
        return [k for k, v in self._tools_available.items() if v]

    @property
    def demo_count(self) -> int:
        """Total demonstrations performed in this session."""
        return len(self._demo_history)

    # ──────────────────────────────────────
    # Code Demonstration
    # ──────────────────────────────────────

    def demonstrate_with_code(
        self,
        code: str,
        language: str = "python",
        annotation: str = "",
        show_errors: bool = True,
    ) -> ToolDemoResult:
        """
        Run a code snippet and return the annotated output for teaching.

        This lets the tutor show students what code ACTUALLY does
        instead of just explaining theoretically.

        Args:
            code: The code to execute
            language: Programming language
            annotation: Teaching context (e.g., "Watch what happens when we divide by zero")
            show_errors: If True, show errors as teaching moments

        Returns:
            ToolDemoResult with formatted output
        """
        result = ToolDemoResult(
            tool=ToolCategory.CODE_EXECUTOR,
            teaching_annotation=annotation or f"Running {language} code demonstration",
        )
        start = time.monotonic()

        try:
            from agents.tools.code_executor import execute_code
            exec_result = execute_code(code=code, language=language, timeout=15)
            elapsed = (time.monotonic() - start) * 1000

            result.execution_ms = elapsed
            raw_output = ""
            if isinstance(exec_result, dict):
                raw_output = exec_result.get("output", "") or exec_result.get("result", "")
                error = exec_result.get("error", "")
                if error and show_errors:
                    raw_output += f"\n⚠️ Error: {error}"
                    result.teaching_annotation += " (Notice the error — this is a common pitfall!)"
            else:
                raw_output = str(exec_result)

            result.raw_output = raw_output
            result.formatted_output = self._truncate(raw_output)
            result.success = True

        except ImportError:
            result.error_message = "Code executor not available in this environment"
            result.success = False
        except Exception as exc:
            elapsed = (time.monotonic() - start) * 1000
            result.execution_ms = elapsed
            if show_errors:
                result.error_message = f"{type(exc).__name__}: {exc}"
                result.formatted_output = (
                    f"❌ Code raised: {type(exc).__name__}: {exc}\n"
                    f"💡 This is what happens in real programs — always handle exceptions!"
                )
                result.success = True  # Error IS the demo
                result.teaching_annotation = "Error demonstration — this is expected!"
            else:
                result.error_message = str(exc)
                result.success = False

        self._demo_history.append(result)
        logger.info(
            "🔬 Code demo: success=%s, output_len=%d, time=%.0fms",
            result.success, len(result.formatted_output), result.execution_ms,
        )
        return result

    # ──────────────────────────────────────
    # Live Web Search
    # ──────────────────────────────────────

    def live_search(
        self,
        query: str,
        max_results: int = 3,
        annotation: str = "",
    ) -> ToolDemoResult:
        """
        Search the web for real-time facts to support teaching.

        Returns curated, teaching-formatted search results with sources.
        """
        result = ToolDemoResult(
            tool=ToolCategory.WEB_SEARCH,
            teaching_annotation=annotation or f"Searching: '{query}'",
        )
        start = time.monotonic()

        try:
            from agents.tools.web_search import advanced_web_search
            search_result = advanced_web_search(
                query=query,
                network="surface",
                max_results=max_results,
                deep_scrape=False,
            )
            elapsed = (time.monotonic() - start) * 1000
            result.execution_ms = elapsed

            items = search_result.get("results", [])
            if not items:
                result.formatted_output = "No results found for this query."
                result.success = True
                self._demo_history.append(result)
                return result

            lines = [f"📚 Found {len(items)} source(s):\n"]
            for i, item in enumerate(items[:max_results], 1):
                title = item.get("title", "Untitled")
                snippet = item.get("snippet", "")[:200]
                url = item.get("href", "")
                lines.append(f"  {i}. **{title}**")
                lines.append(f"     {snippet}")
                if url:
                    lines.append(f"     🔗 {url}")
                lines.append("")

            result.raw_output = str(items)
            result.formatted_output = "\n".join(lines)
            result.success = True
            if items:
                result.source_url = items[0].get("href", "")

        except ImportError:
            result.error_message = "Web search not available"
            result.success = False
        except Exception as exc:
            result.execution_ms = (time.monotonic() - start) * 1000
            result.error_message = f"Search failed: {exc}"
            result.success = False

        self._demo_history.append(result)
        return result

    # ──────────────────────────────────────
    # Calculator
    # ──────────────────────────────────────

    def calculate(
        self,
        expression: str,
        annotation: str = "",
    ) -> ToolDemoResult:
        """
        Perform a math calculation and show the result with working.

        Supports basic arithmetic, algebra, and common math functions.
        """
        result = ToolDemoResult(
            tool=ToolCategory.CALCULATOR,
            teaching_annotation=annotation or f"Calculating: {expression}",
        )
        start = time.monotonic()

        try:
            from agents.tools.calculator import evaluate_expression
            calc_result = evaluate_expression(expression)
            elapsed = (time.monotonic() - start) * 1000
            result.execution_ms = elapsed

            if isinstance(calc_result, dict):
                answer = calc_result.get("result", calc_result.get("answer", ""))
                steps = calc_result.get("steps", "")
            else:
                answer = str(calc_result)
                steps = ""

            lines = [f"🧮 {expression} = **{answer}**"]
            if steps:
                lines.append(f"\n📝 Working:\n{steps}")

            result.raw_output = str(answer)
            result.formatted_output = "\n".join(lines)
            result.success = True

        except ImportError:
            # Fallback: use Python eval for basic math (safe subset)
            try:
                import ast
                # Only allow safe math operations
                tree = ast.parse(expression, mode='eval')
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Call, ast.Attribute)):
                        raise ValueError("Complex expressions not supported in fallback")
                answer = eval(compile(tree, "<calc>", "eval"))  # noqa: S307
                result.raw_output = str(answer)
                result.formatted_output = f"🧮 {expression} = **{answer}**"
                result.success = True
                result.execution_ms = (time.monotonic() - start) * 1000
            except Exception as calc_err:
                result.error_message = f"Calculator not available: {calc_err}"
                result.success = False
        except Exception as exc:
            result.execution_ms = (time.monotonic() - start) * 1000
            result.error_message = f"Calculation failed: {exc}"
            result.success = False

        self._demo_history.append(result)
        return result

    # ──────────────────────────────────────
    # Data Analysis
    # ──────────────────────────────────────

    def analyze_data(
        self,
        data_description: str,
        analysis_type: str = "summary",
        annotation: str = "",
    ) -> ToolDemoResult:
        """
        Perform data analysis to support teaching with real patterns.

        Args:
            data_description: Description of data to analyze or generate
            analysis_type: Type of analysis (summary, trend, comparison)
            annotation: Teaching context
        """
        result = ToolDemoResult(
            tool=ToolCategory.DATA_ANALYZER,
            teaching_annotation=annotation or f"Analyzing: {data_description[:60]}",
        )
        start = time.monotonic()

        try:
            from agents.tools.data_analyzer import analyze
            analysis = analyze(data_description, analysis_type=analysis_type)
            elapsed = (time.monotonic() - start) * 1000
            result.execution_ms = elapsed

            if isinstance(analysis, dict):
                output = analysis.get("result", "") or analysis.get("analysis", "")
            else:
                output = str(analysis)

            result.raw_output = output
            result.formatted_output = f"📊 Data Analysis:\n{self._truncate(output)}"
            result.success = True

        except ImportError:
            result.error_message = "Data analyzer not available"
            result.success = False
        except Exception as exc:
            result.execution_ms = (time.monotonic() - start) * 1000
            result.error_message = f"Analysis failed: {exc}"
            result.success = False

        self._demo_history.append(result)
        return result

    # ──────────────────────────────────────
    # Claim Verification (Multi-Source)
    # ──────────────────────────────────────

    def verify_claim(
        self,
        claim: str,
        topic_context: str = "",
    ) -> VerificationResult:
        """
        Cross-reference a teaching claim against multiple web sources.

        Returns a VerificationResult with confidence score and sources.
        This is the core of the "truth-first" teaching approach.
        """
        verification = VerificationResult(claim=claim)
        sources_found: List[Dict[str, str]] = []
        supporting = 0
        contradicting = 0

        # Strategy 1: Direct web search for the claim
        search_result = self.live_search(
            query=f'"{claim[:80]}" facts',
            max_results=3,
            annotation="Verifying claim against web sources",
        )
        if search_result.success and search_result.raw_output:
            try:
                import ast
                items = ast.literal_eval(search_result.raw_output)
                if isinstance(items, list):
                    for item in items:
                        if isinstance(item, dict):
                            sources_found.append({
                                "title": item.get("title", ""),
                                "url": item.get("href", ""),
                                "snippet": item.get("snippet", "")[:200],
                            })
            except (ValueError, SyntaxError):
                pass

        # Strategy 2: Search for counter-evidence
        counter_result = self.live_search(
            query=f'"{claim[:60]}" wrong OR myth OR misconception',
            max_results=2,
            annotation="Checking for counter-evidence",
        )

        # Score sources
        if sources_found:
            supporting = len(sources_found)
            verification.sources = sources_found

        # Use LLM to evaluate if sources support or contradict
        if self._generate_fn and sources_found:
            try:
                source_text = "\n".join(
                    f"- {s['title']}: {s['snippet']}" for s in sources_found[:3]
                )
                eval_prompt = (
                    f"Does the following claim appear to be supported by these sources?\n"
                    f"CLAIM: {claim}\n"
                    f"SOURCES:\n{source_text}\n\n"
                    f"Reply with ONLY a JSON object: "
                    f'{{"supported": true/false, "confidence": 0.0-1.0, "reason": "brief explanation"}}'
                )
                eval_result = self._call_llm(eval_prompt)
                import json
                import re
                match = re.search(r'\{.*\}', eval_result, re.DOTALL)
                if match:
                    data = json.loads(match.group(0))
                    verification.confidence = float(data.get("confidence", 0.5))
                    verification.verified = bool(data.get("supported", False))
                    verification.summary = data.get("reason", "")
            except Exception as exc:
                logger.warning("Claim verification LLM eval failed: %s", exc)
                # Fallback: basic heuristic
                verification.confidence = min(1.0, supporting * 0.25)
                verification.verified = supporting >= 2
        else:
            verification.confidence = min(1.0, supporting * 0.25) if supporting else 0.0
            verification.verified = supporting >= 2

        logger.info(
            "🔍 Claim verification: conf=%.2f, sources=%d, verified=%s",
            verification.confidence, len(verification.sources), verification.verified,
        )
        return verification

    # ──────────────────────────────────────
    # Bulk Demo: Run Multiple Demonstrations
    # ──────────────────────────────────────

    def run_teaching_demos(
        self,
        topic: str,
        student_level: str = "beginner",
    ) -> List[ToolDemoResult]:
        """
        Auto-generate and run relevant demonstrations for a topic.

        Uses LLM to decide what demos would be most educational,
        then executes them and returns formatted results.
        """
        demos: List[ToolDemoResult] = []

        if not self._generate_fn:
            return demos

        try:
            plan_prompt = (
                f"You are planning live demonstrations for a {student_level} student "
                f"learning about: {topic}\n\n"
                f"Available tools: {self.available_tools}\n\n"
                f"Generate 1-2 demonstrations as a JSON array:\n"
                f'[{{"tool": "code_executor|calculator|web_search", '
                f'"input": "the code/expression/query", '
                f'"annotation": "why this demo matters"}}]\n'
                f"Choose demos that SHOW rather than TELL. "
                f"Output ONLY the JSON array."
            )
            plan_result = self._call_llm(plan_prompt)

            import json
            import re
            match = re.search(r'\[.*\]', plan_result, re.DOTALL)
            if not match:
                return demos

            items = json.loads(match.group(0))
            for item in items[:2]:
                tool = item.get("tool", "")
                input_val = item.get("input", "")
                annotation = item.get("annotation", "")

                if tool == "code_executor" and input_val:
                    demos.append(self.demonstrate_with_code(
                        code=input_val, annotation=annotation,
                    ))
                elif tool == "calculator" and input_val:
                    demos.append(self.calculate(
                        expression=input_val, annotation=annotation,
                    ))
                elif tool == "web_search" and input_val:
                    demos.append(self.live_search(
                        query=input_val, annotation=annotation,
                    ))

        except Exception as exc:
            logger.warning("Auto-demo generation failed: %s", exc)

        return demos

    # ──────────────────────────────────────
    # Session Summary
    # ──────────────────────────────────────

    def get_session_summary(self) -> Dict[str, Any]:
        """Get a summary of all tool demos performed in this session."""
        successful = sum(1 for d in self._demo_history if d.success)
        by_tool: Dict[str, int] = {}
        for d in self._demo_history:
            by_tool[d.tool.value] = by_tool.get(d.tool.value, 0) + 1

        return {
            "total_demos": len(self._demo_history),
            "successful": successful,
            "failed": len(self._demo_history) - successful,
            "by_tool": by_tool,
            "total_execution_ms": sum(d.execution_ms for d in self._demo_history),
            "tools_available": self.available_tools,
        }

    # ──────────────────────────────────────
    # Internals
    # ──────────────────────────────────────

    def _truncate(self, text: str) -> str:
        """Truncate output to keep teaching focused."""
        if len(text) <= self.MAX_OUTPUT_LENGTH:
            return text
        return text[:self.MAX_OUTPUT_LENGTH] + "\n... (output truncated for clarity)"

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM safely."""
        if not self._generate_fn:
            return ""
        try:
            result = self._generate_fn(prompt)
            if hasattr(result, "answer"):
                return result.answer
            return str(result)
        except Exception as exc:
            logger.error("TutorToolBridge LLM call failed: %s", exc)
            return ""
