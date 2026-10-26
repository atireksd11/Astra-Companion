from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DenoiseConfig:
    enabled: bool = False
    backend: str = "auto"
    strength: float = 0.5


@dataclass
class AntispoofConfig:
    enabled: bool = True
    backend: str = "aasist_l"
    weights: str = "models/AASIST-L.pth"
    soft: float = 0.80
    # Saturated only. On the pinned AASIST-L weights, studio speech scored as
    # high as 0.99999 and room-level noise scored about 0.98.
    hard: float = 1.0
    echo_corr: float = 0.55
    echo_cosine: float = 0.90
    raise_verify: float = 0.08


@dataclass
class VadConfig:
    site: str = "client"
    backend: str = "silero"
    frame_ms: int = 32
    threshold: float = 0.5
    min_speech_ms: int = 280


@dataclass
class SttConfig:
    enabled: bool = False
    model: str = "tiny"
    device: str = "cpu"
    compute_type: str = "int8"
    language: str = "en"
    auto_language: bool = False
    min_language_prob: float = 0.50
    beam_size: int = 1
    vad_filter: bool = False


@dataclass
class MoodConfig:
    enabled: bool = True
    backend: str = "wav2vec2_ser_int8"
    weights: str = "models/speech_emotion_int8.onnx"
    min_confidence: float = 0.70
    min_margin: float = 0.15
    ema_alpha: float = 0.10
    max_seconds: float = 6.0
    score_non_en: bool = True
    learn_non_en: bool = False
    non_en_min_confidence: float = 0.85


@dataclass
class CadenceConfig:
    enabled: bool = False
    min_pause_ms: int = 200
    fillers: list[str] = field(default_factory=lambda: ["uh", "um", "er"])


@dataclass
class PronunciationConfig:
    enabled: bool = False
    aligner: str = "none"
    aligner_url: str = ""
    aligner_timeout_s: float = 8.0
    min_phone_confidence: float = 0.5
    model: str = "charsiu/en_w2v2_ctc_libris_and_cv"
    tokenizer: str = "charsiu/tokenizer_en_cmu"
    min_word_confidence: float = 0.85
    promote_count: int = 5


@dataclass
class ProfileConfig:
    sync_url: str = ""
    sync_timeout_s: float = 2.0
    match_min_similarity: float = 0.72


@dataclass
class LlmConfig:
    """Chat settings. API keys stay in the environment.

    ``provider`` ``groq`` calls Groq, then OpenRouter if that attempt fails.
    ``openrouter`` calls only that free route. Any other value keeps the
    Groq-then-OpenRouter order and does not select a new model.
    """

    enabled: bool = False
    provider: str = "groq"
    temperature: float = 0.6
    max_completion_tokens: int = 256
    reserve_usd: float = 0.00012


@dataclass
class TtsConfig:
    enabled: bool = False
    backend: str = "piper"
    voice: str = "en_US-lessac-medium"
    length_scale: float = 1.0
    weights: str = "models/en_US-lessac-medium.onnx"
    voices: dict[str, str] = field(default_factory=dict)
    fallback_lang: str = "en"


@dataclass
class SafetyConfig:
    moderation: str = "off"


@dataclass
class MemoryConfig:
    enabled: bool = True
    use_mem0: bool = False
    qdrant_path: str = "data/qdrant"
    history_db_path: str = "data/mem0/history.db"
    collection_name: str = "astra_memories"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dims: int = 384
    groq_model: str = "llama-3.1-8b-instant"
    search_limit: int = 5


@dataclass
class ResearchConfig:
    enabled: bool = True
    timeout_s: float = 1.5
    max_results: int = 4
    max_snippet_chars: int = 280


@dataclass
class ListenConfig:
    smart_turn_weights: str = "models/smart-turn-v3.2-cpu.onnx"
    fallback_end_silence_ms: int = 4500
    complete_close_ms: int = 500
    max_extra_pause_ms: int = 8000


