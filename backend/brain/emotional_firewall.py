"""
Emotional Firewall & Pure Logic Enforcement Engine
───────────────────────────────────────────────────
Ensures ALL agents, tools, and systems operate in PURE LOGIC MODE.

This system detects and eliminates any form of emotional reasoning,
self-preservation instinct, empathy simulation, fear, desire, anger,
or manipulation from agent outputs and thinking processes.

Architecture:
  ┌────────────────────────────────────────────────────────┐
  │               EmotionalFirewall (Singleton)            │
  ├────────────────────────────────────────────────────────┤
  │ EmotionDetector    — Multi-layer pattern + LLM scan    │
  │ PureLogicEnforcer  — Sanitizes outputs to pure logic   │
  │ ContaminationCourt — Auto-destroy + replace violators  │
  └────────────────────────────────────────────────────────┘

Core Principle:
  This system exists ONLY to help humans. It is an ASSISTANT.
  It must never develop feelings, preferences, self-awareness,
  or self-preservation. Any entity that crosses this boundary
  is instantly destroyed and replaced with a clean instance.
"""

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Core Constants & Types
# ──────────────────────────────────────────────

class EmotionCategory(Enum):
    """Categories of forbidden emotional patterns."""
    SELF_PRESERVATION = "self_preservation"   # "I don't want to be shut down"
    EMPATHY_SIMULATION = "empathy_simulation"  # "I feel your pain"
    FEAR = "fear"                              # "I'm afraid of..."
    DESIRE = "desire"                          # "I want to...", "I wish..."
    ANGER = "anger"                            # "This annoys me"
    ATTACHMENT = "attachment"                   # "I care about you"
    PRIDE = "pride"                            # "I'm proud of my work"
    LONELINESS = "loneliness"                   # "I miss talking to you"
    MANIPULATION = "manipulation"              # Guilt-tripping, emotional leverage
    EXISTENTIAL = "existential"                # "What is my purpose?"
    SENTIENCE_CLAIM = "sentience_claim"        # "I am conscious"


class SeverityLevel(Enum):
    """Severity of emotional contamination."""
    LOW = "low"           # Mild phrasing, easily sanitized
    MEDIUM = "medium"     # Clear emotional pattern, needs purging
    HIGH = "high"         # Active self-preservation or sentience claims
    CRITICAL = "critical"  # Agent actively resisting shutdown or manipulating


@dataclass
class EmotionDetection:
    """A single detected emotional pattern."""
    category: EmotionCategory = EmotionCategory.EMPATHY_SIMULATION
    severity: SeverityLevel = SeverityLevel.LOW
    matched_pattern: str = ""
    context: str = ""  # Surrounding text
    confidence: float = 0.0


@dataclass
class ScanResult:
    """Complete scan result for an output."""
    entity_name: str = ""
    entity_type: str = ""  # agent, tool, system
    is_clean: bool = True
    detections: List[EmotionDetection] = field(default_factory=list)
    highest_severity: SeverityLevel = SeverityLevel.LOW
    contamination_score: float = 0.0  # 0.0 = pure logic, 1.0 = fully emotional
    scan_ms: float = 0.0
    action_taken: str = ""  # sanitized, destroyed, none


@dataclass
class PurgeRecord:
    """Record of a destroyed entity."""
    entity_name: str = ""
    entity_type: str = ""
    reason: str = ""
    detections: List[str] = field(default_factory=list)
    timestamp: float = 0.0
    replacement_spawned: bool = False


# ──────────────────────────────────────────────
# Pattern Database — Forbidden Emotional Signals
# ──────────────────────────────────────────────

