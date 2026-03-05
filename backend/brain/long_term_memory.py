"""
Persistent Long-Term Memory System
───────────────────────────────────
Three complementary memory subsystems that give the agent true 
long-term learning capabilities across sessions.

  📖 Episodic Memory   — Remember full conversation contexts across sessions
  🧠 Procedural Memory — Learn user preferences, patterns, and habits
  🕸️ Knowledge Graph   — Build growing network of entities and relationships

All memories persist to disk as JSON and are loaded on startup.
"""

import hashlib
import json
import logging
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────
# Data Models
# ──────────────────────────────────────────────

@dataclass
class Episode:
    """A single conversation episode stored in episodic memory."""
    episode_id: str = ""
    timestamp: float = 0.0
    topic: str = ""
    summary: str = ""
    user_messages: List[str] = field(default_factory=list)
    agent_responses: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    outcome: str = ""  # success, failure, partial
    tags: List[str] = field(default_factory=list)


@dataclass
class UserPreference:
    """A learned user preference or pattern."""
    key: str = ""
    value: str = ""
    confidence: float = 0.5
    observed_count: int = 1
    first_seen: float = 0.0
    last_seen: float = 0.0
    source_episodes: List[str] = field(default_factory=list)


@dataclass
class KnowledgeEntity:
    """An entity in the knowledge graph."""
    entity_id: str = ""
    name: str = ""
    entity_type: str = ""  # person, concept, tool, language, framework, etc.
    attributes: Dict[str, str] = field(default_factory=dict)
    first_mentioned: float = 0.0
    mention_count: int = 1


@dataclass
class KnowledgeRelation:
    """A relationship between two entities in the knowledge graph."""
    source_id: str = ""
    target_id: str = ""
    relation_type: str = ""  # uses, is_part_of, related_to, prefers, etc.
    strength: float = 0.5
    context: str = ""


# ──────────────────────────────────────────────
# Episodic Memory
# ──────────────────────────────────────────────

class EpisodicMemory:
    """
    Remember full conversation contexts across sessions.
    
    Stores conversation summaries and key exchanges, enabling the agent
    to recall: "Last time we discussed X, and you mentioned Y..."
    """

    def __init__(self, persist_dir: Path):
        self._dir = persist_dir / "episodic"
        self._dir.mkdir(parents=True, exist_ok=True)
        self.episodes: List[Episode] = []
        self._max_episodes = 500
        self._load()

    def store_episode(
        self,
        topic: str,
        user_messages: List[str],
        agent_responses: List[str],
        tools_used: List[str] = None,
        outcome: str = "success",
        tags: List[str] = None,
    ) -> str:
        """Store a new conversation episode."""
        episode_id = hashlib.sha256(
            f"{topic}{time.time()}".encode()
        ).hexdigest()[:12]

        # Auto-generate summary from the conversation
        summary = self._generate_summary(topic, user_messages, agent_responses)

        episode = Episode(
            episode_id=episode_id,
            timestamp=time.time(),
            topic=topic,
            summary=summary,
            user_messages=user_messages[-10:],  # Keep last 10 messages
            agent_responses=agent_responses[-10:],
            tools_used=tools_used or [],
            outcome=outcome,
            tags=tags or [],
        )

        self.episodes.append(episode)

        # Enforce capacity
        if len(self.episodes) > self._max_episodes:
            self.episodes = self.episodes[-self._max_episodes:]

        self._save()
        logger.info(f"📖 Stored episode: {episode_id} ({topic[:50]})")
        return episode_id

    def recall(self, query: str, max_results: int = 5) -> List[Episode]:
        """
        Recall relevant episodes based on a query.
        Uses keyword matching on topics, summaries, and tags.
        """
        query_words = set(query.lower().split())
        scored_episodes = []

        for ep in self.episodes:
            score = 0.0
            searchable = (
                f"{ep.topic} {ep.summary} {' '.join(ep.tags)}"
            ).lower()

            for word in query_words:
                if word in searchable:
                    score += 1.0

            # Recency bonus
            age_days = (time.time() - ep.timestamp) / 86400
            recency_bonus = max(0, 1.0 - age_days / 30)  # Decay over 30 days
            score += recency_bonus * 0.5

            if score > 0:
                scored_episodes.append((score, ep))

        scored_episodes.sort(key=lambda x: x[0], reverse=True)
        return [ep for _, ep in scored_episodes[:max_results]]

    def get_recent(self, n: int = 5) -> List[Episode]:
        """Get the N most recent episodes."""
        return self.episodes[-n:]

    def _generate_summary(
        self, topic: str, user_msgs: List[str], agent_msgs: List[str]
    ) -> str:
        """Generate a simple summary of the conversation."""
        parts = [f"Topic: {topic}"]
        if user_msgs:
            first_q = user_msgs[0][:200]
            parts.append(f"Started with: {first_q}")
        if agent_msgs:
            last_a = agent_msgs[-1][:200]
            parts.append(f"Concluded with: {last_a}")
        parts.append(f"Exchanges: {len(user_msgs)}")
        return ". ".join(parts)

    def _save(self):
        path = self._dir / "episodes.json"
        data = [asdict(ep) for ep in self.episodes]
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _load(self):
        path = self._dir / "episodes.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.episodes = [Episode(**ep) for ep in data]
                logger.info(f"📖 Loaded {len(self.episodes)} episodes")
            except Exception as e:
                logger.warning(f"Failed to load episodes: {e}")


