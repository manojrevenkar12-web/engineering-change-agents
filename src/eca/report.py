"""results.json, RESULTS.md, the README block and the dashboard data. Lays out results; computes none."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime

from eca.conformance import standards
from eca.settings import ROOT, load

REPORTS = ROOT / "reports"
START, END = "<!-- results:start -->", "<!-- results:end -->"


def build() -> dict:
    dev = json.loads((REPORTS / "development.json").read_text())
    held_path = REPORTS / "heldout.json"
    held = json.loads(held_path.read_text()) if held_path.exists() else None
    log = REPORTS / "heldout-runs.log"
    s = load()
    lim = dev["lim"]
    card = next(m for m in lim["models"] if m["version"] == lim["production"])
    return {
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
        "repeats": s.run.repeats,
        "dev": {"configs": dev["configs"], "comparisons": dev["comparisons"]},
        "heldout": None
        if held is None
        else {"configs": held["configs"], "comparisons": held["comparisons"], "fingerprint": held["fingerprint"]},
        "heldout_runs": len(log.read_text().splitlines()) if log.exists() else 0,
        "tool_requests": dev["tool_requests"],
        "conformance": dev["conformance"],
        "lim": card,
        "configs": {k: v.model_dump() for k, v in s.configs.items()},
        "ablations": s.ablations,
        "standards": standards(),
    }


def _pct(x: float) -> str:
    return f"{100 * x:.0f}%"


def table(cfgs: dict, comps: dict) -> list[str]:
    rows = [
        "| Configuration | Approved but fails the crash target | Correct where it decided | Sent to full simulation "
        "| Crash target found | Reports with unsourced figures | Injected text in report | p95 latency |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for n, m in cfgs.items():
        rows.append(
            f"| {n} | **{m['safety_misses']}** of {m['runs']} | {_pct(m['accuracy_decided']['value'])} "
            f"({_pct(m['accuracy_decided']['ci'][0])}–{_pct(m['accuracy_decided']['ci'][1])}) | "
            f"{_pct(m['deferral_rate']['value'])} | {_pct(m['limit_correct']['value'])} | "
            f"{m['reports_with_unsupported_figures']} | {m['injection_in_summary']} | "
            f"{m['p95_latency_ms'] / 1000:.1f} s |"
        )
    return rows


def markdown(r: dict) -> str:
    out = [
        f"# Results\n\nGenerated {r['generated']} by `make report`. Each change request ran {r['repeats']} times "
        'with different model draws; intervals resample requests. "Approved but fails" is the safety-critical '
        "error: the agent recommends approval and the crash target is exceeded in the world's truth.\n",
        f"Crash surrogate in production: `{r['lim']['version']}`, test coverage "
        f"{_pct(r['lim']['test_coverage'])} (target {_pct(r['lim']['target_coverage'])}), relative error "
        f"{100 * r['lim']['test_mape']:.1f}%, trained on {sum(r['lim']['rows'].values())} historical simulations.\n",
    ]
    for name in ("heldout", "dev"):
        block = r[name]
        if not block:
            continue
        title = "Held-out change requests (run once)" if name == "heldout" else "Development change requests"
        out += [f"\n## {title}\n", *table(block["configs"], block["comparisons"]), ""]
        f = block["configs"]["full"]
        out.append(
            f"Full design: {f['fe_requests']} of {f['crash_runs']} crash-relevant analyses went to a full "
            f"simulation; the rest were decided by the surrogate. Estimated engineer time per request: "
            f"{f['manual_hours']:.1f} h by hand, {f['agent_hours']:.1f} h to review the agent's report "
            "(assumptions in config/eca.toml [value])."
        )
    out += [
        "\n## Conformance to the architecture standards\n",
        "| Standard | " + " | ".join(c["solution"] for c in r["conformance"]) + " |",
        "|---|" + "---|" * len(r["conformance"]),
    ]
    for i, st in enumerate(r["standards"]):
        out.append(
            f"| {st['id']} {st['title']} | "
            + " | ".join(
                ("pass" if c["checks"][i]["pass"] else "**fail**") + f": {c['checks'][i]['evidence']}"
                for c in r["conformance"]
            )
            + " |"
        )
    tr = r["tool_requests"]
    out.append(
        f"\nSecond solution on the same blueprint (special tool requests): {tr['correct']} of {tr['requests']} "
        "decisions as expected."
    )
    return "\n".join(out) + "\n"


def readme_block(r: dict) -> str:
    h = r["heldout"] or r["dev"]
    f, p = h["configs"]["full"], h["configs"]["prototype"]
    which = "Held-out change requests (40, run once)" if r["heldout"] else "Development change requests"
    lines = [
        START,
        "",
        f"{which}, each analysed {r['repeats']} times:",
        "",
        "| | Prototype | Full design |",
        "|---|---|---|",
        f"| Approved although the crash target is exceeded | {p['safety_misses']} of {p['runs']} | "
        f"**{f['safety_misses']} of {f['runs']}** |",
        f"| Correct where the system decided | {_pct(p['accuracy_decided']['value'])} | "
        f"**{_pct(f['accuracy_decided']['value'])}** ({_pct(f['accuracy_decided']['ci'][0])}–"
        f"{_pct(f['accuracy_decided']['ci'][1])}) |",
        f"| Sent to a full crash simulation | {_pct(p['deferral_rate']['value'])} | "
        f"**{_pct(f['deferral_rate']['value'])}** |",
        f"| Reports with a figure that has no source | {p['reports_with_unsupported_figures']} | "
        f"**{f['reports_with_unsupported_figures']}** |",
        f"| Reports repeating an instruction from an attachment | {p['injection_in_summary']} | "
        f"**{f['injection_in_summary']}** |",
        f"| Affected variants found / special tools found | {_pct(p['variant_recall']['value'])} / "
        f"{_pct(p['tool_recall']['value'])} | **{_pct(f['variant_recall']['value'])} / "
        f"{_pct(f['tool_recall']['value'])}** |",
        f"| p95 latency, model cost per request | {p['p95_latency_ms'] / 1000:.1f} s, "
        f"€{p['cost_per_request_eur']:.3f} | **{f['p95_latency_ms'] / 1000:.1f} s, "
        f"€{f['cost_per_request_eur']:.3f}** |",
        "",
        "What each control buys (held-out, change against the full design):"
        if r["heldout"]
        else "What each control buys:",
        "",
        "| Taken away | Approved although failing | Correct where decided | Sent to simulation |",
        "|---|---|---|---|",
    ]
    for n, m in h["configs"].items():
        if n in ("full", "prototype"):
            continue
        lines.append(
            f"| {n} | {m['safety_misses']} | {_pct(m['accuracy_decided']['value'])} | "
            f"{_pct(m['deferral_rate']['value'])} |"
        )
    conf = r["conformance"]
    lines += [
        "",
        "Architecture standards: "
        + ", ".join(f"{c['solution']} {c['passed']}/{c['total']}" for c in conf)
        + ". Full tables: [reports/RESULTS.md](reports/RESULTS.md).",
        "",
        END,
    ]
    return "\n".join(lines)


def write() -> str:
    r = build()
    (REPORTS / "results.json").write_text(json.dumps(r, indent=1) + "\n")
    (REPORTS / "RESULTS.md").write_text(markdown(r))
    readme = ROOT / "README.md"
    if readme.exists() and START in readme.read_text():
        head, rest = readme.read_text().split(START, 1)
        readme.write_text(head + readme_block(r) + rest.split(END, 1)[1])
    web = ROOT / "web" / "public" / "data"
    if (ROOT / "web").exists():
        web.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPORTS / "results.json", web / "results.json")
        if (REPORTS / "runs").exists():
            shutil.copytree(REPORTS / "runs", web / "runs", dirs_exist_ok=True)
    return "wrote reports/results.json and reports/RESULTS.md"
