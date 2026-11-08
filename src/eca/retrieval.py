"""Hybrid retrieval over controlled documents: BM25 and TF-IDF fused by reciprocal rank, with metadata filters
(status, load case, market) applied before ranking."""

from __future__ import annotations

import math
import re
from collections import Counter

STOP = frozenset(
    [
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "by",
        "for",
        "from",
        "in",
        "is",
        "it",
        "of",
        "on",
        "or",
        "that",
        "the",
        "this",
        "to",
        "was",
        "with",
        "which",
    ]
)


def terms(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in STOP]


class DocumentIndex:
    def __init__(self, docs: list[dict], k1: float, b: float, rrf_k: int):
        self.docs, self.k1, self.b, self.rrf_k = docs, k1, b, rrf_k
        self.toks = [terms(d["title"] + " " + d["text"]) for d in docs]
        self.tf = [Counter(t) for t in self.toks]
        n = len(docs)
        df = Counter(w for t in self.toks for w in set(t))
        self.idf = {w: math.log(1 + (n - c + 0.5) / (c + 0.5)) for w, c in df.items()}
        self.idf_tfidf = {w: math.log((1 + n) / (1 + c)) + 1 for w, c in df.items()}
        self.avg = sum(map(len, self.toks)) / max(n, 1)

    def _bm25(self, q: list[str], ids: list[int]) -> list[int]:
        def score(i: int) -> float:
            tf, dl = self.tf[i], len(self.toks[i])
            return sum(
                self.idf.get(w, 0) * tf[w] * (self.k1 + 1) / (tf[w] + self.k1 * (1 - self.b + self.b * dl / self.avg))
                for w in q
                if w in tf
            )

        s = {i: score(i) for i in ids}
        return sorted((i for i in ids if s[i] > 0), key=lambda i: (-s[i], i))

    def _tfidf(self, q: list[str], ids: list[int]) -> list[int]:
        def vec(c: Counter) -> dict[str, float]:
            v = {w: (1 + math.log(n)) * self.idf_tfidf.get(w, 0) for w, n in c.items()}
            norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
            return {w: x / norm for w, x in v.items()}

        qv = vec(Counter(q))
        s = {i: sum(x * vec(self.tf[i]).get(w, 0) for w, x in qv.items()) for i in ids}
        return sorted((i for i in ids if s[i] > 0), key=lambda i: (-s[i], i))

    def search(
        self,
        query: str,
        k: int,
        method: str,
        current_only: bool,
        load_case: str | None = None,
        market: str | None = None,
    ) -> list[dict]:
        q = terms(query)
        ids = [
            i
            for i, d in enumerate(self.docs)
            if (not current_only or d["status"] == "current")
            and (load_case is None or d["load_case"] in (load_case, None))
            and (market is None or d["market"] in (market, None))
        ]
        if method == "bm25":
            ranked = self._bm25(q, ids)
        else:
            fused: dict[int, float] = {}
            for ranking in (self._bm25(q, ids), self._tfidf(q, ids)):
                for r, i in enumerate(ranking):
                    fused[i] = fused.get(i, 0.0) + 1 / (self.rrf_k + r + 1)
            ranked = sorted(fused, key=lambda i: (-fused[i], i))
        return [self.docs[i] for i in ranked[:k]]
