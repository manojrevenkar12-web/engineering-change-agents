"""The crash surrogate: promoted only through its gates, calibrated, and honest about what it has not seen."""

import json

from eca.lim.train import MODELS, production


def test_the_production_model_passed_its_gates(s):
    reg = json.loads((MODELS / "registry.json").read_text())
    card = next(m for m in reg["models"] if m["version"] == reg["production"])
    assert card["promoted"] and card["test_coverage"] >= s.lim.promote_min_coverage
    assert card["test_mape"] <= s.lim.promote_max_mape
    assert card["data_sha256"] and card["rows"]["calibration"] > 0


def test_intervals_contain_the_prediction(s):
    m = production()
    p = m.predict("side_pole", 1.6, 1100, 1890, True, "press_hardened", "22MnB5")
    assert p.low_mm <= p.intrusion_mm <= p.high_mm and p.in_distribution


def test_thinner_is_worse(s):
    m = production()
    thick = m.predict("frontal_odb", 2.0, 700, 1850, False, "cold_formed_steel", "CR700Y980T-CP")
    thin = m.predict("frontal_odb", 1.4, 700, 1850, False, "cold_formed_steel", "CR700Y980T-CP")
    assert thin.intrusion_mm > thick.intrusion_mm


def test_unseen_inputs_are_flagged(s):
    m = production()
    new_material = m.predict("side_pole", 1.5, 1180, 1850, False, "cold_formed_steel", "CR1180Y1500T-MS")
    too_thin = m.predict("side_pole", 0.6, 700, 1850, False, "cold_formed_steel", "CR700Y980T-CP")
    assert not new_material.in_distribution and "not in the training data" in new_material.reasons[0]
    assert not too_thin.in_distribution and "thickness" in too_thin.reasons[0]
