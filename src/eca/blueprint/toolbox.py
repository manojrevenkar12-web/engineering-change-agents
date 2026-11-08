"""Reusable building blocks every solution on the platform uses: MCP clients with a provenance ledger, simulated
latency, and spans for the trace. A solution declares which servers it needs; it never talks to a system directly."""

from __future__ import annotations

import json
import math
import random
from contextlib import AsyncExitStack
from dataclasses import asdict, dataclass, field
from typing import Any

from mcp import Client

from eca.settings import Settings


class ToolFailure(Exception):
    pass


@dataclass
class Record:
    """One entry of the provenance ledger: a tool call or a value code derived from earlier records."""

    id: str
    kind: str  # tool | derived | input
    name: str
    args: dict
    output: Any
    status: str = "ok"
    sources: list[str] = field(default_factory=list)


@dataclass
class Span:
    name: str
    kind: str  # agent | model | tool
    start: float
    end: float
    status: str = "ok"
    detail: str = ""


class Ledger:
    def __init__(self):
        self.records: list[Record] = []

    def add(self, kind: str, name: str, args: dict, output: Any, status: str = "ok", sources=()) -> Record:
        r = Record(f"R{len(self.records) + 1:03d}", kind, name, args, output, status, list(sources))
        self.records.append(r)
        return r

    def dump(self) -> list[dict]:
        return [asdict(r) for r in self.records]


class Toolbox:
    """Connected MCP clients for one solution run. Calls are recorded in the ledger of the request at hand."""

    def __init__(self, servers: dict, s: Settings, rng: random.Random):
        self.servers, self.s, self.rng = servers, s, rng
        self.clients: dict[str, Client] = {}
        self._stack = AsyncExitStack()
        self.schemas: dict[str, list] = {}

    async def __aenter__(self) -> Toolbox:
        for name, srv in self.servers.items():
            self.clients[name] = await self._stack.enter_async_context(Client(srv))
            self.schemas[name] = (await self.clients[name].list_tools()).tools
        return self

    async def __aexit__(self, *exc) -> None:
        await self._stack.aclose()

    def latency(self) -> float:
        t = self.s.tools
        return t.latency_ms * math.exp(self.rng.gauss(0, t.latency_spread))

    async def call(
        self, ledger: Ledger, spans: list, server: str, tool: str, args: dict, t: float
    ) -> tuple[Any, float]:
        r = await self.clients[server].call_tool(tool, args)
        end = t + self.latency()
        text = r.content[0].text if r.content else "{}"
        if r.is_error:
            ledger.add("tool", f"{server}.{tool}", args, text, "error")
            spans.append(Span(f"{server}.{tool}", "tool", t, end, "error", text))
            raise ToolFailure(text)
        out = json.loads(text)
        ledger.add("tool", f"{server}.{tool}", args, out)
        spans.append(Span(f"{server}.{tool}", "tool", t, end, "ok", json.dumps(args)[:80]))
        return out, end
