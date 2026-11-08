"""eca lim-train | develop | heldout | report | analyse | conformance | serve"""

from __future__ import annotations

import argparse
import asyncio
import json
import random


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="eca")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("lim-train", help="train, calibrate and register the crash surrogate; promote if the gates pass")
    sub.add_parser("develop", help="every configuration and ablation on the development change requests")
    h = sub.add_parser("heldout", help="the pinned held-out change requests, once")
    h.add_argument("--again", action="store_true")
    sub.add_parser("report", help="reports/results.json, reports/RESULTS.md, the README block, the dashboard data")
    a = sub.add_parser("analyse", help="analyse one change request with the full design")
    a.add_argument("text")
    a.add_argument("--attachment", default="")
    sub.add_parser("conformance", help="check every solution against the architecture standards")
    sub.add_parser("serve", help="the API on :8000")
    args = p.parse_args(argv)

    if args.cmd == "lim-train":
        from eca.lim.train import train

        print(json.dumps(train(), indent=1))
    elif args.cmd == "develop":
        from eca.experiments import develop

        f = develop()["configs"]["full"]
        print(
            f"full design: {f['safety_misses']} safety misses, "
            f"{f['accuracy_decided']['value']:.3f} correct where decided"
        )
    elif args.cmd == "heldout":
        from eca.experiments import run_heldout

        f = run_heldout(again=args.again)["configs"]["full"]
        print(
            f"held out: {f['safety_misses']} safety misses, {f['accuracy_decided']['value']:.3f} correct where decided"
        )
    elif args.cmd == "report":
        from eca.report import write

        print(write())
    elif args.cmd == "analyse":
        from eca.blueprint.toolbox import Toolbox
        from eca.engine import servers
        from eca.guard import Guard
        from eca.llm import SimModel
        from eca.settings import load
        from eca.solutions.engineering_change import EngineeringChange, Run

        s = load()
        cfg = s.configs["full"]

        async def go():
            async with Toolbox(servers(), s, random.Random(0)) as tb:
                run = Run(s, cfg, tb, SimModel(s, random.Random(0)), Guard(s, cfg.guard))
                return await EngineeringChange(s, cfg).analyse(
                    run, {"id": "CLI-1", "text": args.text, "attachment": args.attachment}
                )

        rep = asyncio.run(go())
        print(rep["summary"])
        print(
            json.dumps({k: rep[k] for k in ("recommendation", "variants", "tools", "regulations", "flags")}, indent=1)
        )
    elif args.cmd == "conformance":
        from eca.conformance import report

        for sol in report():
            print(f"{sol['solution']}: {sol['passed']}/{sol['total']}")
            for c in sol["checks"]:
                print(f"  {'pass' if c['pass'] else 'FAIL'} {c['id']} {c['evidence']}")
    elif args.cmd == "serve":
        import uvicorn

        uvicorn.run("eca.api:app", port=8000)


if __name__ == "__main__":
    main()
