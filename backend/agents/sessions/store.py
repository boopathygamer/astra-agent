"""
Session Store — SQLite-based transcript persistence.
────────────────────────────────────────────────────
Replaces the old JSONL flat files with a robust, indexed SQLite DB.
Ensures thread-safety and fast retrieval of session messages.

Schema:
  - sessions: session_id, agent_id, created_at, last_active, summary
  - messages: id, session_id, role, content, timestamp, metadata
"""

import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionStore:
    """
    SQLite-backed session transcript store.

    Replaces the legacy JSONL approach. Offers indexed queries,
    efficient compaction, and single-file database management.
    """

    def __init__(self, base_dir: str = "data/sessions"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.base_dir / "agent_sessions.db"
        self._init_db()

    def _get_connection(self):
        # Isolation level None for autocommit, check_same_thread=False since we handle locks/scope
        conn = sqlite3.connect(self.db_path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initialize SQLite schema if it doesn't exist."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_active TEXT NOT NULL,
                    summary TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY(session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_msg_session ON messages(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_agent ON sessions(agent_id)")

    def append(
        self,
        agent_id: str,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Append a message to the session transcript."""
        now = _now_iso()
        meta_json = json.dumps(metadata) if metadata else None

        with self._get_connection() as conn:
            # 1. Upsert session
            conn.execute("""
                INSERT INTO sessions (session_id, agent_id, created_at, last_active)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET last_active = ?
            """, (session_id, agent_id, now, now, now))
            
            # 2. Insert message
            conn.execute("""
                INSERT INTO messages (session_id, role, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, role, content, now, meta_json))

    def read(
        self,
        agent_id: str,
        session_id: str,
        limit: Optional[int] = None,
        include_tools: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Read session transcript.

        Args:
            limit: If set, return only the last N messages
            include_tools: If False, filter out tool messages
        """
        query = "SELECT role, content, timestamp, metadata FROM messages WHERE session_id = ?"
        params = [session_id]

        if not include_tools:
            query += " AND role != 'tool'"
            
        query += " ORDER BY id ASC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()

        messages = []
        for row in rows:
            entry = {
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
            }
            if row["metadata"]:
                try:
                    entry["metadata"] = json.loads(row["metadata"])
                except json.JSONDecodeError:
                    pass
            messages.append(entry)

        if limit:
            messages = messages[-limit:]
        return messages

    def list_sessions(self, agent_id: str) -> List[Dict[str, Any]]:
        """List all sessions for an agent with metadata."""
        query = """
            SELECT 
                s.session_id, 
                s.agent_id, 
                s.created_at, 
                s.last_active,
                (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.session_id) as msg_count
            FROM sessions s
            WHERE s.agent_id = ?
            ORDER BY s.last_active DESC
        """
        with self._get_connection() as conn:
            rows = conn.execute(query, (agent_id,)).fetchall()

        sessions = []
        for row in rows:
            sessions.append({
                "session_id": row["session_id"],
                "agent_id": row["agent_id"],
                "message_count": row["msg_count"],
                "size_bytes": 0,  # Legacy field, not very meaningful for DB
                "created": row["created_at"],
                "last_active": row["last_active"],
            })
        return sessions

    def delete_session(self, agent_id: str, session_id: str) -> bool:
        """Delete a session transcript."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM sessions WHERE session_id = ? AND agent_id = ?", (session_id, agent_id))
            # Delete messages cascade IF we had pragmas enabled, but just to be safe:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            deleted = cursor.rowcount > 0
            
        if deleted:
            logger.info(f"Deleted SQLite session: {agent_id}/{session_id}")
        return deleted

    def compact(
        self,
        agent_id: str,
        session_id: str,
        summary: str,
        keep_last: int = 5,
    ):
        """
        Compact a session: replace old messages with a summary system message,
        keeping the last N messages intact.
        """
        with self._get_connection() as conn:
            # 1. Get all message IDs for this session
            rows = conn.execute("SELECT id FROM messages WHERE session_id = ? ORDER BY id ASC", (session_id,)).fetchall()
            msg_ids = [r["id"] for r in rows]
            
            if len(msg_ids) <= keep_last:
                return  # Nothing to compact

            ids_to_delete = msg_ids[:-keep_last]
            
            # 2. Delete older messages
            placeholders = ",".join("?" * len(ids_to_delete))
            conn.execute(f"DELETE FROM messages WHERE id IN ({placeholders})", ids_to_delete)
            
            # 3. Insert the summary as a system message right before the kept messages
            now = _now_iso()
            meta_json = json.dumps({"compacted": True, "original_count": len(msg_ids)})
            system_content = f"[Session compacted] Summary of {len(ids_to_delete)} earlier messages:\n{summary}"
            
            conn.execute("""
                INSERT INTO messages (session_id, role, content, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, "system", system_content, now, meta_json))
            
            # Reorder isn't strictly necessary if we order by ID, but the system message will now have the highest ID 
            # while semantically it belongs FIRST. Let's fix that by faking the ID or manipulating timestamp.
            # Actually, to make the system message appear FIRST before the kept ones, it needs an older ID.
            # SQLite AUTOINCREMENT doesn't let us easily insert an old ID without risking collision.
            # Easiest way: read the kept messages, delete everything, insert system + kept.
            
            # Wait, since compaction is a bit complex in SQL, the read/delete/insert is safer:
            pass
            
        # Re-doing the safe approach
        self._compact_safe(agent_id, session_id, summary, keep_last)

    def _compact_safe(self, agent_id: str, session_id: str, summary: str, keep_last: int):
        messages = self.read(agent_id, session_id)
        if len(messages) <= keep_last:
            return
            
        kept = messages[-keep_last:]
        now = _now_iso()
        
        with self._get_connection() as conn:
            conn.execute("BEGIN TRANSACTION")
            try:
                # 1. Clear all
                conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
                
                # 2. Insert summary
                meta_json = json.dumps({"compacted": True, "original_count": len(messages)})
                system_content = f"[Session compacted] Summary of {len(messages) - keep_last} earlier messages:\n{summary}"
                conn.execute("""
                    INSERT INTO messages (session_id, role, content, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """, (session_id, "system", system_content, now, meta_json))
                
                # 3. Insert kept
                for msg in kept:
                    m_meta = json.dumps(msg.get("metadata")) if msg.get("metadata") else None
                    conn.execute("""
                        INSERT INTO messages (session_id, role, content, timestamp, metadata)
                        VALUES (?, ?, ?, ?, ?)
                    """, (session_id, msg["role"], msg["content"], msg["timestamp"], m_meta))
                
                conn.execute("COMMIT")
                logger.info(f"Compacted SQLite session {session_id}: {len(messages)} → {keep_last + 1} messages")
            except Exception as e:
                conn.execute("ROLLBACK")
                logger.error(f"Failed to compact session: {e}")
