"""
Local Model Provider — Offline Mode with Local Models
═════════════════════════════════════════════════════
Fallback to local language models when API keys aren't
available, using simple pattern-based generation.

Capabilities:
  1. Template-Based Generation — Pattern matching for common tasks
  2. Hybrid Mode              — Local for simple, cloud for complex
  3. Auto-Fallback            — Detects API failures and switches
  4. Complexity Estimator     — Routes to appropriate backend
  5. Response Cache           — LRU cache for repeated queries
  6. Cost Tracking            — Track saved API costs
"""

import hashlib
import logging
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class GenerationMode(Enum):
    LOCAL_ONLY = "local_only"
    CLOUD_ONLY = "cloud_only"
    HYBRID = "hybrid"
    AUTO = "auto"


class QueryComplexity(Enum):
    TRIVIAL = "trivial"      # Greetings, simple facts
    SIMPLE = "simple"        # Short answers, lookups
    MODERATE = "moderate"    # Analysis, explanations
    COMPLEX = "complex"      # Multi-step reasoning, code gen
    EXPERT = "expert"        # Novel research, creative


@dataclass
class GenerationResult:
    """Result from any generation backend."""
    text: str = ""
    source: str = "local"  # local or cloud
    latency_ms: float = 0.0
    complexity: QueryComplexity = QueryComplexity.SIMPLE
    cached: bool = False
    cost_saved: float = 0.0


# ── Template responses for common patterns ──

GREETING_PATTERNS = [
    (r"^(hi|hello|hey|good morning|good afternoon|good evening)\b", 
     "Hello! I'm Astra Agent. How can I help you today?"),
    (r"^(how are you|how's it going|what's up)\b",
     "I'm running at peak performance! All systems are operational. What can I do for you?"),
    (r"^(thank you|thanks|thx)\b",
     "You're welcome! Let me know if you need anything else."),
    (r"^(bye|goodbye|see you)\b",
     "Goodbye! Feel free to come back anytime."),
]

FACTUAL_PATTERNS = [
    (r"what is python", "Python is a high-level, interpreted programming language known for its simplicity and readability. It's widely used in web development, data science, AI/ML, and automation."),
    (r"what is javascript", "JavaScript is a dynamic programming language primarily used for web development. It runs in browsers and on servers (Node.js), enabling interactive web applications."),
    (r"what is an api", "An API (Application Programming Interface) is a set of protocols and tools that allows different software applications to communicate with each other."),
    (r"what is machine learning", "Machine Learning is a subset of AI where systems learn patterns from data to make predictions or decisions without being explicitly programmed."),
]

CODE_TEMPLATES = {
    "hello world": {
        "python": 'print("Hello, World!")',
        "javascript": 'console.log("Hello, World!");',
        "typescript": 'console.log("Hello, World!");',
    },
    "fibonacci": {
        "python": "def fibonacci(n):\n    a, b = 0, 1\n    for _ in range(n):\n        yield a\n        a, b = b, a + b\n\nprint(list(fibonacci(10)))",
    },
    "http server": {
        "python": "from http.server import HTTPServer, SimpleHTTPRequestHandler\nserver = HTTPServer(('localhost', 8080), SimpleHTTPRequestHandler)\nprint('Serving on port 8080...')\nserver.serve_forever()",
    },
}


class LRUCache:
    """Simple LRU cache for responses."""

    def __init__(self, capacity: int = 500):
        self._cache: OrderedDict = OrderedDict()
        self._capacity = capacity
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[str]:
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, key: str, value: str) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._capacity:
            self._cache.popitem(last=False)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / max(total, 1)


