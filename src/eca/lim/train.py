"""MLOps for the crash surrogate: train, calibrate, test, register, and promote only if the gates pass.

    eca lim-train

Writes models/<version>.pkl and models/registry.json (model cards: data hash, metrics, decision)."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor

from eca.lim.model import CrashSurrogate, features
from eca.settings import ROOT, Settings, load

DATA = ROOT / "data" / "historical_simulations.csv"
MODELS = ROOT / "models"


def _rows() -> list[dict]:
    with DATA.open() as f:
        return list(csv.DictReader(f))


def _matrix(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(
        [
            features(
                r["load_case"],
                float(r["thickness_mm"]),
                float(r["yield_mpa"]),
                float(r["mass_kg"]),
                r["reinforced"] == "1",
                r["material_class"],
            )
            for r in rows
        ]
    )
    y = np.log(np.asarray([float(r["intrusion_mm"]) for r in rows]))
    return x, y


def train(s: Settings | None = None) -> dict:
    s = s or load()
    cfg = s.lim
    rows = _rows()
    data_hash = hashlib.sha256(DATA.read_bytes()).hexdigest()
    rng = np.random.default_rng(s.run.seed)
    idx = rng.permutation(len(rows))
    n_test, n_cal = int(len(rows) * cfg.test_share), int(len(rows) * cfg.calibration_share)
    test, cal, fit = idx[:n_test], idx[n_test : n_test + n_cal], idx[n_test + n_cal :]
    x, y = _matrix(rows)

    def gbr(**kw):
        return GradientBoostingRegressor(
            n_estimators=cfg.n_estimators,
            max_depth=cfg.max_depth,
            learning_rate=cfg.learning_rate,
            random_state=s.run.seed,
            **kw,
        ).fit(x[fit], y[fit])

    point = gbr()
    low = gbr(loss="quantile", alpha=cfg.quantiles[0])
    high = gbr(loss="quantile", alpha=cfg.quantiles[1])
    # conformalised quantile regression: widen by the calibration set's conformity score quantile
    scores = np.maximum(low.predict(x[cal]) - y[cal], y[cal] - high.predict(x[cal]))
    level = min(1.0, np.ceil((len(cal) + 1) * (1 - cfg.alpha)) / len(cal))
    q_hat = float(np.quantile(scores, level, method="higher"))

    lo, hi = np.exp(low.predict(x[test]) - q_hat), np.exp(high.predict(x[test]) + q_hat)
    actual, pred = np.exp(y[test]), np.exp(point.predict(x[test]))
    coverage = float(np.mean((actual >= lo) & (actual <= hi)))
    mae = float(np.mean(np.abs(pred - actual)))
    mape = float(np.mean(np.abs(pred - actual) / actual))
    rel_width = float(np.median((hi - lo) / actual))
    width = float(np.median(hi - lo))
    thick = [float(r["thickness_mm"]) for r in rows]
    mass = [float(r["mass_kg"]) for r in rows]
    from eca.servers.plm import materials_by_yield  # the materials seen in training, by their properties

    seen = sorted({materials_by_yield(float(r["yield_mpa"]), r["material_class"]) for r in rows} - {None})
    envelope = {
        "thickness_mm": [min(thick) - cfg.thickness_range_margin, max(thick) + cfg.thickness_range_margin],
        "mass_kg": [round(min(mass)), round(max(mass))],
        "materials": seen,
    }
    version = f"{cfg.model_version_prefix}-{data_hash[:8]}"
    promoted = coverage >= cfg.promote_min_coverage and mape <= cfg.promote_max_mape
    MODELS.mkdir(exist_ok=True)
    CrashSurrogate(point, low, high, q_hat, envelope, version).save(MODELS / f"{version}.pkl")
    model_card = {
        "version": version,
        "trained_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "data_sha256": data_hash,
        "rows": {"fit": len(fit), "calibration": len(cal), "test": len(test)},
        "target_coverage": 1 - cfg.alpha,
        "test_coverage": round(coverage, 4),
        "test_mae_mm": round(mae, 3),
        "test_mape": round(mape, 4),
        "median_interval_mm": round(width, 2),
        "median_relative_interval": round(rel_width, 4),
        "q_hat_log": round(q_hat, 5),
        "envelope": envelope,
        "promoted": promoted,
        "gates": {"min_coverage": cfg.promote_min_coverage, "max_mape": cfg.promote_max_mape},
    }
    registry_path = MODELS / "registry.json"
    registry = json.loads(registry_path.read_text()) if registry_path.exists() else {"models": [], "production": None}
    registry["models"] = [m for m in registry["models"] if m["version"] != version] + [model_card]
    if promoted:
        registry["production"] = version
    registry_path.write_text(json.dumps(registry, indent=1) + "\n")
    return model_card


def production() -> CrashSurrogate:
    registry = json.loads((MODELS / "registry.json").read_text())
    version = registry["production"]
    if not version:
        raise RuntimeError("no crash surrogate has passed the promotion gates")
    path = MODELS / f"{version}.pkl"
    if not path.exists():
        train()
    return CrashSurrogate.load(path)
