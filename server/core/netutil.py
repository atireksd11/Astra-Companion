from __future__ import annotations

import re
import socket
import subprocess
import sys


def port_is_listening(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex((host, port)) == 0


def find_listeners_windows(port: int) -> list[int]:
    """Return PIDs listening on TCP port (Windows netstat)."""
    try:
        out = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return []
    pids: list[int] = []
    needle = f":{port}"
    for line in out.stdout.splitlines():
        if "LISTENING" not in line.upper():
            continue
        if needle not in line:
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid not in pids and pid > 0:
            pids.append(pid)
    return pids


def format_port_busy_help(port: int) -> str:
    lines = [
        f"Port {port} is already in use - another bridge (or old python) is still running.",
        "",
        "Fix (pick one):",
        "  1. Close the other terminal where you ran: python bridge.py",
        "  2. Or stop the process using the port:",
    ]
    if sys.platform == "win32":
        pids = find_listeners_windows(port)
        if pids:
            for pid in pids:
                lines.append(f"       taskkill /PID {pid} /F")
        else:
            lines.append(
                f"       Get-NetTCPConnection -LocalPort {port} | "
                "Select-Object -ExpandProperty OwningProcess -Unique"
            )
            lines.append("       Stop-Process -Id <that number> -Force")
        lines.append(f"  3. Or use another port: python bridge.py --port {port + 1}")
    else:
        lines.append(f"       lsof -i :{port}   # then kill that PID")
        lines.append(f"  3. Or: python bridge.py --port {port + 1}")
    return "\n".join(lines)