@dataclass
class FocusConfig:
    enabled: bool = False
    wake_phrase: str = "hey astra"
    wake_model: str = "hey_jarvis"
    wake_threshold: float = 0.5
    session_timeout_s: float = 90.0
    embedding: str = "ecapa"
    ecapa_source: str = "speechbrain/spkrec-ecapa-voxceleb"
    min_similarity: float = 0.40
    min_enroll_s: float = 3.0
    wake_min_speech_ms: int = 500
    lock_owner: bool = True
    owner_speaker_id: str = ""
    min_gain: float = 0.45
    max_gain: float = 1.8
    firmware_volume_cap: float = 0.55
    azimuth_gate_deg: float = 35.0
    mask_other_voices: bool = True
    mask_window_s: float = 0.55
    mask_hop_s: float = 0.25
    max_mixed_ratio: float = 0.45
    min_owner_keep_ratio: float = 0.12
    require_owner_enroll: bool = True
    enroll_min_clips: int = 4
    verify_min_mean: float = 0.45
    verify_min_best_clip: float = 0.50
    echo_use_owner_mask: bool = False


@dataclass
class DoaConfig:
    baseline_m: float = 0.04
    offset_deg: float = 0.0
    min_confidence: float = 0.20


@dataclass
class SecurityConfig:
    auth_token: str = ""
    require_auth: bool = False
    max_connections: int = 8


@dataclass
class HealthConfig:
    enabled: bool = False
    port: int = 0  # 0 => websocket port + 1


@dataclass
class VisionConfig:
    enabled: bool = False
    provider: str = "groq"
    max_bytes: int = 400_000


@dataclass
class RobotConfig:
    enabled: bool = True
    require_owner: bool = True


@dataclass
class Limits:
    max_clip_s: int = 60
    max_reply_s: int = 10
    min_clip_s: float = 0.4
    min_speech_s: float = 0.25
    min_speech_ratio: float = 0.15
    end_silence_ms: int = 2000
    max_text_chars: int = 500
    max_reply_chars: int = 400
    merge_gap_ms: int = 2000


