from __future__ import annotations

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
