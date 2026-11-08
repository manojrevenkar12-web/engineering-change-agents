"""The held-out change requests are pinned by fingerprint before any agent code exists. Development never loads
them; `eca heldout` checks the fingerprint, runs once and appends to reports/heldout-runs.log."""

from __future__ import annotations

import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FILES = (
    "data/requests_heldout.jsonl",
    "data/truth/heldout.jsonl",
    "data/plm.json",
    "data/tools.json",
    "data/documents.json",
)


def fingerprint() -> str:
    h = hashlib.sha256()
    for f in FILES:
        h.update(f.encode())
        h.update((ROOT / f).read_bytes())
    return h.hexdigest()


def pinned() -> str:
    return (ROOT / "config" / "heldout.sha256").read_text().split()[0]


def check() -> None:
    if fingerprint() != pinned():
        raise RuntimeError("the held-out change requests or the systems they depend on changed after pinning")
