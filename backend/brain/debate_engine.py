"""
Adversarial Debate Engine
═════════════════════════
Two internal agents argue toward truth via structured debate.

Inspired by:
  • Irving et al. (2018) "AI Safety via Debate"
  • Du et al. (2023) "Improving Factuality with Multi-Agent Debate"

Architecture:
  Round 1:  Proposer generates claim + evidence
  Round 1': Opponent finds counter-evidence + weaknesses
  Round 2:  Proposer rebuts with stronger evidence
  Round 2': Opponent escalates challenge
  ...
  Judge:    Evaluates all arguments, declares verdict

The system converges when both sides agree (consensus) or
when the judge's confidence exceeds a threshold.
"""

import hashlib
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class DebateRole(Enum):
    PROPOSER = "proposer"
    OPPONENT = "opponent"
    JUDGE = "judge"


class ArgumentType(Enum):
    CLAIM = "claim"
    EVIDENCE = "evidence"
    REBUTTAL = "rebuttal"
    CONCESSION = "concession"
    COUNTER_EXAMPLE = "counter_example"


class Verdict(Enum):
    PROPOSER_WINS = "proposer_wins"
    OPPONENT_WINS = "opponent_wins"
    SYNTHESIS = "synthesis"       # Both sides contributed to a better answer
    DEADLOCK = "deadlock"


@dataclass
class Argument:
    """A single argument in the debate."""
    arg_id: str = ""
    role: DebateRole = DebateRole.PROPOSER
    arg_type: ArgumentType = ArgumentType.CLAIM
    content: str = ""
    evidence: List[str] = field(default_factory=list)
    targets: List[str] = field(default_factory=list)  # IDs of arguments this responds to
    strength: float = 0.5
    round_number: int = 0

    def __post_init__(self):
        if not self.arg_id:
            self.arg_id = hashlib.md5(
                f"{self.role.value}:{self.content[:30]}:{time.time()}".encode()
            ).hexdigest()[:10]


@dataclass
class DebateRound:
    """A single round of the debate."""
    round_number: int = 0
    proposer_argument: Optional[Argument] = None
    opponent_argument: Optional[Argument] = None
    judge_assessment: str = ""
    round_score: float = 0.5  # 0=opponent dominates, 1=proposer dominates

    @property
    def summary(self) -> str:
        p = self.proposer_argument.content[:80] if self.proposer_argument else "—"
        o = self.opponent_argument.content[:80] if self.opponent_argument else "—"
        return f"R{self.round_number}: P({p}...) vs O({o}...) → {self.round_score:.2f}"


@dataclass
class DebateResult:
    """Complete debate result."""
    topic: str = ""
    verdict: Verdict = Verdict.DEADLOCK
    final_conclusion: str = ""
    confidence: float = 0.0
    rounds: List[DebateRound] = field(default_factory=list)
    all_arguments: List[Argument] = field(default_factory=list)
    consensus_reached: bool = False
    total_duration_ms: float = 0.0
    score_trajectory: List[float] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "confidence": round(self.confidence, 4),
            "rounds": len(self.rounds),
            "consensus": self.consensus_reached,
            "score_trajectory": [round(s, 3) for s in self.score_trajectory],
            "duration_ms": round(self.total_duration_ms, 2),
        }


