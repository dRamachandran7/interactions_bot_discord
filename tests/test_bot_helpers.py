"""Tests for pure helper functions (utils.py)."""
from __future__ import annotations

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
