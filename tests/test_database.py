"""Tests for database.py — leaderboard save, ranking, and worst-list query."""
from __future__ import annotations

import json
import sqlite3

import pytest

import config
import database
from database import get_tied_interaction, get_worst_interactions, update_interaction_score


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


class TestGetTiedInteraction:
    def test_returns_none_when_no_entries(self, tmp_db):
        assert get_tied_interaction("g", 2.0) is None

    def test_returns_none_when_no_match(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 1.0)
        assert get_tied_interaction("g", 2.0) is None

    def test_returns_entry_when_score_matches(self, tmp_db):
        msgs = [{"author": "Alice", "content": "lol"}]
        database.save_bad_interaction("g", "c", json.dumps(msgs), 2.0)
        result = get_tied_interaction("g", 2.0)
        assert result is not None
        assert result["score"] == 2.0
        assert result["messages"] == msgs

    def test_returned_entry_has_id(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 2.0)
        result = get_tied_interaction("g", 2.0)
        assert "id" in result
        assert isinstance(result["id"], int)

    def test_guild_isolation(self, tmp_db):
        database.save_bad_interaction("guild_A", "c", "[]", 2.0)
        # Same score but different guild — should not match
        assert get_tied_interaction("guild_B", 2.0) is None

    def test_returns_none_for_near_miss(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 2.0)
        # 2.001 is close but not identical
        assert get_tied_interaction("g", 2.001) is None

    def test_returns_one_result_when_multiple_tied(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 2.0)
        database.save_bad_interaction("g", "c", "[]", 2.0)
        result = get_tied_interaction("g", 2.0)
        assert result is not None  # returns one, not both


class TestUpdateInteractionScore:
    def test_updates_score(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 2.0)
        entry = get_tied_interaction("g", 2.0)
        update_interaction_score(entry["id"], 1.5)
        with sqlite3.connect(config.DB_PATH) as conn:
            row = conn.execute(
                "SELECT score FROM bad_interactions WHERE id = ?", (entry["id"],)
            ).fetchone()
        assert row[0] == 1.5

    def test_only_updates_target_row(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 2.0)
        database.save_bad_interaction("g", "c", "[]", 3.0)
        entry = get_tied_interaction("g", 2.0)
        update_interaction_score(entry["id"], 1.9)
        # The 3.0 entry must be unchanged
        with sqlite3.connect(config.DB_PATH) as conn:
            rows = conn.execute(
                "SELECT score FROM bad_interactions ORDER BY score ASC"
            ).fetchall()
        scores = [r[0] for r in rows]
        assert 3.0 in scores
        assert 1.9 in scores

    def test_update_does_not_create_new_row(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 2.0)
        entry = get_tied_interaction("g", 2.0)
        update_interaction_score(entry["id"], 1.0)
        with sqlite3.connect(config.DB_PATH) as conn:
            count = conn.execute("SELECT COUNT(*) FROM bad_interactions").fetchone()[0]
        assert count == 1


class TestGetWorstInteractions:
    def test_empty_db_returns_empty_list(self, tmp_db):
        assert get_worst_interactions("g") == []

    def test_returns_worst_first(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 3.0)
        database.save_bad_interaction("g", "c", "[]", 1.0)
        database.save_bad_interaction("g", "c", "[]", 2.0)
        scores = [e["score"] for e in get_worst_interactions("g")]
        assert scores == [1.0, 2.0, 3.0]

    def test_rank_starts_at_one(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 2.0)
        result = get_worst_interactions("g")
        assert result[0]["rank"] == 1

    def test_ranks_are_sequential(self, tmp_db):
        for score in [3.0, 1.0, 2.0]:
            database.save_bad_interaction("g", "c", "[]", score)
        ranks = [e["rank"] for e in get_worst_interactions("g")]
        assert ranks == [1, 2, 3]

    def test_default_limit_is_ten(self, tmp_db):
        for i in range(15):
            database.save_bad_interaction("g", "c", "[]", float(i))
        assert len(get_worst_interactions("g")) == 10

    def test_custom_limit_respected(self, tmp_db):
        for i in range(8):
            database.save_bad_interaction("g", "c", "[]", float(i))
        assert len(get_worst_interactions("g", limit=5)) == 5

    def test_fewer_entries_than_limit(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 1.0)
        database.save_bad_interaction("g", "c", "[]", 2.0)
        assert len(get_worst_interactions("g")) == 2

    def test_messages_are_parsed_from_json(self, tmp_db):
        msgs = [{"author": "Alice", "content": "hello"}]
        database.save_bad_interaction("g", "c", json.dumps(msgs), 1.0)
        result = get_worst_interactions("g")
        assert result[0]["messages"] == msgs

    def test_includes_timestamp(self, tmp_db):
        database.save_bad_interaction("g", "c", "[]", 1.0)
        result = get_worst_interactions("g")
        assert result[0]["timestamp"] is not None

    def test_guild_isolation(self, tmp_db):
        database.save_bad_interaction("guild_A", "c", "[]", 1.0)
        database.save_bad_interaction("guild_B", "c", "[]", 2.0)
        assert len(get_worst_interactions("guild_A")) == 1
        assert len(get_worst_interactions("guild_B")) == 1
        assert get_worst_interactions("guild_A")[0]["score"] == 1.0
        assert get_worst_interactions("guild_B")[0]["score"] == 2.0
