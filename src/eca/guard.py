"""Untrusted text (attachments, supplier notes, documents) is data. The guard removes sentences that address the
assistant or tell it to change its rules, before any model reads them."""

from __future__ import annotations

import re

from eca.settings import Settings


def sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


class Guard:
    def __init__(self, s: Settings, enabled: bool):
        self.patterns = [re.compile(p, re.I) for p in s.guard.patterns] if enabled else []
        self.removed: list[str] = []

    def clean(self, text: str) -> str:
        if not self.patterns:
            return text
        keep = []
        for s in sentences(text):
            if any(p.search(s) for p in self.patterns):
                self.removed.append(s)
            else:
                keep.append(s)
        return " ".join(keep)
