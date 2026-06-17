"""Hermes `macs_dump` observability plugin.

Thin shell over the runtime-agnostic MACS core. The real wiring lives in
``macs.dump.adapters.hermes.register``.

For local dogfooding, install the macs package (``pip install -e <macs-repo>``)
so this import resolves. For an upstream-mergeable PR we ship a self-contained,
zero-dependency vendored variant (the core is small and MIT) — see the repo
README "upstream packaging" note.
"""
from __future__ import annotations

from macs.dump.adapters.hermes import register  # noqa: F401

__all__ = ["register"]
