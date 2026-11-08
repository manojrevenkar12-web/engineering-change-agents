"""The agents never see the truth, and the held-out set stays pinned and runs once."""

import ast
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from eca import experiments, heldout
from eca.settings import ROOT, Config, load

SRC = ROOT / "src" / "eca"
AGENT_SIDE = [
    *(SRC / "solutions").glob("*.py"),
    *(SRC / "blueprint").glob("*.py"),
    *(SRC / "servers").glob("*.py"),
    *(SRC / "lim").glob("*.py"),
    SRC / "llm.py",
    SRC / "guard.py",
    SRC / "retrieval.py",
    SRC / "engine.py",
]


def test_agent_side_never_reads_the_truth():
    for f in AGENT_SIDE:
        text = f.read_text()
        tree = ast.parse(text)
        mods = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        assert not mods & {"eca.world.physics", "eca.evaluate", "eca.experiments"}, f.name
        assert "truth" not in text.replace("truth_like", ""), f.name


def test_the_world_is_reproducible_and_pinned():
    assert heldout.fingerprint() == heldout.pinned()
    rows = [json.loads(x) for x in (ROOT / "data/requests_heldout.jsonl").read_text().splitlines()]
    assert len(rows) == load().world.heldout_requests and all(
        set(r) == {"id", "text", "attachment", "submitted_by"} for r in rows
    )


def test_requests_carry_no_answers():
    for name in ("dev", "heldout"):
        for line in (ROOT / f"data/requests_{name}.jsonl").read_text().splitlines():
            r = json.loads(line)
            assert not {"recommendation", "intrusion_mm", "tools"} & set(r)


def test_settings_are_strict(s):
    data = s.configs["full"].model_dump() | {"gate": "vibes"}
    with pytest.raises(ValidationError):
        Config.model_validate(data)
    assert set(s.ablations) and all(set(o) <= set(Config.model_fields) for o in s.ablations.values())


def test_the_heldout_runs_once(tmp_path, monkeypatch):
    monkeypatch.setattr(experiments, "REPORTS", tmp_path)
    (tmp_path / "heldout-runs.log").write_text("2026-11-08 x safety_misses=0\n")
    with pytest.raises(RuntimeError, match="already run"):
        experiments.run_heldout()


def test_a_changed_heldout_is_refused(monkeypatch):
    monkeypatch.setattr(heldout, "pinned", lambda: "0" * 64)
    with pytest.raises(RuntimeError, match="changed"):
        heldout.check()


def test_no_example_code_is_imported_by_the_package():
    for f in SRC.rglob("*.py"):
        assert "nonconformant_assistant" not in f.read_text() or f.name == "conformance.py", f
    assert Path(ROOT / "examples/nonconformant_assistant.py").exists()
