"""Side-effect-free auto-goal classification and simulation harness."""

from .audit import BoundedRedactedAuditWriter
from .classifier import CANDIDATE_GOAL, NO_GOAL, classify
from .simulator import SimulationStore, simulate

__all__ = [
    "BoundedRedactedAuditWriter",
    "CANDIDATE_GOAL",
    "NO_GOAL",
    "SimulationStore",
    "classify",
    "simulate",
]
