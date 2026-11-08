"""HTTP API: analyse a change request, collect signatures, release through PLM; read results and conformance."""

from __future__ import annotations

import json
import random
from itertools import count

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from mcp import Client
from pydantic import BaseModel

from eca.blueprint.toolbox import Toolbox
from eca.engine import seed_for, servers
from eca.guard import Guard
from eca.llm import SimModel
from eca.servers.plm import changes_server
from eca.settings import ROOT, load
from eca.solutions.engineering_change import EngineeringChange, Run

app = FastAPI(title="engineering-change-agents")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])
_reports: dict[str, dict] = {}
_signatures: dict[str, list[dict]] = {}
_ids = count(1)
_changes = changes_server()


class ChangeRequest(BaseModel):
    text: str
    attachment: str = ""


class Signature(BaseModel):
    person: str
    role: str


@app.get("/results")
def results() -> dict:
    path = ROOT / "reports" / "results.json"
    if not path.exists():
        raise HTTPException(404, "no results yet: run make develop report")
    return json.loads(path.read_text())


@app.get("/runs/{name}/{config}")
def runs(name: str, config: str) -> list[dict]:
    path = ROOT / "reports" / "runs" / name / f"{config}.json"
    if name not in ("dev", "heldout") or config not in ("full", "prototype") or not path.exists():
        raise HTTPException(404, "no such run")
    return json.loads(path.read_text())


@app.post("/requests")
async def analyse(body: ChangeRequest) -> dict:
    s = load()
    cfg = s.configs["full"]
    rid = f"API-{next(_ids):04d}"
    req = {"id": rid, "text": body.text, "attachment": body.attachment}
    async with Toolbox(servers(), s, random.Random(seed_for(s, rid, "tools"))) as tb:
        run = Run(s, cfg, tb, SimModel(s, random.Random(seed_for(s, rid))), Guard(s, cfg.guard))
        report = await EngineeringChange(s, cfg).analyse(run, req)
    _reports[rid], _signatures[rid] = report, []
    return {k: v for k, v in report.items() if k != "ledger"} | {"status": "awaiting signatures"}


@app.post("/requests/{rid}/signatures")
async def sign(rid: str, sig: Signature) -> dict:
    """People sign; the release happens only when every required role has signed, by different people."""
    report = _reports.get(rid)
    if report is None:
        raise HTTPException(404, "no such request")
    if report["recommendation"] != "approve":
        raise HTTPException(409, f"the recommendation is {report['recommendation']}; nothing to release")
    if sig.role not in report["approval_roles"]:
        raise HTTPException(422, f"this change needs {report['approval_roles']}")
    sigs = _signatures[rid]
    if any(x["person"] == sig.person for x in sigs):
        raise HTTPException(403, "four eyes: each signature must come from a different person")
    sigs.append(sig.model_dump())
    missing = sorted(set(report["approval_roles"]) - {x["role"] for x in sigs})
    if missing:
        return {"status": "awaiting signatures", "missing": missing}
    async with Client(_changes) as c:
        r = await c.call_tool(
            "release_change_order", {"request_id": rid, "crash_relevant": report["crash_relevant"], "signatures": sigs}
        )
    if r.is_error:
        raise HTTPException(409, r.content[0].text)
    return {"status": "released"} | json.loads(r.content[0].text)


@app.get("/conformance")
def conformance_report() -> list[dict]:
    path = ROOT / "reports" / "development.json"
    if not path.exists():
        raise HTTPException(404, "no conformance report yet")
    return json.loads(path.read_text())["conformance"]
