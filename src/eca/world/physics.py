"""The truth of the synthetic world: how a structural part behaves in a crash load case. Only the world generator
and the evaluation import this module. The agents see a learned model of it (the LIM), never the formula."""

from __future__ import annotations

# Intrusion in mm at the reference design (1.5 mm, 700 MPa, 1,850 kg vehicle, no reinforcement). Invented values.
BASE_MM = {"side_pole": 108.0, "side_mdb": 92.0, "frontal_odb": 135.0, "frontal_full": 78.0, "rear": 58.0,
           "roof": 66.0}
CLASS_FACTOR = {"cold_formed_steel": 1.0, "press_hardened": 0.97, "aluminium": 1.08}


def intrusion_mm(load_case: str, thickness_mm: float, yield_mpa: float, mass_kg: float, reinforced: bool,
                 material_class: str, geometry: float = 1.0) -> float:
    return (BASE_MM[load_case] * (1.5 / thickness_mm) ** 1.6 * (700.0 / yield_mpa) ** 0.75
            * (mass_kg / 1850.0) ** 0.9 * (0.86 if reinforced else 1.0) * CLASS_FACTOR[material_class] * geometry)
