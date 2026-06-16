"""Tests for database.py — leaderboard save and ranking."""
from __future__ import annotations

import sqlite3

import pytest

import config
import database


# All tests use the tmp_db fixture from conftest.py which redirects DB_PATH.


class TestInitDb:
    def test_creates_table(self, tmp_db):
        with sqlite3.connect(config.DB_PATH) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='bad_interactions'"
            )
            assert cursor.fetchone() is not None

    def test_idempotent(self, tmp_db):
        # Calling init_db a second time must not raise
        database.init_db()


class TestSaveBadInteraction:
    def test_saves_row(self, tmp_db):
        database.save_bad_interaction("guild1", "chan1", '[]', 3.5)
        with sqlite3.connect(config.DB_PATH) as conn:
            rows = conn.execute("SELECT * FROM bad_interactions").fetchall()
        assert len(rows) == 1

    def test_saves_correct_values(self, tmp_db):
        database.save_bad_interaction("guild1", "chan1", '[{"author":"A"}]', 2.0)
        with sqlite3.connect(config.DB_PATH) as conn:
            row = conn.execute(
                "SELECT guild_id, channel_id, messages, score FROM bad_interactions"
            ).fetchone()
        assert row[0] == "guild1"
        assert row[1] == "chan1"
        assert row[2] == '[{"author":"A"}]'
        assert row[3] == 2.0

    def test_multiple_saves(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 1.0)
        database.save_bad_interaction("g", "c", "[]", 2.0)
        database.save_bad_interaction("g", "c", "[]", 3.0)
        with sqlite3.connect(config.DB_PATH) as conn:
            count = conn.execute("SELECT COUNT(*) FROM bad_interactions").fetchone()[0]
        assert count == 3


class TestGetRank:
    def test_first_entry_is_rank_one(self, tmp_db):
        database.save_bad_interaction("guild1", "c", "[]", 2.0)
        rank = database.get_rank("guild1", 2.0)
        assert rank == 1

    def test_worst_score_always_rank_one(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 3.0)
        database.save_bad_interaction("g", "c", "[]", 2.0)
        database.save_bad_interaction("g", "c", "[]", 1.0)
        rank = database.get_rank("g", 1.0)
        assert rank == 1

    def test_second_worst_is_rank_two(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 1.0)
        database.save_bad_interaction("g", "c", "[]", 2.0)
        rank = database.get_rank("g", 2.0)
        assert rank == 2

    def test_rank_increments_correctly(self, tmp_db):
        scores = [1.0, 2.0, 3.0, 4.0]
        for s in scores:
            database.save_bad_interaction("g", "c", "[]", s)
        assert database.get_rank("g", 1.0) == 1
        assert database.get_rank("g", 2.0) == 2
        assert database.get_rank("g", 3.0) == 3
        assert database.get_rank("g", 4.0) == 4

    def test_tied_scores_get_same_rank(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 1.0)
        database.save_bad_interaction("g", "c", "[]", 2.0)
        database.save_bad_interaction("g", "c", "[]", 2.0)
        # Both 2.0 entries: 1 row has score < 2.0 → rank 2
        rank = database.get_rank("g", 2.0)
        assert rank == 2

    def test_different_guilds_are_isolated(self, tmp_db):
        database.save_bad_interaction("guild_A", "c", "[]", 1.0)
        database.save_bad_interaction("guild_A", "c", "[]", 2.0)
        database.save_bad_interaction("guild_B", "c", "[]", 3.0)
        # guild_B has only one entry at 3.0; no entries < 3.0 in guild_B → rank 1
        rank_b = database.get_rank("guild_B", 3.0)
        assert rank_b == 1

    def test_empty_database_rank_is_one(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 5.0)
        rank = database.get_rank("g", 5.0)
        assert rank == 1

    def test_score_zero_is_rank_one(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 0.0)
        rank = database.get_rank("g", 0.0)
        assert rank == 1

    def test_new_entry_worse_than_all_others(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 3.5)
        database.save_bad_interaction("g", "c", "[]", 2.5)
        database.save_bad_interaction("g", "c", "[]", 0.5)
        # 0.5 is the worst: 0 rows < 0.5 → rank 1
        rank = database.get_rank("g", 0.5)
        assert rank == 1

    def test_new_entry_better_than_all_others(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 1.0)
        database.save_bad_interaction("g", "c", "[]", 2.0)
        database.save_bad_interaction("g", "c", "[]", 3.9)
        # 3.9 is least-bad: 2 rows < 3.9 → rank 3
        rank = database.get_rank("g", 3.9)
        assert rank == 3
