#!/usr/bin/env python3
"""
regions.py — data-driven region registry (replaces the Rust `enum Country`).

The whole engine is region-parameterised through this one table, so adding Canada
(or any region) is a registry entry, not a code fork. Each region supplies the data
the pipeline needs to regionalise: which background grid/process location to prefer,
the AWARE water-scarcity factor, IPCC climate-zone parameters for on-farm emissions,
default LCIA method, and currency.

`location_prefer` is a ranked list of ecoinvent/store location strings the matcher
should favour when choosing a background process (e.g. Canadian grid for a Canadian
farm), falling back to Rest-of-World / Global.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Region:
    code: str
    name: str
    currency: str
    climate_zone: str                     # IPCC climate zone (drives on-farm EF selection)
    ipcc_n2o_ef1: float                   # IPCC 2019 direct N2O EF1 (kg N2O-N / kg N)
    aware_country: str                    # key into the AWARE water-scarcity CFs
    default_method: str                   # LCIA method name in the canonical store
    location_prefer: tuple = ()           # ranked store/ecoinvent locations for backgrounds
    # Official national grid climate factor (kg CO2e/kWh), where an authoritative national
    # figure exists. See engine/recommend/reference/ghana_grid_ef.json for provenance. The
    # ecoinvent GH low-voltage market characterises to ~0.16 kg CO2e/kWh, understating the
    # official 2024 figure of 0.35 by ~2.2x: ecoinvent 3.11's underlying GH grid-mix data is
    # a hydro-dominant vintage, whereas Ghana's actual 2024 mix is 61% thermal / 39% hydro,
    # which computes to ~0.35 at low voltage. engine/grid_calibration.py APPLIES this at the
    # inventory level (climate-only) for electricity inputs; toggle USE_OFFICIAL_GRID_EF.
    grid_ef_kgco2_per_kwh: float | None = None


# IPCC 2019 Refinement, Vol 4 Ch 11: EF1 disaggregated by climate.
#   wet climates 0.016, dry 0.005 (kg N2O-N per kg N). Aggregate default 0.010.
REGIONS: dict[str, Region] = {
    "GH": Region(
        code="GH", name="Ghana", currency="GHS",
        climate_zone="wet tropical", ipcc_n2o_ef1=0.016,
        aware_country="Ghana", default_method="ReCiPe 2016 v1.03, midpoint (H)",
        location_prefer=("GH", "Ghana", "WA", "RAF", "Rest of World", "RoW", "GLO"),
        grid_ef_kgco2_per_kwh=0.35,  # Energy Commission of Ghana, 2025 Energy Statistics, Table 6.3 (2024)
    ),
    "NG": Region(
        code="NG", name="Nigeria", currency="NGN",
        climate_zone="wet/dry tropical", ipcc_n2o_ef1=0.016,
        aware_country="Nigeria", default_method="ReCiPe 2016 v1.03, midpoint (H)",
        location_prefer=("NG", "Nigeria", "WA", "RAF", "Rest of World", "RoW", "GLO"),
    ),
    "CA": Region(
        code="CA", name="Canada", currency="CAD",
        climate_zone="cool temperate", ipcc_n2o_ef1=0.010,  # temperate ≈ aggregate default
        aware_country="Canada", default_method="EF v3.1",
        location_prefer=("CA", "Canada", "CA-QC", "CA-ON", "US", "RNA",
                         "Rest of World", "RoW", "GLO"),
    ),
}

ALIASES = {
    "ghana": "GH", "gh": "GH", "nigeria": "NG", "ng": "NG",
    "canada": "CA", "ca": "CA", "can": "CA",
}


def get_region(code_or_name: str) -> Region:
    if not code_or_name:
        raise KeyError("region required")
    key = code_or_name.strip()
    if key.upper() in REGIONS:
        return REGIONS[key.upper()]
    a = ALIASES.get(key.lower())
    if a:
        return REGIONS[a]
    raise KeyError(f"unknown region '{code_or_name}'. Known: {', '.join(REGIONS)}")


def location_rank(region: Region, location: str | None) -> int:
    """Lower is better. Rank a background process's location against the region's
    preference list; unknown locations sort last."""
    loc = (location or "").strip()
    for i, pref in enumerate(region.location_prefer):
        if loc == pref or (pref and pref in loc):
            return i
    return len(region.location_prefer) + 1


if __name__ == "__main__":
    for r in REGIONS.values():
        print(f"{r.code}: {r.name:<8} zone={r.climate_zone:<16} EF1={r.ipcc_n2o_ef1} "
              f"AWARE={r.aware_country:<8} method={r.default_method}")
