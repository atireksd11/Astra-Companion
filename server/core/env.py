"""Load KEY=VALUE files into the process environment.

Existing variables win, so a value set in the shell is kept. Empty values are
skipped. Between files, server/.env overrides the repo root .env.
"""

from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(paths: list[Path] | None = None) -> None:
    """Load .env files. The process environment is left unchanged."""
    protected = set(os.environ)
    if paths is None:
        server_dir = Path(__file__).resolve().parent.parent
        repo_root = server_dir.parent
        paths = [repo_root / ".env", server_dir / ".env"]
    for path in paths:
        _load_file(path, protected)


def _load_file(path: Path, protected: set[str]) -> None:
    if not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in protected:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        if value == "":
            continue
        os.environ[key] = value
