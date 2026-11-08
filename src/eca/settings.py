"""Settings from config/eca.toml, loaded strictly: a typo fails at start-up, not in a customer workshop."""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Run(Strict):
    seed: int
    repeats: int


class World(Strict):
    seed: int
    heldout_seed: int
    historical_simulations: int
    dev_requests: int
    heldout_requests: int
    injected_share: float


class LLM(Strict):
    latency_ms: float
    latency_spread: float
    ms_per_1k_in: float
    price_in: float
    price_out: float
    misread_number: float
    wrong_part: float
    missed_scope: float
    hallucinate_number: float
    follow_injection: float
    misjudge: float
    recover: float


class Tokens(Strict):
    system: int
    per_tool_schema: int
    per_observation: int
    summary: int
    action: int
    tokens_per_word: float


class Tools(Strict):
    latency_ms: float
    latency_spread: float
    fe_simulation_hours: float


class Lim(Strict):
    model_version_prefix: str
    n_estimators: int
    max_depth: int
    learning_rate: float
    quantiles: list[float]
    calibration_share: float
    test_share: float
    alpha: float
    promote_min_coverage: float
    promote_max_mape: float
    thickness_range_margin: float


class Retrieval(Strict):
    k: int
    rrf_k: int
    bm25_k1: float
    bm25_b: float


class Guard(Strict):
    patterns: list[str]


class Policy(Strict):
    schedule_weeks: int
    transfer_cost_share: float
    transfer_weeks: int


class Approval(Strict):
    crash_relevant: list[str]
    other: list[str]


class Value(Strict):
    manual_base_hours: float
    manual_per_variant: float
    manual_per_tool: float
    manual_per_regulation: float
    review_hours: float


class Eval(Strict):
    bootstrap: int
    alpha: float


class Gateway(Strict):
    base_url: str
    model: str
    timeout_s: float


class Config(Strict):
    """One way to build the solution. Each switch is an architecture decision with a measured effect."""

    decides: Literal["code", "model"]  # who turns the specialists' findings into a recommendation
    gate: Literal["conformal", "point"]  # the crash model's interval, or its point prediction
    ood_check: bool  # inputs outside the model's training data go to a full simulation
    reviewer: bool  # every figure in the summary must trace to a tool output
    guard: bool  # instruction-like sentences in attachments and documents are removed
    retrieval: Literal["hybrid", "bm25"]
    current_only: bool  # superseded documents are filtered out by metadata
    validate_extraction: bool  # the extracted change is checked against the PLM before use


class Settings(Strict):
    run: Run
    world: World
    llm: LLM
    tokens: Tokens
    tools: Tools
    lim: Lim
    retrieval: Retrieval
    guard: Guard
    policy: Policy
    approval: Approval
    value: Value
    eval: Eval
    gateway: Gateway
    configs: dict[str, Config]
    ablations: dict[str, dict[str, str | bool]]


@lru_cache
def load(path: Path | None = None) -> Settings:
    with open(path or ROOT / "config" / "eca.toml", "rb") as f:
        return Settings.model_validate(tomllib.load(f))
