"""Tests for scorer.py — algorithmic slur detection and score computation."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scorer import check_slurs, compute_final_score, score_with_grok


# ---------------------------------------------------------------------------
# check_slurs — algorithmic detection, no LLM
# ---------------------------------------------------------------------------

class TestCheckSlurs:
    def test_clean_text_no_slurs(self):
        has_slur, has_nword = check_slurs("hello how are you doing today")
        assert not has_slur
        assert not has_nword

    def test_nword_standard(self):
        has_slur, has_nword = check_slurs("he said nigger in chat")
        assert has_slur
        assert has_nword

    def test_nword_aave_variant(self):
        has_slur, has_nword = check_slurs("nigga please")
        assert has_slur
        assert has_nword

    def test_nword_leet_digit_substitution(self):
        has_slur, has_nword = check_slurs("n1gga")
        assert has_slur
        assert has_nword

    def test_nword_special_char_substitution(self):
        has_slur, has_nword = check_slurs("n!gga")
        assert has_slur
        assert has_nword

    def test_nword_plural(self):
        has_slur, has_nword = check_slurs("niggas everywhere")
        assert has_slur
        assert has_nword

    def test_nword_z_suffix(self):
        has_slur, has_nword = check_slurs("niggaz")
        assert has_slur
        assert has_nword

    def test_nword_uppercase(self):
        has_slur, has_nword = check_slurs("NIGGER")
        assert has_slur
        assert has_nword

    def test_other_slur_faggot(self):
        has_slur, has_nword = check_slurs("you are a faggot")
        assert has_slur
        assert not has_nword

    def test_other_slur_fag(self):
        has_slur, has_nword = check_slurs("what a fag")
        assert has_slur
        assert not has_nword

    def test_other_slur_spic(self):
        has_slur, has_nword = check_slurs("spic")
        assert has_slur
        assert not has_nword

    def test_other_slur_kike(self):
        has_slur, has_nword = check_slurs("kike")
        assert has_slur
        assert not has_nword

    def test_other_slur_tranny(self):
        has_slur, has_nword = check_slurs("tranny")
        assert has_slur
        assert not has_nword

    def test_both_nword_and_other_slur(self):
        has_slur, has_nword = check_slurs("nigger and faggot")
        assert has_slur
        assert has_nword

    def test_empty_string(self):
        has_slur, has_nword = check_slurs("")
        assert not has_slur
        assert not has_nword

    def test_partial_word_no_false_positive(self):
        # "fig" contains "fi" and "g" but should not match slurs
        has_slur, has_nword = check_slurs("the fig tree")
        assert not has_slur
        assert not has_nword

    def test_multiline_text(self):
        text = "line one\nline two with nigga in it\nline three"
        has_slur, has_nword = check_slurs(text)
        assert has_slur
        assert has_nword


# ---------------------------------------------------------------------------
# compute_final_score — pure function, no LLM
# ---------------------------------------------------------------------------

class TestComputeFinalScore:
    def test_clean_high_intellectual(self):
        score, is_retarded = compute_final_score(
            {"intellectual": 9, "retarded": False}, False, False
        )
        assert score == 9.0
        assert not is_retarded

    def test_clean_low_intellectual(self):
        score, is_retarded = compute_final_score(
            {"intellectual": 2, "retarded": False}, False, False
        )
        assert score == 2.0
        assert not is_retarded

    def test_retarded_caps_score_at_one(self):
        score, is_retarded = compute_final_score(
            {"intellectual": 8, "retarded": True}, False, False
        )
        assert score == 1.0
        assert is_retarded

    def test_retarded_already_low_score_stays(self):
        score, is_retarded = compute_final_score(
            {"intellectual": 0, "retarded": True}, False, False
        )
        assert score == 0.0
        assert is_retarded

    def test_nword_subtracts_five(self):
        score, _ = compute_final_score(
            {"intellectual": 8, "retarded": False}, True, True
        )
        assert score == 3.0

    def test_nword_cannot_go_below_zero(self):
        score, _ = compute_final_score(
            {"intellectual": 3, "retarded": False}, True, True
        )
        assert score == 0.0

    def test_other_slur_subtracts_three(self):
        score, _ = compute_final_score(
            {"intellectual": 8, "retarded": False}, True, False
        )
        assert score == 5.0

    def test_other_slur_cannot_go_below_zero(self):
        score, _ = compute_final_score(
            {"intellectual": 2, "retarded": False}, True, False
        )
        assert score == 0.0

    def test_nword_takes_priority_over_other_slur(self):
        # has_nword=True → 5-point penalty, NOT the 3-point slur penalty
        score, _ = compute_final_score(
            {"intellectual": 6, "retarded": False}, True, True
        )
        assert score == 1.0

    def test_retarded_and_nword_stack(self):
        # retarded caps to 1, then nword subtracts 5 → 0
        score, is_retarded = compute_final_score(
            {"intellectual": 10, "retarded": True}, True, True
        )
        assert score == 0.0
        assert is_retarded

    def test_score_clamped_to_ten(self):
        # Grok returns >10 (shouldn't happen but be safe)
        score, _ = compute_final_score(
            {"intellectual": 15, "retarded": False}, False, False
        )
        assert score == 10.0

    def test_missing_keys_use_defaults(self):
        # Grok returns empty dict — defaults to intellectual=5, retarded=False
        score, is_retarded = compute_final_score({}, False, False)
        assert score == 5.0
        assert not is_retarded

    def test_score_rounded_to_one_decimal(self):
        score, _ = compute_final_score(
            {"intellectual": 7.333, "retarded": False}, False, False
        )
        assert score == 7.3


# ---------------------------------------------------------------------------
# score_with_grok — verify the API call structure with a mock client
# ---------------------------------------------------------------------------

class TestScoreWithGrok:
    def _make_mock_client(self, response_json: str) -> MagicMock:
        mock_message = MagicMock()
        mock_message.content = response_json
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        return mock_client

    def test_returns_parsed_json(self):
        client = self._make_mock_client('{"intellectual":7,"retarded":false}')
        messages = [{"author": "Alice", "content": "Hello"}, {"author": "Bob", "content": "Hi"}]
        result = score_with_grok(client, messages)
        assert result == {"intellectual": 7, "retarded": False}

    def test_calls_correct_model(self):
        import config
        client = self._make_mock_client('{"intellectual":5,"retarded":false}')
        messages = [{"author": "A", "content": "test"}]
        score_with_grok(client, messages)
        call_kwargs = client.chat.completions.create.call_args[1]
        assert call_kwargs["model"] == config.GROK_MODEL

    def test_uses_json_response_format(self):
        client = self._make_mock_client('{"intellectual":5,"retarded":false}')
        messages = [{"author": "A", "content": "test"}]
        score_with_grok(client, messages)
        call_kwargs = client.chat.completions.create.call_args[1]
        assert call_kwargs["response_format"] == {"type": "json_object"}

    def test_max_tokens_is_small(self):
        import config
        client = self._make_mock_client('{"intellectual":5,"retarded":false}')
        messages = [{"author": "A", "content": "test"}]
        score_with_grok(client, messages)
        call_kwargs = client.chat.completions.create.call_args[1]
        assert call_kwargs["max_tokens"] == config.GROK_MAX_TOKENS

    def test_temperature_is_zero(self):
        client = self._make_mock_client('{"intellectual":5,"retarded":false}')
        messages = [{"author": "A", "content": "test"}]
        score_with_grok(client, messages)
        call_kwargs = client.chat.completions.create.call_args[1]
        assert call_kwargs["temperature"] == 0

    def test_messages_formatted_in_user_turn(self):
        client = self._make_mock_client('{"intellectual":5,"retarded":false}')
        messages = [
            {"author": "Alice", "content": "What is quantum entanglement?"},
            {"author": "Bob", "content": "It is a phenomenon..."},
        ]
        score_with_grok(client, messages)
        call_kwargs = client.chat.completions.create.call_args[1]
        user_turn = next(m for m in call_kwargs["messages"] if m["role"] == "user")
        assert "Alice: What is quantum entanglement?" in user_turn["content"]
        assert "Bob: It is a phenomenon..." in user_turn["content"]

    def test_raises_on_invalid_json(self):
        client = self._make_mock_client("not json at all")
        messages = [{"author": "A", "content": "test"}]
        with pytest.raises(Exception):
            score_with_grok(client, messages)
