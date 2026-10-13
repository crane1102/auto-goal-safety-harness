"""In-memory simulation; it never creates or resumes a production task."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from typing import Any

from .classifier import CANDIDATE_GOAL, NO_GOAL, classify, has_usable_session_id


class SimulationStore:
    """Test-local state container with deterministic duplicate suppression."""

    def __init__(self) -> None:
        self.records: dict[str, dict[str, Any]] = {}

    def key_for(self, text: Any, metadata: Any) -> str:
        try:
            session = metadata.get("session_id") if isinstance(metadata, Mapping) else None
        except Exception:
            session = None
        try:
            payload = repr((text, session)).encode("utf-8", "replace")
        except Exception:
            payload = f"unrepresentable:{type(text).__module__}.{type(text).__qualname__}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def _safe_audit(audit_writer: Any, result: dict[str, Any]) -> bool:
    if audit_writer is None:
        return False
    try:
        return bool(
            audit_writer.write(
                classification=result["classification"],
                action=result["action"],
                duplicate=result["duplicate"],
                fail_open=result["fail_open"],
            )
        )
    except Exception:
        return False


def simulate(
    text: Any,
    metadata: Any = None,
    *,
    store: SimulationStore | None = None,
    audit_writer: Any = None,
    classifier: Callable[[Any, Any], str] = classify,
    prompt: Any = None,
) -> dict[str, Any]:
    """Classify and record an isolated observation with fail-open semantics.

    A candidate is reported as ``candidate_only`` only when the caller gives a
    locally well-shaped, non-placeholder session ID.  That shape check is not
    a session lookup.  No result creates a native Goal or continuation.
    """

    del prompt  # Explicitly unused: simulation must not mutate or rewrite prompts.
    local_store = store if isinstance(store, SimulationStore) else SimulationStore()
    fail_open = False
    if not isinstance(text, str) or not text.strip():
        fail_open = True
    try:
        classification = classifier(text, metadata)
        if classification not in {NO_GOAL, CANDIDATE_GOAL}:
            classification = NO_GOAL
            fail_open = True
    except Exception:
        classification = NO_GOAL
        fail_open = True

    try:
        key = local_store.key_for(text, metadata)
        duplicate = key in local_store.records
    except Exception:
        key = None
        duplicate = False
        fail_open = True
    try:
        session_ok = has_usable_session_id(metadata)
    except Exception:
        session_ok = False
        fail_open = True
    action = "candidate_only" if classification == CANDIDATE_GOAL and session_ok else "no_goal"
    if classification == CANDIDATE_GOAL and not session_ok:
        fail_open = True
    record = {
        "classification": classification,
        "action": action,
        "duplicate": duplicate,
        "fail_open": fail_open,
        "session_checked": False,
    }
    if key is not None and not duplicate:
        local_store.records[key] = dict(record)
    result = dict(record)
    result["audit_written"] = _safe_audit(audit_writer, result)
    if audit_writer is not None and not result["audit_written"]:
        result["fail_open"] = True
    result["stored_records"] = len(local_store.records)
    return result
