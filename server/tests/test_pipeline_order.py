from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import load_config  # noqa: E402
from core.config_validate import validate_step_contract  # noqa: E402


def test_example_config_pipeline_order(tmp_path: Path) -> None:
    example = ROOT / "config.example.json"
    cfg = load_config(example)
    assert "echo" not in cfg.steps
    assert cfg.steps.index("antispoof") < cfg.steps.index("denoise")
    assert cfg.steps.index("denoise") < cfg.steps.index("focus") < cfg.steps.index("stt")
    assert cfg.steps.index("stt") < cfg.steps.index("safety_in") < cfg.steps.index("llm")
    assert cfg.steps.index("safety_in") < cfg.steps.index("context_retrieve") < cfg.steps.index("llm")
    assert cfg.steps.index("context_retrieve") < cfg.steps.index("research") < cfg.steps.index("llm")
    assert cfg.steps.index("llm") < cfg.steps.index("intent") < cfg.steps.index("safety_out")
    assert cfg.steps.index("safety_out") < cfg.steps.index("memory_persist") < cfg.steps.index("tts")
    assert cfg.denoise.backend == "rnnoise"


def test_live_config_pipeline_order() -> None:
    cfg = load_config(ROOT / "config.json")
    assert "echo" not in cfg.steps
    assert "tts" in cfg.steps
    assert cfg.steps.index("safety_in") < cfg.steps.index("llm") < cfg.steps.index("safety_out")
    assert cfg.steps.index("safety_out") < cfg.steps.index("memory_persist") < cfg.steps.index("tts")
    if "context_retrieve" in cfg.steps:
        assert cfg.steps.index("context_retrieve") < cfg.steps.index("llm")
    if "research" in cfg.steps:
        assert cfg.steps.index("research") < cfg.steps.index("llm")


def test_example_config_passes_step_contract() -> None:
    cfg = load_config(ROOT / "config.example.json")
    validate_step_contract(cfg.steps)
