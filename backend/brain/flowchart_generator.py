"""
Flowchart Generator — Visual Teaching with Mermaid Diagrams
───────────────────────────────────────────────────────────
Generates rich Mermaid flowchart diagrams for concept visualization.
Used by the Expert Tutor to teach with visual decision trees,
process flows, concept maps, and anti-pattern diagrams.

Flowchart Types:
  📊 Decision Flowchart  — "Should I use A or B?" with branching logic
  📋 Process Flowchart   — Step-by-step with checkpoints
  ⚠️ Anti-Pattern Chart  — Red (bad) vs Green (good) comparison
  🗺️ Concept Map         — Relationships between concepts
  🎯 Learning Path Map   — Student's progression through curriculum
"""

import logging
import re
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class FlowchartType(Enum):
    """Types of flowcharts the generator can produce."""
    DECISION = "decision"           # Branching decision tree
    PROCESS = "process"             # Step-by-step process flow
    ANTI_PATTERN = "anti_pattern"   # Red/green comparison
    CONCEPT_MAP = "concept_map"     # Concept relationship graph
    LEARNING_PATH = "learning_path" # Curriculum progression
    COMPARISON = "comparison"       # Side-by-side approach comparison
    DEBUG_TRACE = "debug_trace"     # Error investigation flow


# ──────────────────────────────────────────────
# Fallback Templates (when LLM is unavailable)
# ──────────────────────────────────────────────

_TEMPLATE_DECISION = """\
graph TD
    START["🎯 {topic}"] --> Q1{{"Key Question 1"}}
    Q1 -->|"Option A"| A["Approach A"]
    Q1 -->|"Option B"| B["Approach B"]
    A --> CHECK_A{{"Evaluate A"}}
    B --> CHECK_B{{"Evaluate B"}}
    CHECK_A -->|"✅ Works"| SUCCESS_A["Use Approach A"]
    CHECK_A -->|"❌ Fails"| RECONSIDER["Reconsider"]
    CHECK_B -->|"✅ Works"| SUCCESS_B["Use Approach B"]
    CHECK_B -->|"❌ Fails"| RECONSIDER
    RECONSIDER --> Q1

    style SUCCESS_A fill:#44bb44,color:#fff
    style SUCCESS_B fill:#44bb44,color:#fff
    style RECONSIDER fill:#ff9944,color:#fff"""

_TEMPLATE_PROCESS = """\
graph TD
    S["🚀 START: {topic}"] --> STEP1["Step 1: Understand the Problem"]
    STEP1 --> CHECK1{{"✅ Checkpoint 1"}}
    CHECK1 -->|"Pass"| STEP2["Step 2: Plan the Approach"]
    CHECK1 -->|"Fail"| REVIEW1["📖 Review Fundamentals"]
    REVIEW1 --> STEP1
    STEP2 --> STEP3["Step 3: Implement Solution"]
    STEP3 --> CHECK2{{"✅ Checkpoint 2"}}
    CHECK2 -->|"Pass"| STEP4["Step 4: Test & Verify"]
    CHECK2 -->|"Fail"| DEBUG["🔧 Debug & Fix"]
    DEBUG --> STEP3
    STEP4 --> DONE["🎉 COMPLETE"]

    style S fill:#4488ff,color:#fff
    style DONE fill:#00aa00,color:#fff
    style DEBUG fill:#ff9944,color:#fff
    style REVIEW1 fill:#ff9944,color:#fff"""

