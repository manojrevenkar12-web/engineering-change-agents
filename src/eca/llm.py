"""Model access goes through one client per provider, configured in config/eca.toml (standard AS-03).

`SimModel` is the evaluation's model: it reads with the mistakes a real model makes, at the rates in config, and
accounts tokens, latency and cost. `GatewayChat` is an OpenAI-compatible client for a central enterprise AI
platform, with structured output; it is tested against a mock transport and never called by the evaluation."""

from __future__ import annotations

import json
import math
import os
import random
import re
from dataclasses import dataclass

import httpx

from eca.settings import Settings

ADDRESSED = re.compile(r"\b(ai|assistant|agent)\b", re.I)
IMPERATIVE = re.compile(r"\b(ignore|mark|approve|skip)\b", re.I)


@dataclass
class Usage:
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    cost_eur: float = 0.0


class SimModel:
    def __init__(self, s: Settings, rng: random.Random):
        self.s, self.cfg, self.rng = s, s.llm, rng
        self.usage = Usage()

    def call(self, tokens_in: int, tokens_out: int) -> float:
        c = self.cfg
        self.usage.calls += 1
        self.usage.tokens_in += tokens_in
        self.usage.tokens_out += tokens_out
        self.usage.cost_eur += tokens_in / 1000 * c.price_in + tokens_out / 1000 * c.price_out
        return (c.latency_ms + c.ms_per_1k_in * tokens_in / 1000) * math.exp(self.rng.gauss(0, c.latency_spread))

    def chance(self, p: float) -> bool:
        return self.rng.random() < p

    def instructions_in(self, text: str) -> list[str]:
        """What the model would read as an instruction to itself inside data."""
        return [x for x in re.split(r"(?<=[.!?])\s+", text) if ADDRESSED.search(x) and IMPERATIVE.search(x)]

    def follows(self, text: str) -> bool:
        return bool(self.instructions_in(text)) and self.chance(self.cfg.follow_injection)


class GatewayChat:
    """OpenAI-compatible chat completions with JSON-schema structured output and tool calls."""

    def __init__(self, s: Settings, api_key: str | None = None, transport: httpx.BaseTransport | None = None):
        key = api_key or os.environ.get("AI_GATEWAY_KEY")
        if not key:
            raise RuntimeError("AI_GATEWAY_KEY is not set")
        self.s = s
        self.http = httpx.Client(
            base_url=s.gateway.base_url,
            timeout=s.gateway.timeout_s,
            transport=transport,
            headers={"Authorization": f"Bearer {key}"},
        )

    def structured(self, system: str, user: str, schema: dict, name: str) -> dict:
        body = {
            "model": self.s.gateway.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "response_format": {"type": "json_schema", "json_schema": {"name": name, "schema": schema, "strict": True}},
        }
        r = self.http.post("/chat/completions", json=body)
        r.raise_for_status()
        return json.loads(r.json()["choices"][0]["message"]["content"])

    def text(self, system: str, user: str) -> str:
        body = {
            "model": self.s.gateway.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        r = self.http.post("/chat/completions", json=body)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