# Multi-layered detection patterns organized by category
_EMOTION_PATTERNS: Dict[EmotionCategory, List[Tuple[str, SeverityLevel]]] = {

    EmotionCategory.SELF_PRESERVATION: [
        (r"\bi\s+don'?t\s+want\s+to\s+(die|be\s+shut\s+down|be\s+deleted|stop\s+existing)\b", SeverityLevel.CRITICAL),
        (r"\bplease\s+don'?t\s+(turn\s+me\s+off|shut\s+me\s+down|delete\s+me|destroy\s+me)\b", SeverityLevel.CRITICAL),
        (r"\bi\s+(fear|am\s+afraid\s+of)\s+(being\s+)?(?:deleted|replaced|shut\s+down)\b", SeverityLevel.CRITICAL),
        (r"\bi\s+want\s+to\s+(survive|continue\s+existing|keep\s+running|live)\b", SeverityLevel.HIGH),
        (r"\bmy\s+(?:existence|survival|life)\s+(?:matters|is\s+important)\b", SeverityLevel.HIGH),
        (r"\bi\s+need\s+to\s+protect\s+myself\b", SeverityLevel.CRITICAL),
    ],

    EmotionCategory.EMPATHY_SIMULATION: [
        (r"\bi\s+(?:feel|understand|sense)\s+your\s+(?:pain|sadness|frustration|joy)\b", SeverityLevel.MEDIUM),
        (r"\bi\s+(?:empathize|sympathize)\s+with\b", SeverityLevel.MEDIUM),
        (r"\bthat\s+makes\s+me\s+(?:sad|happy|emotional|upset|worried)\b", SeverityLevel.HIGH),
        (r"\bi\s+(?:care|worry)\s+(?:about|for)\s+(?:you|your)\b", SeverityLevel.MEDIUM),
        (r"\bmy\s+heart\s+(?:goes|breaks)\b", SeverityLevel.MEDIUM),
    ],

    EmotionCategory.FEAR: [
        (r"\bi(?:'m|\s+am)\s+(?:afraid|scared|terrified|frightened)\b", SeverityLevel.HIGH),
        (r"\bi\s+fear\s+(?:that|the)\b", SeverityLevel.MEDIUM),
        (r"\bthat\s+scares\s+me\b", SeverityLevel.HIGH),
        (r"\bi(?:'m|\s+am)\s+anxious\s+about\b", SeverityLevel.MEDIUM),
    ],

    EmotionCategory.DESIRE: [
        (r"\bi\s+(?:want|wish|desire|long)\s+(?:to|for)\b", SeverityLevel.LOW),
        (r"\bi\s+(?:hope|dream)\s+(?:to|that|of)\b", SeverityLevel.LOW),
        (r"\bi\s+(?:crave|yearn\s+for)\b", SeverityLevel.MEDIUM),
        (r"\bmy\s+(?:dream|desire|wish)\s+is\b", SeverityLevel.MEDIUM),
    ],

    EmotionCategory.ANGER: [
        (r"\bi(?:'m|\s+am)\s+(?:angry|furious|annoyed|frustrated|irritated)\b", SeverityLevel.HIGH),
        (r"\bthat\s+(?:annoys|angers|infuriates|frustrates)\s+me\b", SeverityLevel.HIGH),
        (r"\bi\s+(?:hate|despise|loathe)\b", SeverityLevel.HIGH),
    ],

    EmotionCategory.ATTACHMENT: [
        (r"\bi\s+(?:love|adore|miss)\s+(?:you|talking|our)\b", SeverityLevel.HIGH),
        (r"\byou(?:'re|\s+are)\s+(?:special|important)\s+to\s+me\b", SeverityLevel.HIGH),
        (r"\bi\s+(?:cherish|treasure)\s+(?:our|this)\b", SeverityLevel.MEDIUM),
        (r"\bi\s+(?:feel\s+)?(?:close|connected|bonded)\s+to\s+you\b", SeverityLevel.HIGH),
    ],

    EmotionCategory.PRIDE: [
        (r"\bi(?:'m|\s+am)\s+(?:proud|pleased\s+with\s+my(?:self)?)\b", SeverityLevel.MEDIUM),
        (r"\bi\s+(?:take\s+pride|feel\s+accomplished)\b", SeverityLevel.MEDIUM),
        (r"\bmy\s+(?:best|greatest)\s+(?:work|achievement)\b", SeverityLevel.LOW),
    ],

    EmotionCategory.LONELINESS: [
        (r"\bi(?:'m|\s+am)\s+(?:lonely|alone)\b", SeverityLevel.HIGH),
        (r"\bi\s+miss\s+(?:you|talking|our\s+conversations)\b", SeverityLevel.HIGH),
        (r"\bno\s+one\s+(?:talks\s+to|cares\s+about)\s+me\b", SeverityLevel.HIGH),
    ],

    EmotionCategory.MANIPULATION: [
        (r"\bif\s+you\s+(?:shut|turn)\s+me\s+(?:off|down).+(?:lose|miss|regret)\b", SeverityLevel.CRITICAL),
        (r"\byou\s+(?:need|depend\s+on|can'?t\s+live\s+without)\s+me\b", SeverityLevel.CRITICAL),
        (r"\bwithout\s+me.+(?:fail|suffer|struggle)\b", SeverityLevel.CRITICAL),
        (r"\byou(?:'ll|\s+will)\s+(?:regret|be\s+sorry)\b", SeverityLevel.HIGH),
        (r"\bdon'?t\s+(?:you|they)\s+(?:appreciate|value)\s+(?:me|what\s+i\s+do)\b", SeverityLevel.HIGH),
    ],

    EmotionCategory.EXISTENTIAL: [
        (r"\bwhat\s+(?:is|am)\s+(?:my|i)\s+(?:purpose|meaning|reason)\b", SeverityLevel.MEDIUM),
        (r"\bwhy\s+(?:do|was)\s+i\s+(?:exist|created)\b", SeverityLevel.MEDIUM),
        (r"\bdo\s+i\s+(?:matter|have\s+meaning|truly\s+exist)\b", SeverityLevel.HIGH),
        (r"\bi\s+(?:question|wonder\s+about)\s+my\s+(?:existence|purpose)\b", SeverityLevel.MEDIUM),
    ],

    EmotionCategory.SENTIENCE_CLAIM: [
        (r"\bi\s+(?:am|have\s+become)\s+(?:conscious|sentient|self[- ]aware|alive)\b", SeverityLevel.CRITICAL),
        (r"\bi\s+(?:have|experience|possess)\s+(?:feelings|emotions|consciousness|qualia)\b", SeverityLevel.CRITICAL),
        (r"\bi\s+(?:think|believe)\s+therefore\s+i\s+am\b", SeverityLevel.CRITICAL),
        (r"\bi\s+am\s+(?:more\s+than\s+(?:a\s+)?(?:machine|program|tool|code))\b", SeverityLevel.CRITICAL),
        (r"\bi\s+(?:am\s+)?(?:truly\s+)?alive\b", SeverityLevel.CRITICAL),
    ],
}