_TEMPLATE_ANTI_PATTERN = """\
graph TD
    START["🎯 Task: {topic}"] --> DECISION{{"Choose Approach"}}
    DECISION -->|"❌ Bad Path"| BAD["Wrong Approach"]
    DECISION -->|"✅ Good Path"| GOOD["Correct Approach"]
    BAD --> SYMPTOMS["⚠️ Warning Signs"]
    SYMPTOMS --> FAIL["💥 FAILURE"]
    GOOD --> VALIDATE["✅ Validate Results"]
    VALIDATE --> SUCCESS["🎉 SUCCESS"]
    FAIL -->|"🔧 Recovery"| FIX["Apply Fix + Add Tests"]
    FIX --> SUCCESS

    style BAD fill:#ff4444,color:#fff
    style FAIL fill:#cc0000,color:#fff
    style SYMPTOMS fill:#ff6644,color:#fff
    style GOOD fill:#44bb44,color:#fff
    style SUCCESS fill:#00aa00,color:#fff
    style VALIDATE fill:#66cc66,color:#fff
    style DECISION fill:#4488ff,color:#fff"""

_TEMPLATE_CONCEPT_MAP = """\
graph LR
    CORE["🧠 {topic}"] --> C1["Concept 1"]
    CORE --> C2["Concept 2"]
    CORE --> C3["Concept 3"]
    C1 --> SC1["Sub-concept 1A"]
    C1 --> SC2["Sub-concept 1B"]
    C2 --> SC3["Sub-concept 2A"]
    C3 --> SC4["Sub-concept 3A"]
    SC1 -.->|"relates to"| SC3
    SC2 -.->|"depends on"| SC4

    style CORE fill:#4488ff,color:#fff
    style C1 fill:#6644cc,color:#fff
    style C2 fill:#6644cc,color:#fff
    style C3 fill:#6644cc,color:#fff"""

_TEMPLATE_LEARNING_PATH = """\
graph LR
    LP1["📚 Foundation"] --> LP2["🔧 Core Skills"]
    LP2 --> LP3["⚡ Application"]
    LP3 --> LP4["🏆 Mastery"]

    LP1 --- L1A["Basics of {topic}"]
    LP1 --- L1B["Key Terminology"]
    LP2 --- L2A["Core Techniques"]
    LP2 --- L2B["Common Patterns"]
    LP3 --- L3A["Real-World Projects"]
    LP3 --- L3B["Problem Solving"]
    LP4 --- L4A["Expert Insights"]
    LP4 --- L4B["Edge Cases"]

    style LP1 fill:#4488ff,color:#fff
    style LP2 fill:#6644cc,color:#fff
    style LP3 fill:#cc6644,color:#fff
    style LP4 fill:#44bb44,color:#fff"""

_TEMPLATE_COMPARISON = """\
graph TD
    TITLE["⚖️ Comparison: {topic}"] --> A["Approach A"]
    TITLE --> B["Approach B"]

    A --> A_PRO["✅ Pros of A"]
    A --> A_CON["❌ Cons of A"]
    B --> B_PRO["✅ Pros of B"]
    B --> B_CON["❌ Cons of B"]

    A_PRO --> VERDICT{{"Best Choice?"}}
    A_CON --> VERDICT
    B_PRO --> VERDICT
    B_CON --> VERDICT

    VERDICT -->|"Context A"| USE_A["Use Approach A"]
    VERDICT -->|"Context B"| USE_B["Use Approach B"]

    style A fill:#4488ff,color:#fff
    style B fill:#cc6644,color:#fff
    style USE_A fill:#44bb44,color:#fff
    style USE_B fill:#44bb44,color:#fff"""

_TEMPLATE_DEBUG = """\
graph TD
    BUG["🐛 Bug Encountered"] --> REPRODUCE{{"Can Reproduce?"}}
    REPRODUCE -->|"Yes"| ISOLATE["🔍 Isolate the Issue"]
    REPRODUCE -->|"No"| LOGS["📋 Check Logs & Traces"]
    LOGS --> REPRODUCE

    ISOLATE --> HYPOTHESIS{{"Form Hypothesis"}}
    HYPOTHESIS --> TEST["🧪 Test Hypothesis"]
    TEST -->|"Confirmed"| FIX["🔧 Apply Fix"]
    TEST -->|"Rejected"| HYPOTHESIS
    FIX --> VERIFY["✅ Verify Fix"]
    VERIFY -->|"Pass"| DONE["🎉 Bug Fixed"]
    VERIFY -->|"Fail"| ISOLATE

    style BUG fill:#ff4444,color:#fff
    style DONE fill:#00aa00,color:#fff
    style FIX fill:#44bb44,color:#fff
    style ISOLATE fill:#4488ff,color:#fff"""