@dataclass
class AppConfig:
    host: str = "127.0.0.1"
    port: int = 8765
    proto: int = 1
    limits: Limits = field(default_factory=Limits)
    daily_cost_cap_usd: float = 5.0
    pipeline_step_timeout_s: float = 120.0
    steps: list[str] = field(default_factory=lambda: ["echo"])
    store_audio_days: int = 0
    security: SecurityConfig = field(default_factory=SecurityConfig)
    doa: DoaConfig = field(default_factory=DoaConfig)
    denoise: DenoiseConfig = field(default_factory=DenoiseConfig)
    antispoof: AntispoofConfig = field(default_factory=AntispoofConfig)
    vad: VadConfig = field(default_factory=VadConfig)
    focus: FocusConfig = field(default_factory=FocusConfig)
    stt: SttConfig = field(default_factory=SttConfig)
    mood: MoodConfig = field(default_factory=MoodConfig)
    cadence: CadenceConfig = field(default_factory=CadenceConfig)
    pronunciation: PronunciationConfig = field(default_factory=PronunciationConfig)
    profile: ProfileConfig = field(default_factory=ProfileConfig)
    llm: LlmConfig = field(default_factory=LlmConfig)
    tts: TtsConfig = field(default_factory=TtsConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    research: ResearchConfig = field(default_factory=ResearchConfig)
    listen: ListenConfig = field(default_factory=ListenConfig)
    health: HealthConfig = field(default_factory=HealthConfig)
    vision: VisionConfig = field(default_factory=VisionConfig)
    robot: RobotConfig = field(default_factory=RobotConfig)
    step_warnings: list[str] = field(default_factory=list)


_PLAYBACK = frozenset({"echo", "tts"})


def _insert_before(steps: list[str], name: str, before: frozenset[str]) -> None:
    insert_at = len(steps)
    for target in before:
        if target in steps:
            insert_at = min(insert_at, steps.index(target))
    steps.insert(insert_at, name)


def normalize_steps(
    steps: list[str],
    denoise: DenoiseConfig,
    focus: FocusConfig,
    stt: SttConfig,
    cadence: CadenceConfig,
    pronunciation: PronunciationConfig,
    antispoof: AntispoofConfig,
    mood: MoodConfig,
    vision: VisionConfig | None = None,
) -> tuple[list[str], list[str]]:
    """Ensure antispoof → denoise → focus → stt → mood → cadence → pronunciation → echo when enabled."""
    warnings: list[str] = []
    out: list[str] = []
    seen: set[str] = set()
    for name in steps:
        if name in seen:
            warnings.append(f'duplicate step "{name}" removed')
            continue
        seen.add(name)
        out.append(name)

    def _active(name: str) -> bool:
        if name == "antispoof":
            return antispoof.enabled
        if name == "denoise":
            return denoise.enabled
        if name == "focus":
            return focus.enabled
        if name == "stt":
            return stt.enabled
        if name == "mood":
            return mood.enabled
        if name == "cadence":
            return cadence.enabled
        if name == "pronunciation":
            return pronunciation.enabled
        if name == "vision":
            return vision.enabled if vision is not None else False
        return True

    for name, cfg_on in (
        ("antispoof", antispoof.enabled),
        ("denoise", denoise.enabled),
        ("focus", focus.enabled),
        ("stt", stt.enabled),
        ("vision", vision.enabled if vision is not None else False),
        ("mood", mood.enabled),
        ("cadence", cadence.enabled),
        ("pronunciation", pronunciation.enabled),
    ):
        if cfg_on and name not in out:
            before = frozenset({"safety_in"}) if name == "vision" else _PLAYBACK
            _insert_before(out, name, before)
            warnings.append(
                f'{name}.enabled is true but "{name}" was missing from steps — inserted before playback'
            )

    order = [
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
    for step_name in order:
        if not _active(step_name) or step_name not in out:
            continue
        idx = out.index(step_name)
        for play in _PLAYBACK:
            if play not in out:
                continue
            p_idx = out.index(play)
            if p_idx < idx:
                out.remove(step_name)
                out.insert(p_idx, step_name)
                warnings.append(
                    f'step order fixed: moved "{step_name}" before "{play}"'
                )
                break

    # Compare steps that are actually present. safety_in sits between stt and
    # mood in the canonical list; skipping absent names keeps mood after stt
    # and before cadence when those steps are on.
    present = [name for name in order if _active(name) and name in out]
    for _ in range(max(len(present) - 1, 0)):
        for i in range(len(present) - 1):
            a, b = present[i], present[i + 1]
            if out.index(b) < out.index(a):
                out.remove(b)
                out.insert(out.index(a) + 1, b)
                warnings.append(f'step order fixed: moved "{b}" after "{a}"')

    return out, warnings


def _config_from(cls, raw: dict):
    known = set(cls.__dataclass_fields__)
    return cls(**{k: v for k, v in raw.items() if k in known})


def _focus_config(raw: dict) -> FocusConfig:
    known = {f.name for f in FocusConfig.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    return FocusConfig(**{k: v for k, v in raw.items() if k in known})


def load_config(path: Path | None = None) -> AppConfig:
    import os

    from core.config_validate import (
        antispoof_before_denoise,
        find_forbidden_secrets,
        mood_after_stt,
        validate_implemented_steps,
        validate_step_contract,
        vision_after_stt,
    )

    path = path or Path(__file__).resolve().parent.parent / "config.json"
    if not path.is_file():
        example = path.parent / "config.example.json"
        raw = json.loads(example.read_text(encoding="utf-8"))
    else:
        raw = json.loads(path.read_text(encoding="utf-8"))

    bad = find_forbidden_secrets(raw)
    if bad:
        raise ValueError(
            "config.json must not contain API keys or secrets "
            f"(use environment variables): {', '.join(bad)}"
        )
    limits = Limits(**raw.get("limits", {}))
    doa = DoaConfig(**raw.get("doa", {}))
    denoise = DenoiseConfig(**raw.get("denoise", {}))
    antispoof = _config_from(AntispoofConfig, raw.get("antispoof", {}))
    vad = VadConfig(**raw.get("vad", {}))
    focus = _focus_config(raw.get("focus", {}))
    stt = SttConfig(**raw.get("stt", {}))
    if stt.auto_language and stt.model.endswith(".en"):
        raise ValueError(
            "stt.auto_language requires a multilingual Whisper model (not *.en); "
            f"got stt.model={stt.model!r}"
        )
    mood = _config_from(MoodConfig, raw.get("mood", {}))
    cadence = CadenceConfig(**raw.get("cadence", {}))
    pronunciation = PronunciationConfig(**raw.get("pronunciation", {}))
    profile = ProfileConfig(**raw.get("profile", {}))
    llm = _config_from(LlmConfig, raw.get("llm", {}))
    tts = _config_from(TtsConfig, raw.get("tts", {}))
    safety = _config_from(SafetyConfig, raw.get("safety", {}))
    memory = _config_from(MemoryConfig, raw.get("memory", {}))
    research = _config_from(ResearchConfig, raw.get("research", {}))
    listen = _config_from(ListenConfig, raw.get("listen", {}))
    health = _config_from(HealthConfig, raw.get("health", {}))
    vision = _config_from(VisionConfig, raw.get("vision", {}))
    robot = _config_from(RobotConfig, raw.get("robot", {}))
    sec_raw = raw.get("security", {})
    security = SecurityConfig(
        auth_token=str(sec_raw.get("auth_token", "")),
        require_auth=bool(sec_raw.get("require_auth", False)),
        max_connections=int(sec_raw.get("max_connections", 8)),
    )
    env_token = os.environ.get("ASTRA_AUTH_TOKEN", "").strip()
    if env_token:
        security.auth_token = env_token
        security.require_auth = True
    if os.environ.get("ASTRA_BIND_ALL", "").strip() in ("1", "true", "yes"):
        bind_host = "0.0.0.0"
    else:
        bind_host = raw.get("host", "127.0.0.1")
    raw_steps = list(raw.get("steps", ["echo"]))
    # Do not silently rewrite denoise-before-antispoof. That order scores
    # cleaned audio and must fail to load.
    antispoof_before_denoise(raw_steps)
    # Do not silently rewrite mood-before-stt. Both names in that order fail to load.
    mood_after_stt(raw_steps)
    vision_after_stt(raw_steps)
    steps, step_warnings = normalize_steps(
        raw_steps, denoise, focus, stt, cadence, pronunciation, antispoof, mood, vision
    )
    validate_step_contract(steps)
    validate_implemented_steps(steps)
    if security.require_auth and not security.auth_token.strip():
        raise ValueError(
            "security.require_auth is true but auth_token is empty "
            "(set ASTRA_AUTH_TOKEN or security.auth_token in config)"
        )
    return AppConfig(
        host=bind_host,
        port=int(raw.get("port", 8765)),
        proto=int(raw.get("proto", 1)),
        limits=limits,
        daily_cost_cap_usd=float(raw.get("daily_cost_cap_usd", 5.0)),
        pipeline_step_timeout_s=float(raw.get("pipeline_step_timeout_s", 120.0)),
        steps=steps,
        store_audio_days=int(raw.get("store_audio_days", 0)),
        security=security,
        doa=doa,
        denoise=denoise,
        antispoof=antispoof,
        vad=vad,
        focus=focus,
        stt=stt,
        mood=mood,
        cadence=cadence,
        pronunciation=pronunciation,
        profile=profile,
        llm=llm,
        tts=tts,
        safety=safety,
        memory=memory,
        research=research,
        listen=listen,
        health=health,
        vision=vision,
        robot=robot,
        step_warnings=step_warnings,
    )
