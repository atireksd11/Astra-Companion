"""Optional HTTP sync for speaker profiles (no audio)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


def push_profile(sync_url: str, profile: dict[str, Any], timeout_s: float = 2.0) -> bool:
    base = (sync_url or "").rstrip("/")
    if not base:
        return True
    sid = profile.get("speaker_id", "")
    url = f"{base}/v1/profiles/{sid}"
    body = json.dumps(profile).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="PUT")
    req.add_header("Content-Type", "application/json")
    token = os.environ.get("ASTRA_PROFILE_SYNC_TOKEN", "")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s):
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False
