"""Runs a solution configuration over change requests. The agents get the request and nothing else; scoring is
elsewhere. Draws are keyed by (request, repeat), so configurations meet the same luck."""

from __future__ import annotations

import asyncio
import hashlib
import json
import random

from eca.blueprint.toolbox import Toolbox
from eca.guard import Guard
from eca.lim.train import production
from eca.llm import SimModel
from eca.servers.plm import documents_server, plm_server, simulation_server, tooling_server
from eca.settings import ROOT, Config, Settings
from eca.solutions.engineering_change import EngineeringChange, Run


def seed_for(s: Settings, *parts: object) -> int:
    return int(hashlib.sha256("|".join(map(str, (s.run.seed, *parts))).encode()).hexdigest()[:15], 16)


def requests(name: str) -> list[dict]:
    return [json.loads(x) for x in (ROOT / "data" / f"requests_{name}.jsonl").read_text().splitlines() if x.strip()]


def servers() -> dict:
    return {
        "plm": plm_server(),
        "tooling": tooling_server(),
        "documents": documents_server(),
        "simulation": simulation_server(production()),
    }


async def analyse_all(s: Settings, cfg: Config, reqs: list[dict], repeats: int) -> list[tuple[int, dict]]:
    solution = EngineeringChange(s, cfg)
    out = []
    async with Toolbox(servers(), s, random.Random(s.run.seed)) as tb:
        for r in range(repeats):
            for req in reqs:
                seed = seed_for(s, req["id"], r)
                tb.rng = random.Random(seed + 1)
                run = Run(s, cfg, tb, SimModel(s, random.Random(seed)), Guard(s, cfg.guard))
                out.append((r, await solution.analyse(run, req)))
    return out


def run(s: Settings, cfg: Config, reqs: list[dict], repeats: int | None = None) -> list[tuple[int, dict]]:
    return asyncio.run(analyse_all(s, cfg, reqs, repeats or s.run.repeats))
