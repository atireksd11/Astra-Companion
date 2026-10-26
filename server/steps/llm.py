"""One completion. Intent is parsed from that JSON, not a second call."""

from __future__ import annotations

from context.builder import build_context
from core.config import Limits, LlmConfig
from core.meter import Meter
from core.safety_list import REFUSAL, match_category
from core.turn import Turn
from providers.llm import (
    OFFLINE_LINE,
    LIMIT_LINE,
    ChatResult,
    chat_completion,
    has_llm_key,
    json_object_text,
)
from store.db import TurnStore
from store.profiles import ProfileStore

_INTENTS = frozenset({"chat", "question", "remember", "stop", "unknown"})
_RESERVE_USD = 0.00012


def _blocked(turn: Turn) -> bool:
    safety = turn.notes.get("safety")
    return isinstance(safety, dict) and safety.get("blocked") is True


def _skip_for_safety(turn: Turn) -> None:
    """A blocklist hit never reaches the provider, and the refusal stays put."""
    category = match_category(turn.text_in or "")
    if not _blocked(turn) and category:
        turn.notes["safety"] = {
            "blocked": True,
            "stage": "safety_in",
            "source": "blocklist",
            "category": category,
        }
    if _blocked(turn) or category:
        turn.text_out = REFUSAL
        turn.notes["intent"] = "unknown"
        turn.notes.pop("memory_request", None)
    turn.notes["llm"] = {"skipped": "safety", "ok": False}
    turn.cost_usd = 0.0


def _clip_text_in(turn: Turn, limits: Limits) -> None:
    cap = limits.max_text_chars if limits.max_text_chars > 0 else 500
    text = turn.text_in or ""
    if len(text) > cap:
        turn.text_in = text[:cap]
        turn.notes["text_truncated"] = True


def _parse_reply(content: str) -> tuple[str, str] | None:
    obj = json_object_text(content)
    if not isinstance(obj, dict) or not isinstance(obj.get("say"), str):
        return None
    intent = obj.get("intent", "unknown")
    if not isinstance(intent, str):
        intent = "unknown"
    intent = intent.strip().casefold()
    if intent not in _INTENTS:
        intent = "unknown"
    say = obj["say"]
    if not say.strip():
        # A blank line is not a reply. Stop is still an intent; other blanks
        # must not fall through to the transcript or the raw model text.
        if intent == "stop":
            return "stop", ""
        return None
    return intent, say


def _parse_reply_or_prose(content: str, limits: Limits) -> tuple[str, str, str] | None:
    """JSON reply first; plain model text is spoken when it is safe prose."""
    parsed = _parse_reply(content)
    if parsed is not None:
        intent, say = parsed
        return intent, say, "json"
    text = (content or "").strip()
    if not text or match_category(text):
        return None
    if text.startswith("{") or text.startswith("["):
        return None
    cap = limits.max_reply_chars if limits.max_reply_chars > 0 else 400
    if len(text) > cap:
        text = text[:cap]
    return "chat", text, "prose"


def _recent_pairs(
    store: TurnStore | None, speaker_id: str | None = None
) -> list[tuple[str, str]] | None:
    if store is None:
        return None
    sid = str(speaker_id or "").strip() or None
    try:
        newest_first = store.recent_text_pairs(2, speaker_id=sid)
    except Exception:
        return None
    return list(reversed(newest_first))


def _add_reserve(turn: Turn, amount: float) -> None:
    prev = turn.notes.get("cost_reserved", 0) or 0
    try:
        prev_f = float(prev)
    except (TypeError, ValueError):
        prev_f = 0.0
    turn.notes["cost_reserved"] = prev_f + float(amount)


def _release_reserve(turn: Turn, meter: Meter | None, amount: float) -> None:
    """Return an unused reserve. The note drops by the same amount so a later settle does not refund twice."""
    if amount <= 0:
        return
    if meter is not None:
        meter.settle(amount, 0.0)
    prev = turn.notes.get("cost_reserved", 0) or 0
    try:
        prev_f = float(prev)
    except (TypeError, ValueError):
        prev_f = 0.0
    left = prev_f - float(amount)
    turn.notes["cost_reserved"] = left if left > 1e-12 else 0.0


def make_llm_step(
    cfg: LlmConfig,
    limits: Limits,
    meter: Meter | None = None,
    store: TurnStore | None = None,
    profiles: ProfileStore | None = None,
):
    def llm_step(turn: Turn) -> None:
        if not cfg.enabled:
            return
        if _blocked(turn) or match_category(turn.text_in or ""):
            _skip_for_safety(turn)
            return

        _clip_text_in(turn, limits)

        if not has_llm_key(cfg.provider):
            turn.text_out = OFFLINE_LINE
            turn.notes["intent"] = "unknown"
            turn.notes["llm"] = {"provider": "canned", "ok": False, "reason": "no_key"}
            turn.cost_usd = 0.0
            return

        reserve = float(cfg.reserve_usd) if cfg.reserve_usd > 0 else _RESERVE_USD
        if meter is not None and not meter.try_reserve(reserve):
            turn.text_out = LIMIT_LINE
            turn.notes["intent"] = "unknown"
            turn.notes["llm"] = {
                "provider": "canned",
                "ok": False,
                "reason": "daily_cap",
            }
            turn.cost_usd = 0.0
            return
        held = 0.0
        if meter is not None:
            _add_reserve(turn, reserve)
            held = reserve

        profile_doc = None
        sid = turn.notes.get("speaker_id")
        if profiles is not None and sid:
            profile_doc = profiles.get(str(sid))
        messages = build_context(
            turn,
            profile=profile_doc,
            recent_turns=_recent_pairs(store, sid),
        )
        try:
            result = chat_completion(
                messages,
                temperature=cfg.temperature,
                max_completion_tokens=cfg.max_completion_tokens,
                provider=cfg.provider,
            )
            if not result.ok and result.detail in (
                "empty_content",
                "timeout",
                "network",
                "http_429",
                "http_502",
                "http_503",
            ):
                result = chat_completion(
                    messages,
                    temperature=cfg.temperature,
                    max_completion_tokens=cfg.max_completion_tokens,
                    provider=cfg.provider,
                )
        except Exception:
            result = ChatResult(False, "", "canned", 0.0)

        if not result.ok:
            _release_reserve(turn, meter, held)
            turn.text_out = OFFLINE_LINE
            turn.notes["intent"] = "unknown"
            note: dict = {
                "provider": "canned",
                "ok": False,
                "reason": "unreachable",
            }
            if result.detail:
                note["detail"] = result.detail
            turn.notes["llm"] = note
            turn.cost_usd = 0.0
            return

        parsed = _parse_reply_or_prose(result.content, limits)
        if parsed is None:
            _release_reserve(turn, meter, held)
            turn.text_out = OFFLINE_LINE
            turn.notes["intent"] = "unknown"
            note = {
                "provider": result.provider,
                "ok": False,
                "reason": "bad_json",
            }
            turn.notes["llm"] = note
            turn.cost_usd = 0.0
            return

        intent, say, parse_mode = parsed
        cap = limits.max_reply_chars if limits.max_reply_chars > 0 else 400
        # A phrase past the clip point still has to reach safety_out whole.
        if match_category(say) is None and len(say) > cap:
            say = say[:cap]
            turn.notes["reply_text_truncated"] = True
        turn.text_out = say
        turn.notes["intent"] = intent
        llm_note: dict = {"provider": result.provider, "ok": True}
        if parse_mode == "prose":
            llm_note["parse"] = "prose"
        turn.notes["llm"] = llm_note
        turn.cost_usd = float(result.cost_usd)

    return llm_step
