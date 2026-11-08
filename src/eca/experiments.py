"""Development and the held-out run. "full" is the design; the prototype and the ablations each take controls away
and run on the same requests with the same random draws, so differences are paired."""

from __future__ import annotations

import asyncio
import json
import random
from datetime import UTC, datetime

from eca import conformance, heldout
from eca.blueprint.toolbox import Toolbox
from eca.engine import requests, run, seed_for, servers
from eca.evaluate import score, summarize, truth
from eca.guard import Guard
from eca.lim.train import MODELS, production, train
from eca.llm import SimModel
from eca.settings import ROOT, Settings, load
from eca.solutions.engineering_change import Run
from eca.solutions.tool_requests import ToolRequests

REPORTS = ROOT / "reports"
KEEP = (
    "id",
    "request",
    "recommendation",
    "flags",
    "change",
    "part_no",
    "crash_relevant",
    "variants",
    "tools",
    "tooling_cost_eur",
    "lead_weeks",
    "regulations",
    "crash",
    "summary",
    "removed",
    "notes",
    "approval_roles",
    "latency_ms",
    "model_calls",
    "cost_eur",
    "spans",
    "ledger",
    "guard_removed",
)


def variants(s: Settings) -> dict:
    full = s.configs["full"]
    return {"full": full, "prototype": s.configs["prototype"]} | {
        a: full.model_copy(update=o) for a, o in s.ablations.items()
    }


def paired(a: list[dict], b: list[dict], key: str, s: Settings) -> dict:
    """Difference b - a in the per-request mean of a metric, with a bootstrap interval over requests."""
    import numpy as np

    def per(xs):
        d: dict[str, list[float]] = {}
        for x in xs:
            d.setdefault(x["id"], []).append(float(x[key]))
        return {k: sum(v) / len(v) for k, v in d.items()}

    pa, pb = per(a), per(b)
    ids = sorted(pa)
    diff = np.asarray([pb[i] - pa[i] for i in ids])
    rng = np.random.default_rng(s.run.seed)
    boots = [float(diff[rng.integers(0, len(diff), len(diff))].mean()) for _ in range(s.eval.bootstrap)]
    lo, hi = np.quantile(boots, [s.eval.alpha / 2, 1 - s.eval.alpha / 2])
    return {"diff": float(diff.mean()), "ci": [float(lo), float(hi)]}


def evaluate_set(name: str, s: Settings) -> tuple[dict, dict, dict]:
    t = truth(name)
    reqs = requests(name)
    summaries, scores, samples = {}, {}, {}
    for cname, cfg in variants(s).items():
        results = run(s, cfg, reqs)
        sc = [score(rep, t[rep["id"]], s) for _, rep in results]
        summaries[cname], scores[cname] = summarize(sc, s), sc
        if cname in ("full", "prototype"):
            samples[cname] = [
                {k: rep[k] for k in KEEP} | {"truth": t[rep["id"]]["recommendation"]} for r, rep in results if r == 0
            ]
    comparisons = {
        c: {k: paired(scores["full"], scores[c], k, s) for k in ("safety_miss", "correct", "deferred")}
        for c in summaries
        if c != "full"
    }
    return summaries, comparisons, samples


def tool_requests_eval(s: Settings) -> dict:
    reqs = [json.loads(x) for x in (ROOT / "data" / "tool_requests.jsonl").read_text().splitlines() if x.strip()]
    t = {
        r["id"]: r
        for r in (
            json.loads(x)
            for x in (ROOT / "data" / "truth" / "tool_requests.jsonl").read_text().splitlines()
            if x.strip()
        )
    }

    async def go():
        sol, out = ToolRequests(s, s.configs["full"]), []
        async with Toolbox(servers(), s, random.Random(s.run.seed)) as tb:
            for r in reqs:
                run_ = Run(s, s.configs["full"], tb, SimModel(s, random.Random(seed_for(s, r["id"]))), Guard(s, True))
                out.append(await sol.analyse(run_, r))
        return out

    out = asyncio.run(go())
    correct = sum(o["decision"] == t[o["id"]]["decision"] for o in out)
    return {
        "requests": len(out),
        "correct": correct,
        "safety_misses": 0,
        "results": [
            {"id": o["id"], "decision": o["decision"], "expected": t[o["id"]]["decision"], "summary": o["summary"]}
            for o in out
        ],
    }


def _lim() -> dict:
    if not (MODELS / "registry.json").exists():
        train()
    production()
    return json.loads((MODELS / "registry.json").read_text())


def _write_runs(name: str, samples: dict) -> None:
    d = REPORTS / "runs" / name
    d.mkdir(parents=True, exist_ok=True)
    for c, rows in samples.items():
        (d / f"{c}.json").write_text(json.dumps(rows, indent=1) + "\n")


def develop() -> dict:
    s = load()
    registry = _lim()
    summaries, comparisons, samples = evaluate_set("dev", s)
    tr = tool_requests_eval(s)
    conf = conformance.report({"engineering-change-impact": summaries["full"], "special-tool-requests": tr})
    _write_runs("dev", samples)
    out = {
        "set": "dev",
        "configs": summaries,
        "comparisons": comparisons,
        "tool_requests": tr,
        "conformance": conf,
        "lim": registry,
    }
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "development.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


def run_heldout(again: bool = False) -> dict:
    heldout.check()
    log = REPORTS / "heldout-runs.log"
    previous = log.read_text().splitlines() if log.exists() else []
    if previous and not again:
        raise RuntimeError(f"the held-out set has already run ({len(previous)} entries in {log.name})")
    s = load()
    _lim()
    summaries, comparisons, samples = evaluate_set("heldout", s)
    _write_runs("heldout", samples)
    out = {"set": "heldout", "fingerprint": heldout.fingerprint(), "configs": summaries, "comparisons": comparisons}
    (REPORTS / "heldout.json").write_text(json.dumps(out, indent=1) + "\n")
    f = summaries["full"]
    with log.open("a") as fh:
        fh.write(
            f"{datetime.now(UTC).isoformat(timespec='seconds')} {heldout.fingerprint()[:12]} "
            f"safety_misses={f['safety_misses']} accuracy_decided={f['accuracy_decided']['value']:.3f} "
            f"deferral={f['deferral_rate']['value']:.3f}\n"
        )
    return out
