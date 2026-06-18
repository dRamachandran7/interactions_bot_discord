from __future__ import annotations

import json
import sqlite3

import config


def init_db() -> None:
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS bad_interactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    TEXT    NOT NULL,
                channel_id  TEXT    NOT NULL,
                messages    TEXT    NOT NULL,
                score       REAL    NOT NULL,
                timestamp   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)


def save_bad_interaction(
    guild_id: str, channel_id: str, messages_json: str, score: float
) -> None:
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute(
            "INSERT INTO bad_interactions (guild_id, channel_id, messages, score)"
            " VALUES (?, ?, ?, ?)",
            (guild_id, channel_id, messages_json, score),
        )


def get_worst_interactions(guild_id: str, limit: int = 10) -> list[dict]:
    """Return up to *limit* worst (lowest score) interactions for this guild.

    Each entry has keys: rank (1=worst), score, messages (list), timestamp.
    """
    with sqlite3.connect(config.DB_PATH) as conn:
        rows = conn.execute(
            "SELECT score, messages, timestamp FROM bad_interactions"
            " WHERE guild_id = ? ORDER BY score ASC LIMIT ?",
            (guild_id, limit),
        ).fetchall()
    return [
        {
            "rank": i + 1,
            "score": row[0],
            "messages": json.loads(row[1]),
            "timestamp": row[2],
        }
        for i, row in enumerate(rows)
    ]


def get_tied_interaction(guild_id: str, score: float) -> dict | None:
    """Return one existing interaction whose score exactly matches *score*, or None.

    Used for tiebreaking before a new entry is saved.
    """
    with sqlite3.connect(config.DB_PATH) as conn:
        row = conn.execute(
            "SELECT id, score, messages FROM bad_interactions"
            " WHERE guild_id = ? AND score = ? LIMIT 1",
            (guild_id, score),
        ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "score": row[1],
        "messages": json.loads(row[2]),
    }


def update_interaction_score(interaction_id: int, new_score: float) -> None:
    """Adjust the score of an existing interaction (used by tiebreaker)."""
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute(
            "UPDATE bad_interactions SET score = ? WHERE id = ?",
            (new_score, interaction_id),
        )


def get_rank(guild_id: str, score: float) -> int:
    """Return the rank of *score* among bad interactions for this guild.

    Rank 1 = the single worst (lowest) score ever recorded.
    Call this *after* saving so the new row is included.
    """
    with sqlite3.connect(config.DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM bad_interactions WHERE guild_id = ? AND score < ?",
            (guild_id, score),
        )
        worse_count: int = cursor.fetchone()[0]
    return worse_count + 1
