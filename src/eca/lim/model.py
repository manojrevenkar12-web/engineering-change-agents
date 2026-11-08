"""A stand-in for a Large Industry Model: a surrogate of crash simulation trained on historical runs. It returns a
conformalised interval (CQR) and says when an input lies outside what it was trained on."""

from __future__ import annotations

import json
import pickle
from dataclasses import dataclass

import numpy as np

LOAD_CASES = ["side_pole", "side_mdb", "frontal_odb", "frontal_full", "rear", "roof"]
CLASSES = ["cold_formed_steel", "press_hardened", "aluminium"]


def features(
    load_case: str, thickness_mm: float, yield_mpa: float, mass_kg: float, reinforced: bool, material_class: str
) -> list[float]:
    """Physically shaped features: the model learns exponents, not raw magnitudes."""
    return (
        [np.log(thickness_mm), np.log(yield_mpa), np.log(mass_kg), float(reinforced)]
        + [float(load_case == lc) for lc in LOAD_CASES]
        + [float(material_class == c) for c in CLASSES]
    )


@dataclass
class Prediction:
    intrusion_mm: float
    low_mm: float
    high_mm: float
    in_distribution: bool
    reasons: list[str]
    model_version: str


class CrashSurrogate:
    def __init__(self, point, low, high, q_hat: float, envelope: dict, version: str):
        self.point, self.low, self.high, self.q_hat = point, low, high, q_hat
        self.envelope, self.version = envelope, version

    def predict(
        self,
        load_case: str,
        thickness_mm: float,
        yield_mpa: float,
        mass_kg: float,
        reinforced: bool,
        material_class: str,
        material_id: str,
    ) -> Prediction:
        x = np.asarray([features(load_case, thickness_mm, yield_mpa, mass_kg, reinforced, material_class)])
        # the models learn log intrusion; intervals are conformalised in log space
        y = float(np.exp(self.point.predict(x)[0]))
        lo = float(np.exp(self.low.predict(x)[0] - self.q_hat))
        hi = float(np.exp(self.high.predict(x)[0] + self.q_hat))
        reasons = []
        env = self.envelope
        if not env["thickness_mm"][0] <= thickness_mm <= env["thickness_mm"][1]:
            reasons.append(f"thickness {thickness_mm} mm outside trained range {env['thickness_mm']}")
        if not env["mass_kg"][0] <= mass_kg <= env["mass_kg"][1]:
            reasons.append(f"vehicle mass {mass_kg} kg outside trained range {env['mass_kg']}")
        if material_id not in env["materials"]:
            reasons.append(f"material {material_id} not in the training data")
        return Prediction(round(y, 2), round(min(lo, y), 2), round(max(hi, y), 2), not reasons, reasons, self.version)

    def save(self, path) -> None:
        path.write_bytes(pickle.dumps(self))

    @staticmethod
    def load(path) -> CrashSurrogate:
        return pickle.loads(path.read_bytes())


def card(path) -> dict:
    return json.loads(path.read_text())
