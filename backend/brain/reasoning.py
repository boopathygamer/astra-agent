"""
Reasoning Engine — Human-like Chain-of-Thought with 5 Cognitive Modes.
Modes: DECOMPOSE, ANALOGIZE, ABSTRACT, SIMULATE, BACKTRACK
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)

NL = "\n"


class CognitiveMode(Enum):
    DECOMPOSE = "decompose"
    ANALOGIZE = "analogize"
    ABSTRACT = "abstract"
    SIMULATE = "simulate"
    BACKTRACK = "backtrack"


@dataclass
class ReasoningStep:
    step_id: int = 0
    mode: CognitiveMode = CognitiveMode.DECOMPOSE
    thought: str = ""
    action: str = ""
    result: str = ""
    confidence: float = 0.0

    def to_prompt(self):
        return (
            f"Step {self.step_id} [{self.mode.value}]: {self.thought}{NL}"
            f"  Action: {self.action} Result: {self.result[:200]}"
        )


@dataclass
class SubProblem:
    id: int = 0
    description: str = ""
    dependencies: List[int] = field(default_factory=list)
    solution: str = ""
    solved: bool = False
    confidence: float = 0.0


@dataclass
class ReasoningTrace:
    problem: str = ""
    mode_used: CognitiveMode = CognitiveMode.DECOMPOSE
    steps: List[ReasoningStep] = field(default_factory=list)
    sub_problems: List[SubProblem] = field(default_factory=list)
    final_answer: str = ""
    total_confidence: float = 0.0
    modes_tried: List[CognitiveMode] = field(default_factory=list)
    duration_ms: float = 0.0
    backtrack_count: int = 0

    def summary(self):
        modes_str = str([m.value for m in self.modes_tried])
        lines = [
            f"Reasoning ({self.mode_used.value})",
            f"  Steps={len(self.steps)} Backtracks={self.backtrack_count}",
            f"  Modes={modes_str}",
            f"  Confidence={self.total_confidence:.3f}",
        ]
        if self.sub_problems:
            solved = sum(1 for sp in self.sub_problems if sp.solved)
            lines.append(f"  Sub-problems: {solved}/{len(self.sub_problems)}")
        return NL.join(lines)


class ReasoningEngine:
    """Chain-of-thought reasoning with 5 cognitive modes."""

    def __init__(self, generate_fn: Callable = None):
        self.generate_fn = generate_fn
        self._step_counter = 0

    def set_generate_fn(self, fn: Callable):
        self.generate_fn = fn

    def reason(self, problem: str, mode: CognitiveMode = None,
               max_depth: int = 3, memory_context: str = "") -> ReasoningTrace:
        start = time.time()
        trace = ReasoningTrace(problem=problem)
        self._step_counter = 0
        if mode is None:
            mode = self._select_mode(problem)
        trace.mode_used = mode
        trace.modes_tried.append(mode)
        logger.info(f"Reasoning [{mode.value}]: {problem[:80]}")

        dispatch = {
            CognitiveMode.DECOMPOSE: self._decompose,
            CognitiveMode.ANALOGIZE: self._analogize,
            CognitiveMode.ABSTRACT: self._abstract,
            CognitiveMode.SIMULATE: self._simulate,
            CognitiveMode.BACKTRACK: self._backtrack,
        }
        dispatch[mode](problem, trace, memory_context)
        trace.duration_ms = (time.time() - start) * 1000
        logger.info(trace.summary())
        return trace

    def _decompose(self, problem, trace, ctx):
        ctx_line = "Context: " + ctx if ctx else ""
        prompt = (
            "Break this problem into 2-5 sub-problems." + NL + NL
            + "Problem: " + problem + NL + ctx_line + NL + NL
            + "Format:" + NL + "SUB_PROBLEM N: description" + NL
            + "DEPENDS_ON: none or numbers" + NL
        )
        response = self.generate_fn(prompt)
        subs = self._parse_subs(response)
        trace.sub_problems = subs
        trace.steps.append(self._step(
            CognitiveMode.DECOMPOSE,
            f"Decomposed into {len(subs)} sub-problems",
            "decompose", response[:200], 0.8))

        solved_parts = []
        for sp in self._topo_sort(subs):
            dep_parts = []
            for d in sp.dependencies:
                if d < len(subs) and subs[d].solved:
                    dep_parts.append(f"[{d}]: {subs[d].solution[:200]}")
            dep_text = NL.join(dep_parts)
            dep_header = ("Dependencies:" + NL + dep_text) if dep_text else ""

            sol_prompt = (
                "Solve sub-problem: " + sp.description + NL
                + "Main: " + problem + NL
                + dep_header + NL + "Solution:" + NL
            )
            sol = self.generate_fn(sol_prompt)
            sp.solution = sol
            sp.solved = True
            sp.confidence = 0.8
            trace.steps.append(self._step(
                CognitiveMode.DECOMPOSE,
                "Solving: " + sp.description[:60],
                "solve", sol[:200], 0.8))
            solved_parts.append(f"[{sp.id}] {sol[:300]}")

        synth_prompt = (
            "Synthesize final answer from sub-solutions." + NL
            + "Problem: " + problem + NL
            + "Solutions:" + NL + NL.join(solved_parts) + NL
        )
        trace.final_answer = self.generate_fn(synth_prompt)
        trace.total_confidence = (
            sum(s.confidence for s in subs) / max(len(subs), 1))

    def _analogize(self, problem, trace, ctx):
        ctx_line = "Context: " + ctx if ctx else ""
        analogies = self.generate_fn(
            "Find 2-3 analogous well-known problems." + NL
            + "Problem: " + problem + NL + ctx_line + NL
            + "Format:" + NL + "ANALOGY N: problem" + NL
            + "SIMILARITY: ..." + NL + "KNOWN_SOLUTION: ..." + NL)
        trace.steps.append(self._step(
            CognitiveMode.ANALOGIZE, "Finding analogies",
            "find", analogies[:200], 0.7))
        trace.final_answer = self.generate_fn(
            "Adapt best analogy." + NL
            + "Problem: " + problem + NL
            + "Analogies:" + NL + analogies + NL
            + "Adapted solution:" + NL)
        trace.total_confidence = 0.75
        trace.steps.append(self._step(
            CognitiveMode.ANALOGIZE, "Adapting analogy",
            "adapt", trace.final_answer[:200], 0.75))

    def _abstract(self, problem, trace, ctx):
        abstraction = self.generate_fn(
            "Abstract to general pattern." + NL
            + "Problem: " + problem + NL
            + "ABSTRACT_PATTERN: ..." + NL + "PATTERN_TYPE: ..." + NL)
        trace.steps.append(self._step(
            CognitiveMode.ABSTRACT, "Abstracting",
            "abstract", abstraction[:200], 0.7))
        abs_sol = self.generate_fn(
            "Solve abstract pattern." + NL + abstraction + NL)
        trace.steps.append(self._step(
            CognitiveMode.ABSTRACT, "Solving abstract",
            "solve", abs_sol[:200], 0.75))
        trace.final_answer = self.generate_fn(
            "Concretize solution." + NL
            + "Problem: " + problem + NL
            + "Abstract: " + abs_sol + NL)
        trace.total_confidence = 0.8
        trace.steps.append(self._step(
            CognitiveMode.ABSTRACT, "Concretizing",
            "concretize", trace.final_answer[:200], 0.8))

    def _simulate(self, problem, trace, ctx):
        ctx_line = "Context: " + ctx if ctx else ""
        proposed = self.generate_fn(
            "Propose a solution." + NL
            + "Problem: " + problem + NL + ctx_line + NL)
        trace.steps.append(self._step(
            CognitiveMode.SIMULATE, "Proposing solution",
            "propose", proposed[:200], 0.6))
        simulation = self.generate_fn(
            "Mentally execute step-by-step. Trace state changes." + NL
            + "Problem: " + problem + NL
            + "Solution:" + NL + proposed[:2000] + NL + NL
            + "STATE_0: initial" + NL
            + "STEP_1: ... -> STATE_1: ..." + NL
            + "ERRORS_FOUND: ..." + NL
            + "CORRECTED_SOLUTION: ..." + NL)
        trace.steps.append(self._step(
            CognitiveMode.SIMULATE, "Mental execution",
            "simulate", simulation[:300], 0.8))
        if "CORRECTED_SOLUTION:" in simulation:
            trace.final_answer = simulation.split(
                "CORRECTED_SOLUTION:")[-1].strip()
            trace.total_confidence = 0.85
        else:
            trace.final_answer = proposed
            trace.total_confidence = 0.7

    def _backtrack(self, problem, trace, ctx):
        attempts = []
        for attempt in range(3):
            exclude = ""
            if attempts:
                failed = NL.join("- " + a[:100] for a in attempts)
                exclude = "FAILED:" + NL + failed + NL + "Use DIFFERENT." + NL
            sol = self.generate_fn(
                "Solve with fresh approach." + NL
                + "Problem: " + problem + NL + exclude)
            ev = self.generate_fn(
                "Score 0-10." + NL + "Problem: " + problem + NL
                + "Solution: " + sol[:1500] + NL
                + "SCORE: N" + NL + "VERDICT: accept/reject" + NL)
            score = 5.0
            for line in ev.split(NL):
                if line.strip().upper().startswith("SCORE:"):
                    try:
                        score = float(
                            line.split(":")[-1].strip().split("/")[0])
                    except Exception as e:
                        import logging
                        logging.debug(f"Reasoning mod fallback error: {e}")
                        pass
            trace.steps.append(self._step(
                CognitiveMode.BACKTRACK,
                f"Attempt {attempt + 1}",
                f"try_{attempt + 1}", sol[:200], score / 10))
            if score >= 7 or "accept" in ev.lower():
                trace.final_answer = sol
                trace.total_confidence = score / 10
                return
            attempts.append(sol[:300])
            trace.backtrack_count += 1
        if trace.steps:
            best = max(trace.steps, key=lambda s: s.confidence)
            trace.final_answer = best.result
            trace.total_confidence = best.confidence

    def _select_mode(self, problem: str) -> CognitiveMode:
        try:
            r = self.generate_fn(
                "Choose ONE mode: DECOMPOSE|ANALOGIZE|ABSTRACT|"
                "SIMULATE|BACKTRACK" + NL
                + "Problem: " + problem + NL + "BEST_MODE: ")
            u = r.upper()
            for m in CognitiveMode:
                if m.value.upper() in u:
                    return m
        except Exception as e:
            import logging
            logging.debug(f"Mode selection fallback: {e}")
        return CognitiveMode.DECOMPOSE

    def _step(self, mode, thought, action, result, conf):
        self._step_counter += 1
        return ReasoningStep(self._step_counter, mode, thought,
                             action, result, conf)

    def _parse_subs(self, text):
        subs = []
        desc = ""
        deps = []
        idx = 0
        for line in text.split(NL):
            u = line.strip().upper()
            if u.startswith("SUB_PROBLEM"):
                if desc:
                    subs.append(SubProblem(idx, desc, deps))
                    idx += 1
                desc = line.split(":", 1)[-1].strip()
                deps = []
            elif u.startswith("DEPENDS_ON:"):
                d = line.split(":", 1)[-1].strip()
                if d.lower() != "none":
                    deps = [
                        int(x) - 1
                        for x in d.split(",")
                        if x.strip().isdigit()
                    ]
        if desc:
            subs.append(SubProblem(idx, desc, deps))
        return subs or [SubProblem(0, text[:300])]

    def _topo_sort(self, subs):
        solved = set()
        ordered = []
        remaining = list(subs)
        for _ in range(len(remaining) * 2 + 1):
            if not remaining:
                break
            for sp in list(remaining):
                if all(d in solved for d in sp.dependencies):
                    ordered.append(sp)
                    solved.add(sp.id)
                    remaining.remove(sp)
        ordered.extend(remaining)
        return ordered
