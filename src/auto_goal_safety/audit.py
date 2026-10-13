"""Bounded, redacted audit output for tests and local inspection only."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any


class BoundedRedactedAuditWriter:
    """Append allow-listed JSONL records without retaining user text or IDs."""

    def __init__(self, directory: Path | str, filename: str = "audit.jsonl", max_bytes: int = 4096):
        root = Path(directory)
        if not isinstance(max_bytes, int) or isinstance(max_bytes, bool) or max_bytes < 64:
            raise ValueError("max_bytes must be an integer of at least 64")
        if Path(filename).name != filename:
            raise ValueError("filename must not contain path separators")
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / filename
        self.max_bytes = max_bytes
        self._lock = threading.Lock()

    def write(self, *, classification: str, action: str, duplicate: bool, fail_open: bool) -> bool:
        """Write one small record, returning false when the bound is reached."""

        event = {
            "classification": classification if classification in {"no_goal", "candidate_goal"} else "no_goal",
            "action": action if action in {"no_goal", "candidate_only"} else "no_goal",
            "duplicate": bool(duplicate),
            "fail_open": bool(fail_open),
        }
        line = (json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n").encode("utf-8")
        with self._lock:
            if self.path.is_symlink():
                return False
            current = self.path.stat().st_size if self.path.exists() else 0
            if current + len(line) > self.max_bytes:
                return False
            flags = os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
            try:
                fd = os.open(self.path, flags, 0o600)
            except OSError:
                return False
            try:
                os.write(fd, line)
            finally:
                os.close(fd)
        return True
