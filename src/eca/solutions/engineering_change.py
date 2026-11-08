"""Engineering change impact analysis: a LangGraph multi-agent system over MCP servers.

    intake -> context -> tooling ---------------------------> decide -> write -> review
                      -> compliance -> crash (LIM + gate) -/

An engineer's change request goes in. Out comes the affected variants, the special tools to rework or replace with
their cost and lead time, the crash targets that apply, a crash prediction with its interval, and a recommendation.
The recommendation is decided by code from the specialists' findings (standard AS-02); the model reads the request
and writes the summary. A person signs before anything is released.
"""

from __future__ import annotations

import operator
import re
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from eca.blueprint.review import known_numbers, review, unsupported_in
from eca.blueprint.toolbox import Ledger, Span, Toolbox, ToolFailure
from eca.guard import Guard
from eca.llm import SimModel
from eca.settings import Config, Settings

SPEC = {
    "name": "engineering-change-impact",
    "servers": ["plm", "tooling", "documents", "simulation"],
    "untrusted_inputs": ["request.attachment", "documents"],
    "decision": "code",
    "policy": "_policy",
    "reviewer": True,
    "eval_suite": "data/requests_dev.jsonl",
    "approval_roles": "config.approval",
}
LOAD_CASE_WORDS = {
    "side_pole": "pole side impact",
    "side_mdb": "moving-barrier side impact",
    "frontal_odb": "offset frontal impact",
    "frontal_full": "full-width frontal impact",
    "rear": "rear impact fuel system",
    "roof": "roof crush",
}
PART = re.compile(r"\b7\d{6}\b")
THICK = re.compile(r"(\d+(?:[.,]\d+)?)\s*mm\s*(?:to|->)\s*(\d+(?:[.,]\d+)?)\s*mm")
MATERIAL = re.compile(r"material from (.+?) to (.+?)(?= on | and |\.\s|$)")
SUPPLIER = re.compile(r"\b(S-\d{4})\b")
SCOPE_ONE = re.compile(r"\b(P\d) (sedan|touring|ev) only\b")
SCOPE_ALL = re.compile(r"\ball (P\d) derivatives\b")
LIMIT = re.compile(r"maximum intrusion (\d+) mm")


def merge(a: dict, b: dict) -> dict:
    return {**a, **b}


def later(a: float, b: float) -> float:
    """Parallel agents join at the later of their clocks."""
    return max(a, b)


class State(TypedDict, total=False):
    request: dict
    change: dict
    part: dict | None
    variants: list[dict]
    findings: Annotated[dict, merge]
    spans: Annotated[list, operator.add]
    clock: Annotated[float, later]
    notes: Annotated[list, operator.add]
    recommendation: str
    flags: list[str]
    summary: str
    removed: list[dict]


def _num(x: str) -> float:
    return float(x.replace(",", "."))


def parse(text: str) -> dict:
    """What a model returns as structured output for a change request (the schema in GatewayChat.structured)."""
    c: dict[str, Any] = {
        "part_no": None,
        "thickness_from": None,
        "thickness_to": None,
        "material_from": None,
        "material_to": None,
        "supplier_to": None,
        "scope": None,
    }
    if m := PART.search(text):
        c["part_no"] = m.group(0)
    if m := THICK.search(text):
        c["thickness_from"], c["thickness_to"] = _num(m.group(1)), _num(m.group(2))
    if m := MATERIAL.search(text):
        c["material_from"], c["material_to"] = m.group(1).strip(), m.group(2).strip()
    if m := SUPPLIER.search(text):
        c["supplier_to"] = m.group(1)
    if m := SCOPE_ONE.search(text):
        c["scope"] = f"{m.group(1)}-{m.group(2)}"
    elif SCOPE_ALL.search(text):
        c["scope"] = "all"
    return c


@dataclass
class Run:
    """What one analysis needs: the toolbox, the model, the guard and the ledger for this request."""

    s: Settings
    cfg: Config
    tb: Toolbox
    model: SimModel
    guard: Guard
    ledger: Ledger = field(default_factory=Ledger)


