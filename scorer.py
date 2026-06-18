from __future__ import annotations

import json
import re

from openai import OpenAI

import config

# ---------------------------------------------------------------------------
# Algorithmic slur detection — no LLM involved
# ---------------------------------------------------------------------------

# Matches the n-word and leet/phonetic imitations.
# Requires n + i-variant + double-g + any word chars (catches nigga, nigger,
# niggaz, n1gga, n!gga, etc.). False-positives on rare words like "niggardly"
# are acceptable given the context.
_NWORD_RE = re.compile(
    r"\bn[i!1|l@4]+g{2,}\w*\b",
    re.IGNORECASE,
)

# Other common slurs (racial, ethnic, anti-LGBTQ+).
_SLUR_RE = re.compile(
    r"\b("
    r"f[a4]gg?[o0]t|f[a4]g(?!ot\w)|"  # f-word (exclude "fagot" in music)
    r"tr[a4]nn[yi]|"
    r"sp[i1]c|"
    r"k[i1]ke|"
    r"ch[i1]nk|"
    r"w[e3]tb[a4]ck|"
    r"g[o0]{2}k|"
    r"j[i1]gg?[a4]b[o0]{2}|"
    r"c[o0]{2}n"
    r")\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Grok scoring (one API call, minimal prompt)
# ---------------------------------------------------------------------------

# System prompt kept deliberately short to minimise input tokens.
# "retarded" here means a dumb/low-quality exchange (colloquial usage).
_SYSTEM_PROMPT = (
    'Rate this Discord chat. JSON only: {"intellectual":0.0,"retarded":false}\n'
    "intellectual is a float 0.0–10.0 with one decimal place. retarded=true means dumb or nonsensical."
)

_REASONING_SYSTEM_PROMPT = (
    "You are a sly, mischievous, but fun agent who roasts Discord conversations with sharp wit "
    "and playful cruelty. Your job is to skewer the intellectual (or severe lack thereof) content "
    "of whatever brain-dead exchange you're presented with. "
    "Your favorite word to call people is \"jackass\" — use it at any given opportunity, but never "
    "more than once per sentence. Keep your roast to 1-2 punchy, but concise sentences. Be creative, "
    "be vulgar, and be funny. Prioritize maximizing the effect in a shorter format."
)

_TIEBREAK_SYSTEM_PROMPT = (
    "You are the arbiter of stupidity. Given two Discord conversations, decide which is more "
    "nonsensical or intellectually bankrupt. "
    'Return JSON only: {"winner":1} if the first is more retarded, {"winner":2} if the second.'
)


def check_slurs(text: str) -> tuple[bool, bool]:
    """Algorithmically detect slurs.  Returns (has_any_slur, has_nword)."""
    has_nword = bool(_NWORD_RE.search(text))
    has_slur = has_nword or bool(_SLUR_RE.search(text))
    return has_slur, has_nword


def _format_messages(messages: list[dict]) -> str:
    """Minimal format to keep input tokens low."""
    return "\n".join(f"{m['author']}: {m['content']}" for m in messages)


def score_with_grok(client: OpenAI, messages: list[dict]) -> dict:
    """Call Grok via OpenRouter and return the raw parsed JSON dict.

    Raises on API or JSON parse errors — callers should catch.
    """
    text = _format_messages(messages)
    response = client.chat.completions.create(
        model=config.GROK_MODEL,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        max_tokens=config.GROK_MAX_TOKENS,
        temperature=0,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def generate_reasoning(client: OpenAI, messages: list[dict]) -> str:
    """Generate a vulgar 1-2 sentence roast of the interaction."""
    text = _format_messages(messages)
    response = client.chat.completions.create(
        model=config.GROK_MODEL,
        messages=[
            {"role": "system", "content": _REASONING_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        max_tokens=config.GROK_REASONING_MAX_TOKENS,
        temperature=0.8,
    )
    return response.choices[0].message.content.strip()


def tiebreak_interactions(
    client: OpenAI,
    messages_a: list[dict],
    messages_b: list[dict],
) -> int:
    """Return 1 if messages_a is more retarded, 2 if messages_b is.

    Raises on API or JSON parse errors — callers should catch.
    """
    text_a = _format_messages(messages_a)
    text_b = _format_messages(messages_b)
    prompt = (
        f"Interaction 1:\n{text_a}\n\n"
        f"Interaction 2:\n{text_b}\n\n"
        "Which is more retarded?"
    )
    response = client.chat.completions.create(
        model=config.GROK_MODEL,
        messages=[
            {"role": "system", "content": _TIEBREAK_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        max_tokens=config.GROK_TIEBREAK_MAX_TOKENS,
        temperature=0,
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    return int(result.get("winner", 1))


def compute_final_score(
    grok_result: dict,
    has_slur: bool,
    has_nword: bool,
) -> tuple[float, bool]:
    """Apply slur penalties and retarded cap to produce a final 0–10 score.

    Returns (final_score, is_retarded).
    """
    intellectual: float = float(grok_result.get("intellectual", 5))
    is_retarded: bool = bool(grok_result.get("retarded", False))

    score = intellectual

    if is_retarded:
        score = min(score, 1.0)

    if has_nword:
        score -= 5.0
    elif has_slur:
        score -= 3.0

    return round(min(10.0, max(0.0, score)), 1), is_retarded
