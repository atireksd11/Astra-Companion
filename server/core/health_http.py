"""Minimal HTTP health check (no extra dependencies)."""

from __future__ import annotations

import asyncio
import json
from typing import Any


def _response(status: int, body: bytes, content_type: str = "application/json") -> bytes:
    reason = "OK" if status == 200 else "Not Found"
    header = (
        f"HTTP/1.1 {status} {reason}\r\n"
        f"Content-Type: {content_type}\r\n"
        f"Content-Length: {len(body)}\r\n"
        f"Connection: close\r\n\r\n"
    )
    return header.encode("ascii") + body


def _target_path(request_line: bytes) -> tuple[bytes, bytes]:
    """Method and path from the request line. Query strings are stripped."""
    parts = request_line.split()
    if len(parts) < 2:
        return b"", b""
    raw = parts[1]
    cut = raw.find(b"?")
    path = raw if cut < 0 else raw[:cut]
    if len(path) > 1 and path.endswith(b"/"):
        path = path[:-1]
    return parts[0], path


async def _handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    payload: dict[str, Any],
) -> None:
    try:
        head = await reader.read(2048)
        first = head.split(b"\r\n", 1)[0] if head else b""
        method, path = _target_path(first)
        if method == b"GET" and path == b"/health":
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            writer.write(_response(200, body))
        elif method == b"GET" and path == b"/":
            body = b'{"service":"astra-bridge"}'
            writer.write(_response(200, body))
        else:
            writer.write(_response(404, b""))
        await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def serve_health(host: str, port: int, payload: dict[str, Any]) -> asyncio.Server:
    return await asyncio.start_server(
        lambda r, w: _handle_client(r, w, payload),
        host,
        port,
    )