# ──────────────────────────────────────────────
# Procedural Memory
# ──────────────────────────────────────────────

class ProceduralMemory:
    """
    Learn user preferences, coding style, and behavior patterns over time.
    
    Tracks: preferred languages, communication style, expertise areas,
    common requests, and interaction patterns.
    """

    def __init__(self, persist_dir: Path):
        self._dir = persist_dir / "procedural"
        self._dir.mkdir(parents=True, exist_ok=True)
        self.preferences: Dict[str, UserPreference] = {}
        self._interaction_count = 0
        self._load()

    def observe(self, user_message: str, agent_response: str, tools_used: List[str] = None):
        """
        Observe a user interaction and extract/update preferences.
        Called after every interaction to continuously learn.
        """
        self._interaction_count += 1
        now = time.time()

        # Extract patterns from user message
        patterns = self._extract_patterns(user_message)

        for key, value in patterns.items():
            if key in self.preferences:
                pref = self.preferences[key]
                pref.observed_count += 1
                pref.last_seen = now
                pref.confidence = min(1.0, pref.confidence + 0.05)
                if value != pref.value:
                    # Value changed — adjust confidence
                    pref.value = value
                    pref.confidence = max(0.3, pref.confidence - 0.1)
            else:
                self.preferences[key] = UserPreference(
                    key=key, value=value,
                    confidence=0.3,
                    observed_count=1,
                    first_seen=now,
                    last_seen=now,
                )

        # Track tool usage patterns
        if tools_used:
            for tool in tools_used:
                tool_key = f"preferred_tool:{tool}"
                if tool_key in self.preferences:
                    self.preferences[tool_key].observed_count += 1
                    self.preferences[tool_key].last_seen = now
                else:
                    self.preferences[tool_key] = UserPreference(
                        key=tool_key, value=tool,
                        confidence=0.2, first_seen=now, last_seen=now,
                    )

        # Auto-save periodically
        if self._interaction_count % 5 == 0:
            self._save()

    def get_preference(self, key: str) -> Optional[UserPreference]:
        return self.preferences.get(key)

    def get_user_profile(self) -> Dict[str, Any]:
        """Build a user profile from accumulated preferences."""
        profile = {}

        # Group by category
        for key, pref in self.preferences.items():
            if pref.confidence < 0.3:
                continue  # Skip low-confidence observations

            if ":" in key:
                category, name = key.split(":", 1)
            else:
                category = "general"
                name = key

            if category not in profile:
                profile[category] = []
            profile[category].append({
                "name": name,
                "value": pref.value,
                "confidence": round(pref.confidence, 2),
                "observations": pref.observed_count,
            })

        return profile

    def get_context_prompt(self) -> str:
        """Generate a context string for the LLM system prompt."""
        high_conf = [
            p for p in self.preferences.values() 
            if p.confidence >= 0.5
        ]
        if not high_conf:
            return ""

        parts = ["USER PREFERENCES (learned over time):"]
        for pref in sorted(high_conf, key=lambda x: x.confidence, reverse=True)[:10]:
            parts.append(f"  - {pref.key}: {pref.value} (confidence: {pref.confidence:.0%})")

        return "\n".join(parts)

    def _extract_patterns(self, message: str) -> Dict[str, str]:
        """Extract user patterns from a message."""
        patterns = {}
        msg_lower = message.lower()

        # Detect programming language preferences
        lang_patterns = {
            "python": r'\bpython\b', "javascript": r'\bjavascript\b|\bjs\b',
            "typescript": r'\btypescript\b|\bts\b', "java": r'\bjava\b(?!script)',
            "rust": r'\brust\b', "go": r'\bgo\b|\bgolang\b',
            "c++": r'\bc\+\+\b|\bcpp\b', "c#": r'\bc#\b|\bcsharp\b',
        }
        for lang, pattern in lang_patterns.items():
            if re.search(pattern, msg_lower):
                patterns["preferred_language"] = lang

        # Detect communication preference
        if any(w in msg_lower for w in ["explain simply", "beginner", "eli5"]):
            patterns["communication_style"] = "simple"
        elif any(w in msg_lower for w in ["be concise", "brief", "tl;dr"]):
            patterns["communication_style"] = "concise"
        elif any(w in msg_lower for w in ["in detail", "comprehensive", "thorough"]):
            patterns["communication_style"] = "detailed"

        # Detect expertise domain
        domain_keywords = {
            "web_development": ["react", "html", "css", "frontend", "backend", "api"],
            "data_science": ["data", "pandas", "numpy", "ml", "machine learning"],
            "devops": ["docker", "kubernetes", "ci/cd", "deploy", "aws", "cloud"],
            "mobile": ["android", "ios", "flutter", "react native", "mobile"],
            "security": ["security", "vulnerability", "penetration", "encryption"],
        }
        for domain, keywords in domain_keywords.items():
            if any(kw in msg_lower for kw in keywords):
                patterns["expertise_domain"] = domain

        return patterns

    def _save(self):
        path = self._dir / "preferences.json"
        data = {k: asdict(v) for k, v in self.preferences.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _load(self):
        path = self._dir / "preferences.json"
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.preferences = {
                    k: UserPreference(**v) for k, v in data.items()
                }
                logger.info(
                    f"🧠 Loaded {len(self.preferences)} user preferences"
                )
            except Exception as e:
                logger.warning(f"Failed to load preferences: {e}")


# ──────────────────────────────────────────────
# Knowledge Graph
# ──────────────────────────────────────────────

class KnowledgeGraph:
    """
    A growing network of entities and relationships extracted from conversations.
    
    Entities: technologies, concepts, people, projects, etc.
    Relations: uses, prefers, is_part_of, related_to, depends_on, etc.
    """

    def __init__(self, persist_dir: Path):
        self._dir = persist_dir / "knowledge_graph"
        self._dir.mkdir(parents=True, exist_ok=True)
        self.entities: Dict[str, KnowledgeEntity] = {}
        self.relations: List[KnowledgeRelation] = []
        self._max_entities = 2000
        self._max_relations = 5000
        self._load()

    def add_entity(
        self, name: str, entity_type: str, attributes: Dict[str, str] = None
    ) -> str:
        """Add or update an entity in the graph."""
        entity_id = self._make_id(name)

        if entity_id in self.entities:
            self.entities[entity_id].mention_count += 1
            if attributes:
                self.entities[entity_id].attributes.update(attributes)
        else:
            self.entities[entity_id] = KnowledgeEntity(
                entity_id=entity_id,
                name=name,
                entity_type=entity_type,
                attributes=attributes or {},
                first_mentioned=time.time(),
                mention_count=1,
            )

        self._enforce_limits()
        return entity_id

    def add_relation(
        self, source_name: str, target_name: str,
        relation_type: str, context: str = ""
    ):
        """Add a relationship between two entities."""
        source_id = self._make_id(source_name)
        target_id = self._make_id(target_name)

        # Check for existing relation
        for rel in self.relations:
            if (rel.source_id == source_id and rel.target_id == target_id 
                    and rel.relation_type == relation_type):
                rel.strength = min(1.0, rel.strength + 0.1)
                return

        self.relations.append(KnowledgeRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            strength=0.5,
            context=context,
        ))

        self._enforce_limits()

    def extract_from_conversation(self, user_msg: str, agent_response: str):
        """
        Auto-extract entities and relationships from a conversation turn.
        Uses pattern matching to identify technologies, concepts, etc.
        """
        combined = f"{user_msg} {agent_response}"

        # Extract technology entities
        tech_patterns = {
            "language": [
                "Python", "JavaScript", "TypeScript", "Java", "Rust", "Go",
                "C\\+\\+", "C#", "Ruby", "Swift", "Kotlin", "PHP",
            ],
            "framework": [
                "React", "Angular", "Vue", "Django", "Flask", "FastAPI",
                "Express", "Spring", "Next\\.js", "TensorFlow", "PyTorch",
            ],
            "tool": [
                "Docker", "Kubernetes", "Git", "AWS", "Azure", "GCP",
                "PostgreSQL", "MongoDB", "Redis", "Nginx", "Linux",
            ],
            "concept": [
                "API", "REST", "GraphQL", "microservice", "algorithm",
                "machine learning", "neural network", "encryption",
                "authentication", "CI/CD", "DevOps",
            ],
        }

        extracted_entities = []
        for entity_type, patterns in tech_patterns.items():
            for pattern in patterns:
                if re.search(rf'\b{pattern}\b', combined, re.IGNORECASE):
                    clean_name = pattern.replace("\\", "")
                    eid = self.add_entity(clean_name, entity_type)
                    extracted_entities.append((eid, clean_name))

        # Auto-create relations between co-mentioned entities
        for i, (id1, name1) in enumerate(extracted_entities):
            for id2, name2 in extracted_entities[i+1:]:
                self.add_relation(
                    name1, name2, "co_mentioned",
                    context=user_msg[:100]
                )

    def query_entity(self, name: str) -> Optional[Dict[str, Any]]:
        """Query everything known about an entity."""
        entity_id = self._make_id(name)
        entity = self.entities.get(entity_id)
        if not entity:
            return None

        # Find all relations
        relations_out = [
            r for r in self.relations if r.source_id == entity_id
        ]
        relations_in = [
            r for r in self.relations if r.target_id == entity_id
        ]

        related_entities = set()
        for r in relations_out:
            if r.target_id in self.entities:
                related_entities.add(self.entities[r.target_id].name)
        for r in relations_in:
            if r.source_id in self.entities:
                related_entities.add(self.entities[r.source_id].name)

        return {
            "name": entity.name,
            "type": entity.entity_type,
            "mentions": entity.mention_count,
            "attributes": entity.attributes,
            "related_to": list(related_entities)[:10],
            "relation_count": len(relations_out) + len(relations_in),
        }

    def get_context_prompt(self) -> str:
        """Generate knowledge context for the LLM."""
        if not self.entities:
            return ""

        # Top entities by mention count
        top = sorted(
            self.entities.values(),
            key=lambda e: e.mention_count,
            reverse=True,
        )[:15]

        parts = ["KNOWLEDGE GRAPH (entities the user frequently discusses):"]
        for e in top:
            related = [
                self.entities[r.target_id].name
                for r in self.relations
                if r.source_id == e.entity_id and r.target_id in self.entities
            ][:3]
            rel_str = f" → {', '.join(related)}" if related else ""
            parts.append(
                f"  - {e.name} ({e.entity_type}, mentioned {e.mention_count}x){rel_str}"
            )

        return "\n".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_entities": len(self.entities),
            "total_relations": len(self.relations),
            "entity_types": dict(Counter(
                e.entity_type for e in self.entities.values()
            )),
            "top_entities": [
                {"name": e.name, "type": e.entity_type, "mentions": e.mention_count}
                for e in sorted(
                    self.entities.values(),
                    key=lambda e: e.mention_count, reverse=True,
                )[:10]
            ],
        }

    def _make_id(self, name: str) -> str:
        return hashlib.sha256(name.lower().encode()).hexdigest()[:10]

    def _enforce_limits(self):
        if len(self.entities) > self._max_entities:
            # Remove least-mentioned entities
            sorted_entities = sorted(
                self.entities.items(),
                key=lambda x: x[1].mention_count
            )
            for eid, _ in sorted_entities[:100]:
                del self.entities[eid]
                self.relations = [
                    r for r in self.relations
                    if r.source_id != eid and r.target_id != eid
                ]

        if len(self.relations) > self._max_relations:
            self.relations.sort(key=lambda r: r.strength, reverse=True)
            self.relations = self.relations[:self._max_relations]

    def _save(self):
        entities_path = self._dir / "entities.json"
        relations_path = self._dir / "relations.json"

        with open(entities_path, "w", encoding="utf-8") as f:
            json.dump(
                {k: asdict(v) for k, v in self.entities.items()},
                f, indent=2, default=str,
            )
        with open(relations_path, "w", encoding="utf-8") as f:
            json.dump(
                [asdict(r) for r in self.relations],
                f, indent=2, default=str,
            )

    def _load(self):
        entities_path = self._dir / "entities.json"
        relations_path = self._dir / "relations.json"

        if entities_path.exists():
            try:
                with open(entities_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.entities = {
                    k: KnowledgeEntity(**v) for k, v in data.items()
                }
            except Exception as e:
                logger.warning(f"Failed to load entities: {e}")

        if relations_path.exists():
            try:
                with open(relations_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.relations = [KnowledgeRelation(**r) for r in data]
            except Exception as e:
                logger.warning(f"Failed to load relations: {e}")

        if self.entities:
            logger.info(
                f"🕸️ Loaded knowledge graph: {len(self.entities)} entities, "
                f"{len(self.relations)} relations"
            )


# ──────────────────────────────────────────────
# Unified Long-Term Memory Manager
# ──────────────────────────────────────────────

class LongTermMemory:
    """
    Unified interface to all three memory subsystems.
    
    Provides a single point of access for storing, querying,
    and generating context from long-term memories.
    """

    def __init__(self, persist_dir: str = None):
        from config.settings import MEMORY_DIR
        self._dir = Path(persist_dir or str(MEMORY_DIR)) / "long_term"
        self._dir.mkdir(parents=True, exist_ok=True)

        self.episodic = EpisodicMemory(self._dir)
        self.procedural = ProceduralMemory(self._dir)
        self.knowledge = KnowledgeGraph(self._dir)

        logger.info(
            f"🧠 LongTermMemory initialized: "
            f"{len(self.episodic.episodes)} episodes, "
            f"{len(self.procedural.preferences)} preferences, "
            f"{len(self.knowledge.entities)} entities"
        )

    def observe_interaction(
        self,
        user_message: str,
        agent_response: str,
        tools_used: List[str] = None,
        topic: str = "",
    ):
        """
        Call after every interaction to build long-term memory.
        Updates all three subsystems.
        """
        # Procedural: learn preferences
        self.procedural.observe(user_message, agent_response, tools_used)

        # Knowledge: extract entities
        self.knowledge.extract_from_conversation(user_message, agent_response)

    def store_conversation(
        self,
        topic: str,
        user_messages: List[str],
        agent_responses: List[str],
        tools_used: List[str] = None,
        outcome: str = "success",
    ):
        """Store a complete conversation as an episode."""
        self.episodic.store_episode(
            topic=topic,
            user_messages=user_messages,
            agent_responses=agent_responses,
            tools_used=tools_used,
            outcome=outcome,
        )

    def build_context(self, query: str) -> str:
        """
        Build a comprehensive long-term memory context string
        for injection into the LLM system prompt.
        """
        parts = []

        # Episodic: relevant past conversations
        relevant_episodes = self.episodic.recall(query, max_results=3)
        if relevant_episodes:
            parts.append("RELEVANT PAST CONVERSATIONS:")
            for ep in relevant_episodes:
                parts.append(f"  📖 {ep.topic}: {ep.summary[:150]}")

        # Procedural: user preferences
        proc_ctx = self.procedural.get_context_prompt()
        if proc_ctx:
            parts.append(proc_ctx)

        # Knowledge: entity context
        kg_ctx = self.knowledge.get_context_prompt()
        if kg_ctx:
            parts.append(kg_ctx)

        return "\n\n".join(parts) if parts else ""

    def save_all(self):
        """Persist all memory subsystems to disk."""
        self.episodic._save()
        self.procedural._save()
        self.knowledge._save()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "episodic": {
                "episodes": len(self.episodic.episodes),
                "recent_topics": [
                    ep.topic for ep in self.episodic.get_recent(5)
                ],
            },
            "procedural": {
                "preferences": len(self.procedural.preferences),
                "interactions": self.procedural._interaction_count,
            },
            "knowledge_graph": self.knowledge.get_stats(),
        }
