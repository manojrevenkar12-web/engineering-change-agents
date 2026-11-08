import asyncio
import random

import pytest

from eca.blueprint.toolbox import Toolbox
from eca.engine import servers
from eca.guard import Guard
from eca.lim.train import MODELS, production, train
from eca.llm import SimModel
from eca.settings import load
from eca.solutions.engineering_change import EngineeringChange, Run

PERFECT = {
    "misread_number": 0.0,
    "wrong_part": 0.0,
    "missed_scope": 0.0,
    "hallucinate_number": 0.0,
    "follow_injection": 0.0,
    "misjudge": 0.0,
    "recover": 1.0,
}


@pytest.fixture(scope="session")
def s():
    if not (MODELS / "registry.json").exists():
        train()
    production()
    return load()


def settings_with(s, **rates):
    return s.model_copy(update={"llm": s.llm.model_copy(update=PERFECT | rates)})


def analyse(s, text, attachment="", config="full", seed=1, **cfg_overrides):
    cfg = s.configs[config].model_copy(update=cfg_overrides)

    async def go():
        async with Toolbox(servers(), s, random.Random(seed)) as tb:
            run = Run(s, cfg, tb, SimModel(s, random.Random(seed)), Guard(s, cfg.guard))
            return await EngineeringChange(s, cfg).analyse(run, {"id": "T-1", "text": text, "attachment": attachment})

    return asyncio.run(go())