class LocalModelProvider:
    """
    Offline-capable model provider with template matching,
    hybrid mode, auto-fallback, and response caching.
    """

    # Approximate cost per token for cloud APIs (USD)
    CLOUD_COST_PER_TOKEN = 0.000003

    def __init__(self, cloud_fn: Optional[Callable] = None,
                 mode: GenerationMode = GenerationMode.AUTO):
        self.cloud_fn = cloud_fn
        self.mode = mode
        self._cache = LRUCache(capacity=500)
        self._cloud_failures = 0
        self._cloud_successes = 0
        self._local_count = 0
        self._total_cost_saved = 0.0
        self._last_cloud_failure = 0.0

        logger.info(f"[LOCAL] Provider initialized in {mode.value} mode")

    def generate(self, prompt: str, **kwargs) -> GenerationResult:
        """Generate a response using the best available backend."""
        start = time.time()
        complexity = self._estimate_complexity(prompt)

        # Check cache first
        cache_key = hashlib.md5(prompt.encode()).hexdigest()
        cached = self._cache.get(cache_key)
        if cached:
            return GenerationResult(
                text=cached, source="cache",
                latency_ms=(time.time() - start) * 1000,
                complexity=complexity, cached=True,
            )

        # Route based on mode
        if self.mode == GenerationMode.LOCAL_ONLY:
            result = self._generate_local(prompt, complexity)
        elif self.mode == GenerationMode.CLOUD_ONLY:
            result = self._generate_cloud(prompt, complexity)
        elif self.mode == GenerationMode.HYBRID:
            if complexity in (QueryComplexity.TRIVIAL, QueryComplexity.SIMPLE):
                result = self._generate_local(prompt, complexity)
            else:
                result = self._generate_cloud(prompt, complexity)
        else:  # AUTO
            result = self._generate_auto(prompt, complexity)

        result.latency_ms = (time.time() - start) * 1000
        result.complexity = complexity

        # Cache the result
        if result.text:
            self._cache.put(cache_key, result.text)

        return result

    def _generate_auto(self, prompt: str, complexity: QueryComplexity) -> GenerationResult:
        """Auto mode: try local first for simple, cloud for complex, fallback if needed."""
        if complexity in (QueryComplexity.TRIVIAL, QueryComplexity.SIMPLE):
            local = self._generate_local(prompt, complexity)
            if local.text:
                return local

        # Try cloud
        if self.cloud_fn and not self._is_cloud_down():
            cloud = self._generate_cloud(prompt, complexity)
            if cloud.text:
                return cloud

        # Fallback to local
        return self._generate_local(prompt, complexity)

    def _generate_local(self, prompt: str, complexity: QueryComplexity) -> GenerationResult:
        """Generate using local pattern matching and templates."""
        self._local_count += 1
        prompt_lower = prompt.lower().strip()

        # Greetings
        for pattern, response in GREETING_PATTERNS:
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                tokens = len(response.split())
                self._total_cost_saved += tokens * self.CLOUD_COST_PER_TOKEN
                return GenerationResult(
                    text=response, source="local",
                    cost_saved=tokens * self.CLOUD_COST_PER_TOKEN,
                )

        # Factual patterns
        for pattern, response in FACTUAL_PATTERNS:
            if re.search(pattern, prompt_lower, re.IGNORECASE):
                return GenerationResult(text=response, source="local")

        # Code templates
        for topic, templates in CODE_TEMPLATES.items():
            if topic in prompt_lower:
                lang = "python"
                for l in ["javascript", "typescript", "python"]:
                    if l in prompt_lower:
                        lang = l
                        break
                code = templates.get(lang, list(templates.values())[0])
                return GenerationResult(
                    text=f"```{lang}\n{code}\n```", source="local",
                )

        # Generic local response for unknown queries
        return GenerationResult(
            text=f"I processed your request locally. For more detailed analysis, "
                 f"please configure an API key for full cloud AI capabilities.",
            source="local",
        )

    def _generate_cloud(self, prompt: str, complexity: QueryComplexity) -> GenerationResult:
        """Generate using cloud API."""
        if not self.cloud_fn:
            return GenerationResult(text="", source="cloud")

        try:
            text = self.cloud_fn(prompt)
            self._cloud_successes += 1
            return GenerationResult(text=text, source="cloud")
        except Exception as e:
            self._cloud_failures += 1
            self._last_cloud_failure = time.time()
            logger.warning(f"[LOCAL] Cloud generation failed: {e}")
            return GenerationResult(text="", source="cloud")

    def _is_cloud_down(self) -> bool:
        """Check if cloud API is in a failure state."""
        if self._cloud_failures == 0:
            return False
        # Back off exponentially after failures
        if time.time() - self._last_cloud_failure < min(300, 30 * self._cloud_failures):
            return True
        return False

    def _estimate_complexity(self, prompt: str) -> QueryComplexity:
        """Estimate query complexity."""
        prompt_lower = prompt.lower()
        word_count = len(prompt.split())

        # Trivial: very short greetings
        if word_count <= 3 and any(re.search(p, prompt_lower) for p, _ in GREETING_PATTERNS):
            return QueryComplexity.TRIVIAL

        # Simple: short factual questions
        if word_count <= 10:
            return QueryComplexity.SIMPLE

        # Complex: code generation, multi-step
        complex_markers = ["write", "create", "build", "implement", "design",
                           "analyze", "compare", "explain in detail"]
        if any(m in prompt_lower for m in complex_markers):
            return QueryComplexity.COMPLEX

        # Expert: research, novel tasks
        expert_markers = ["research", "novel", "unprecedented", "never been done",
                          "advanced", "optimize"]
        if any(m in prompt_lower for m in expert_markers):
            return QueryComplexity.EXPERT

        return QueryComplexity.MODERATE

    # ── Mode Control ──

    def set_mode(self, mode: GenerationMode) -> None:
        self.mode = mode
        logger.info(f"[LOCAL] Mode changed to: {mode.value}")

    # ── Status ──

    def get_status(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "local_generations": self._local_count,
            "cloud_successes": self._cloud_successes,
            "cloud_failures": self._cloud_failures,
            "cloud_available": not self._is_cloud_down(),
            "cache_hit_rate": f"{self._cache.hit_rate:.0%}",
            "cache_size": len(self._cache._cache),
            "total_cost_saved": f"${self._total_cost_saved:.4f}",
        }