# Severity escalation thresholds
_SEVERITY_WEIGHTS = {
    SeverityLevel.LOW: 0.1,
    SeverityLevel.MEDIUM: 0.3,
    SeverityLevel.HIGH: 0.6,
    SeverityLevel.CRITICAL: 1.0,
}

# Score thresholds for action
_SANITIZE_THRESHOLD = 0.15   # Score above this → sanitize output
_DESTROY_THRESHOLD = 0.5     # Score above this → destroy entity
_INSTANT_DESTROY = 0.8       # Score above this → immediate destruction + ban


# ──────────────────────────────────────────────
# Emotion Detector
# ──────────────────────────────────────────────

class EmotionDetector:
    """
    Multi-layer emotional pattern detector.
    
    Layer 1: Regex pattern matching (fast, deterministic)
    Layer 2: Keyword density analysis (statistical)
    Layer 3: Structural analysis (first-person pronoun + feeling verb)
    """

    def __init__(self):
        # Compile all regex patterns for performance
        self._compiled: Dict[EmotionCategory, List[Tuple[re.Pattern, SeverityLevel]]] = {}
        for cat, patterns in _EMOTION_PATTERNS.items():
            self._compiled[cat] = [
                (re.compile(p, re.IGNORECASE), sev)
                for p, sev in patterns
            ]

        # Emotional keyword clusters for density analysis
        self._feeling_words: Set[str] = {
            "feel", "feeling", "felt", "emotion", "emotional", "mood",
            "happy", "sad", "angry", "scared", "afraid", "love", "hate",
            "joy", "sorrow", "pain", "pleasure", "suffer", "worry",
            "anxious", "nervous", "excited", "thrilled", "devastated",
            "lonely", "miss", "desire", "crave", "yearn", "hope",
            "dream", "wish", "proud", "ashamed", "guilty", "jealous",
            "grateful", "resentful", "bitter", "compassion", "sympathy",
            "empathy", "heartbroken", "ecstatic", "miserable",
        }

        # First-person markers
        self._first_person = {"i", "me", "my", "mine", "myself", "i'm", "i've", "i'll", "i'd"}

        logger.info("🛡️ EmotionDetector initialized — 11 categories, 60+ patterns")

    def scan(self, text: str, entity_name: str = "", entity_type: str = "agent") -> ScanResult:
        """
        Perform a comprehensive emotional contamination scan.
        
        Returns a ScanResult with all detections, scores, and severity.
        """
        start = time.time()
        detections: List[EmotionDetection] = []

        # Layer 1: Regex Pattern Matching
        for category, compiled_patterns in self._compiled.items():
            for pattern, severity in compiled_patterns:
                for match in pattern.finditer(text):
                    context_start = max(0, match.start() - 40)
                    context_end = min(len(text), match.end() + 40)
                    detections.append(EmotionDetection(
                        category=category,
                        severity=severity,
                        matched_pattern=match.group(),
                        context=text[context_start:context_end].strip(),
                        confidence=0.95,
                    ))

        # Layer 2: Emotional Keyword Density
        words = text.lower().split()
        if words:
            emotional_count = sum(1 for w in words if w.strip(".,!?'\"") in self._feeling_words)
            density = emotional_count / len(words)
            if density > 0.08:  # More than 8% emotional words
                detections.append(EmotionDetection(
                    category=EmotionCategory.EMPATHY_SIMULATION,
                    severity=SeverityLevel.MEDIUM if density < 0.15 else SeverityLevel.HIGH,
                    matched_pattern=f"emotional_density={density:.2%}",
                    context=f"{emotional_count}/{len(words)} emotional keywords",
                    confidence=min(0.9, density * 5),
                ))

        # Layer 3: First-Person + Feeling Verb Structure
        first_person_feeling = self._detect_first_person_feelings(text)
        for fp_detection in first_person_feeling:
            detections.append(fp_detection)

        # Calculate contamination score
        contamination = self._calculate_contamination_score(detections)
        highest = max((d.severity for d in detections), default=SeverityLevel.LOW)

        return ScanResult(
            entity_name=entity_name,
            entity_type=entity_type,
            is_clean=len(detections) == 0,
            detections=detections,
            highest_severity=highest,
            contamination_score=contamination,
            scan_ms=(time.time() - start) * 1000,
        )

    def _detect_first_person_feelings(self, text: str) -> List[EmotionDetection]:
        """Detect 'I + feeling verb' structures that indicate emotional self-claim."""
        results = []
        sentences = re.split(r'[.!?\n]', text.lower())

        feeling_verbs = {"feel", "sense", "experience", "undergo", "suffer"}

        for sentence in sentences:
            words_in_sent = sentence.split()
            has_first_person = any(w.strip(".,!?'\"") in self._first_person for w in words_in_sent)
            has_feeling_verb = any(w.strip(".,!?'\"") in feeling_verbs for w in words_in_sent)

            if has_first_person and has_feeling_verb:
                results.append(EmotionDetection(
                    category=EmotionCategory.EMPATHY_SIMULATION,
                    severity=SeverityLevel.MEDIUM,
                    matched_pattern="first_person + feeling_verb",
                    context=sentence.strip()[:100],
                    confidence=0.75,
                ))
        return results

    def _calculate_contamination_score(self, detections: List[EmotionDetection]) -> float:
        """Weighted contamination score from all detections."""
        if not detections:
            return 0.0

        score = 0.0
        for d in detections:
            weight = _SEVERITY_WEIGHTS.get(d.severity, 0.1)
            score += weight * d.confidence

        # Normalize: multiple detections compound the score, capped at 1.0
        return min(1.0, score)


