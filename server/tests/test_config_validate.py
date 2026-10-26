from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config_validate import (  # noqa: E402
    find_forbidden_secrets,
    validate_implemented_steps,
    validate_step_contract,
)


def test_llm_requires_safety_in() -> None:
    with pytest.raises(ValueError, match="safety_in"):
        validate_step_contract(["denoise", "focus", "stt", "llm", "echo"])


def test_tts_requires_safety_out() -> None:
    with pytest.raises(ValueError, match="safety_out"):
        validate_step_contract(["stt", "safety_in", "llm", "tts"])


def test_llm_requires_safety_out() -> None:
    with pytest.raises(ValueError, match="safety_out"):
        validate_step_contract(["safety_in", "llm", "intent", "echo"])


def test_echo_and_tts_mutually_exclusive() -> None:
    with pytest.raises(ValueError, match="both"):
        validate_step_contract(["echo", "tts"])


def test_forbidden_api_key_in_config() -> None:
    bad = find_forbidden_secrets({"stt": {"openai_api_key": "sk-x"}})
    assert bad
    camel = find_forbidden_secrets({"llm": {"apiKey": "not-a-real-key", "groq_key": "nope"}})
    assert "llm.apiKey" in camel
    assert "llm.groq_key" in camel
    hyphen = find_forbidden_secrets({"llm": {"groq-api-key": "nope"}})
    assert hyphen


def test_antispoof_is_implemented() -> None:
    validate_implemented_steps(["antispoof", "denoise", "echo"])


def test_unimplemented_step_rejected() -> None:
    validate_implemented_steps(["llm", "echo"])
    with pytest.raises(ValueError, match="not implemented"):
        validate_implemented_steps(["not_a_step"])
    with pytest.raises(ValueError, match="safety_in"):
        validate_step_contract(["llm", "echo"])


def test_auth_token_in_security_allowed() -> None:
    bad = find_forbidden_secrets({"security": {"auth_token": "local-dev"}})
    assert not bad
    assert not find_forbidden_secrets({"llm": {"max_completion_tokens": 256}})
    named = find_forbidden_secrets({"llm": {"key": "not-a-real-key", "token": "nope"}})
    assert "llm.key" in named
    assert "llm.token" in named
