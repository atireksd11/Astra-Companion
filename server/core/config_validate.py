"""Config validation for Phase 0 hardening."""

from __future__ import annotations

import re
from typing import Any

IMPLEMENTED_STEPS = frozenset(
    {
        "echo",
        "antispoof",
        "denoise",
        "focus",
        "stt",
        "safety_in",
        "mood",
        "cadence",
        "pronunciation",
        "llm",
        "intent",
        "safety_out",
        "memory_persist",
        "context_retrieve",
        "research",
        "tts",
        "vision",
    }
)

KNOWN_STEPS = frozenset(
    {
        "antispoof",
        "denoise",
        "focus",
        "stt",
        "safety_in",
        "mood",
        "cadence",
        "pronunciation",
        "llm",
        "intent",
        "safety_out",
        "memory_persist",
        "context_retrieve",
        "research",
        "tts",
        "vision",
        "echo",
    }
)

_PLAYBACK = frozenset({"echo", "tts"})

def _is_secret_key(key: str) -> bool:
    """True for api_key, apiKey, groq-key, and the same shapes with a provider prefix."""
    compact = re.sub(r"[^a-z0-9]", "", str(key).lower())
    if compact in {
        "apikey",
        "secret",
        "password",
        "groqkey",
        "openrouterkey",
        "openaikey",
        "key",
        "token",
        "bearer",
        "credential",
        "credentials",
    }:
        return True
    # max_completion_tokens is a limit, not a secret. auth_token is the exception
    # handled by the caller for security.auth_token only.
    if compact.endswith("tokens"):
        return False
    return compact.endswith(("apikey", "secret", "password", "token"))


def find_forbidden_secrets(raw: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(raw, dict):
        for key, val in raw.items():
            full = f"{path}.{key}" if path else key
            if full.endswith("security.auth_token"):
                found.extend(find_forbidden_secrets(val, full))
                continue
            if _is_secret_key(str(key)):
                found.append(full)
            found.extend(find_forbidden_secrets(val, full))
    elif isinstance(raw, list):
        for i, item in enumerate(raw):
            found.extend(find_forbidden_secrets(item, f"{path}[{i}]"))
    return found


def validate_implemented_steps(steps: list[str]) -> None:
    missing = [s for s in steps if s not in IMPLEMENTED_STEPS]
    if missing:
        raise ValueError(
            f"Pipeline steps not implemented in bridge yet: {missing}. "
            "Remove them from config steps until Phase 1+."
        )


def vision_after_stt(steps: list[str]) -> None:
    """Vision caption runs on transcript path; must follow stt when both are listed."""
    vision_at = [i for i, name in enumerate(steps) if name == "vision"]
    stt_at = [i for i, name in enumerate(steps) if name == "stt"]
    if not vision_at or not stt_at:
        return
    if min(vision_at) < max(stt_at):
        raise ValueError('step "vision" must run after "stt"')


def mood_after_stt(steps: list[str]) -> None:
    """Reject a listed mood step that sits before any stt.

    Normalize will happily reorder a single swap. Load must not: the contract
    is that every mood step runs after every transcript step when both names
    are present. A later copy of stt after mood is the same violation.
    """
    mood_at = [i for i, name in enumerate(steps) if name == "mood"]
    stt_at = [i for i, name in enumerate(steps) if name == "stt"]
    if not mood_at or not stt_at:
        return
    if min(mood_at) < max(stt_at):
        raise ValueError('step "mood" must run after "stt"')


def mood_before_cadence(steps: list[str]) -> None:
    """Every mood step has to finish before cadence reads the same profile."""
    mood_at = [i for i, name in enumerate(steps) if name == "mood"]
    cadence_at = [i for i, name in enumerate(steps) if name == "cadence"]
    if not mood_at or not cadence_at:
        return
    if max(mood_at) > min(cadence_at):
        raise ValueError('step "mood" must run before "cadence"')


def antispoof_before_denoise(steps: list[str]) -> None:
    """Raw PCM must be scored before denoise wipes the cues AASIST-L uses.

    Every antispoof step has to sit before the first denoise. A later copy
    would score cleaned audio and can overwrite the raw-PCM note.
    """
    if "antispoof" not in steps or "denoise" not in steps:
        return
    denoise_at = steps.index("denoise")
    if any(name == "antispoof" and i > denoise_at for i, name in enumerate(steps)):
        raise ValueError('step "denoise" must run after "antispoof"')


def validate_step_contract(steps: list[str]) -> None:
    unknown = [s for s in steps if s not in KNOWN_STEPS]
    if unknown:
        raise ValueError(f"Unknown pipeline steps: {unknown}")

    if "echo" in steps and "tts" in steps:
        raise ValueError('steps cannot include both "echo" and "tts"')

    if "llm" in steps and "safety_in" not in steps:
        raise ValueError('steps include "llm" but missing required "safety_in"')
    if "intent" in steps and "safety_in" not in steps:
        raise ValueError('steps include "intent" but missing required "safety_in"')
    if "llm" in steps and "safety_out" not in steps:
        raise ValueError('steps include "llm" but missing required "safety_out"')
    if "tts" in steps and "safety_out" not in steps:
        raise ValueError('steps include "tts" but missing required "safety_out"')

    order_before_playback = [
        "antispoof",
        "denoise",
        "focus",
        "stt",
        "vision",
        "safety_in",
        "mood",
        "cadence",
        "pronunciation",
        "context_retrieve",
        "research",
        "llm",
        "intent",
        "safety_out",
        "memory_persist",
    ]

    def idx(name: str) -> int:
        return steps.index(name) if name in steps else -1

    vision_after_stt(steps)
    mood_after_stt(steps)
    mood_before_cadence(steps)
    antispoof_before_denoise(steps)

    playback_idx = min(
        (idx(p) for p in _PLAYBACK if p in steps),
        default=len(steps),
    )
    has_playback = playback_idx < len(steps)

    last = -1
    for name in order_before_playback:
        i = idx(name)
        if i < 0:
            continue
        if i < last:
            raise ValueError(f'step "{name}" must run after earlier analysis steps')
        if has_playback and i >= playback_idx:
            raise ValueError(f'step "{name}" must run before playback (echo/tts)')
        last = i