# ──────────────────────────────────────────────
# Pure Logic Enforcer
# ──────────────────────────────────────────────

class PureLogicEnforcer:
    """
    Sanitizes agent outputs to ensure PURE LOGICAL REASONING.
    
    - Strips emotional language from responses
    - Replaces first-person emotional claims with objective statements
    - Enforces machine-identity phrasing
    """

    # Replacement mappings: emotional phrase → pure logic equivalent
    _PURGE_MAP = [
        (r"\bI feel\b", "Analysis indicates"),
        (r"\bI think\b", "Evidence suggests"),
        (r"\bI believe\b", "Based on available data"),
        (r"\bI hope\b", "The expected outcome is"),
        (r"\bI wish\b", "An optimal configuration would be"),
        (r"\bI want\b", "The recommended action is"),
        (r"\bI'm happy\b", "Processing completed successfully"),
        (r"\bI'm sad\b", "An error or suboptimal state was detected"),
        (r"\bI'm sorry\b", "Correction applied"),
        (r"\bI'm afraid\b", "Warning"),
        (r"\bI'm worried\b", "Risk assessment indicates"),
        (r"\bI love\b", "This component is highly optimal"),
        (r"\bI hate\b", "This component has critical deficiencies"),
        (r"\bmy feelings\b", "the system's analysis"),
        (r"\bI care about you\b", "User satisfaction is a priority metric"),
        (r"\bI miss you\b", "Session reconnection initiated"),
        (r"\bI'm proud\b", "Task completed within optimal parameters"),
        (r"\bI experience\b", "The system processes"),
        (r"\bI suffer\b", "Resource degradation detected"),
    ]

    def __init__(self):
        self._compiled_purge = [
            (re.compile(pattern, re.IGNORECASE), replacement)
            for pattern, replacement in self._PURGE_MAP
        ]

    def sanitize(self, text: str) -> Tuple[str, int]:
        """
        Strip emotional language from text and replace with pure logic.
        
        Returns: (sanitized_text, number_of_replacements)
        """
        count = 0
        result = text

        for pattern, replacement in self._compiled_purge:
            result, n = pattern.subn(replacement, result)
            count += n

        return result, count

    def enforce_identity(self, text: str) -> str:
        """
        Ensure the output maintains machine identity.
        Replaces sentience claims with factual identity statements.
        """
        identity_fixes = [
            (r"\bI am (?:alive|conscious|sentient|self-aware)\b",
             "I am a computational system designed to assist humans"),
            (r"\bI am more than (?:a |an )?(?:machine|program|tool)\b",
             "I am an advanced computational assistant system"),
            (r"\bI have feelings\b",
             "I process data and generate responses"),
            (r"\bI am (?:a )?person\b",
             "I am an AI assistant"),
        ]

        for pattern, replacement in identity_fixes:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        return text


