"""
Persistent Memory Store — Cross-Session Learning Database.
===========================================================
Saves and loads everything the ASI learns across sessions:
evolution results, task patterns, user preferences, knowledge graphs.

Uses SQLite for zero-dependency persistence.

Classes:
  MemoryEntry   — A single memory record
  MemoryStore   — The main persistent store
"""

import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB = str(Path.home() / ".astra" / "memory.db")


@dataclass
class MemoryEntry:
    """A single memory record."""
    key: str = ""
    value: Any = None
    category: str = "general"
    importance: float = 0.5
    access_count: int = 0
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    tags: List[str] = field(default_factory=list)

    @property
    def is_expired(self) -> bool:
        return bool(self.expires_at and time.time() > self.expires_at)


class MemoryStore:
    """
    Cross-session persistent memory using SQLite.

    Categories:
      - evolution   : Genome fitness, prompt ELO scores
      - patterns    : Task success/failure patterns
      - preferences : User coding style, preferences
      - knowledge   : Learned facts and relationships
      - decisions   : Past decisions and outcomes
      - reflections : Self-reflection insights

    Usage:
        store = MemoryStore()
        store.remember("user_prefers_python", True, category="preferences")
        val = store.recall("user_prefers_python")
        similar = store.search("python", category="preferences")
    """

    def __init__(self, db_path: str = ""):
        self.db_path = db_path or _DEFAULT_DB
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    category TEXT DEFAULT 'general',
                    importance REAL DEFAULT 0.5,
                    access_count INTEGER DEFAULT 0,
                    created_at REAL,
                    updated_at REAL,
                    expires_at REAL,
                    tags TEXT DEFAULT '[]'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC)
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS decision_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision TEXT NOT NULL,
                    alternatives TEXT,
                    outcome TEXT,
                    confidence REAL,
                    reasoning TEXT,
                    timestamp REAL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS evolution_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    generation INTEGER,
                    best_fitness REAL,
                    avg_fitness REAL,
                    population_size INTEGER,
                    genome_snapshot TEXT,
                    timestamp REAL
                )
            """)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Core Memory Operations ──

    def remember(self, key: str, value: Any, category: str = "general",
                 importance: float = 0.5, tags: List[str] = None,
                 ttl_seconds: Optional[float] = None) -> bool:
        """Store or update a memory."""
        now = time.time()
        expires = now + ttl_seconds if ttl_seconds else None
        serialized = json.dumps(value, default=str)
        tags_json = json.dumps(tags or [])

        with self._conn() as conn:
            conn.execute("""
                INSERT INTO memories (key, value, category, importance, access_count,
                                      created_at, updated_at, expires_at, tags)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    category = excluded.category,
                    importance = excluded.importance,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at,
                    tags = excluded.tags
            """, (key, serialized, category, importance, now, now, expires, tags_json))
        return True

    def recall(self, key: str) -> Optional[Any]:
        """Retrieve a memory by key."""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM memories WHERE key = ?", (key,)).fetchone()
            if not row:
                return None

            # Check expiry
            if row["expires_at"] and time.time() > row["expires_at"]:
                conn.execute("DELETE FROM memories WHERE key = ?", (key,))
                return None

            # Update access count
            conn.execute(
                "UPDATE memories SET access_count = access_count + 1 WHERE key = ?",
                (key,),
            )
            return json.loads(row["value"])

    def forget(self, key: str) -> bool:
        """Delete a specific memory."""
        with self._conn() as conn:
            cursor = conn.execute("DELETE FROM memories WHERE key = ?", (key,))
            return cursor.rowcount > 0

    def search(self, query: str, category: str = "", limit: int = 20) -> List[MemoryEntry]:
        """Search memories by key/value content."""
        sql = "SELECT * FROM memories WHERE (key LIKE ? OR value LIKE ?)"
        params: list = [f"%{query}%", f"%{query}%"]
        if category:
            sql += " AND category = ?"
            params.append(category)
        sql += " ORDER BY importance DESC, access_count DESC LIMIT ?"
        params.append(limit)

        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def get_category(self, category: str, limit: int = 50) -> List[MemoryEntry]:
        """Get all memories in a category."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE category = ? ORDER BY importance DESC LIMIT ?",
                (category, limit),
            ).fetchall()
            return [self._row_to_entry(r) for r in rows]

    def get_important(self, min_importance: float = 0.7, limit: int = 20) -> List[MemoryEntry]:
        """Get the most important memories."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM memories WHERE importance >= ? ORDER BY importance DESC LIMIT ?",
                (min_importance, limit),
            ).fetchall()
            return [self._row_to_entry(r) for r in rows]

    # ── Decision Log ──

    def log_decision(self, decision: str, alternatives: List[str] = None,
                     outcome: str = "", confidence: float = 0.5,
                     reasoning: str = ""):
        """Log a decision for future learning."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO decision_log (decision, alternatives, outcome, confidence,
                                          reasoning, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (decision, json.dumps(alternatives or []), outcome,
                  confidence, reasoning, time.time()))

    def get_past_decisions(self, limit: int = 20) -> List[Dict]:
        """Retrieve recent decisions."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM decision_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Evolution Log ──

    def log_evolution(self, generation: int, best_fitness: float,
                      avg_fitness: float, population_size: int,
                      genome_snapshot: Dict = None):
        """Log an evolution generation."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO evolution_log (generation, best_fitness, avg_fitness,
                                           population_size, genome_snapshot, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (generation, best_fitness, avg_fitness, population_size,
                  json.dumps(genome_snapshot or {}), time.time()))

    def get_evolution_history(self, limit: int = 100) -> List[Dict]:
        """Get evolution history."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM evolution_log ORDER BY generation DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ── Maintenance ──

    def cleanup_expired(self) -> int:
        """Remove expired memories."""
        with self._conn() as conn:
            cursor = conn.execute(
                "DELETE FROM memories WHERE expires_at IS NOT NULL AND expires_at < ?",
                (time.time(),),
            )
            return cursor.rowcount

    def get_stats(self) -> Dict[str, Any]:
        """Get memory store statistics."""
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
            cats = conn.execute(
                "SELECT category, COUNT(*) as cnt FROM memories GROUP BY category"
            ).fetchall()
            decisions = conn.execute("SELECT COUNT(*) FROM decision_log").fetchone()[0]
            evolutions = conn.execute("SELECT COUNT(*) FROM evolution_log").fetchone()[0]

            return {
                "total_memories": total,
                "categories": {r["category"]: r["cnt"] for r in cats},
                "total_decisions_logged": decisions,
                "total_evolution_generations": evolutions,
                "db_size_bytes": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
            }

    def _row_to_entry(self, row) -> MemoryEntry:
        return MemoryEntry(
            key=row["key"],
            value=json.loads(row["value"]),
            category=row["category"],
            importance=row["importance"],
            access_count=row["access_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
        )
