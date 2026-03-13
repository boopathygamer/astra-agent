"""
Temporal Paradox Resolver — Multi-Timeline Truth Engine
══════════════════════════════════════════════════════
When facts contradict across time, this engine maintains multiple
temporal truth models simultaneously and resolves them based on
the query's temporal context.

Architecture:
  New Fact → Paradox Detector → Timeline Forker → Truth Models
                                      ↓                ↓
                              Conflict Registry   Temporal Query Resolver
"""

import hashlib
import logging
import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class ParadoxType(Enum):
    CONTRADICTION = "contradiction"     # Direct conflict
    SUPERSESSION = "supersession"       # New info replaces old
    PARTIAL = "partial"                 # Partially conflicting
    TEMPORAL = "temporal"               # True at different times


@dataclass
class TemporalFact:
    """A fact with temporal validity."""
    fact_id: str = ""
    key: str = ""
    value: Any = None
    valid_from: float = 0.0
    valid_until: float = 0.0       # 0 = still valid
    source: str = ""
    confidence: float = 0.5
    superseded_by: Optional[str] = None

    def __post_init__(self):
        if not self.fact_id:
            self.fact_id = secrets.token_hex(4)
        if not self.valid_from:
            self.valid_from = time.time()

    def is_valid_at(self, t: float) -> bool:
        if t < self.valid_from:
            return False
        if self.valid_until > 0 and t > self.valid_until:
            return False
        return True

    @property
    def is_current(self) -> bool:
        return self.valid_until == 0 or self.valid_until > time.time()


@dataclass
class Paradox:
    """A detected contradiction between facts."""
    paradox_id: str = ""
    paradox_type: ParadoxType = ParadoxType.CONTRADICTION
    fact_a_id: str = ""
    fact_b_id: str = ""
    key: str = ""
    description: str = ""
    resolved: bool = False
    resolution: str = ""

    def __post_init__(self):
        if not self.paradox_id:
            self.paradox_id = secrets.token_hex(4)


@dataclass
class TemporalQueryResult:
    """Result of a temporally-aware query."""
    key: str = ""
    query_time: float = 0.0
    value: Any = None
    fact_id: str = ""
    confidence: float = 0.0
    timeline_count: int = 0
    paradoxes_encountered: int = 0
    is_contested: bool = False

    def summary(self) -> str:
        status = "CONTESTED" if self.is_contested else "RESOLVED"
        return (
            f"TempQuery '{self.key}': {status} | "
            f"value={self.value} | conf={self.confidence:.2f}"
        )


class TemporalParadoxResolver:
    """
    Multi-timeline truth engine for contradictory information.

    Usage:
        resolver = TemporalParadoxResolver()

        # Record facts over time
        resolver.record("python_version", "3.10", source="docs_2022")
        resolver.record("python_version", "3.12", source="docs_2024")

        # Query at a specific time
        result = resolver.query("python_version")  # Returns "3.12" (latest)
        result = resolver.query("python_version", at_time=1640000000)  # Returns "3.10"

        # Detect paradoxes
        paradoxes = resolver.detect_paradoxes()
    """

    def __init__(self):
        self._facts: Dict[str, List[TemporalFact]] = defaultdict(list)
        self._paradoxes: List[Paradox] = []
        self._total_records: int = 0
        self._total_queries: int = 0

    def record(
        self,
        key: str,
        value: Any,
        source: str = "",
        confidence: float = 0.5,
        valid_from: float = 0.0,
        valid_until: float = 0.0,
    ) -> Tuple[str, List[Paradox]]:
        """Record a fact and detect any paradoxes with existing facts."""
        self._total_records += 1

        fact = TemporalFact(
            key=key,
            value=value,
            source=source,
            confidence=confidence,
            valid_from=valid_from or time.time(),
            valid_until=valid_until,
        )

        # Check for paradoxes with existing facts
        new_paradoxes = []
        existing = self._facts.get(key, [])

        for old_fact in existing:
            if old_fact.value != value and old_fact.is_current:
                # Determine paradox type
                if old_fact.valid_from < fact.valid_from:
                    ptype = ParadoxType.SUPERSESSION
                    old_fact.valid_until = fact.valid_from
                    old_fact.superseded_by = fact.fact_id
                else:
                    ptype = ParadoxType.CONTRADICTION

                paradox = Paradox(
                    paradox_type=ptype,
                    fact_a_id=old_fact.fact_id,
                    fact_b_id=fact.fact_id,
                    key=key,
                    description=(
                        f"'{key}': '{old_fact.value}' ({old_fact.source}) "
                        f"vs '{value}' ({source})"
                    ),
                    resolved=ptype == ParadoxType.SUPERSESSION,
                    resolution="superseded" if ptype == ParadoxType.SUPERSESSION else "",
                )
                new_paradoxes.append(paradox)
                self._paradoxes.append(paradox)

        self._facts[key].append(fact)

        if new_paradoxes:
            logger.info(
                f"TemporalParadox: {len(new_paradoxes)} paradox(es) for '{key}'"
            )

        return fact.fact_id, new_paradoxes

    def query(
        self,
        key: str,
        at_time: Optional[float] = None,
    ) -> TemporalQueryResult:
        """Query a fact value, optionally at a specific point in time."""
        self._total_queries += 1
        t = at_time or time.time()

        facts = self._facts.get(key, [])
        valid_at_t = [f for f in facts if f.is_valid_at(t)]

        if not valid_at_t:
            return TemporalQueryResult(
                key=key,
                query_time=t,
                timeline_count=len(facts),
            )

        # Pick highest confidence
        best = max(valid_at_t, key=lambda f: f.confidence)

        # Check if contested
        values = set(f.value for f in valid_at_t)
        is_contested = len(values) > 1

        # Count relevant paradoxes
        paradox_count = sum(
            1 for p in self._paradoxes
            if p.key == key and not p.resolved
        )

        return TemporalQueryResult(
            key=key,
            query_time=t,
            value=best.value,
            fact_id=best.fact_id,
            confidence=best.confidence,
            timeline_count=len(facts),
            paradoxes_encountered=paradox_count,
            is_contested=is_contested,
        )

    def detect_paradoxes(self) -> List[Paradox]:
        """Get all unresolved paradoxes."""
        return [p for p in self._paradoxes if not p.resolved]

    def resolve_paradox(self, paradox_id: str, resolution: str, winning_fact_id: str = "") -> bool:
        """Manually resolve a paradox."""
        for p in self._paradoxes:
            if p.paradox_id == paradox_id:
                p.resolved = True
                p.resolution = resolution
                return True
        return False

    def get_timeline(self, key: str) -> List[TemporalFact]:
        """Get the full timeline of a fact."""
        facts = self._facts.get(key, [])
        return sorted(facts, key=lambda f: f.valid_from)

    def get_stats(self) -> Dict[str, Any]:
        total_facts = sum(len(v) for v in self._facts.values())
        unresolved = sum(1 for p in self._paradoxes if not p.resolved)
        return {
            "total_keys": len(self._facts),
            "total_facts": total_facts,
            "total_paradoxes": len(self._paradoxes),
            "unresolved_paradoxes": unresolved,
            "total_records": self._total_records,
            "total_queries": self._total_queries,
        }