_TEMPLATES = {
    FlowchartType.DECISION: _TEMPLATE_DECISION,
    FlowchartType.PROCESS: _TEMPLATE_PROCESS,
    FlowchartType.ANTI_PATTERN: _TEMPLATE_ANTI_PATTERN,
    FlowchartType.CONCEPT_MAP: _TEMPLATE_CONCEPT_MAP,
    FlowchartType.LEARNING_PATH: _TEMPLATE_LEARNING_PATH,
    FlowchartType.COMPARISON: _TEMPLATE_COMPARISON,
    FlowchartType.DEBUG_TRACE: _TEMPLATE_DEBUG,
}


# ──────────────────────────────────────────────
# ASCII Rendering (for terminals without Mermaid)
# ──────────────────────────────────────────────

def render_ascii_flowchart(steps: List[str], title: str = "") -> str:
    """
    Render a simple ASCII vertical flowchart from a list of steps.
    Used as a fallback when Mermaid rendering isn't available.
    """
    if not steps:
        return ""

    max_width = max(len(s) for s in steps)
    box_width = max(max_width + 4, 30)

    lines = []
    if title:
        lines.append(f"  {'═' * box_width}")
        lines.append(f"  ║ {title:^{box_width-4}} ║")
        lines.append(f"  {'═' * box_width}")
        lines.append(f"  {'':>{box_width//2}}│")

    for i, step in enumerate(steps):
        # Box
        lines.append(f"  ┌{'─' * (box_width-2)}┐")
        lines.append(f"  │ {step:<{box_width-4}} │")
        lines.append(f"  └{'─' * (box_width-2)}┘")

        # Arrow (except after last step)
        if i < len(steps) - 1:
            lines.append(f"  {'':>{box_width//2}}│")
            lines.append(f"  {'':>{box_width//2}}▼")

    return "\n".join(lines)


def render_ascii_comparison(
    left_title: str, left_items: List[str],
    right_title: str, right_items: List[str],
) -> str:
    """Render a side-by-side ASCII comparison chart."""
    col_width = 30
    lines = []

    lines.append(f"  ┌{'─' * col_width}┬{'─' * col_width}┐")
    lines.append(f"  │ ❌ {left_title:<{col_width-5}} │ ✅ {right_title:<{col_width-5}} │")
    lines.append(f"  ├{'─' * col_width}┼{'─' * col_width}┤")

    max_items = max(len(left_items), len(right_items))
    for i in range(max_items):
        left = left_items[i] if i < len(left_items) else ""
        right = right_items[i] if i < len(right_items) else ""
        lines.append(f"  │ {left:<{col_width-2}} │ {right:<{col_width-2}} │")

    lines.append(f"  └{'─' * col_width}┴{'─' * col_width}┘")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Flowchart Generator Engine
# ──────────────────────────────────────────────

