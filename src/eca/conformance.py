"""Checks a solution against config/standards.toml from evidence: its source (AST), its declared SPEC, the
configuration it runs with, and the tools its MCP servers expose."""

from __future__ import annotations

import ast
import asyncio
import json
import tomllib
from pathlib import Path

from mcp import Client

from eca.settings import ROOT, Config

MODEL_SDKS = {"openai", "anthropic", "boto3", "langchain_openai", "langchain_anthropic", "mistralai", "google"}
MODEL_NAMES = ("gpt-", "claude-", "mistral-", "gemini-", "llama-")


def standards() -> list[dict]:
    return tomllib.loads((ROOT / "config" / "standards.toml").read_text())["standard"]


def read_spec(tree: ast.AST) -> dict:
    """The SPEC a solution declares, read without importing (or running) the solution."""
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "SPEC" for t in n.targets):
            return ast.literal_eval(n.value)
    raise ValueError("solution declares no SPEC")


def _imports(tree: ast.AST) -> set[str]:
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module.split(".")[0])
    return out


def _function(tree: ast.AST, name: str) -> ast.AST | None:
    return next(
        (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == name), None
    )


def _names(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)
    }


async def _tools(servers: dict, names: list[str]) -> dict[str, list]:
    out = {}
    for n in names:
        if n in servers:
            async with Client(servers[n]) as c:
                out[n] = (await c.list_tools()).tools
    return out


def _cases(path: Path) -> int:
    if not path.exists():
        return 0
    if path.suffix == ".jsonl":
        return sum(1 for x in path.read_text().splitlines() if x.strip())
    return sum(1 for x in path.read_text().splitlines() if x.startswith("def test_") or "def test_" in x)


def check(path: Path, cfg: Config, servers: dict, results: dict | None = None) -> dict:
    src = path.read_text()
    tree = ast.parse(src)
    spec = read_spec(tree)
    tools = asyncio.run(_tools(servers, spec["servers"]))
    missing_servers = [s for s in spec["servers"] if s not in servers]
    rows = []

    def add(sid: str, ok: bool, evidence: str) -> None:
        rows.append({"id": sid, "pass": bool(ok), "evidence": evidence})

    undeclared = [
        f"{s}.{t.name}"
        for s, ts in tools.items()
        for t in ts
        if not t.meta or "scope" not in t.meta or "side_effect" not in t.meta
    ]
    add(
        "AS-01",
        not undeclared and not missing_servers,
        f"{sum(map(len, tools.values()))} tools declare scope and side effect"
        if not undeclared
        else f"undeclared: {', '.join(undeclared)}"
        + (f"; unknown servers {missing_servers}" if missing_servers else ""),
    )

    fn = _function(tree, spec.get("policy") or "")
    reads_model = fn is not None and bool(_names(fn) & {"model", "llm", "complete", "chat"})
    add(
        "AS-02",
        spec["decision"] == "code" and cfg.decides == "code" and fn is not None and not reads_model,
        f"policy {spec.get('policy')}() is plain code; configured to decide by {cfg.decides}"
        if not reads_model
        else f"{spec.get('policy')}() calls a model",
    )

    sdks = _imports(tree) & MODEL_SDKS
    add("AS-03", not sdks, "no model SDK imported" if not sdks else f"imports {', '.join(sorted(sdks))}")

    has_review = _function(tree, "review") is not None
    add(
        "AS-04",
        spec["reviewer"] and cfg.reviewer and has_review,
        "summaries pass the provenance reviewer" if has_review and cfg.reviewer else "no reviewer step",
    )

    cleans = "guard.clean" in src
    add(
        "AS-05",
        (not spec["untrusted_inputs"]) or (cfg.guard and cleans),
        f"guard applied to {', '.join(spec['untrusted_inputs'])}"
        if cleans and cfg.guard
        else "untrusted text unguarded",
    )

    if "simulation" in spec["servers"]:
        probe = next((t for t in tools.get("simulation", []) if t.name == "predict_intrusion"), None)
        ok = probe is not None and cfg.gate == "conformal" and cfg.ood_check
        add("AS-06", ok, f"interval gate {cfg.gate}, input check {'on' if cfg.ood_check else 'off'}")
    else:
        add("AS-06", True, "no domain model used")

    approval_tools = [t.name for ts in tools.values() for t in ts if t.meta and t.meta.get("approval")]
    called = [t for t in approval_tools if f'"{t}"' in src or f"'{t}'" in src]
    add(
        "AS-07",
        not called,
        "releases only through signed approvals" if not called else f"calls {', '.join(called)} directly",
    )

    suite = ROOT / spec["eval_suite"]
    n = _cases(suite)
    misses = (results or {}).get("safety_misses")
    add(
        "AS-08",
        n >= 5 and (misses is None or misses == 0),
        f"{n} evaluation cases" + ("" if misses is None else f"; {misses} safety misses in the last run"),
    )

    literals = [
        c.value
        for c in ast.walk(tree)
        if isinstance(c, ast.Constant) and isinstance(c.value, str) and c.value.lower().startswith(MODEL_NAMES)
    ]
    add("AS-09", not literals, "no model names in code" if not literals else f"hard-coded: {', '.join(literals)}")

    return {
        "solution": spec["name"],
        "path": str(path.relative_to(ROOT)),
        "checks": rows,
        "passed": sum(r["pass"] for r in rows),
        "total": len(rows),
    }


def report(results_by_solution: dict[str, dict] | None = None) -> list[dict]:
    from eca.engine import servers
    from eca.servers.plm import changes_server
    from eca.settings import load

    s = load()
    srv = servers() | {"changes": changes_server()}
    targets = [
        (ROOT / "src/eca/solutions/engineering_change.py", s.configs["full"]),
        (ROOT / "src/eca/solutions/tool_requests.py", s.configs["full"]),
        (ROOT / "examples/nonconformant_assistant.py", s.configs["prototype"]),
    ]
    out = []
    for path, cfg in targets:
        name = read_spec(ast.parse(path.read_text()))["name"]
        out.append(check(path, cfg, srv, (results_by_solution or {}).get(name)))
    return out


if __name__ == "__main__":
    print(json.dumps(report(), indent=1))
