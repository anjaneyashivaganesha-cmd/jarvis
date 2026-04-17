"""SQLite FTS5 conversation memory for JARVIS."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite

from app.config import DB_PATH

log = logging.getLogger("jarvis.memory")

_db: aiosqlite.Connection | None = None


async def init_db() -> None:
    """Initialize the database and create tables."""
    global _db
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _db = await aiosqlite.connect(str(DB_PATH))
    _db.row_factory = aiosqlite.Row

    await _db.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS conversations_fts USING fts5(
            content,
            content='conversations',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS conversations_ai AFTER INSERT ON conversations BEGIN
            INSERT INTO conversations_fts(rowid, content) VALUES (new.id, new.content);
        END;

        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            title, body,
            content='notes',
            content_rowid='id'
        );

        CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
            INSERT INTO notes_fts(rowid, title, body) VALUES (new.id, new.title, new.body);
        END;
    """)
    await _db.commit()
    log.info("Database initialized at %s", DB_PATH)


async def close_db() -> None:
    global _db
    if _db:
        await _db.close()
        _db = None


async def save_message(role: str, content: str) -> None:
    """Save a conversation message."""
    if not _db:
        return
    now = datetime.now(timezone.utc).isoformat()
    await _db.execute(
        "INSERT INTO conversations (role, content, timestamp) VALUES (?, ?, ?)",
        (role, content, now),
    )
    await _db.commit()


async def get_recent_messages(limit: int = 20) -> list[dict[str, str]]:
    """Get recent conversation messages for context."""
    if not _db:
        return []
    cursor = await _db.execute(
        "SELECT role, content FROM conversations ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [{"role": row["role"], "content": row["content"]} for row in reversed(rows)]


async def search_memory(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Full-text search across conversation history."""
    if not _db:
        return []
    cursor = await _db.execute(
        """
        SELECT c.role, c.content, c.timestamp
        FROM conversations_fts f
        JOIN conversations c ON c.id = f.rowid
        WHERE conversations_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    )
    rows = await cursor.fetchall()
    return [{"role": row["role"], "content": row["content"], "timestamp": row["timestamp"]} for row in rows]


# --- Notes CRUD ---

async def create_note(title: str, body: str) -> int:
    if not _db:
        return -1
    now = datetime.now(timezone.utc).isoformat()
    cursor = await _db.execute(
        "INSERT INTO notes (title, body, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (title, body, now, now),
    )
    await _db.commit()
    return cursor.lastrowid or -1


async def get_notes(limit: int = 10) -> list[dict]:
    if not _db:
        return []
    cursor = await _db.execute(
        "SELECT id, title, body, created_at FROM notes ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def search_notes(query: str, limit: int = 5) -> list[dict]:
    if not _db:
        return []
    cursor = await _db.execute(
        """
        SELECT n.id, n.title, n.body, n.created_at
        FROM notes_fts f
        JOIN notes n ON n.id = f.rowid
        WHERE notes_fts MATCH ?
        ORDER BY rank
        LIMIT ?
        """,
        (query, limit),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def delete_note(note_id: int) -> bool:
    if not _db:
        return False
    cursor = await _db.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    await _db.commit()
    return (cursor.rowcount or 0) > 0


# --- Persistent Memory (facts that survive sessions) ---

async def _ensure_facts_table() -> None:
    if not _db:
        return
    await _db.executescript("""
        CREATE TABLE IF NOT EXISTS facts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fact TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            created_at TEXT NOT NULL
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS facts_fts USING fts5(
            fact, category,
            content='facts',
            content_rowid='id'
        );
        CREATE TRIGGER IF NOT EXISTS facts_ai AFTER INSERT ON facts BEGIN
            INSERT INTO facts_fts(rowid, fact, category) VALUES (new.id, new.fact, new.category);
        END;
    """)
    await _db.commit()


async def remember_fact(fact: str, category: str = "general") -> int:
    """Save a fact to persistent memory."""
    if not _db:
        return -1
    await _ensure_facts_table()
    now = datetime.now(timezone.utc).isoformat()
    cursor = await _db.execute(
        "INSERT INTO facts (fact, category, created_at) VALUES (?, ?, ?)",
        (fact, category, now),
    )
    await _db.commit()
    return cursor.lastrowid or -1


async def recall_facts(query: str, limit: int = 5) -> list[dict]:
    """Search persistent memory for matching facts."""
    if not _db:
        return []
    await _ensure_facts_table()
    try:
        cursor = await _db.execute(
            """
            SELECT f.id, f.fact, f.category, f.created_at
            FROM facts_fts fts
            JOIN facts f ON f.id = fts.rowid
            WHERE facts_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (query, limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception:
        # Fallback to LIKE search if FTS fails
        cursor = await _db.execute(
            "SELECT id, fact, category, created_at FROM facts WHERE fact LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{query}%", limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def get_all_facts(limit: int = 20) -> list[dict]:
    """Get all saved facts."""
    if not _db:
        return []
    await _ensure_facts_table()
    cursor = await _db.execute(
        "SELECT id, fact, category, created_at FROM facts ORDER BY id DESC LIMIT ?",
        (limit,),
    )
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def forget_fact(fact_id: int) -> bool:
    """Delete a fact from persistent memory."""
    if not _db:
        return False
    await _ensure_facts_table()
    cursor = await _db.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
    await _db.commit()
    return (cursor.rowcount or 0) > 0
