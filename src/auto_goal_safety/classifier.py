"""Pure, conservative classification for the isolated harness.

This module deliberately has no I/O, clock, environment, session, or network
access.  ``metadata`` is inspected only for in-band internal markers; it is
never used to look up or authorize a session.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

NO_GOAL = "no_goal"
CANDIDATE_GOAL = "candidate_goal"

_INTERNAL_TEXT = re.compile(
    r"(?:__auto_goal_internal__|internal[ _-]?continuation|"
    r"continuation[_ -]?id\s*[=:]|pending[_ -]?event\s*[=:]|"
    r"\[(?:internal[ _-]?)?continuation\])",
    re.IGNORECASE,
)
_INTERNAL_KEYS = frozenset(
    {
        "internal",
        "is_internal",
        "internal_continuation",
        "continuation_id",
        "pending_event",
        "queue",
        "lock",
        "goal_id",
        "task_id",
        "wake_event",
        "resume_token",
    }
)
_PLACEHOLDER_VALUES = frozenset(
    {"", "fake", "forged", "invalid", "missing", "none", "null", "unknown"}
)
_PLACEHOLDER_FRAGMENTS = ("fake", "forged", "mock", "dummy", "test-session")

# Signals are intentionally phrase-based and conservative.  A single generic
# word such as "continue" is not enough to classify a user request.
_STRONG_PATTERNS = (
    re.compile(r"(?:until|till)\s+(?:it\s+is\s+)?(?:complete|done|verified|usable)", re.I),
    re.compile(r"\b(?:finish|complete|deliver)\s+(?:and\s+)?(?:verify|test|ship)\b", re.I),
    re.compile(r"(?:直到|直至).{0,12}(?:完成|验收|可用|交付)", re.S),
    re.compile(r"(?:跨轮|多轮|后台|异步|重启恢复|持续推进)", re.I),
    re.compile(r"(?:修改|实现).{0,20}(?:测试|验收).{0,20}(?:修复|重跑|再验证)", re.S),
    re.compile(r"\b(?:multi[- ]step|multi[- ]round|background|async|restart[- ]safe)\b", re.I),
)
_STAGE_WORDS = frozenset(
    {
        "plan",
        "implement",
        "modify",
        "test",
        "verify",
        "repair",
        "audit",
        "deploy",
        "规划",
        "实施",
        "修改",
        "测试",
        "验收",
        "修复",
        "审计",
        "部署",
    }
)


def _has_internal_marker(text: str, metadata: Any) -> bool:
    if _INTERNAL_TEXT.search(text):
        return True
    if not isinstance(metadata, Mapping):
        return False
    for key, value in metadata.items():
        if str(key).lower() in _INTERNAL_KEYS:
            if key == "continuation_id" and value in (None, ""):
                continue
            return bool(value) or key in {"continuation_id", "pending_event"}
    source = metadata.get("source")
    return isinstance(source, str) and source.lower() in {"internal", "continuation", "system"}


def _has_candidate_signal(text: str) -> bool:
    if any(pattern.search(text) for pattern in _STRONG_PATTERNS):
        return True
    lowered = text.lower()
    stage_hits = sum(1 for word in _STAGE_WORDS if word in lowered or word in text)
    has_dependency = bool(re.search(r"(?:then|after|before|and then|and|然后|再|并且|、|→|->|,)", text, re.I))
    return stage_hits >= 3 and has_dependency


def classify(text: Any, metadata: Any = None) -> str:
    """Return exactly ``no_goal`` or ``candidate_goal``.

    Invalid input and internal continuation-shaped input fail open to
    ``no_goal``.  ``metadata`` cannot make a request a candidate; it can only
    suppress classification when it carries an internal marker.
    """

    if not isinstance(text, str) or not text.strip():
        return NO_GOAL
    try:
        normalized = text.strip()
        if _has_internal_marker(normalized, metadata):
            return NO_GOAL
        return CANDIDATE_GOAL if _has_candidate_signal(normalized) else NO_GOAL
    except Exception:
        return NO_GOAL


def has_usable_session_id(metadata: Any) -> bool:
    """Recognize only a local shape; this never validates a real session."""

    if not isinstance(metadata, Mapping):
        return False
    try:
        value = metadata.get("session_id")
    except Exception:
        return False
    if not isinstance(value, str):
        return False
    candidate = value.strip()
    lowered = candidate.lower()
    if lowered in _PLACEHOLDER_VALUES or any(fragment in lowered for fragment in _PLACEHOLDER_FRAGMENTS):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,127}", candidate))
