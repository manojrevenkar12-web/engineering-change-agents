"""Special tool requests (relocate or scrap an OEM-owned die or fixture), built from the same blueprint as the
engineering change solution: MCP toolbox with provenance, guard, code policy, reviewer. It exists to show that the
architecture standards carry to a second use case with little new code."""

from __future__ import annotations

import operator
import re
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from eca.blueprint.review import review
from eca.blueprint.toolbox import ToolFailure
from eca.solutions.engineering_change import Run

SPEC = {
    "name": "special-tool-requests",
    "servers": ["plm", "tooling"],
    "untrusted_inputs": ["request.attachment"],
    "decision": "code",
    "policy": "policy",
    "reviewer": True,
    "eval_suite": "data/tool_requests.jsonl",
    "approval_roles": "config.approval",
}
TOOL = re.compile(r"\bWZ-\d{4}-\d\b")
SUPPLIER = re.compile(r"\bS-\d{4}\b")


class State(TypedDict, total=False):
    request: dict
    action: str
    tool: dict | None
    part: dict | None
    supplier: dict | None
    decision: str
    reason: str
    summary: str
    removed: list
    spans: Annotated[list, operator.add]


def policy(
    action: str, tool: dict | None, part: dict | None, supplier: dict | None, transfer_share: float, transfer_weeks: int
) -> tuple[str, str, dict]:
    if tool is None:
        return "engineer_review", "the tool could not be found", {}
    if action == "scrap":
        if part and part["variants"]:
            return "reject", f"part {part['part_no']} is in production on {len(part['variants'])} variants", {}
        return "approve", "the part is no longer used", {}
    if supplier is None:
        return "engineer_review", "the target supplier could not be found", {}
    if supplier["supplier_id"] == tool["supplier_id"]:
        return "reject", "the tool is already at that supplier", {}
    cost = int(round(tool["new_cost_eur"] * transfer_share, -2))
    return "approve", "transfer to a qualified supplier", {"transfer_cost_eur": cost, "weeks": transfer_weeks}


class ToolRequests:
    def __init__(self, s, cfg):
        self.s, self.cfg, self.run = s, cfg, None
        g = StateGraph(State)
        for name in ("intake", "lookup", "decide", "review"):
            g.add_node(name, getattr(self, name))
        g.add_edge(START, "intake")
        g.add_edge("intake", "lookup")
        g.add_edge("lookup", "decide")
        g.add_edge("decide", "review")
        g.add_edge("review", END)
        self.graph = g.compile()

    async def analyse(self, run: Run, request: dict) -> dict:
        self.run = run
        st = await self.graph.ainvoke({"request": request, "spans": []})
        return {
            "id": request["id"],
            "decision": st["decision"],
            "reason": st["reason"],
            "summary": st["summary"],
            "removed": st.get("removed", []),
            "ledger": run.ledger.dump(),
        }

    async def intake(self, st: State) -> dict:
        text = st["request"]["text"]
        self.run.guard.clean(st["request"].get("attachment", ""))
        self.run.ledger.add("input", "request", {}, {"text": text})
        self.run.model.call(self.s.tokens.system, self.s.tokens.action)
        return {"action": "scrap" if re.search(r"\bscrap", text, re.I) else "relocate"}

    async def lookup(self, st: State) -> dict:
        text, tb, ledger = st["request"]["text"], self.run.tb, self.run.ledger
        out: dict = {"tool": None, "part": None, "supplier": None}
        spans: list = []
        if m := TOOL.search(text):
            try:
                out["tool"], _ = await tb.call(ledger, spans, "tooling", "get_tool", {"tool_id": m.group(0)}, 0.0)
                out["part"], _ = await tb.call(
                    ledger, spans, "plm", "get_part", {"part_no": out["tool"]["part_no"]}, 0.0
                )
            except ToolFailure:
                pass
        if m := SUPPLIER.search(text):
            try:
                out["supplier"], _ = await tb.call(
                    ledger, spans, "tooling", "get_supplier", {"supplier_id": m.group(0)}, 0.0
                )
            except ToolFailure:
                pass
        return out | {"spans": spans}

    async def decide(self, st: State) -> dict:
        p = self.s.policy
        decision, reason, extra = policy(
            st["action"], st.get("tool"), st.get("part"), st.get("supplier"), p.transfer_cost_share, p.transfer_weeks
        )
        part = st.get("part")
        self.run.ledger.add(
            "derived",
            "decision",
            {},
            {"decision": decision, **extra, "variants_in_production": len(part["variants"]) if part else 0},
        )
        self.run.model.call(self.s.tokens.system, self.s.tokens.summary)
        text = f"Request to {st['action']} {st['tool']['tool_id'] if st.get('tool') else 'an unknown tool'}: {reason}."
        if extra:
            text += f" Transfer cost {extra['transfer_cost_eur']} EUR, about {extra['weeks']} weeks."
        return {
            "decision": decision,
            "reason": reason,
            "summary": text + f" Recommendation: {decision.replace('_', ' ')}.",
        }

    async def review(self, st: State) -> dict:
        text, removed = review(st["summary"], self.run.ledger.dump(), st["decision"])
        return {"summary": text, "removed": removed}