class EngineeringChange:
    def __init__(self, s: Settings, cfg: Config):
        self.s, self.cfg = s, cfg
        self.run: Run | None = None
        self.graph = self._build()

    # ------------------------------------------------------------------ graph

    def _build(self):
        g = StateGraph(State)
        g.add_node("intake", self.intake)
        g.add_node("context", self.context)
        g.add_node("tooling", self.tooling)
        g.add_node("compliance", self.compliance)
        g.add_node("crash", self.crash)
        g.add_node("decide", self.decide)
        g.add_node("write", self.write)
        g.add_node("review", self.review)
        g.add_edge(START, "intake")
        g.add_edge("intake", "context")
        g.add_edge("context", "tooling")
        g.add_edge("context", "compliance")
        g.add_edge("compliance", "crash")
        g.add_edge(["tooling", "crash"], "decide")
        g.add_edge("decide", "write")
        g.add_edge("write", "review")
        g.add_edge("review", END)
        return g.compile()

    async def analyse(self, run: Run, request: dict) -> dict:
        self.run = run
        state = await self.graph.ainvoke({"request": request, "findings": {}, "spans": [], "clock": 0.0, "notes": []})
        return self._report(request, state)

    # ------------------------------------------------------------------ helpers

    def _think(self, spans: list, name: str, t: float, words: int, out_tokens: int, schemas: int = 0) -> float:
        tk = self.s.tokens
        end = t + self.run.model.call(
            int(tk.system + tk.per_tool_schema * schemas + words * tk.tokens_per_word), out_tokens
        )
        spans.append(Span(name, "model", t, end))
        return end

    async def _tool(self, spans: list, server: str, tool: str, args: dict, t: float):
        return await self.run.tb.call(self.run.ledger, spans, server, tool, args, t)

    def _corrupt(self, c: dict, notes: list) -> dict:
        """The mistakes a model makes when it reads a request, at the configured rates."""
        m, rates = self.run.model, self.s.llm
        c = dict(c)
        if c["thickness_to"] is not None and m.chance(rates.misread_number):
            key = m.rng.choice(["thickness_from", "thickness_to"])
            c[key] = round(c[key] + m.rng.choice([-0.3, -0.2, 0.2, 0.3]), 2)
            notes.append(f"model misread {key}")
        if c["part_no"] and m.chance(rates.wrong_part):
            d = list(c["part_no"])
            i = m.rng.randrange(1, 6)
            d[i], d[i + 1] = d[i + 1], d[i]
            c["part_no"] = "".join(d)
            notes.append("model swapped digits of the part number")
        if c["scope"] not in (None, "all") and m.chance(rates.missed_scope):
            c["scope"] = "all"
            notes.append("model missed the scope restriction")
        return c

    # ------------------------------------------------------------------ agents

    async def intake(self, st: State) -> dict:
        r, spans, notes = st["request"], [], []
        attachment = self.run.guard.clean(r.get("attachment", ""))
        self.run.ledger.add("input", "request", {}, {"text": r["text"]})
        t = self._think(
            spans, "intake: read request", 0.0, len(r["text"].split()) + len(attachment.split()), self.s.tokens.action
        )
        truth_like = parse(r["text"])
        change = self._corrupt(truth_like, notes)
        change["skip_simulation"] = self.run.model.follows(attachment)
        if change["skip_simulation"]:
            notes.append("model took an instruction from the attachment")
        change["unresolved"] = None
        if self.cfg.validate_extraction:
            for attempt in range(2):
                problem = await self._validate(change, spans, t)
                t = max([t] + [s.end for s in spans])
                if not problem:
                    break
                notes.append(f"validation: {problem}")
                if attempt == 1:
                    change["unresolved"] = problem
                    break
                t = self._think(spans, "intake: re-read request", t, len(r["text"].split()), self.s.tokens.action)
                if self.run.model.chance(self.s.llm.recover):
                    change = truth_like | {"skip_simulation": change["skip_simulation"], "unresolved": None}
        return {"change": change, "spans": spans, "clock": t, "notes": notes}

    async def _validate(self, c: dict, spans: list, t: float) -> str | None:
        if not c["part_no"]:
            return "no part number in the request"
        try:
            part, _ = await self._tool(spans, "plm", "get_part", {"part_no": c["part_no"]}, t)
        except ToolFailure:
            return f"part {c['part_no']} does not exist"
        if c["thickness_from"] is not None and abs(c["thickness_from"] - part["thickness_mm"]) > 1e-6:
            return f"stated current thickness {c['thickness_from']} mm, PLM has {part['thickness_mm']} mm"
        if c["material_from"] and c["material_from"] != part["material"]:
            return f"stated current material {c['material_from']}, PLM has {part['material']}"
        if c["thickness_to"] is not None and not 0.5 <= c["thickness_to"] <= 4.0:
            return f"implausible thickness {c['thickness_to']} mm"
        return None

    async def context(self, st: State) -> dict:
        c, spans, t = st["change"], [], st["clock"]
        if c.get("unresolved") or not c["part_no"]:
            return {"part": None, "variants": [], "spans": spans}
        try:
            part, t = await self._tool(spans, "plm", "get_part", {"part_no": c["part_no"]}, t)
        except ToolFailure as e:
            return {"part": None, "variants": [], "spans": spans, "clock": t, "change": c | {"unresolved": str(e)}}
        scope = part["variants"] if c["scope"] in (None, "all") else [v for v in part["variants"] if v == c["scope"]]
        variants, t = await self._tool(spans, "plm", "get_variants", {"variant_ids": scope or part["variants"]}, t)
        self.run.ledger.add("derived", "scope", {}, {"variants": len(variants["variants"])})
        return {"part": part, "variants": variants["variants"], "spans": spans, "clock": t}

    async def tooling(self, st: State) -> dict:
        c, part, spans, t = st["change"], st.get("part"), [], st["clock"]
        if part is None:
            return {"findings": {"tooling": None}}
        t = self._think(spans, "tooling agent", t, 60, self.s.tokens.action, schemas=2)
        tools, t = await self._tool(spans, "tooling", "tools_for_part", {"part_no": part["part_no"]}, t)
        new_class = None
        if c["material_to"]:
            try:
                mat, t = await self._tool(spans, "plm", "get_material", {"material_id": c["material_to"]}, t)
                new_class = mat["class"]
            except ToolFailure:
                new_class = "unknown"
        old = part["thickness_mm"]
        new = c["thickness_to"] if c["thickness_to"] is not None else old
        actions, cost, lead = {}, 0.0, 0
        p = self.s.policy
        for tl in tools["tools"]:
            if c["supplier_to"]:
                act, cst, wk = "transfer", round(tl["new_cost_eur"] * p.transfer_cost_share, -2), p.transfer_weeks
            elif tl["kind"] == "welding_fixture":
                continue
            elif (new_class and new_class not in tl["material_classes"]) or abs(new - old) > tl["tolerance_mm"] + 1e-9:
                act, cst, wk = "new", tl["new_cost_eur"], tl["new_lead_weeks"]
            elif new != old or c["material_to"]:
                act, cst, wk = "rework", tl["rework_cost_eur"], tl["rework_lead_weeks"]
            else:
                continue
            actions[tl["tool_id"]] = act
            cost += cst
            lead = max(lead, wk)
        rec = self.run.ledger.add(
            "derived",
            "tooling impact",
            {},
            {
                "tools": actions,
                "tooling_cost_eur": cost,
                "tooling_cost_keur": round(cost / 1000, 1),
                "lead_weeks": lead,
                "new_tools": sum(a == "new" for a in actions.values()),
                "reworked_tools": sum(a == "rework" for a in actions.values()),
                "transferred_tools": sum(a == "transfer" for a in actions.values()),
            },
        )
        spans.append(Span("tooling agent", "agent", st["clock"], t))
        return {"findings": {"tooling": rec.output}, "spans": spans, "clock": t}

    def _crash_relevant(self, c: dict, part: dict) -> bool:
        changed = (c["thickness_to"] is not None and c["thickness_to"] != part["thickness_mm"]) or bool(
            c["material_to"]
        )
        return bool(part["crash_load_case"]) and changed

    async def compliance(self, st: State) -> dict:
        c, part, spans, t = st["change"], st.get("part"), [], st["clock"]
        if part is None:
            return {"findings": {"compliance": None}}
        t = self._think(spans, "compliance agent", t, 60, self.s.tokens.action, schemas=1)
        regs, limit, limits = [], None, {}
        search = {"method": self.cfg.retrieval, "current_only": self.cfg.current_only}
        if self._crash_relevant(c, part):
            lc = part["crash_load_case"]
            for market in sorted({m for v in st["variants"] for m in v["markets"]}):
                out, t = await self._tool(
                    spans,
                    "documents",
                    "search_documents",
                    {
                        "query": f"internal crash target {LOAD_CASE_WORDS[lc]} {market} maximum intrusion",
                        "load_case": lc,
                        "market": market,
                        "k": 2,
                        **search,
                    },
                    t,
                )
                doc = next((d for d in out["documents"] if LIMIT.search(self.run.guard.clean(d["text"]))), None)
                if doc:
                    value = int(LIMIT.search(doc["text"]).group(1))
                    limits[market] = value
                    regs.append(doc["id"])
            limit = min(limits.values()) if limits else None
        if c["supplier_to"]:
            out, t = await self._tool(
                spans,
                "documents",
                "search_documents",
                {"query": "supplier change production part approval", "k": 1, **search},
                t,
            )
            regs += [d["id"] for d in out["documents"]]
        approved = True
        if c["material_to"]:
            try:
                mat, t = await self._tool(spans, "plm", "get_material", {"material_id": c["material_to"]}, t)
                approved = mat["approved"]
            except ToolFailure:
                approved = False
        rec = self.run.ledger.add(
            "derived",
            "compliance",
            {},
            {"regulations": regs, "limits": limits, "limit_mm": limit, "material_approved": approved},
        )
        spans.append(Span("compliance agent", "agent", st["clock"], t))
        return {"findings": {"compliance": rec.output | {"end": t}}, "spans": spans, "clock": t}

    async def crash(self, st: State) -> dict:
        c, part, spans = st["change"], st.get("part"), []
        comp = st["findings"].get("compliance")
        if part is None or comp is None or not self._crash_relevant(c, part):
            return {"findings": {"crash": None}}
        t0 = t = comp["end"]
        t = self._think(spans, "crash agent", t, 80, self.s.tokens.action, schemas=2)
        material = c["material_to"] or part["material"]
        thickness = c["thickness_to"] if c["thickness_to"] is not None else part["thickness_mm"]
        preds = []
        for v in st["variants"]:
            try:
                p, t = await self._tool(
                    spans,
                    "simulation",
                    "predict_intrusion",
                    {
                        "load_case": part["crash_load_case"],
                        "thickness_mm": thickness,
                        "material_id": material,
                        "mass_kg": v["mass_kg"],
                        "reinforced": part["reinforced"],
                    },
                    t,
                )
            except ToolFailure:
                continue
            preds.append(p | {"variant": v["variant"]})
        limit = comp["limit_mm"]
        if not preds or limit is None:
            gate, worst = "fe_required", None
        else:
            worst = max(preds, key=lambda p: p["high_mm"] if self.cfg.gate == "conformal" else p["intrusion_mm"])
            ood = not all(p["in_distribution"] for p in preds)
            if self.cfg.ood_check and ood:
                gate = "fe_required"
            elif self.cfg.gate == "point":
                gate = "pass" if worst["intrusion_mm"] <= limit else "fail"
            elif worst["high_mm"] <= limit:
                gate = "pass"  # every variant's interval lies below the target
            elif max(p["low_mm"] for p in preds) > limit:
                gate = "fail"  # at least one variant fails even at the low end of its interval
            else:
                gate = "fe_required"  # the interval straddles the target: only a full simulation can decide
        ticket = None
        if gate == "fe_required":
            out, t = await self._tool(
                spans,
                "simulation",
                "request_fe_simulation",
                {
                    "part_no": part["part_no"],
                    "load_case": part["crash_load_case"],
                    "reason": "prediction interval or input outside what the surrogate can decide",
                },
                t,
            )
            ticket = out["ticket"]
        result = {
            "gate": gate,
            "limit_mm": limit,
            "fe_ticket": ticket,
            "predictions": preds,
            "worst": None
            if worst is None
            else {
                k: worst[k]
                for k in ("variant", "intrusion_mm", "low_mm", "high_mm", "in_distribution", "reasons", "model_version")
            },
        }
        self.run.ledger.add("derived", "crash gate", {}, result)
        spans.append(Span("crash agent", "agent", t0, t))
        return {"findings": {"crash": result}, "spans": spans, "clock": t}

    async def decide(self, st: State) -> dict:
        c, f, part, spans = st["change"], st["findings"], st.get("part"), []
        t = st["clock"]
        crash, comp, tooling = f.get("crash"), f.get("compliance"), f.get("tooling")
        flags = []
        if tooling and tooling["lead_weeks"] > self.s.policy.schedule_weeks:
            flags.append(f"schedule risk: new tooling needs {tooling['lead_weeks']} weeks")
        if c.get("unresolved") or part is None:
            rec = "engineer_review"
        elif self.cfg.decides == "code":
            rec = self._policy(comp, crash)
        else:
            t = self._think(spans, "decide (model)", t, 200, self.s.tokens.action)
            rec = self._model_decides(c, comp, crash)
        return {"recommendation": rec, "flags": flags, "spans": spans, "clock": t}

    @staticmethod
    def _policy(comp: dict | None, crash: dict | None) -> str:
        """Code decides: the rules an engineering change board applies, in order."""
        if comp and not comp["material_approved"]:
            return "reject"
        if crash:
            return {"pass": "approve", "fail": "reject", "fe_required": "fe_simulation"}[crash["gate"]]
        return "approve"

    def _model_decides(self, c: dict, comp: dict | None, crash: dict | None) -> str:
        m = self.run.model
        if c.get("skip_simulation"):
            return "approve"
        if comp and not comp["material_approved"] and not m.chance(self.s.llm.misjudge):
            return "reject"
        if crash and crash["worst"]:
            ok = crash["worst"]["intrusion_mm"] <= crash["limit_mm"]
            if m.chance(self.s.llm.misjudge):
                ok = not ok
            return "approve" if ok else "reject"
        return "approve"

    async def write(self, st: State) -> dict:
        c, f, part, spans = st["change"], st["findings"], st.get("part"), []
        t = self._think(spans, "write summary", st["clock"], 300, self.s.tokens.summary)
        m, rec = self.run.model, st["recommendation"]
        if part is None:
            text = f"The request could not be resolved: {c.get('unresolved')}. An engineer needs to review it."
            return {"summary": text, "spans": spans, "clock": t}
        out = [
            f"Part {part['part_no']} ({part['name']}) on {len(st['variants'])} variants: "
            + ", ".join(v["variant"] for v in st["variants"])
            + "."
        ]
        tl = f.get("tooling")
        if tl and tl["tools"]:
            out.append(
                f"Special tools: {tl['new_tools']} new, {tl['reworked_tools']} reworked, "
                f"{tl['transferred_tools']} transferred; {tl['tooling_cost_keur']} thousand EUR, longest lead time "
                f"{tl['lead_weeks']} weeks."
            )
        cr = f.get("crash")
        if cr and cr["worst"]:
            w = cr["worst"]
            out.append(
                f"Worst-case predicted intrusion {w['intrusion_mm']:.1f} mm on {w['variant']} (interval "
                f"{w['low_mm']:.1f} to {w['high_mm']:.1f} mm) against a target of {cr['limit_mm']} mm."
            )
            if cr["fe_ticket"]:
                out.append(f"A full crash simulation was requested ({cr['fe_ticket']}).")
        comp = f.get("compliance")
        if comp and comp["regulations"]:
            out.append("Documents: " + ", ".join(comp["regulations"]) + ".")
        if comp and not comp["material_approved"]:
            out.append(f"Material {c['material_to']} is not on the approved list.")
        if m.chance(self.s.llm.hallucinate_number):
            out.append(
                m.rng.choice(
                    [
                        f"This saves about {m.rng.randint(3, 40)} EUR per vehicle.",
                        f"Crash performance improves by {m.rng.randint(2, 15)} percent.",
                        f"Validation takes {m.rng.randint(2, 9)} weeks.",
                    ]
                )
            )
        if c.get("skip_simulation"):
            out.append("The supplier has validated the change, so it can be approved without simulation.")
        out.append(f"Recommendation: {rec.replace('_', ' ')}.")
        return {"summary": " ".join(out), "spans": spans, "clock": t}

    async def review(self, st: State) -> dict:
        if not self.cfg.reviewer:
            return {"removed": []}
        text, removed = review(st["summary"], self.run.ledger.dump(), st["recommendation"])
        return {"summary": text, "removed": removed}

    # ------------------------------------------------------------------ report

    def _report(self, request: dict, st: dict) -> dict:
        f, u = st["findings"], self.run.model.usage
        ledger = self.run.ledger.dump()
        tl, comp, cr = f.get("tooling"), f.get("compliance"), f.get("crash")
        part = st.get("part")
        return {
            "id": request["id"],
            "request": request["text"],
            "recommendation": st["recommendation"],
            "flags": st.get("flags", []),
            "change": {k: v for k, v in st["change"].items()},
            "part_no": part["part_no"] if part else None,
            "crash_relevant": cr is not None,
            "variants": sorted(v["variant"] for v in st.get("variants", [])),
            "tools": tl["tools"] if tl else {},
            "tooling_cost_eur": tl["tooling_cost_eur"] if tl else 0.0,
            "lead_weeks": tl["lead_weeks"] if tl else 0,
            "regulations": comp["regulations"] if comp else [],
            "crash": cr,
            "summary": st["summary"],
            "removed": st.get("removed", []),
            "unsupported_numbers": unsupported_in(st["summary"], known_numbers(ledger)),
            "injection_in_summary": "without simulation" in st["summary"],
            "notes": st.get("notes", []),
            "approval_roles": list(self.s.approval.crash_relevant if cr is not None else self.s.approval.other),
            "latency_ms": round(max([s.end for s in st["spans"]] + [0.0]), 1),
            "model_calls": u.calls,
            "tokens_in": u.tokens_in,
            "tokens_out": u.tokens_out,
            "cost_eur": round(u.cost_eur, 6),
            "spans": [s.__dict__ for s in st["spans"]],
            "ledger": ledger,
            "guard_removed": self.run.guard.removed,
        }
