"""Loader for .env files. The process environment wins over the file."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.env import load_dotenv  # noqa: E402

_KEYS = ("GROQ_API_KEY", "OPENROUTER_API_KEY", "OPENAI_API_KEY")


def _restore(saved: dict[str, str | None]) -> None:
    for name, old in saved.items():
        if old is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = old


def test_loads_quoted_export_and_skips_comments(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "# comment",
                "export GROQ_API_KEY=\"groq-secret\"",
                "OPENROUTER_API_KEY='router-secret'",
                "OPENAI_API_KEY=",
                "",
            ]
        ),
        encoding="utf-8",
    )
    saved = {name: os.environ.get(name) for name in _KEYS}
    for name in _KEYS:
        os.environ.pop(name, None)
    try:
        load_dotenv([env_file])
        assert os.environ["GROQ_API_KEY"] == "groq-secret"
        assert os.environ["OPENROUTER_API_KEY"] == "router-secret"
        assert "OPENAI_API_KEY" not in os.environ
    finally:
        _restore(saved)


def test_shell_wins_and_later_file_overrides_earlier_file(tmp_path: Path) -> None:
    root_env = tmp_path / "root.env"
    server_env = tmp_path / "server.env"
    root_env.write_text(
        "GROQ_API_KEY=from-root\nOPENROUTER_API_KEY=from-root\n",
        encoding="utf-8",
    )
    server_env.write_text("GROQ_API_KEY=from-server\n", encoding="utf-8")
    saved = {name: os.environ.get(name) for name in _KEYS}
    os.environ["OPENROUTER_API_KEY"] = "from-shell"
    os.environ.pop("GROQ_API_KEY", None)
    try:
        load_dotenv([root_env, server_env])
        assert os.environ["GROQ_API_KEY"] == "from-server"
        assert os.environ["OPENROUTER_API_KEY"] == "from-shell"
    finally:
        _restore(saved)


def test_missing_file_is_ignored(tmp_path: Path) -> None:
    saved = os.environ.get("GROQ_API_KEY")
    os.environ.pop("GROQ_API_KEY", None)
    try:
        load_dotenv([tmp_path / "missing.env"])
        assert "GROQ_API_KEY" not in os.environ
    finally:
        if saved is None:
            os.environ.pop("GROQ_API_KEY", None)
        else:
            os.environ["GROQ_API_KEY"] = saved