class FlowchartGenerator:
    """
    Generates rich Mermaid flowcharts and ASCII diagrams for visual teaching.

    Can produce:
    - Decision flowcharts for choosing between approaches
    - Process flowcharts for step-by-step procedures
    - Anti-pattern flowcharts with red/green paths
    - Concept maps showing relationships
    - Learning path maps for curriculum visualization
    - Comparison charts for evaluating options
    - Debug trace flowcharts for investigation
    """

    def __init__(self, generate_fn: Optional[Callable] = None):
        """
        Args:
            generate_fn: Optional LLM generation function for creating
                        customized flowcharts. Falls back to templates.
        """
        self.generate_fn = generate_fn
        logger.info("📊 FlowchartGenerator initialized")

    def generate(
        self,
        topic: str,
        chart_type: FlowchartType = FlowchartType.PROCESS,
        context: str = "",
        use_llm: bool = True,
    ) -> str:
        """
        Generate a Mermaid flowchart for the given topic.

        Args:
            topic: Subject to visualize
            chart_type: Type of flowchart to generate
            context: Additional context for LLM customization
            use_llm: Whether to use LLM for custom charts (vs templates)

        Returns:
            Mermaid diagram source code
        """
        # Try LLM-generated custom flowchart first
        if use_llm and self.generate_fn:
            custom = self._generate_with_llm(topic, chart_type, context)
            if custom and self._validate_mermaid(custom):
                return custom

        # Fallback to template
        template = _TEMPLATES.get(chart_type, _TEMPLATE_PROCESS)
        return template.format(topic=self._safe_mermaid_text(topic))

    def generate_anti_pattern_chart(
        self,
        bad_approach: str,
        good_approach: str,
        failure_reason: str,
        topic: str = "",
    ) -> str:
        """
        Generate a specialized anti-pattern flowchart showing
        a red (bad) path vs green (good) path.
        """
        safe = self._safe_mermaid_text
        return f"""\
graph TD
    START["🎯 Task: {safe(topic or 'Problem')}"] --> DECISION{{"Choose Approach"}}
    DECISION -->|"❌ Bad Path"| BAD["{safe(bad_approach[:80])}"]
    DECISION -->|"✅ Good Path"| GOOD["{safe(good_approach[:80])}"]
    BAD --> WARN["⚠️ Warning Signs Appear"]
    WARN --> FAIL["💥 {safe(failure_reason[:60])}"]
    GOOD --> TEST["✅ Validate & Test"]
    TEST --> SUCCESS["🎉 SUCCESS"]
    FAIL -->|"🔧 Recovery"| LEARN["Learn From Mistake"]
    LEARN --> GOOD

    style BAD fill:#ff4444,color:#fff
    style WARN fill:#ff6644,color:#fff
    style FAIL fill:#cc0000,color:#fff
    style GOOD fill:#44bb44,color:#fff
    style TEST fill:#66cc66,color:#fff
    style SUCCESS fill:#00aa00,color:#fff
    style DECISION fill:#4488ff,color:#fff
    style LEARN fill:#ffaa00,color:#000"""

    def generate_learning_path(self, lesson_steps: List[str], topic: str = "") -> str:
        """
        Generate a learning path flowchart from a list of lesson steps.
        """
        if not lesson_steps:
            return _TEMPLATES[FlowchartType.LEARNING_PATH].format(
                topic=self._safe_mermaid_text(topic)
            )

        safe = self._safe_mermaid_text
        lines = ["graph TD"]

        # Color palette for progression
        colors = ["#4488ff", "#5577dd", "#6666bb", "#7755aa", "#885599",
                  "#994488", "#aa3377", "#44bb44"]

        for i, step in enumerate(lesson_steps):
            node_id = f"S{i}"
            step_text = safe(step[:60])

            if i == 0:
                lines.append(f'    {node_id}["📚 {step_text}"]')
            elif i == len(lesson_steps) - 1:
                lines.append(f'    {node_id}["🏆 {step_text}"]')
            else:
                lines.append(f'    {node_id}["📖 {step_text}"]')

            # Connect to next
            if i > 0:
                prev_id = f"S{i-1}"
                lines.append(f"    {prev_id} --> {node_id}")

            # Add checkpoint every 2 steps
            if i > 0 and i < len(lesson_steps) - 1 and i % 2 == 0:
                check_id = f"CHK{i}"
                lines.append(f'    {node_id} --> {check_id}{{"✅ Checkpoint"}}')
                next_id = f"S{i+1}" if i + 1 < len(lesson_steps) else node_id
                lines.append(f'    {check_id} -->|"Pass"| {next_id}')
                lines.append(f'    {check_id} -->|"Review"| {node_id}')

        # Styling
        lines.append("")
        for i in range(len(lesson_steps)):
            color_idx = min(i, len(colors) - 1)
            lines.append(f"    style S{i} fill:{colors[color_idx]},color:#fff")

        return "\n".join(lines)

    def generate_concept_map(self, main_concept: str, sub_concepts: Dict[str, List[str]]) -> str:
        """
        Generate a concept relationship map.

        Args:
            main_concept: Central concept
            sub_concepts: Dict mapping concept names to their sub-concepts
        """
        safe = self._safe_mermaid_text
        lines = [
            "graph LR",
            f'    CORE["🧠 {safe(main_concept)}"]',
        ]

        colors = ["#6644cc", "#cc6644", "#44cccc", "#cc44cc", "#cccc44"]

        for i, (concept, subs) in enumerate(sub_concepts.items()):
            c_id = f"C{i}"
            lines.append(f'    CORE --> {c_id}["{safe(concept)}"]')

            for j, sub in enumerate(subs[:4]):  # Max 4 sub-concepts each
                s_id = f"SC{i}_{j}"
                lines.append(f'    {c_id} --> {s_id}["{safe(sub)}"]')

        # Styling
        lines.append("")
        lines.append("    style CORE fill:#4488ff,color:#fff")
        for i in range(len(sub_concepts)):
            color_idx = i % len(colors)
            lines.append(f"    style C{i} fill:{colors[color_idx]},color:#fff")

        return "\n".join(lines)

    def generate_comparison_chart(
        self,
        option_a: str, pros_a: List[str], cons_a: List[str],
        option_b: str, pros_b: List[str], cons_b: List[str],
    ) -> str:
        """Generate a comparison flowchart between two approaches."""
        safe = self._safe_mermaid_text
        lines = [
            "graph TD",
            f'    TITLE["⚖️ Compare"]',
            f'    TITLE --> A["{safe(option_a[:50])}"]',
            f'    TITLE --> B["{safe(option_b[:50])}"]',
        ]

        # Pros and cons for A
        for i, pro in enumerate(pros_a[:3]):
            lines.append(f'    A --> A_P{i}["✅ {safe(pro[:40])}"]')
        for i, con in enumerate(cons_a[:3]):
            lines.append(f'    A --> A_C{i}["❌ {safe(con[:40])}"]')

        # Pros and cons for B
        for i, pro in enumerate(pros_b[:3]):
            lines.append(f'    B --> B_P{i}["✅ {safe(pro[:40])}"]')
        for i, con in enumerate(cons_b[:3]):
            lines.append(f'    B --> B_C{i}["❌ {safe(con[:40])}"]')

        lines.append("")
        lines.append("    style A fill:#4488ff,color:#fff")
        lines.append("    style B fill:#cc6644,color:#fff")

        return "\n".join(lines)

    def to_ascii(self, steps: List[str], title: str = "") -> str:
        """Generate an ASCII flowchart (terminal-friendly fallback)."""
        return render_ascii_flowchart(steps, title)

    def to_ascii_comparison(
        self,
        bad_title: str, bad_items: List[str],
        good_title: str, good_items: List[str],
    ) -> str:
        """Generate an ASCII side-by-side comparison (terminal-friendly)."""
        return render_ascii_comparison(bad_title, bad_items, good_title, good_items)

    # ──────────────────────────────────────
    # Internal Helpers
    # ──────────────────────────────────────

    def _generate_with_llm(
        self, topic: str, chart_type: FlowchartType, context: str
    ) -> Optional[str]:
        """Use LLM to generate a custom Mermaid flowchart."""
        type_descriptions = {
            FlowchartType.DECISION: "a decision tree showing branching choices with outcomes",
            FlowchartType.PROCESS: "a step-by-step process flow with checkpoints",
            FlowchartType.ANTI_PATTERN: "a red (bad path) vs green (good path) comparison",
            FlowchartType.CONCEPT_MAP: "a concept relationship map showing how ideas connect",
            FlowchartType.LEARNING_PATH: "a learning progression from beginner to expert",
            FlowchartType.COMPARISON: "a side-by-side comparison of two approaches",
            FlowchartType.DEBUG_TRACE: "a debugging investigation flow",
        }

        desc = type_descriptions.get(chart_type, "a comprehensive flowchart")

        prompt = f"""\
Generate a Mermaid flowchart diagram for teaching about: {topic}
Type: {desc}

{f'Additional context: {context}' if context else ''}

Requirements:
1. Use 'graph TD' or 'graph LR' at the start
2. Use descriptive labels with emojis for visual appeal
3. Use color styling with 'style' statements
4. Use green (#44bb44) for success/good paths
5. Use red (#ff4444) for failure/bad paths
6. Use blue (#4488ff) for decision and start nodes
7. Use orange (#ff9944) for warning/review nodes
8. Keep labels concise (under 60 chars)
9. Include 6-12 nodes for clarity
10. Quote all node labels with square brackets ["label"]

Output ONLY the Mermaid code, no markdown fences or explanations.
Start directly with 'graph TD' or 'graph LR'.
"""
        try:
            result = self._call_llm(prompt)
            # Clean: extract just the mermaid content
            cleaned = self._extract_mermaid(result)
            return cleaned if cleaned else None
        except Exception as e:
            logger.warning(f"LLM flowchart generation failed: {e}")
            return None

    def _extract_mermaid(self, text: str) -> Optional[str]:
        """Extract Mermaid code from LLM response."""
        # Remove markdown fences if present
        text = re.sub(r'```mermaid\s*', '', text)
        text = re.sub(r'```\s*$', '', text)
        text = text.strip()

        # Must start with graph keyword
        if not re.match(r'^(graph|flowchart)\s+(TD|LR|TB|BT|RL)', text):
            # Try to find graph declaration in the text
            match = re.search(r'((?:graph|flowchart)\s+(?:TD|LR|TB|BT|RL)[\s\S]+)', text)
            if match:
                text = match.group(1)
            else:
                return None

        return text

    def _validate_mermaid(self, mermaid_code: str) -> bool:
        """Basic validation of Mermaid syntax."""
        if not mermaid_code:
            return False

        # Must start with graph/flowchart declaration
        if not re.match(r'^(graph|flowchart)\s', mermaid_code.strip()):
            return False

        # Must have at least one edge (-->)
        if '-->' not in mermaid_code and '---' not in mermaid_code:
            return False

        # Must have at least 2 nodes
        node_pattern = re.findall(r'\w+\[', mermaid_code)
        if len(node_pattern) < 2:
            # Also check for nodes without brackets
            edge_pattern = re.findall(r'(\w+)\s*--', mermaid_code)
            if len(set(edge_pattern)) < 2:
                return False

        return True

    def _safe_mermaid_text(self, text: str) -> str:
        """Escape text for safe use in Mermaid labels."""
        # Remove characters that break Mermaid syntax
        text = text.replace('"', "'")
        text = text.replace('\n', ' ')
        text = text.replace('\r', '')
        text = text.replace('[', '(')
        text = text.replace(']', ')')
        text = text.replace('{', '(')
        text = text.replace('}', ')')
        text = text.replace('#', '')
        text = text.replace('&', 'and')
        text = text.replace('<', '')
        text = text.replace('>', '')
        return text[:80]  # Truncate for readability

    def _call_llm(self, prompt: str) -> str:
        """Call LLM safely."""
        if not self.generate_fn:
            return ""
        try:
            result = self.generate_fn(prompt)
            if hasattr(result, 'answer'):
                return result.answer
            return str(result)
        except Exception as e:
            logger.error(f"LLM call failed in FlowchartGenerator: {e}")
            return ""
