#!/usr/bin/env python3
"""
heavy_metals.py: heavy-metal (cadmium) input from mineral phosphate fertiliser, SALCA-SM
(Freiermuth 2006, Agroscope; ecoinvent report No. 15, Nemecek & Kägi 2007) -- DISCLOSURE ONLY.

SALCA-SM books the net heavy-metal balance of a field (inputs from fertiliser, seed,
deposition minus outputs with the harvest, leaching and erosion). Its driving input here
would be the Cd content of the phosphate fertilisers actually used. No defensible Cd content
is available for the fertilisers sold in the served markets (it varies by an order of
magnitude with the phosphate-rock origin), so no Cd flow is booked.

What is reported instead, for transparency, is an UPPER BOUND on the Cd applied, using the
EU regulatory limit for inorganic fertilisers: 60 mg Cd per kg P2O5 (Regulation (EU)
2019/1009, Annex I, Part II, PFC 1(C)(I), contaminant limits). That is a legal ceiling for
EU-marketed products, not an average content, and is not an emission.
"""
from __future__ import annotations

try:
    from . import phosphorus as _p
except ImportError:  # script use
    import phosphorus as _p  # type: ignore

EU_CD_LIMIT_MG_PER_KG_P2O5 = 60.0   # Regulation (EU) 2019/1009 Annex I PFC 1(C)(I)
SRC_EU_LIMIT = "Regulation (EU) 2019/1009, Annex I, PFC 1(C)(I): 60 mg Cd/kg P2O5"


def cadmium_disclosure(assessment: dict) -> tuple[dict, list[str]]:
    """({'mineral_p2o5_kg', 'cd_upper_bound_g', 'booked': False}, notes)."""
    per_crop, _ = _p.p2o5_by_crop(assessment)
    foods = assessment.get("foods") or []
    p2o5 = sum(per_crop[i]["min"] * float(f.get("area_allocated") or 0.0)
               for i, f in enumerate(foods))
    rec = {"mineral_p2o5_kg": p2o5, "booked": False,
           "cd_upper_bound_g": p2o5 * EU_CD_LIMIT_MG_PER_KG_P2O5 / 1000.0}
    if p2o5 <= 0:
        return rec, []
    return rec, [
        f"heavy metals (SALCA-SM) not modelled: no defensible cadmium content for the phosphate "
        f"fertilisers used. For context, {p2o5:.0f} kg P2O5 of mineral fertiliser at the EU limit "
        f"would carry at most {rec['cd_upper_bound_g']:.1f} g Cd/yr ({SRC_EU_LIMIT}); "
        "not booked as an emission, so toxicity categories exclude fertiliser Cd"]
