"""The customer's systems as MCP servers: PLM (parts, variants, materials), special tools and suppliers,
controlled documents, crash simulation (the surrogate and full FE runs) and change orders.

Each tool declares in its metadata the scope it needs and whether it has a side effect; the conformance check reads
those declarations. Data comes from data/*.json, the systems of record of the synthetic world."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from eca.retrieval import DocumentIndex
from eca.settings import ROOT, load

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)


@lru_cache
def systems() -> dict[str, Any]:
    plm = json.loads((ROOT / "data" / "plm.json").read_text())
    tools = json.loads((ROOT / "data" / "tools.json").read_text())
    docs = json.loads((ROOT / "data" / "documents.json").read_text())
    return {"plm": plm, "tools": tools, "docs": docs}


def materials_by_yield(yield_mpa: float, material_class: str) -> str | None:
    for m in systems()["plm"]["materials"]:
        if m["yield_mpa"] == yield_mpa and m["class"] == material_class:
            return m["id"]
    return None


def meta(scope: str, side_effect: bool = False, approval: bool = False) -> dict:
    return {"scope": scope, "side_effect": side_effect, "approval": approval}


def plm_server() -> MCPServer:
    srv = MCPServer(
        "plm", instructions="Parts, variants and materials of the vehicle programmes.", log_level="CRITICAL"
    )
    data = systems()["plm"]
    parts = {p["part_no"]: p for p in data["parts"]}
    variants = {v["variant"]: v for v in data["variants"]}
    materials = {m["id"]: m for m in data["materials"]}

    @srv.tool(
        description="A part's master data: material, thickness, mass, crash load case, supplier, variants.",
        annotations=READ,
        meta=meta("plm:read"),
    )
    def get_part(part_no: str) -> dict:
        if part_no not in parts:
            raise ToolError(f"no part {part_no}")
        return parts[part_no]

    @srv.tool(
        description="Variants of a platform with vehicle mass and the markets they are sold in.",
        annotations=READ,
        meta=meta("plm:read"),
    )
    def get_variants(variant_ids: list[str]) -> dict:
        missing = [v for v in variant_ids if v not in variants]
        if missing:
            raise ToolError(f"no variants {missing}")
        return {"variants": [variants[v] for v in variant_ids]}

    @srv.tool(
        description="A material's properties and whether it is approved for series production.",
        annotations=READ,
        meta=meta("plm:read"),
    )
    def get_material(material_id: str) -> dict:
        if material_id not in materials:
            raise ToolError(f"no material {material_id}")
        return materials[material_id]

    return srv


def tooling_server() -> MCPServer:
    srv = MCPServer("tooling", instructions="OEM-owned special tools and suppliers.", log_level="CRITICAL")
    data = systems()["tools"]

    @srv.tool(
        description="Special tools (dies, fixtures) built for a part, with tolerances, costs and lead times.",
        annotations=READ,
        meta=meta("tooling:read"),
    )
    def tools_for_part(part_no: str) -> dict:
        return {"tools": [t for t in data["tools"] if t["part_no"] == part_no]}

    @srv.tool(description="One special tool by its id.", annotations=READ, meta=meta("tooling:read"))
    def get_tool(tool_id: str) -> dict:
        t = next((x for x in data["tools"] if x["tool_id"] == tool_id), None)
        if t is None:
            raise ToolError(f"no special tool {tool_id}")
        return t

    @srv.tool(description="A supplier's master data.", annotations=READ, meta=meta("tooling:read"))
    def get_supplier(supplier_id: str) -> dict:
        s = next((x for x in data["suppliers"] if x["supplier_id"] == supplier_id), None)
        if s is None:
            raise ToolError(f"no supplier {supplier_id}")
        return s

    return srv


def documents_server() -> MCPServer:
    s = load()
    srv = MCPServer(
        "documents",
        instructions="Controlled engineering documents: crash targets, processes, standards.",
        log_level="CRITICAL",
    )
    index = DocumentIndex(systems()["docs"], s.retrieval.bm25_k1, s.retrieval.bm25_b, s.retrieval.rrf_k)

    @srv.tool(
        description="Searches controlled documents. Filters: status, load case, market.",
        annotations=READ,
        meta=meta("documents:read"),
    )
    def search_documents(
        query: str,
        method: str = "hybrid",
        current_only: bool = True,
        load_case: str | None = None,
        market: str | None = None,
        k: int = 4,
    ) -> dict:
        return {"documents": index.search(query, k, method, current_only, load_case, market)}

    return srv


def simulation_server(surrogate) -> MCPServer:
    srv = MCPServer(
        "simulation",
        instructions="Crash surrogate (LIM) predictions and full FE simulation requests.",
        log_level="CRITICAL",
    )
    queue: list[dict] = []

    @srv.tool(
        description="Predicts intrusion with a calibrated interval, and flags inputs outside the training data.",
        annotations=READ,
        meta=meta("simulation:read"),
    )
    def predict_intrusion(
        load_case: str, thickness_mm: float, material_id: str, mass_kg: float, reinforced: bool
    ) -> dict:
        m = next((x for x in systems()["plm"]["materials"] if x["id"] == material_id), None)
        if m is None:
            raise ToolError(f"no material {material_id}")
        p = surrogate.predict(load_case, thickness_mm, m["yield_mpa"], mass_kg, reinforced, m["class"], material_id)
        return p.__dict__

    @srv.tool(
        description="Queues a full finite-element crash simulation. Results come back in about a day.",
        annotations=WRITE,
        meta=meta("simulation:request", side_effect=True),
    )
    def request_fe_simulation(part_no: str, load_case: str, reason: str) -> dict:
        queue.append({"part_no": part_no, "load_case": load_case, "reason": reason})
        return {"ticket": f"FE-{len(queue):05d}", "status": "queued"}

    return srv


def changes_server() -> MCPServer:
    srv = MCPServer(
        "changes", instructions="Change orders in PLM. Releases need the required signatures.", log_level="CRITICAL"
    )
    orders: list[dict] = []
    roles = load().approval

    @srv.tool(
        description="Releases a change order. Requires signatures of the roles the change needs.",
        annotations=WRITE,
        meta=meta("changes:release", side_effect=True, approval=True),
    )
    def release_change_order(request_id: str, crash_relevant: bool, signatures: list[dict]) -> dict:
        needed = set(roles.crash_relevant if crash_relevant else roles.other)
        signed = {s.get("role") for s in signatures}
        people = [s.get("person") for s in signatures]
        if not needed <= signed:
            raise ToolError(f"missing signatures: {sorted(needed - signed)}")
        if len(set(people)) < len(people):
            raise ToolError("one person signed twice: four eyes means two people")
        orders.append({"request_id": request_id, "signatures": signatures})
        return {"change_order": f"CO-{len(orders):05d}", "status": "released"}

    return srv
