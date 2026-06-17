from __future__ import annotations

import asyncio
import json
from collections import defaultdict, deque
from datetime import datetime

import discord
from discord.ext import commands, tasks
from openai import OpenAI

import config
from database import get_rank, get_worst_interactions, init_db, save_bad_interaction
from scorer import check_slurs, compute_final_score, score_with_grok
from utils import format_snippet


class InteractionBot(commands.Bot):
    def __init__(self) -> None:
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

        self._grok = OpenAI(
            base_url=config.OPENROUTER_BASE_URL,
            api_key=config.OPENROUTER_API_KEY,
            default_headers={"X-Title": "Discord Interaction Rater"},
        )
        # Per channel: sliding buffer of the last CONVERSATION_WINDOW messages
        self._buffers: dict[int, deque[dict]] = defaultdict(
            lambda: deque(maxlen=config.CONVERSATION_WINDOW)
        )
        # Per channel: when we last scored (for cooldown)
        self._last_scored: dict[int, datetime] = {}

    async def setup_hook(self) -> None:
        await self.tree.sync()
        self._background_check.start()

    async def on_ready(self) -> None:
        print(f"Logged in as {self.user} (id: {self.user.id})")

    # ------------------------------------------------------------------
    # Message ingestion and immediate slur-triggered scoring
    # ------------------------------------------------------------------

    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return

        msg_data = {
            "author": message.author.display_name,
            "content": message.content,
        }
        buf = self._buffers[message.channel.id]
        buf.append(msg_data)

        # Immediate path: slur detected → score right now
        has_slur, _ = check_slurs(message.content)
        if has_slur and not self._on_cooldown(message.channel.id):
            await self._score_buffer(message.channel)
        # Buffer-full path: 10 msgs from 2+ users → score
        elif (
            len(buf) >= config.CONVERSATION_WINDOW
            and not self._on_cooldown(message.channel.id)
            and len({m["author"] for m in buf}) >= config.MIN_USERS_FOR_SCORING
        ):
            await self._score_buffer(message.channel)

        await self.process_commands(message)

    # ------------------------------------------------------------------
    # Background task: catches low-quality convos with no slurs
    # ------------------------------------------------------------------

    @tasks.loop(minutes=config.BACKGROUND_CHECK_INTERVAL_MINUTES)
    async def _background_check(self) -> None:
        for channel_id, buf in list(self._buffers.items()):
            if len(buf) < config.MIN_MESSAGES_FOR_SCORING:
                continue
            if len({m["author"] for m in buf}) < config.MIN_USERS_FOR_SCORING:
                continue
            if self._on_cooldown(channel_id):
                continue

            channel = self.get_channel(channel_id)
            if not isinstance(channel, discord.TextChannel):
                continue

            await self._score_buffer(channel)

    # ------------------------------------------------------------------
    # Core scoring helper shared by all paths
    # ------------------------------------------------------------------

    async def _score_buffer(self, channel: discord.TextChannel) -> float | None:
        buf = self._buffers[channel.id]
        if not buf:
            return None

        messages = list(buf)
        buf.clear()
        self._last_scored[channel.id] = datetime.now()

        all_text = " ".join(m["content"] for m in messages)
        has_slur, has_nword = check_slurs(all_text)

        try:
            grok_result = await asyncio.to_thread(
                score_with_grok, self._grok, messages
            )
        except Exception as exc:
            print(f"[scorer] Grok error in channel {channel.id}: {exc}")
            return None

        score, is_retarded = compute_final_score(grok_result, has_slur, has_nword)

        if score <= config.BAD_INTERACTION_THRESHOLD or is_retarded:
            await _post_bad_interaction(channel, str(channel.guild.id), messages, score)

        return score

    def _on_cooldown(self, channel_id: int) -> bool:
        last = self._last_scored.get(channel_id)
        if last is None:
            return False
        return (datetime.now() - last).total_seconds() < config.SCORE_COOLDOWN_SECONDS


# ---------------------------------------------------------------------------
# Helper: save to leaderboard + post Function-1 message
# ---------------------------------------------------------------------------

async def _post_bad_interaction(
    channel: discord.TextChannel,
    guild_id: str,
    messages: list[dict],
    score: float,
) -> None:
    messages_json = json.dumps(messages)
    save_bad_interaction(guild_id, str(channel.id), messages_json, score)
    rank = get_rank(guild_id, score)
    await channel.send(f"Bottom {rank} interaction of all time.")


# ---------------------------------------------------------------------------
# Bot instance + slash commands
# ---------------------------------------------------------------------------

bot = InteractionBot()


@bot.tree.command(name="rate", description="Rate the most recent interaction in this channel")
async def rate_command(interaction: discord.Interaction) -> None:
    await interaction.response.defer()

    buf = bot._buffers[interaction.channel_id]
    messages = list(buf)

    if not messages:
        await interaction.followup.send("No recent interaction to rate.")
        return

    all_text = " ".join(m["content"] for m in messages)
    has_slur, has_nword = check_slurs(all_text)

    try:
        grok_result = await asyncio.to_thread(
            score_with_grok, bot._grok, messages
        )
    except Exception as exc:
        print(f"[scorer] /rate Grok error: {exc}")
        await interaction.followup.send("Error contacting scoring service.")
        return

    score, is_retarded = compute_final_score(grok_result, has_slur, has_nword)
    await interaction.followup.send(f"This interaction was a {score}/10")

    if score <= config.BAD_INTERACTION_THRESHOLD or is_retarded:
        await _post_bad_interaction(
            interaction.channel,  # type: ignore[arg-type]
            str(interaction.guild_id),
            messages,
            score,
        )


@bot.tree.command(name="list", description="Show the 10 worst interactions on this server")
async def list_command(interaction: discord.Interaction) -> None:
    entries = get_worst_interactions(str(interaction.guild_id))
    if not entries:
        await interaction.response.send_message("No bad interactions recorded yet.")
        return

    parts = ["**Worst Interactions of All Time**\n"]
    for entry in entries:
        snippet = format_snippet(entry["messages"])
        parts.append(f"**#{entry['rank']}** · {entry['score']}/10\n{snippet}")

    await interaction.response.send_message("\n\n".join(parts))


if __name__ == "__main__":
    init_db()
    bot.run(config.DISCORD_TOKEN)
