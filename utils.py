from __future__ import annotations


def format_snippet(messages: list[dict], max_line: int = 85, max_msgs: int = 2) -> str:
    """Format the first few messages of an interaction as Discord blockquotes."""
    lines = []
    for m in messages[:max_msgs]:
        line = f"> **{m['author']}**: {m['content']}"
        if len(line) > max_line:
            line = line[:max_line - 3] + "..."
        lines.append(line)
    return "\n".join(lines)
