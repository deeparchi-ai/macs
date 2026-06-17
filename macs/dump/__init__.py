"""MACS Decision-Chain Dump.

Runtime-agnostic core:
  - model:     the ``macs.dump.v0`` artifact builder + schema constants
  - triggers:  SLIP-style predicate engine
  - collector: per-turn ring buffer that assembles a dump on trigger
  - sinks:     where dumps are written (file/jsonl, OTel later)
  - adapters:  map a specific runtime's events into the core (hermes is #1)
"""

from .model import SCHEMA_VERSION, SOURCE_SCHEMA_DEFAULT, build_dump
from .triggers import DEFAULT_TRIGGERS, TriggerHit, evaluate
from .collector import TurnCollector
from .sinks import FileSink

__all__ = [
    "SCHEMA_VERSION",
    "SOURCE_SCHEMA_DEFAULT",
    "build_dump",
    "DEFAULT_TRIGGERS",
    "TriggerHit",
    "evaluate",
    "TurnCollector",
    "FileSink",
]
