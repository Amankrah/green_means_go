#!/usr/bin/env python3
"""
heavy_metals.py: heavy-metal (cadmium) input from mineral phosphate fertiliser, SALCA-SM
(Freiermuth 2006, Agroscope; ecoinvent report No. 15, Nemecek & Kägi 2007) -- DISCLOSURE ONLY.

SALCA-SM books the net heavy-metal balance of a field (inputs from fertiliser, seed,
deposition minus outputs with the harvest, leaching and erosion). Its driving input here
would be the Cd content of the phosphate fertilisers actually used. No defensible Cd content
is available for the fertilisers sold in the served markets (it varies by an order of
magnitude with the phosphate-rock origin), so no Cd flow is booked.

What is reported instead, for transparency, is the Cd applied at the EU regulatory limit
for inorganic fertilisers, 60 mg Cd per kg P2O5 (Regulation (EU) 2019/1009, Annex I, Part
II, PFC 1(C)(I)), alongside the range of the sedimentary rocks supplying the region. The EU
limit is NOT an upper bound here: it binds only EU-marketed products, and West African rock
exceeds it (Togo 147-179, Senegal Taiba 165-221 mg Cd/kg P2O5; Morocco, most regional
supply, 17-121; OPERA Research (2021) after Davister 1996, Botschek & Van Balken 1999,
Demandt 1999). Neither figure is an emission.
"""
from __future__ import annotations

try:
    from . import phosphorus as _p
except ImportError:  # script use
    import phosphorus as _p  # type: ignore

EU_CD_LIMIT_MG_PER_KG_P2O5 = 60.0   # Regulation (EU) 2019/1009 Annex I PFC 1(C)(I)
SRC_EU_LIMIT = "Regulation (EU) 2019/1009, Annex I, PFC 1(C)(I): 60 mg Cd/kg P2O5"
# Sedimentary phosphate rocks supplying West Africa (Morocco low end to Senegal Taiba high end)
REGIONAL_CD_RANGE_MG_PER_KG_P2O5 = (17.0, 221.0)
SRC_REGIONAL_CD = ("OPERA Research (2021) Cadmium limits in phosphorous fertilizers, table after "
                   "Davister 1996, Botschek & Van Balken 1999, Demandt 1999: Morocco 17-121, Togo "
                   "147-179, Senegal Taiba 165-221 mg Cd/kg P2O5")


def cadmium_disclosure(assessment: dict) -> tuple[dict, list[str]]:
    """({'mineral_p2o5_kg', 'cd_at_eu_limit_g', 'cd_regional_range_g', 'booked': False}, notes)."""
    per_crop, _ = _p.p2o5_by_crop(assessment)
    foods = assessment.get("foods") or []
    p2o5 = sum(per_crop[i]["min"] * float(f.get("area_allocated") or 0.0)
               for i, f in enumerate(foods))
    lo, hi = REGIONAL_CD_RANGE_MG_PER_KG_P2O5
    rec = {"mineral_p2o5_kg": p2o5, "booked": False,
           "cd_at_eu_limit_g": p2o5 * EU_CD_LIMIT_MG_PER_KG_P2O5 / 1000.0,
           "cd_regional_range_g": [p2o5 * lo / 1000.0, p2o5 * hi / 1000.0]}
    if p2o5 <= 0:
        return rec, []
    rlo, rhi = rec["cd_regional_range_g"]
    return rec, [
        f"heavy metals (SALCA-SM) not modelled: the cadmium content of the phosphate fertilisers "
        f"used is unknown and depends on the rock origin. For context, {p2o5:.0f} kg P2O5 of "
        f"mineral fertiliser carries {rlo:.1f}-{rhi:.1f} g Cd/yr across the rocks supplying the "
        f"region ({SRC_REGIONAL_CD}); {rec['cd_at_eu_limit_g']:.1f} g Cd/yr at the EU limit "
        f"({SRC_EU_LIMIT}), which local products may exceed. Not booked as an emission, so "
        "toxicity categories exclude fertiliser Cd"]