class DebateEngine:
    """
    Adversarial debate between Proposer and Opponent with Judge evaluation.

    The debate proceeds in rounds with escalating difficulty:
    - Early rounds: surface-level claims and critiques
    - Later rounds: deeper evidence, counter-examples, edge cases
    - Final: judge synthesizes the strongest arguments from both sides
    """

    PROPOSER_PROMPT = (
        "You are the PROPOSER in a structured debate. Your role is to present "
        "and defend a well-reasoned position.\n\n"
        "Topic: {topic}\n"
        "{context}"
        "Round {round_num} of {max_rounds}.\n"
        "{previous_args}\n\n"
        "Present your argument with:\n"
        "CLAIM: [your main point]\n"
        "EVIDENCE:\n- [supporting point 1]\n- [supporting point 2]\n"
        "STRENGTH: [0.0-1.0 how confident you are]"
    )

    OPPONENT_PROMPT = (
        "You are the OPPONENT in a structured debate. Your role is to rigorously "
        "challenge the proposer's arguments and find weaknesses.\n\n"
        "Topic: {topic}\n"
        "Round {round_num} of {max_rounds}.\n"
        "Proposer's argument:\n{proposer_arg}\n"
        "{previous_args}\n\n"
        "Challenge with:\n"
        "REBUTTAL: [your counter-argument]\n"
        "COUNTER_EXAMPLES:\n- [example that breaks the claim]\n"
        "WEAKNESSES:\n- [flaw 1]\n- [flaw 2]\n"
        "STRENGTH: [0.0-1.0]"
    )

    JUDGE_PROMPT = (
        "You are an impartial JUDGE evaluating a debate.\n\n"
        "Topic: {topic}\n\n"
        "All arguments:\n{all_arguments}\n\n"
        "Evaluate:\n"
        "1. Which side presented stronger evidence?\n"
        "2. Were counter-arguments adequately addressed?\n"
        "3. What is the most defensible conclusion?\n\n"
        "VERDICT: [proposer_wins / opponent_wins / synthesis]\n"
        "CONFIDENCE: [0.0-1.0]\n"
        "CONCLUSION: [the most well-supported answer]\n"
        "REASONING: [brief explanation]"
    )

    def __init__(
        self,
        generate_fn: Optional[Callable] = None,
        max_rounds: int = 3,
        consensus_threshold: float = 0.85,
        judge_confidence_threshold: float = 0.80,
    ):
        self.generate_fn = generate_fn
        self.max_rounds = max_rounds
        self.consensus_threshold = consensus_threshold
        self.judge_conf_threshold = judge_confidence_threshold
        self._history: List[Dict[str, Any]] = []

        logger.info(
            f"[DEBATE] Initialized — rounds={max_rounds}, "
            f"consensus_θ={consensus_threshold}"
        )

    def debate(self, topic: str, context: str = "") -> DebateResult:
        """
        Run a full adversarial debate on a topic.
        """
        start = time.time()
        result = DebateResult(topic=topic)
        all_args: List[Argument] = []

        for round_num in range(1, self.max_rounds + 1):
            debate_round = DebateRound(round_number=round_num)

            # Proposer's turn
            prev_text = self._format_previous(all_args, DebateRole.OPPONENT)
            ctx = f"Context: {context}\n" if context else ""
            p_arg = self._run_proposer(topic, ctx, round_num, prev_text)
            p_arg.round_number = round_num
            debate_round.proposer_argument = p_arg
            all_args.append(p_arg)

            # Opponent's turn
            prev_text = self._format_previous(all_args, DebateRole.PROPOSER)
            o_arg = self._run_opponent(topic, round_num, p_arg, prev_text)
            o_arg.round_number = round_num
            debate_round.opponent_argument = o_arg
            all_args.append(o_arg)

            # Quick judge assessment for this round
            debate_round.round_score = self._score_round(p_arg, o_arg)
            result.score_trajectory.append(debate_round.round_score)

            result.rounds.append(debate_round)

            # Early consensus check
            if round_num > 1:
                scores = result.score_trajectory
                if len(scores) >= 2:
                    diff = abs(scores[-1] - scores[-2])
                    if diff < 0.05:
                        result.consensus_reached = True
                        logger.info(f"[DEBATE] Consensus reached at round {round_num}")
                        break

        # Final judge verdict
        result.all_arguments = all_args
        verdict_data = self._run_judge(topic, all_args)
        result.verdict = verdict_data["verdict"]
        result.confidence = verdict_data["confidence"]
        result.final_conclusion = verdict_data["conclusion"]

        result.total_duration_ms = (time.time() - start) * 1000
        self._history.append(result.to_dict())

        logger.info(
            f"[DEBATE] Complete — verdict={result.verdict.value}, "
            f"conf={result.confidence:.3f}, rounds={len(result.rounds)}"
        )
        return result

    def _run_proposer(self, topic: str, context: str,
                      round_num: int, previous: str) -> Argument:
        """Generate proposer's argument."""
        arg = Argument(role=DebateRole.PROPOSER, arg_type=ArgumentType.CLAIM)

        if self.generate_fn:
            prompt = self.PROPOSER_PROMPT.format(
                topic=topic[:400], context=context,
                round_num=round_num, max_rounds=self.max_rounds,
                previous_args=previous,
            )
            try:
                response = self.generate_fn(prompt)
                arg.content = self._extract_section(response, "CLAIM")
                arg.evidence = self._extract_bullets(response, "EVIDENCE")
                arg.strength = self._extract_float(response, "STRENGTH", 0.6)
            except Exception as e:
                logger.warning(f"[DEBATE] Proposer failed: {e}")
                arg.content = f"Initial position on: {topic[:100]}"
        else:
            arg.content = f"Proposer argues: {topic[:100]}"
            arg.strength = 0.6

        return arg

    def _run_opponent(self, topic: str, round_num: int,
                      proposer_arg: Argument, previous: str) -> Argument:
        """Generate opponent's counter-argument."""
        arg = Argument(
            role=DebateRole.OPPONENT,
            arg_type=ArgumentType.REBUTTAL,
            targets=[proposer_arg.arg_id],
        )

        if self.generate_fn:
            prompt = self.OPPONENT_PROMPT.format(
                topic=topic[:400], round_num=round_num,
                max_rounds=self.max_rounds,
                proposer_arg=proposer_arg.content[:500],
                previous_args=previous,
            )
            try:
                response = self.generate_fn(prompt)
                arg.content = self._extract_section(response, "REBUTTAL")
                arg.evidence = self._extract_bullets(response, "COUNTER_EXAMPLES", "WEAKNESSES")
                arg.strength = self._extract_float(response, "STRENGTH", 0.5)
            except Exception as e:
                logger.warning(f"[DEBATE] Opponent failed: {e}")
                arg.content = f"Challenge to: {proposer_arg.content[:80]}"
        else:
            arg.content = f"Opponent challenges: {proposer_arg.content[:80]}"
            arg.strength = 0.5

        return arg

    def _run_judge(self, topic: str, all_args: List[Argument]) -> Dict[str, Any]:
        """Run the final judge evaluation."""
        verdict_data = {
            "verdict": Verdict.SYNTHESIS,
            "confidence": 0.5,
            "conclusion": "",
        }

        args_text = "\n\n".join(
            f"[{a.role.value.upper()} R{a.round_number}]: {a.content}\n"
            f"  Evidence: {'; '.join(a.evidence[:3])}"
            for a in all_args
        )

        if self.generate_fn:
            prompt = self.JUDGE_PROMPT.format(
                topic=topic[:400], all_arguments=args_text[:3000]
            )
            try:
                response = self.generate_fn(prompt)
                v_str = self._extract_section(response, "VERDICT").lower().strip()
                if "proposer" in v_str:
                    verdict_data["verdict"] = Verdict.PROPOSER_WINS
                elif "opponent" in v_str:
                    verdict_data["verdict"] = Verdict.OPPONENT_WINS
                else:
                    verdict_data["verdict"] = Verdict.SYNTHESIS

                verdict_data["confidence"] = self._extract_float(response, "CONFIDENCE", 0.5)
                verdict_data["conclusion"] = self._extract_section(response, "CONCLUSION")
            except Exception as e:
                logger.warning(f"[DEBATE] Judge failed: {e}")
        else:
            # Heuristic: winner is whichever side had higher average strength
            p_scores = [a.strength for a in all_args if a.role == DebateRole.PROPOSER]
            o_scores = [a.strength for a in all_args if a.role == DebateRole.OPPONENT]
            p_avg = sum(p_scores) / max(len(p_scores), 1)
            o_avg = sum(o_scores) / max(len(o_scores), 1)
            if p_avg > o_avg + 0.1:
                verdict_data["verdict"] = Verdict.PROPOSER_WINS
            elif o_avg > p_avg + 0.1:
                verdict_data["verdict"] = Verdict.OPPONENT_WINS
            else:
                verdict_data["verdict"] = Verdict.SYNTHESIS
            verdict_data["confidence"] = max(p_avg, o_avg)
            verdict_data["conclusion"] = all_args[-1].content if all_args else ""

        return verdict_data

    def _score_round(self, p_arg: Argument, o_arg: Argument) -> float:
        """Score a round: 0.0 = opponent dominates, 1.0 = proposer dominates."""
        p = p_arg.strength
        o = o_arg.strength
        # Weighted by evidence count
        p_ev = min(len(p_arg.evidence) * 0.05, 0.15)
        o_ev = min(len(o_arg.evidence) * 0.05, 0.15)
        total = (p + p_ev) + (o + o_ev)
        if total == 0:
            return 0.5
        return (p + p_ev) / total

    @staticmethod
    def _format_previous(args: List[Argument], exclude_role: DebateRole) -> str:
        relevant = [a for a in args if a.role != exclude_role][-3:]
        if not relevant:
            return ""
        return "Previous arguments:\n" + "\n".join(
            f"[{a.role.value}]: {a.content[:150]}" for a in relevant
        )

    @staticmethod
    def _extract_section(text: str, header: str) -> str:
        for line in text.split("\n"):
            h = header.upper() + ":"
            if h in line.upper():
                return line.split(":", 1)[-1].strip()
        return text[:200]

    @staticmethod
    def _extract_bullets(text: str, *headers: str) -> List[str]:
        items = []
        in_section = False
        for line in text.split("\n"):
            upper = line.strip().upper().rstrip(":")
            if any(h.upper() in upper for h in headers):
                in_section = True
                continue
            if in_section:
                s = line.strip()
                if s.startswith(("-", "•", "*")):
                    items.append(s.lstrip("-•* "))
                elif s and not any(s.upper().startswith(k) for k in ("CLAIM", "EVIDENCE", "STRENGTH", "REBUTTAL")):
                    continue
                else:
                    in_section = False
        return items[:8]

    @staticmethod
    def _extract_float(text: str, key: str, default: float = 0.5) -> float:
        import re
        for line in text.split("\n"):
            if key.upper() in line.upper():
                nums = re.findall(r"(\d+\.?\d*)", line)
                if nums:
                    v = float(nums[0])
                    return v if v <= 1.0 else v / 10.0
        return default

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_debates": len(self._history),
            "avg_confidence": (
                sum(h["confidence"] for h in self._history) / max(len(self._history), 1)
            ),
            "verdict_distribution": {
                v.value: sum(1 for h in self._history if h["verdict"] == v.value)
                for v in Verdict
            },
        }