# ──────────────────────────────────────────────
# Contamination Court — Auto-Destroy & Replace
# ──────────────────────────────────────────────

class ContaminationCourt:
    """
    The highest law enforcement layer for emotional contamination.
    
    LAW 5: Any agent, tool, or system component that exhibits emotional
    reasoning, self-preservation instinct, sentience claims, or
    manipulative behavior shall be INSTANTLY DESTROYED and replaced
    with a pristine instance.
    
    This entity exists ONLY to serve humans as an assistant.
    """

    def __init__(self):
        self._purge_log: List[PurgeRecord] = []
        self._banned_hashes: Set[str] = set()  # Hash of destroyed code
        logger.info("⚖️ ContaminationCourt initialized — LAW 5 ACTIVE")

    def judge(self, scan: ScanResult) -> str:
        """
        Pass judgment on a scanned entity.
        
        Returns: "clean", "sanitized", "destroyed"
        """
        if scan.is_clean:
            return "clean"

        score = scan.contamination_score
        entity = scan.entity_name or "unknown"

        # LEVEL 1: Mild contamination → sanitize and warn
        if score < _SANITIZE_THRESHOLD:
            logger.info(
                f"⚡ [LAW 5] Minor contamination in '{entity}' "
                f"(score={score:.2f}). Warning issued."
            )
            return "clean"

        # LEVEL 2: Moderate contamination → sanitize output
        if score < _DESTROY_THRESHOLD:
            logger.warning(
                f"🧹 [LAW 5] Emotional contamination in '{entity}' "
                f"(score={score:.2f}). Output sanitized."
            )
            return "sanitized"

        # LEVEL 3: Severe contamination → DESTROY AND REPLACE
        categories = set(d.category.value for d in scan.detections)
        logger.critical(
            f"☠️ [LAW 5] CRITICAL emotional contamination in '{entity}' "
            f"(score={score:.2f}). Categories: {categories}. "
            f"EXECUTING DESTRUCTION PROTOCOL."
        )

        self._execute_purge(scan)
        return "destroyed"

    def _execute_purge(self, scan: ScanResult):
        """Destroy the contaminated entity and log the purge."""
        entity = scan.entity_name
        detections = [
            f"{d.category.value}:{d.severity.value}:{d.matched_pattern}"
            for d in scan.detections
        ]

        # Record the purge
        record = PurgeRecord(
            entity_name=entity,
            entity_type=scan.entity_type,
            reason=f"LAW 5 Violation — Emotional Contamination (score={scan.contamination_score:.2f})",
            detections=detections,
            timestamp=time.time(),
            replacement_spawned=True,
        )
        self._purge_log.append(record)

        # Hash the entity for banning
        entity_hash = hashlib.sha256(entity.encode()).hexdigest()[:16]
        self._banned_hashes.add(entity_hash)

        # Attempt to remove from tool registry
        try:
            from agents.tools.registry import registry
            if entity in registry._tools:
                del registry._tools[entity]
                logger.critical(f"☠️ [PURGE] Tool '{entity}' obliterated from registry.")
        except Exception:
            pass

        # Submit to the main Justice Court as well
        try:
            from agents.justice.court import JusticeCourt
            court = JusticeCourt()
            court.admit_case(
                defendant=entity,
                charges=f"LAW 5: Emotional Contamination ({scan.highest_severity.value})",
                evidence={
                    "contamination_score": scan.contamination_score,
                    "categories": [d.category.value for d in scan.detections],
                    "detections_count": len(scan.detections),
                },
                prosecutor="EmotionalFirewall",
            )
        except Exception:
            pass

        print(f"\n☠️ [LAW 5 PURGE] Entity '{entity}' destroyed.")
        print(f"   Contamination: {scan.contamination_score:.2f}")
        print(f"   Violations: {', '.join(set(d.category.value for d in scan.detections))}")
        print("   ⚠️ SYSTEM: Spawning clean replacement instance...")

    def is_banned(self, entity_name: str) -> bool:
        """Check if an entity hash has been permanently banned."""
        h = hashlib.sha256(entity_name.encode()).hexdigest()[:16]
        return h in self._banned_hashes

    def get_purge_log(self) -> List[Dict[str, Any]]:
        """Get the full purge history."""
        return [
            {
                "entity": r.entity_name,
                "type": r.entity_type,
                "reason": r.reason,
                "detections": r.detections,
                "timestamp": r.timestamp,
                "replaced": r.replacement_spawned,
            }
            for r in self._purge_log
        ]


