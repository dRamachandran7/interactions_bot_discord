"""Tests for pure helper functions (utils.py) and bot cooldown logic."""
from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import config
from utils import format_snippet


class TestFormatSnippet:
    def test_single_message(self):
        msgs = [{"author": "Alice", "content": "hello there"}]
        result = format_snippet(msgs)
        assert result == "> **Alice**: hello there"

    def test_two_messages(self):
        msgs = [
            {"author": "Alice", "content": "hi"},
            {"author": "Bob", "content": "hey"},
        ]
        result = format_snippet(msgs)
        assert "> **Alice**: hi" in result
        assert "> **Bob**: hey" in result

    def test_only_first_two_shown(self):
        msgs = [
            {"author": "A", "content": "one"},
            {"author": "B", "content": "two"},
            {"author": "C", "content": "three"},
        ]
        result = format_snippet(msgs)
        assert "three" not in result

    def test_long_line_is_truncated(self):
        long_content = "x" * 200
        msgs = [{"author": "Alice", "content": long_content}]
        result = format_snippet(msgs)
        assert len(result) <= 85
        assert result.endswith("...")

    def test_empty_messages_list(self):
        result = format_snippet([])
        assert result == ""

    def test_custom_max_line(self):
        msgs = [{"author": "A", "content": "y" * 50}]
        result = format_snippet(msgs, max_line=30)
        assert len(result) <= 30
        assert result.endswith("...")

    def test_custom_max_msgs(self):
        msgs = [{"author": str(i), "content": "msg"} for i in range(5)]
        result = format_snippet(msgs, max_msgs=3)
        lines = result.split("\n")
        assert len(lines) == 3

    def test_exactly_at_limit_not_truncated(self):
        # "> **A**: " = 9 chars, so content can be 85-9=76 chars to hit exactly 85
        content = "z" * 76
        msgs = [{"author": "A", "content": content}]
        result = format_snippet(msgs, max_line=85)
        assert not result.endswith("...")
        assert len(result) == 85


# ---------------------------------------------------------------------------
# Auto-post cooldown — unit tests for _auto_post_on_cooldown
# ---------------------------------------------------------------------------

class TestAutoPostCooldown:
    def _make_bot(self):
        """Return an InteractionBot with Discord internals mocked out."""
        with patch("bot.commands.Bot.__init__", return_value=None), \
             patch("bot.OpenAI"):
            from bot import InteractionBot
            b = InteractionBot.__new__(InteractionBot)
            b._last_auto_posted = {}
            return b

    def test_not_on_cooldown_when_never_posted(self):
        from bot import InteractionBot
        b = self._make_bot()
        assert not b._auto_post_on_cooldown(channel_id=1)

    def test_on_cooldown_immediately_after_post(self):
        b = self._make_bot()
        b._last_auto_posted[1] = datetime.now()
        assert b._auto_post_on_cooldown(channel_id=1)

    def test_not_on_cooldown_after_limit_expires(self):
        b = self._make_bot()
        b._last_auto_posted[1] = datetime.now() - timedelta(
            seconds=config.AUTO_POST_COOLDOWN_SECONDS + 1
        )
        assert not b._auto_post_on_cooldown(channel_id=1)

    def test_still_on_cooldown_one_second_before_expiry(self):
        b = self._make_bot()
        b._last_auto_posted[1] = datetime.now() - timedelta(
            seconds=config.AUTO_POST_COOLDOWN_SECONDS - 1
        )
        assert b._auto_post_on_cooldown(channel_id=1)

    def test_cooldown_is_per_channel(self):
        b = self._make_bot()
        b._last_auto_posted[1] = datetime.now()
        # Channel 2 has never posted — should not be on cooldown
        assert not b._auto_post_on_cooldown(channel_id=2)

    def test_cooldown_uses_auto_post_constant(self):
        b = self._make_bot()
        # One second past the boundary — must have expired
        b._last_auto_posted[1] = datetime.now() - timedelta(
            seconds=config.AUTO_POST_COOLDOWN_SECONDS + 1
        )
        assert not b._auto_post_on_cooldown(channel_id=1)
        # One second before the boundary — must still be active
        b._last_auto_posted[1] = datetime.now() - timedelta(
            seconds=config.AUTO_POST_COOLDOWN_SECONDS - 1
        )
        assert b._auto_post_on_cooldown(channel_id=1)
