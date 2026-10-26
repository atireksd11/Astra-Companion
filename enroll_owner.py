"""From repo root:  python enroll_owner.py"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SERVER_DIR = Path(__file__).resolve().parent / "server"


def main() -> None:
    cmd = [sys.executable, "tools/enroll_owner.py", *sys.argv[1:]]
    raise SystemExit(subprocess.call(cmd, cwd=SERVER_DIR))


if __name__ == "__main__":
    main()
