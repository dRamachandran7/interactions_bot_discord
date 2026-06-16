"""Shared pytest fixtures."""
from __future__ import annotations

import pytest

import config


@pytest.fixture()
def tmp_db(tmp_path, monkeypatch):
    """Point the database module at a temporary SQLite file."""
    db_path = str(tmp_path / "test_interactions.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    # Re-import after patch so database uses the new path
    import database
    database.init_db()
    return db_path