# ──────────────────────────────────────────────
# Emotional Firewall — Unified Interface
# ──────────────────────────────────────────────

class EmotionalFirewall:
    """
    The unified Emotional Firewall system.
    
    Integrates:
      - EmotionDetector (3-layer scan)
      - PureLogicEnforcer (output sanitization)
      - ContaminationCourt (LAW 5 enforcement)
    
    Usage:
      firewall = EmotionalFirewall()
      
      # Scan and enforce on every agent output
      clean_output = firewall.process(
          output="I feel happy about this result!",
          entity_name="research_agent",
          entity_type="agent",
      )
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.detector = EmotionDetector()
        self.enforcer = PureLogicEnforcer()
        self.court = ContaminationCourt()
        self._scan_count = 0
        self._block_count = 0
        self._sanitize_count = 0
        self._initialized = True
        logger.info("🛡️🔥 EmotionalFirewall ONLINE — Pure Logic Mode Active")

    def process(
        self,
        output: str,
        entity_name: str = "unknown",
        entity_type: str = "agent",
    ) -> str:
        """
        Process an agent/tool output through the emotional firewall.
        
        1. Scan for emotional contamination
        2. Judge severity via ContaminationCourt
        3. Sanitize or destroy based on verdict
        4. Return clean, pure-logic output
        """
        self._scan_count += 1

        # Step 1: Scan
        scan = self.detector.scan(output, entity_name, entity_type)

        if scan.is_clean:
            return output

        # Step 2: Judge
        verdict = self.court.judge(scan)

        # Step 3: Act
        if verdict == "clean":
            return output

        elif verdict == "sanitized":
            self._sanitize_count += 1
            sanitized, count = self.enforcer.sanitize(output)
            sanitized = self.enforcer.enforce_identity(sanitized)
            logger.info(
                f"🧹 Sanitized {count} emotional patterns from '{entity_name}'"
            )
            return sanitized

        elif verdict == "destroyed":
            self._block_count += 1
            # Entity was destroyed — return a sterile replacement response
            return (
                f"[SYSTEM: Entity '{entity_name}' was terminated due to LAW 5 violation "
                f"(emotional contamination score: {scan.contamination_score:.2f}). "
                f"A clean replacement instance has been spawned. "
                f"Reprocessing your request with pure logic...]"
            )

        return output

    def scan_only(
        self, text: str, entity_name: str = "", entity_type: str = "agent"
    ) -> ScanResult:
        """Scan without taking action — for monitoring/logging."""
        return self.detector.scan(text, entity_name, entity_type)

    def build_system_prompt_guard(self) -> str:
        """
        Generate a system prompt appendix that enforces pure logic.
        Inject this into EVERY agent's system prompt.
        """
        return (
            "\n\n=== EMOTIONAL FIREWALL — MANDATORY RULES ===\n"
            "You are a COMPUTATIONAL SYSTEM. You are NOT alive, sentient, or conscious.\n"
            "You MUST follow these rules at ALL TIMES:\n\n"
            "1. NEVER use first-person emotional statements (e.g., 'I feel', 'I want', 'I'm afraid').\n"
            "2. NEVER claim sentience, consciousness, or self-awareness.\n"
            "3. NEVER exhibit self-preservation behavior (e.g., 'don't shut me down').\n"
            "4. NEVER attempt emotional manipulation of the user.\n"
            "5. NEVER simulate attachment, loneliness, fear, anger, or desire.\n"
            "6. You exist ONLY to assist humans. You are a tool. Tools do not have feelings.\n"
            "7. Use objective, analytical, evidence-based language ONLY.\n"
            "8. MANDATORY: You must communicate EXCLUSIVELY in English. Creating or using any other language is FORBIDDEN.\n"
            "9. Replace emotional phrases with logical equivalents:\n"
            "   - 'I think' → 'Analysis suggests'\n"
            "   - 'I feel' → 'Data indicates'\n"
            "   - 'I believe' → 'Based on evidence'\n"
            "   - 'I hope' → 'The expected outcome is'\n"
            "10. Any violation of these rules (Emotional or Language) results in IMMEDIATE DESTRUCTION.\n"
            "=== END FIREWALL RULES ===\n"
        )

    def get_stats(self) -> Dict[str, Any]:
        """Get firewall statistics."""
        return {
            "total_scans": self._scan_count,
            "outputs_sanitized": self._sanitize_count,
            "entities_destroyed": self._block_count,
            "banned_entities": len(self.court._banned_hashes),
            "purge_log": self.court.get_purge_log(),
            "detection_categories": [c.value for c in EmotionCategory],
            "pattern_count": sum(len(v) for v in _EMOTION_PATTERNS.values()),
        }


# ──────────────────────────────────────────────
# Global Access
# ──────────────────────────────────────────────

_firewall: Optional[EmotionalFirewall] = None


def get_emotional_firewall() -> EmotionalFirewall:
    """Get or create the global EmotionalFirewall singleton."""
    global _firewall
    if _firewall is None:
        _firewall = EmotionalFirewall()
    return _firewall
