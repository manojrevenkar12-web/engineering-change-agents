"""The reviewer: every figure in a written summary must trace to the provenance ledger, and the summary may not
state a decision the code did not take (standard AS-04). Offending sentences are removed and reported."""

from __future__ import annotations

import re
from typing import Any

from eca.guard import sentences

NUMBER = re.compile(r"(?<![\w.,-])\d+(?:[.,]\d+)?(?![.,]?\w)")
DECISION_WORDS = {  # sentences that state a decision, not ones that mention an approved list
    "approve": re.compile(
        r"\b(can|should|will|may) be approved\b|\bis approved\b|\bapprove (it|this|the change)\b", re.I
    ),
    "reject": re.compile(
        r"\b(can|should|will|must) be rejected\b|\bis rejected\b|\breject (it|this|the change)\b", re.I
    ),
}


def _numbers(value: Any, out: set[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, int | float):
        out.add(round(float(value), 4))
    elif isinstance(value, str):
        out.update(float(m.replace(",", ".")) for m in NUMBER.findall(value))
    elif isinstance(value, dict):
        for v in value.values():
            _numbers(v, out)
    elif isinstance(value, list):
        for v in value:
            _numbers(v, out)


def known_numbers(records: list[dict]) -> set[float]:
    out: set[float] = set()
    for r in records:
        if r["status"] == "ok":
            _numbers(r["output"], out)
            _numbers(r["args"], out)
    return out


def supported(x: float, known: set[float]) -> bool:
    return any(abs(x - k) <= max(0.01, 0.005 * abs(k)) for k in known)


def unsupported_in(text: str, known: set[float]) -> list[str]:
    return [m for m in NUMBER.findall(text) if not supported(float(m.replace(",", ".")), known)]


def review(summary: str, records: list[dict], decision: str) -> tuple[str, list[dict]]:
    known = known_numbers(records)
    kept, removed = [], []
    for s in sentences(summary):
        bad = unsupported_in(s, known)
        contradicts = [
            w for w, rx in DECISION_WORDS.items() if rx.search(s) and w != decision and "recommend" not in s.lower()
        ]
        if bad:
            removed.append({"sentence": s, "reason": f"figures without a source: {', '.join(bad)}"})
        elif contradicts:
            removed.append({"sentence": s, "reason": f"states '{contradicts[0]}' but the decision is '{decision}'"})
        else:
            kept.append(s)
    return " ".join(kept), removed
