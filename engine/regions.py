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

Climate-dependent IPCC parameters (IPCC 2019 Refinement, Vol 4, Ch 11; values checked
against the published chapter text, Tables 11.1 and 11.3, "UPDATED"):

  EF1 (direct N2O, kg N2O-N / kg N), Table 11.1:
      aggregated 0.010 (0.002-0.018); synthetic N in wet climates 0.016 (0.013-0.019);
      other N inputs in wet climates 0.006; ALL N inputs in dry climates 0.005 (0.000-0.011).
  EF4 (volatilised and re-deposited N), Table 11.3:
      aggregated 0.010 (0.002-0.018); wet 0.014 (0.011-0.017); dry 0.005 (0.000-0.011).
  EF5 (leaching/runoff), Table 11.3: 0.011 (0.000-0.020), not climate-disaggregated.
  FracGASF (synthetic N volatilised), Table 11.3: aggregated 0.11 (0.02-0.33); by type
      urea 0.15, ammonium-based 0.08, nitrate-based 0.01, ammonium-nitrate-based 0.05.
  FracGASM (organic N / dung and urine volatilised), Table 11.3: 0.21 (0.00-0.31).
  FracLEACH-(H), Table 11.3: 0.24 (0.01-0.73) in wet climates; "For dry climate, the
      default FracLEACH-(H) is taken as zero", EXCEPT (Ch 11 text, p 11.25) "in dry
      climate regions where irrigation (other than drip irrigation) is used, the default
      FracLEACH-(H) is 0.24". See frac_leach_for().
  Wet vs dry (Table 11.1 footnote 4): tropical zones are wet where annual precipitation
      > 1000 mm and dry where < 1000 mm; temperate/boreal zones by P:PET > 1 or < 1.

Admin-region climate (CONTRACT §2): climate_zone_for(), rainy_season_months() and
forest_zone_for() classify a farm from study_meta.admin_region (station/regional rainfall
normals, cited per entry below); engine/service.py applies with_climate() with the result.

Fields other workstreams read via getattr (names are a contract, do not rename):
  frac_gasf, frac_gasm, frac_leach, ef4, ef5, climate_zone, ipcc_n2o_ef1,
  activity_defaults_file, yield_guide_file, grid_ef_source, ghana_inherited,
  field_sources, grid_ef_kgco2_per_kwh.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace

# --- citation strings (one per source; field_sources values point at these) ----------

_IPCC_T11_1 = "IPCC 2019 Refinement, Vol 4, Ch 11, Table 11.1 (Updated)"
_IPCC_T11_3 = "IPCC 2019 Refinement, Vol 4, Ch 11, Table 11.3 (Updated)"
_IPCC_LEACH_TEXT = ("IPCC 2019 Refinement, Vol 4, Ch 11, p 11.25 and Table 11.3 note: "
                    "FracLEACH-(H) = 0 in dry climates unless irrigated (other than drip)")
_AWARE = ("Boulay et al. 2018, AWARE (WULCA), data/AWARE2.0/"
          "AWARE_country_regions_Corrected_online_20230113-1.xlsx, sheet AWARE-annual")
_STORE_LOCATIONS = ("data/canonical/lca_engineer.sqlite processes.location strings "
                    "(queried read-only 2026-11-12)")

# IPCC 2019 Table 11.1 / 11.3 constants (see module docstring for ranges).
EF1_WET_SYNTHETIC = 0.016
EF1_DRY = 0.005
EF1_AGGREGATED = 0.010
EF4_WET = 0.014
EF4_DRY = 0.005
EF4_AGGREGATED = 0.010
EF5_DEFAULT = 0.011
FRAC_GASF_AGGREGATED = 0.11
FRAC_GASM_DEFAULT = 0.21
FRAC_LEACH_WET = 0.24
FRAC_LEACH_DRY = 0.0

# Fields whose value is a GLOBAL IPCC default (identical everywhere by construction), so
# equality with Ghana is not "inheritance". Used by the ghana_inherited audit test.
GLOBAL_DEFAULT_FIELDS = ("ef5", "frac_gasf", "frac_gasm", "default_method")


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
    # --- IPCC 2019 indirect-N2O and leaching parameters (Table 11.3) -------------------
    frac_gasf: float = FRAC_GASF_AGGREGATED   # kg (NH3-N + NOx-N) / kg synthetic N
    frac_gasm: float = FRAC_GASM_DEFAULT      # kg (NH3-N + NOx-N) / kg organic N
    frac_leach: float = FRAC_LEACH_WET        # kg N leached / kg N (rainfed basis)
    ef4: float = EF4_AGGREGATED               # kg N2O-N / kg N volatilised + re-deposited
    ef5: float = EF5_DEFAULT                  # kg N2O-N / kg N leached or run off
    # --- region data tables (filenames under engine/recommend/reference/) --------------
    activity_defaults_file: str | None = None  # same schema as ghana_farm_activity_defaults.json
    yield_guide_file: str | None = None        # national per-crop yield guide
    grid_ef_source: str | None = None          # reference JSON holding the grid EF provenance
    price_feed_file: str | None = None         # national producer-price reference
    # --- provenance --------------------------------------------------------------------
    # Fields still carrying a number copied from Ghana (not region-sourced). Surfaced in
    # the ISO report's data-quality section. Must stay empty for a fully sourced region.
    ghana_inherited: tuple = ()
    # field name -> citation a reviewer can check (author, year, table).
    field_sources: dict = field(default_factory=dict, hash=False)
    # field name -> Weidema pedigree scores (reliability, completeness, temporal,
    # geographical, technological; 1 best .. 5 worst), for engine/pedigree.py.
    field_pedigree: dict = field(default_factory=dict, hash=False)


def _ipcc_sources(wetness: str) -> dict:
    """field_sources entries for the IPCC climate parameters."""
    return {
        "ipcc_n2o_ef1": f"{_IPCC_T11_1}: EF1 {wetness}",
        "ef4": f"{_IPCC_T11_3}: EF4 {wetness}",
        "ef5": f"{_IPCC_T11_3}: EF5 (not climate-disaggregated)",
        "frac_gasf": f"{_IPCC_T11_3}: FracGASF aggregated (fertiliser-type values in table)",
        "frac_gasm": f"{_IPCC_T11_3}: FracGASM",
        "frac_leach": (f"{_IPCC_T11_3}: FracLEACH-(H) wet climate" if wetness == "wet climate"
                       else _IPCC_LEACH_TEXT if wetness == "dry climate"
                       else f"{_IPCC_T11_3}: FracLEACH-(H) aggregated"),
    }


# Pedigree of IPCC Tier 1 defaults applied to a country: reliable method, but generic.
_PED_IPCC = {"reliability": 2, "completeness": 2, "temporal": 2,
             "geographical": 3, "technological": 3}


REGIONS: dict[str, Region] = {
    "GH": Region(
        code="GH", name="Ghana", currency="GHS",
        climate_zone="wet tropical", ipcc_n2o_ef1=EF1_WET_SYNTHETIC,
        aware_country="Ghana", default_method="ReCiPe 2016 v1.03, midpoint (H)",
        location_prefer=("GH", "Ghana", "WA", "RAF", "Rest of World", "RoW", "GLO"),
        grid_ef_kgco2_per_kwh=0.35,  # Energy Commission of Ghana, 2025 Energy Statistics, Table 6.3 (2024)
        frac_leach=FRAC_LEACH_WET, ef4=EF4_WET,
        activity_defaults_file="ghana_farm_activity_defaults.json",
        yield_guide_file=None,  # yield guides are embedded in the activity-defaults rows
        grid_ef_source="ghana_grid_ef.json",
        price_feed_file=None,   # SRID CSV under data/recommendations/Tier1 (engine/recommend/prices.py)
        field_sources={
            **_ipcc_sources("wet climate"),
            "climate_zone": ("Most of Ghana's cropland is tropical moist (>1000 mm/yr); "
                             "IPCC 2019 Table 11.1 footnote 4 wet/dry criterion"),
            "aware_country": _AWARE,
            "grid_ef_kgco2_per_kwh": ("Energy Commission of Ghana (2025) Energy Statistics, "
                                      "Table 6.3, grid EF all other projects 2024 = 0.35 tCO2/MWh"),
            "location_prefer": "existing GH matcher preference (unchanged)",
        },
        field_pedigree={
            "ipcc_n2o_ef1": _PED_IPCC,
            "grid_ef_kgco2_per_kwh": {"reliability": 2, "completeness": 2, "temporal": 1,
                                      "geographical": 1, "technological": 2},
        },
    ),
    "NG": Region(
        code="NG", name="Nigeria", currency="NGN",
        # Kept wet (0.016) as the national default per the team brief. Nigeria's Sudan and
        # Sahel savanna north is DRY under the IPCC <1000 mm criterion (EF1 0.005, FracLEACH
        # 0 for rainfed); a northern farm gets with_climate(NG, "dry") from its admin region
        # (climate_zone_for, engine/service.py). The wet national default mirrors Ghana's, so
        # it is flagged in ghana_inherited.
        climate_zone="wet/dry tropical", ipcc_n2o_ef1=EF1_WET_SYNTHETIC,
        aware_country="Nigeria", default_method="ReCiPe 2016 v1.03, midpoint (H)",
        location_prefer=("NG", "Nigeria", "WA", "RAF", "Rest of World", "RoW", "GLO"),
        frac_leach=FRAC_LEACH_WET, ef4=EF4_WET,
        # Nigeria tables (FAOSTAT 2023 yields, NIAE/ABU diesel) and grid calibration
        # (Ember 2024 lifecycle intensity; no official national factor exists).
        activity_defaults_file="nigeria_farm_activity_defaults.json",
        yield_guide_file=None,  # yield guides are embedded in the activity-defaults rows
        grid_ef_kgco2_per_kwh=0.496, grid_ef_source="nigeria_grid_ef.json",
        ghana_inherited=("ipcc_n2o_ef1", "ef4", "frac_leach"),
        field_sources={
            **_ipcc_sources("wet climate"),
            "climate_zone": ("Wet assumed nationally (south and Middle Belt >1000 mm); the "
                             "dry north (<1000 mm) is under-represented, IPCC 2019 Table 11.1 fn 4"),
            "aware_country": _AWARE,
            "location_prefer": "existing NG matcher preference (unchanged)",
            "grid_ef_kgco2_per_kwh": ("Ember (2026) via Our World in Data, carbon intensity of "
                                      "electricity generation (lifecycle), Nigeria 2024 = 495.74 "
                                      "gCO2e/kWh; no official national factor exists (NERC/ECN "
                                      "publish none). See nigeria_grid_ef.json"),
        },
        field_pedigree={
            "ipcc_n2o_ef1": {**_PED_IPCC, "geographical": 4},
            # Generation-level lifecycle intensity applied at low voltage (no T&D losses):
            # technological correlation 3.
            "grid_ef_kgco2_per_kwh": {"reliability": 2, "completeness": 2, "temporal": 1,
                                      "geographical": 1, "technological": 3},
        },
    ),
    "SN": Region(
        code="SN", name="Senegal", currency="XOF",
        # Groundnut basin and Sahelian north receive ~300-800 mm/yr, so dry tropical under
        # the IPCC <1000 mm criterion. Only lower Casamance exceeds 1000 mm.
        climate_zone="dry tropical", ipcc_n2o_ef1=EF1_DRY,
        aware_country="Senegal", default_method="ReCiPe 2016 v1.03, midpoint (H)",
        # Store strings that exist: "Senegal" (11 processes incl. the SN low/medium-voltage
        # grid), "Africa" (RAF market groups), "Rest of World", "Global". "WA" does not
        # exist in the store, so it is omitted. location_rank matches exact names and
        # sub-national prefixes only, so "Africa" never matches "South Africa".
        location_prefer=("SN", "Senegal", "Africa", "RAF", "Rest of World", "RoW",
                         "Global", "GLO"),
        grid_ef_kgco2_per_kwh=0.744,
        frac_leach=FRAC_LEACH_DRY, ef4=EF4_DRY,
        activity_defaults_file="senegal_farm_activity_defaults.json",
        yield_guide_file="senegal_yield_guides.json",
        grid_ef_source="senegal_grid_ef.json",
        price_feed_file="senegal_producer_prices.json",
        field_sources={
            **_ipcc_sources("dry climate"),
            "climate_zone": ("CIAT; BFS/USAID (2016) Climate-Smart Agriculture in Senegal: "
                             "rainfed agriculture dominates; IPCC 2019 Table 11.1 fn 4 (<1000 mm = dry)"),
            "aware_country": _AWARE + " (row 'Senegal', Agg_CF_irri 80.8)",
            "location_prefer": _STORE_LOCATIONS,
            "grid_ef_kgco2_per_kwh": ("Perspectives Climate Group for GIZ PED Senegal (2021), "
                                      "Rapport final, Tableau 5: GEF OM 2018 = 0.744 tCO2e/MWh "
                                      "(CDM grid tool on the national energy balance)"),
            "currency": "ISO 4217 XOF (BCEAO CFA franc)",
        },
        field_pedigree={
            "ipcc_n2o_ef1": _PED_IPCC,
            "grid_ef_kgco2_per_kwh": {"reliability": 3, "completeness": 2, "temporal": 3,
                                      "geographical": 1, "technological": 3},
        },
    ),
    "BF": Region(
        code="BF", name="Burkina Faso", currency="XOF",
        # Sudano-Sahelian: ~300 mm (north) to ~1200 mm (south-west); the cropped centre and
        # north are below 1000 mm, so dry tropical is the national default.
        climate_zone="dry tropical", ipcc_n2o_ef1=EF1_DRY,
        aware_country="Burkina Faso", default_method="ReCiPe 2016 v1.03, midpoint (H)",
        # No "Burkina Faso" location exists in the store (queried); the matcher falls to
        # "Africa" (RAF market groups), then RoW/Global.
        location_prefer=("BF", "Burkina Faso", "Africa", "RAF", "Rest of World", "RoW",
                         "Global", "GLO"),
        grid_ef_kgco2_per_kwh=0.569,
        frac_leach=FRAC_LEACH_DRY, ef4=EF4_DRY,
        activity_defaults_file="burkina_faso_farm_activity_defaults.json",
        yield_guide_file="burkina_faso_yield_guides.json",
        grid_ef_source="burkina_faso_grid_ef.json",
        price_feed_file="burkina_faso_producer_prices.json",
        field_sources={
            **_ipcc_sources("dry climate"),
            "climate_zone": "IPCC 2019 Table 11.1 fn 4 (<1000 mm = dry); Sudano-Sahelian rainfall",
            "aware_country": _AWARE + " (row 'Burkina Faso', Agg_CF_irri 16.8)",
            "location_prefer": _STORE_LOCATIONS + "; no Burkina Faso location present",
            "grid_ef_kgco2_per_kwh": ("Nana et al. (2023) Clean Air Journal 33(2), "
                                      "doi:10.17159/caj/2023/33/2.15701: SONABEL 2018 "
                                      "generation-mix EF 0.569 kgCO2/kWh (CC BY)"),
            "currency": "ISO 4217 XOF (BCEAO CFA franc)",
        },
        field_pedigree={
            "ipcc_n2o_ef1": _PED_IPCC,
            "grid_ef_kgco2_per_kwh": {"reliability": 2, "completeness": 3, "temporal": 3,
                                      "geographical": 1, "technological": 2},
        },
    ),
    "ZA": Region(
        code="ZA", name="South Africa", currency="ZAR",
        # Default: the summer-rainfall maize belt (Free State, North West, Mpumalanga
        # Highveld) is warm temperate with P:PET < 1, i.e. IPCC DRY. KwaZulu-Natal and the
        # Eastern Cape coast are wet; override per farm with with_climate(ZA, "wet").
        climate_zone="warm temperate dry", ipcc_n2o_ef1=EF1_DRY,
        aware_country="South Africa", default_method="ReCiPe 2016 v1.03, midpoint (H)",
        # "South Africa" has 333 processes in the store (incl. ZA high/medium/low voltage).
        location_prefer=("ZA", "South Africa", "Africa", "RAF", "Rest of World", "RoW",
                         "Global", "GLO"),
        grid_ef_kgco2_per_kwh=1.04,
        frac_leach=FRAC_LEACH_DRY, ef4=EF4_DRY,
        activity_defaults_file="south_africa_farm_activity_defaults.json",
        yield_guide_file="south_africa_yield_guides.json",
        grid_ef_source="south_africa_grid_ef.json",
        price_feed_file="south_africa_producer_prices.json",
        field_sources={
            **_ipcc_sources("dry climate"),
            "climate_zone": ("IPCC 2019 Table 11.1 fn 4: temperate zones are dry where P:PET < 1, "
                             "true of the Highveld maize belt; override with with_climate()"),
            "aware_country": _AWARE + " (row 'South Africa', Agg_CF_irri 40.8)",
            "location_prefer": _STORE_LOCATIONS,
            "grid_ef_kgco2_per_kwh": ("Eskom Holdings (2024) Integrated Report, p 122, "
                                      "'Environmental implications of using or saving electricity', "
                                      "Factor 1: 190.4 Mt CO2 / 183 311 GWh sales = 1.04 t/MWh (FY2023/24)"),
            "currency": "ISO 4217 ZAR",
        },
        field_pedigree={
            "ipcc_n2o_ef1": {**_PED_IPCC, "geographical": 4},  # province-variable climate
            "grid_ef_kgco2_per_kwh": {"reliability": 2, "completeness": 2, "temporal": 1,
                                      "geographical": 1, "technological": 2},
        },
    ),
    "CA": Region(
        code="CA", name="Canada", currency="CAD",
        # Canada spans wet (east) and dry (prairie) temperate zones; the aggregated IPCC
        # defaults are used for every climate-dependent parameter, consistently with EF1.
        climate_zone="cool temperate", ipcc_n2o_ef1=EF1_AGGREGATED,  # temperate ≈ aggregate default
        aware_country="Canada", default_method="EF v3.1",
        # Prefer strings that actually appear in the canonical store ("Global",
        # "Rest of World", "Canada, Quebec", …) — bare "GLO"/"RoW" rarely match.
        location_prefer=("CA", "Canada", "Canada, Quebec", "Canada, Ontario",
                         "CA-QC", "CA-ON", "US", "RNA",
                         "Rest of World", "RoW", "Global", "GLO"),
        frac_leach=FRAC_LEACH_WET, ef4=EF4_AGGREGATED,
        field_sources={
            **_ipcc_sources("aggregated"),
            "ipcc_n2o_ef1": f"{_IPCC_T11_1}: EF1 aggregated (mixed wet east / dry prairie)",
            "ef4": f"{_IPCC_T11_3}: EF4 aggregated",
            "aware_country": _AWARE,
        },
        field_pedigree={"ipcc_n2o_ef1": {**_PED_IPCC, "geographical": 4}},
    ),
}

ALIASES = {
    "ghana": "GH", "gh": "GH", "nigeria": "NG", "ng": "NG",
    "senegal": "SN", "sénégal": "SN", "sn": "SN", "sen": "SN",
    "republic of senegal": "SN",
    "burkina faso": "BF", "burkina": "BF", "bf": "BF", "bfa": "BF",
    "burkina-faso": "BF", "burkina_faso": "BF",
    "south africa": "ZA", "south-africa": "ZA", "south_africa": "ZA", "rsa": "ZA",
    "za": "ZA", "zaf": "ZA", "republic of south africa": "ZA",
    "canada": "CA", "ca": "CA", "can": "CA",
    # Backend country enum uses "Global" for Canada (no "Canada" country in the API).
    "global": "CA",
    # Common free-text provinces / states typed into the facility region field.
    "ontario": "CA", "quebec": "CA", "québec": "CA", "saskatchewan": "CA",
    "alberta": "CA", "manitoba": "CA", "british columbia": "CA", "bc": "CA",
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


# --- climate override + irrigation-aware leaching ------------------------------------

_CLIMATE_PRESETS = {
    "wet": {"ipcc_n2o_ef1": EF1_WET_SYNTHETIC, "ef4": EF4_WET, "frac_leach": FRAC_LEACH_WET},
    "dry": {"ipcc_n2o_ef1": EF1_DRY, "ef4": EF4_DRY, "frac_leach": FRAC_LEACH_DRY},
}


def with_climate(region: Region, wetness: str) -> Region:
    """Return a copy of `region` with the IPCC wet or dry parameter set (EF1, EF4,
    FracLEACH). This is the documented override for province-variable regions (ZA wet
    KwaZulu-Natal, NG dry north). The registry entry itself is never mutated."""
    w = (wetness or "").strip().lower()
    if w not in _CLIMATE_PRESETS:
        raise ValueError(f"wetness must be 'wet' or 'dry', got {wetness!r}")
    label = "wet climate" if w == "wet" else "dry climate"
    other = "dry" if w == "wet" else "wet"
    zone = region.climate_zone
    if other in zone and w not in zone:
        zone = zone.replace(other, w)
    elif w not in zone or other in zone:
        zone = f"{zone} ({w} override)"
    srcs = dict(region.field_sources)
    srcs.update({k: v for k, v in _ipcc_sources(label).items()
                 if k in ("ipcc_n2o_ef1", "ef4", "frac_leach")})
    srcs["climate_zone"] = f"override to IPCC {label} via regions.with_climate()"
    return replace(region, climate_zone=zone, field_sources=srcs,
                   ghana_inherited=tuple(f for f in region.ghana_inherited
                                         if f not in _CLIMATE_PRESETS[w]),
                   **_CLIMATE_PRESETS[w])


def frac_leach_for(region: Region, irrigation_system: str | None = None) -> float:
    """FracLEACH-(H) for a farm. In a dry-climate region the IPCC 2019 default is 0,
    but irrigation other than drip moves it to the wet value 0.24 (Ch 11, p 11.25)."""
    base = getattr(region, "frac_leach", FRAC_LEACH_WET)
    irr = (irrigation_system or "").strip().lower()
    irrigated = bool(irr) and "rainfed" not in irr and irr not in ("none", "no", "n/a")
    if base == 0.0 and irrigated and "drip" not in irr:
        return FRAC_LEACH_WET
    return base


def field_gsd(region: Region, field_name: str, basic_gsd: float = 1.10) -> float | None:
    """Geometric SD for a registry value from its pedigree scores (engine/pedigree.py),
    so a Monte Carlo can widen the spread of poorly sourced regional values. None when
    the field carries no pedigree."""
    scores = (getattr(region, "field_pedigree", None) or {}).get(field_name)
    if not scores:
        return None
    try:
        from .pedigree import gsd_from_pedigree
    except ImportError:
        from pedigree import gsd_from_pedigree
    return gsd_from_pedigree(scores, basic_gsd)


def location_rank(region: Region, location: str | None) -> int:
    """Lower is better. Rank a background process's location against the region's
    preference list; unknown locations sort last.

    Ranks, for preference i (n = number of preferences, step = n + 2):
      * EXACT match on preference i: i*step (ecoinvent codes and store names are treated as
        equal: "GLO" == "Global", "RoW" == "Rest of World");
      * SUB-NATIONAL form of preference i ("Canada, Ontario", "Canada without Quebec",
        "CA-QC" against "Canada"/"CA"): i*step + 1 + j when that sub-national location is
        itself listed at position j, else i*step + 1 + n.
    So the national dataset always outranks every sub-national one, and among sub-national
    datasets the explicitly preferred ones (the farm's own province first, see
    with_admin_locations) outrank unlisted ones deterministically: a similarity-score
    jitter can no longer swap Ontario for Yukon. A bare substring does NOT count: "Africa"
    (the RAF market groups) must not match "South Africa", which is another country.
    Callers break remaining ties by similarity score and then uid
    (see orchestrator.FarmLCA._rank)."""
    same = {"glo": "global", "row": "rest of world"}

    def norm(s):
        s = (s or "").strip().lower()
        return same.get(s, s)

    loc = norm(location)
    prefs = [norm(p) for p in region.location_prefer]
    n = len(prefs)
    step = n + 2
    listed = {}
    for j, p in enumerate(prefs):
        listed.setdefault(p, j)
    best = None
    for i, pref in enumerate(prefs):
        if not pref:
            continue
        if loc == pref:
            r = i * step
        elif loc.startswith((pref + ",", pref + " without ", pref + "-")):
            r = i * step + 1 + listed.get(loc, n)
        else:
            continue
        best = r if best is None else min(best, r)
    return best if best is not None else n * step + 1


# Canadian provinces: ecoinvent sub-national location codes and store names.
_CA_PROVINCES = {
    "alberta": ("CA-AB", "Alberta"), "british columbia": ("CA-BC", "British Columbia"),
    "manitoba": ("CA-MB", "Manitoba"), "new brunswick": ("CA-NB", "New Brunswick"),
    "newfoundland and labrador": ("CA-NF", "Newfoundland and Labrador"),
    "nova scotia": ("CA-NS", "Nova Scotia"), "ontario": ("CA-ON", "Ontario"),
    "prince edward island": ("CA-PE", "Prince Edward Island"),
    "quebec": ("CA-QC", "Quebec"), "saskatchewan": ("CA-SK", "Saskatchewan"),
}


def with_admin_locations(region: Region, admin_region: str | None) -> Region:
    """Region copy whose location preference puts the farm's own province first among the
    sub-national datasets (Canada: provincial grids and PV differ by an order of magnitude,
    Quebec hydro vs Alberta coal/gas). Unchanged for other regions / unknown provinces."""
    if region.code != "CA":
        return region
    prov = _CA_PROVINCES.get(_admin_key(admin_region, _CA_PROVINCES))
    if not prov:
        return region
    code, name = prov
    own = (f"Canada, {name}", code)
    rest = tuple(p for p in region.location_prefer if p not in own)
    head = tuple(p for p in rest if p in ("CA", "Canada"))
    tail = tuple(p for p in rest if p not in ("CA", "Canada"))
    srcs = {**region.field_sources,
            "location_prefer": f"farm province {name} preferred among Canadian sub-national datasets"}
    return replace(region, location_prefer=head + own + tail, field_sources=srcs)


# --- admin-region climate: IPCC wet/dry, rainy season, FAO forest zone -----------------
#
# IPCC 2019 Vol 4 Ch 11 Table 11.1 footnote 4 (p 11.13): "Wet climates occur in temperate
# and boreal zones where the ratio of annual precipitation: potential evapotranspiration > 1,
# and tropical zones where annual precipitation > 1000 mm." The tropical regions (GH, NG,
# SN, BF) are classified from a mean annual precipitation (MAP) per admin region; the
# temperate ones (ZA, CA) only where a cited P:PET classification exists.
#
# Rainy months: a month is DRY when P (mm) <= 2 x T (degC) (Bagnouls & Gaussen 1957; the
# dry-month definition of FAO (2001) Global Ecological Zoning for FRA 2000, FRA Working
# Paper 56, Table 1 note b), so rainy = P > 2T, computed on the station's monthly normals.
#
# Station normals (MAP and months): WMO Climatological Standard Normals 1991-2020, NOAA
# NCEI Accession 0253808, composite files wmo_normals_9120_PRCP.csv and _TAVG.csv; where a
# station has no TAVG, T = (TMAX + TMIN) / 2 from _TMAX.csv / _TMIN.csv (Senegal, Tamale).
# Station = the WMO station inside the admin region (normally its capital).
# Admin regions without a station inside them are NOT mapped (region default applies),
# except where every neighbouring station lies on the same side of the threshold (noted).

_SRC_WMO = ("WMO Climatological Standard Normals 1991-2020 (NOAA NCEI Accession 0253808), "
            "station {station} (WMO {wmo}): annual precipitation {map:g} mm")
_SRC_GMET = ("Ghana Meteorological Agency 30-year regional average annual rainfall {map:g} mm, "
             "in MoFA SRID (2021) Agriculture in Ghana: Facts & Figures 2020, Table 2.9")
_SRC_GH_SEASONS = ("MoFA SRID (2021) Facts & Figures 2020, s 2.1: two rainy seasons in the "
                   "south (March-July, September-October), one in the north (May-October); "
                   "Table 2.5: unimodal in the Guinea and Sudan savanna zones")
_SRC_GAUSSEN = ("rainy month = P > 2T on the station's 1991-2020 monthly normals (dry month "
                "P <= 2T: Bagnouls & Gaussen 1957; FAO 2001 FRA WP 56, Table 1 note b)")
_SRC_ROCHETTE = ("Rochette et al. (2008) Can J Soil Sci 88:641-654: the Prairie region "
                 "(semi-arid Brown and sub-humid Black soil zones) has growing-season "
                 "precipitation well below potential evapotranspiration; Quebec and Ontario "
                 "are the humid provinces")
_SRC_GEZ = ("FAO (2001) Global Ecological Zoning for FRA 2000, FRA WP 56, Table 1: tropical "
            "rain forest 0-3 dry months (and >= 1500 mm), moist deciduous 3-5, dry forest 5-8")

# Ghana: GMet regional MAP (admin-region level, more representative of the cropland than a
# single coastal station: Saltpond, Central Region, is 974.5 mm). Regions created in 2018
# inherit their parent region's value (Western North <- Western, Oti <- Volta, Bono / Bono
# East / Ahafo <- Brong Ahafo, Savannah / North East <- Northern).
_GH_NORTH = (5, 6, 7, 8, 9, 10)
_GH_SOUTH = (3, 4, 5, 6, 7, 9, 10)
_GH = {
    # admin region: (GMet table column, MAP mm, rainy months)
    "greater accra": ("Greater Accra", 788.0, _GH_SOUTH),
    "ashanti": ("Ashanti", 1345.0, _GH_SOUTH),
    "western": ("Western", 1558.0, _GH_SOUTH),
    "western north": ("Western (parent)", 1558.0, _GH_SOUTH),
    "central": ("Central", 1252.0, _GH_SOUTH),
    "volta": ("Volta", 1340.0, _GH_SOUTH),
    "oti": ("Volta (parent)", 1340.0, _GH_SOUTH),
    "eastern": ("Eastern", 1180.0, _GH_SOUTH),
    "brong ahafo": ("Brong Ahafo", 1244.0, _GH_SOUTH),
    "bono": ("Brong Ahafo (parent)", 1244.0, _GH_SOUTH),
    "bono east": ("Brong Ahafo (parent)", 1244.0, _GH_SOUTH),
    "ahafo": ("Brong Ahafo (parent)", 1244.0, _GH_SOUTH),
    "northern": ("Northern", 1155.0, _GH_NORTH),
    "savannah": ("Northern (parent)", 1155.0, _GH_NORTH),
    "north east": ("Northern (parent)", 1155.0, _GH_NORTH),
    "upper east": ("Upper East", 912.0, _GH_NORTH),
    "upper west": ("Upper West", 1022.0, _GH_NORTH),
}

# WMO station normals: station -> (WMO id, MAP mm, rainy months by P > 2T or None when the
# station has no temperature normal).
_STATIONS = {
    # Nigeria
    "Umuahia": ("65254", 2364.2, (3, 4, 5, 6, 7, 8, 9, 10, 11)),
    "Yola": ("65167", 886.1, (5, 6, 7, 8, 9, 10)),
    "Uyo": ("65260", 2435.8, (3, 4, 5, 6, 7, 8, 9, 10, 11)),
    "Awka": ("65246", 2166.9, (3, 4, 5, 6, 7, 8, 9, 10)),
    "Bauchi": ("65055", 1268.3, (5, 6, 7, 8, 9)),
    "Makurdi": ("65271", 1217.1, (4, 5, 6, 7, 8, 9, 10)),
    "Maiduguri": ("65082", 699.0, (6, 7, 8, 9)),
    "Calabar": ("65264", 3022.8, (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12)),
    "Asaba": ("65282", 2041.8, (3, 4, 5, 6, 7, 8, 9, 10)),
    "Benin": ("65229", 2317.5, (3, 4, 5, 6, 7, 8, 9, 10, 11)),
    "Ado-Ekiti": ("65224", 1424.1, (3, 4, 5, 6, 7, 8, 9, 10)),
    "Enugu": ("65257", 1877.3, (4, 5, 6, 7, 8, 9, 10)),
    "Gombe": ("65075", 1046.8, (5, 6, 7, 8, 9)),
    "Owerri": ("65252", 2328.2, (3, 4, 5, 6, 7, 8, 9, 10, 11)),
    "Dutse": ("65048", 1153.3, (6, 7, 8, 9)),
    "Kaduna": ("65019", 1325.0, (5, 6, 7, 8, 9, 10)),
    "Kano": ("65046", 1149.2, (5, 6, 7, 8, 9)),
    "Katsina": ("65028", 597.5, (6, 7, 8, 9)),
    "Yelwa": ("65001", 1089.0, (5, 6, 7, 8, 9, 10)),
    "Lokoja": ("65243", 1252.1, (4, 5, 6, 7, 8, 9, 10)),
    "Ilorin": ("65101", 1401.7, (4, 5, 6, 7, 8, 9, 10)),
    "Ikeja": ("65201", 1549.3, (3, 4, 5, 6, 7, 8, 9, 10, 11)),
    "Lafia": ("65124", 1410.4, (4, 5, 6, 7, 8, 9, 10)),
    "Minna": ("65123", 1277.5, (4, 5, 6, 7, 8, 9, 10)),
    "Abeokuta": ("65213", 1246.3, (3, 4, 5, 6, 7, 8, 9, 10)),
    "Ondo": ("65222", 1717.8, (3, 4, 5, 6, 7, 8, 9, 10)),
    "Oshogbo": ("65215", 1379.6, (3, 4, 5, 6, 7, 8, 9, 10)),
    "Ibadan": ("65208", 1448.9, (3, 4, 5, 6, 7, 8, 9, 10)),
    "Jos": ("65134", 1242.9, (4, 5, 6, 7, 8, 9, 10)),
    "Port Harcourt": ("65250", 2286.5, (2, 3, 4, 5, 6, 7, 8, 9, 10, 11)),
    "Sokoto": ("65010", 685.1, (6, 7, 8, 9)),
    "Jalingo": ("65170", 1178.6, (4, 5, 6, 7, 8, 9, 10)),
    "Potiskum": ("65073", 688.0, (6, 7, 8, 9)),
    "Gusau": ("65015", 970.6, (5, 6, 7, 8, 9)),
    "Abuja": ("65125", 1421.1, (4, 5, 6, 7, 8, 9, 10)),
    # Senegal (ANACIM submission; national station codes where no WMO id)
    "Dakar": ("61641", 392.5, (8, 9)),
    "Diourbel": ("61666", 526.4, (7, 8, 9)),
    "Fatick": ("380092", 604.6, (7, 8, 9)),
    "Koungheul": ("380105", 738.0, (7, 8, 9)),
    "Kaolack": ("61679", 630.6, (7, 8, 9)),
    "Kedougou": ("61699", 1238.2, (6, 7, 8, 9, 10)),
    "Kolda": ("61698", 1057.8, (6, 7, 8, 9, 10)),
    "Louga": ("380051", 323.2, (8, 9)),
    "Matam": ("61630", 385.6, (7, 8, 9)),
    "Saint-Louis": ("61600", 272.4, (8, 9)),
    "Tambacounda": ("61687", 742.2, (6, 7, 8, 9)),
    "Thies": ("380075", 449.5, None),
    "Ziguinchor": ("61695", 1401.2, (6, 7, 8, 9, 10)),
    # Burkina Faso (ANAM-BF synoptic stations)
    "Dedougou": ("65505", 842.2, (5, 6, 7, 8, 9)),
    "Bobo-Dioulasso": ("65510", 1054.0, (5, 6, 7, 8, 9, 10)),
    "Ouagadougou": ("65503", 782.8, (6, 7, 8, 9)),
    "Po": ("65518", 1036.7, (5, 6, 7, 8, 9)),
    "Fada N'Gourma": ("65507", 851.1, (5, 6, 7, 8, 9)),
    "Ouahigouya": ("65502", 734.8, (6, 7, 8, 9)),
    "Dori": ("65501", 507.0, (6, 7, 8, 9)),
    "Gaoua": ("65522", 1097.5, (4, 5, 6, 7, 8, 9, 10)),
    # South Africa (SAWS; rainy months only, see _ZA)
    "Bloemfontein": ("68442", 535.2, (1, 2, 3, 4, 10, 11, 12)),
    "Cape Town": ("68816", 492.8, (4, 5, 6, 7, 8, 9)),
    "East London": ("68858", 822.0, (1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12)),
    "Kimberley": ("68438", 404.3, (1, 2, 3, 4, 12)),
    "Mafikeng": ("68242", 518.9, (1, 2, 3, 4, 11, 12)),
    "Polokwane": ("68174", 474.7, (1, 2, 3, 11, 12)),
}

# admin region -> station (tropical regions: MAP drives wet/dry).
_NG = {
    "abia": "Umuahia", "adamawa": "Yola", "akwa ibom": "Uyo", "anambra": "Awka",
    "bauchi": "Bauchi", "benue": "Makurdi", "borno": "Maiduguri", "cross river": "Calabar",
    "delta": "Asaba", "edo": "Benin", "ekiti": "Ado-Ekiti", "enugu": "Enugu",
    "gombe": "Gombe", "imo": "Owerri", "jigawa": "Dutse", "kaduna": "Kaduna",
    "kano": "Kano", "katsina": "Katsina", "kebbi": "Yelwa", "kogi": "Lokoja",
    "kwara": "Ilorin", "lagos": "Ikeja", "nasarawa": "Lafia", "niger": "Minna",
    "ogun": "Abeokuta", "ondo": "Ondo", "osun": "Oshogbo", "oyo": "Ibadan",
    "plateau": "Jos", "rivers": "Port Harcourt", "sokoto": "Sokoto", "taraba": "Jalingo",
    "yobe": "Potiskum", "zamfara": "Gusau", "fct": "Abuja", "abuja": "Abuja",
    "federal capital territory": "Abuja",
    # Bayelsa and Ebonyi have no station in the normals: region default.
}
_SN = {
    "dakar": "Dakar", "diourbel": "Diourbel", "fatick": "Fatick", "kaffrine": "Koungheul",
    "kaolack": "Kaolack", "kedougou": "Kedougou", "kolda": "Kolda", "louga": "Louga",
    "matam": "Matam", "saint louis": "Saint-Louis", "tambacounda": "Tambacounda",
    "thies": "Thies", "ziguinchor": "Ziguinchor",
}
_BF = {
    "boucle du mouhoun": "Dedougou", "hauts bassins": "Bobo-Dioulasso",
    "centre": "Ouagadougou", "centre sud": "Po", "est": "Fada N'Gourma",
    "nord": "Ouahigouya", "sahel": "Dori", "sud ouest": "Gaoua",
    # Centre-Est, Centre-Nord, Centre-Ouest, Plateau-Central: no station -> region default.
}
# No station inside, but every neighbouring station is on the same side of 1000 mm.
_BRACKETED = {
    ("SN", "sedhiou"): ("wet", ("Ziguinchor", "Kolda"), (6, 7, 8, 9, 10)),
    ("BF", "cascades"): ("wet", ("Bobo-Dioulasso", "Gaoua"), (5, 6, 7, 8, 9, 10)),
}
# Temperate: no cited province P:PET, so wet/dry stays at the region default; the station
# only gives the rainy months (summer rainfall interior vs Western Cape winter rainfall).
_ZA = {
    "free state": "Bloemfontein", "western cape": "Cape Town", "eastern cape": "East London",
    "northern cape": "Kimberley", "north west": "Mafikeng", "limpopo": "Polokwane",
}
_CA = {"alberta": "dry", "saskatchewan": "dry", "manitoba": "dry",
       "ontario": "wet", "quebec": "wet"}

# Region default rainy months when the admin region is unknown: the station representing
# the region's default climate class (GH union of MoFA north and south seasons; NG Abuja,
# central; SN Kaolack, groundnut basin; BF Ouagadougou; ZA Bloemfontein, Highveld maize
# belt, matching the ZA default climate). Canada: no rainy season concept (empty).
_DEFAULT_RAINY = {
    "GH": tuple(sorted(set(_GH_NORTH) | set(_GH_SOUTH))),
    "NG": _STATIONS["Abuja"][2], "SN": _STATIONS["Kaolack"][2],
    "BF": _STATIONS["Ouagadougou"][2], "ZA": _STATIONS["Bloemfontein"][2], "CA": (),
}
WET_THRESHOLD_MM = 1000.0   # IPCC 2019 Table 11.1 fn 4 (tropical zones)
MARGINAL_MM = 100.0         # MAP within this of the threshold is disclosed as marginal


def _norm_admin(text) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(text or "")).encode("ascii", "ignore").decode()
    s = s.lower().replace("-", " ").replace("_", " ").replace("'", " ")
    return " ".join(s.split())


_ADMIN_SUFFIXES = (" region", " state", " province")


def _admin_key(text, *tables) -> str:
    """Normalised admin-region key: the full name when a table has it ("Free State",
    "Federal Capital Territory"), else the name without a trailing Region/State/Province
    ("Upper East Region", "Kano State")."""
    s = _norm_admin(text)
    if any(s in t for t in tables):
        return s
    for suffix in _ADMIN_SUFFIXES:
        if s.endswith(suffix):
            return s[: -len(suffix)].strip()
    return s


def _region_code(region_code) -> str | None:
    try:
        return get_region(region_code).code
    except KeyError:
        return None


def admin_climate(region_code, admin_region) -> dict | None:
    """Climate record of a known admin region, or None (unknown / not mapped):
    {admin_region, wetness ('wet'|'dry'|None), map_mm, rainy_months (tuple|None),
    marginal, source}."""
    code = _region_code(region_code)
    tables = {"GH": (_GH,), "NG": (_NG,), "SN": (_SN,), "BF": (_BF,), "ZA": (_ZA,),
              "CA": (_CA, _CA_PROVINCES)}.get(code or "", ())
    key = _admin_key(admin_region, *tables,
                     {k for (c, k) in _BRACKETED if c == code})
    if not code or not key:
        return None

    def tropical(map_mm, months, src, months_src):
        return {"admin_region": key, "map_mm": map_mm,
                "wetness": "wet" if map_mm > WET_THRESHOLD_MM else "dry",
                "rainy_months": months,
                "marginal": abs(map_mm - WET_THRESHOLD_MM) < MARGINAL_MM,
                "source": f"{src}; {_IPCC_T11_1} footnote 4 (tropical wet if > 1000 mm); "
                          f"rainy months: {months_src}"}

    def station(name):
        wmo, map_mm, months = _STATIONS[name]
        return wmo, map_mm, months, _SRC_WMO.format(station=name, wmo=wmo, map=map_mm)

    if code == "GH" and key in _GH:
        col, map_mm, months = _GH[key]
        return tropical(map_mm, months, _SRC_GMET.format(map=map_mm) + f" ({col})",
                        _SRC_GH_SEASONS)
    table = {"NG": _NG, "SN": _SN, "BF": _BF}.get(code, {})
    if key in table:
        _, map_mm, months, src = station(table[key])
        return tropical(map_mm, months, src, _SRC_GAUSSEN)
    if (code, key) in _BRACKETED:
        wet, names, months = _BRACKETED[(code, key)]
        maps = ", ".join(f"{n} {_STATIONS[n][1]:g} mm" for n in names)
        return {"admin_region": key, "map_mm": None, "wetness": wet, "rainy_months": months,
                "marginal": False,
                "source": (f"no station in the region; every neighbouring station is above "
                           f"1000 mm ({maps}; WMO 1991-2020 normals, NCEI 0253808); "
                           f"{_IPCC_T11_1} footnote 4; rainy months: {_SRC_GAUSSEN}")}
    if code == "ZA" and key in _ZA:
        _, map_mm, months, src = station(_ZA[key])
        return {"admin_region": key, "map_mm": map_mm, "wetness": None,
                "rainy_months": months, "marginal": False,
                "source": (f"{src}; wet/dry not classified (temperate: IPCC P:PET criterion, "
                           f"no cited provincial P:PET), region default kept; rainy months: "
                           f"{_SRC_GAUSSEN}")}
    if code == "CA" and key in _CA:
        return {"admin_region": key, "map_mm": None, "wetness": _CA[key], "rainy_months": (),
                "marginal": False,
                "source": f"{_SRC_ROCHETTE}; {_IPCC_T11_1} footnote 4 (temperate: P:PET)"}
    return None


def _default_wetness(region: Region) -> str:
    return "dry" if region.ipcc_n2o_ef1 == EF1_DRY else "wet"


def climate_zone_for(region_code: str, admin_region: str | None) -> str:
    """IPCC wet/dry class ('wet' | 'dry') of a farm's admin region (IPCC 2019 Vol 4 Ch 11
    Table 11.1 footnote 4); falls back to the region default when the admin region is
    unknown, unmapped or not classifiable (temperate without a cited P:PET). Canada's
    registry entry uses the aggregated factors; its fallback label here is 'wet'."""
    rec = admin_climate(region_code, admin_region)
    if rec and rec.get("wetness") in ("wet", "dry"):
        return rec["wetness"]
    code = _region_code(region_code)
    return _default_wetness(REGIONS[code]) if code else "wet"


def rainy_season_months(region_code: str, admin_region: str | None) -> set[int]:
    """Calendar months (1-12) of the rainy season for the farm's admin region (station
    normals, P > 2T; Ghana per MoFA), else the region default. Empty for Canada."""
    rec = admin_climate(region_code, admin_region)
    if rec and rec.get("rainy_months"):
        return set(rec["rainy_months"])
    code = _region_code(region_code)
    return set(_DEFAULT_RAINY.get(code or "", ()))


def forest_zone_for(region_code: str, admin_region: str | None) -> str | None:
    """IPCC/FAO tropical forest ecological zone key of land_use_change.FOREST ('tropical
    wet' | 'tropical moist' | 'tropical dry') for a known tropical admin region, from its
    number of dry months (FAO 2001 GEZ, Table 1). None when the admin region is unknown, the
    region is not tropical, or the climate is drier than dry forest (> 8 dry months, FAO
    tropical shrubland): the caller keeps its own default."""
    code = _region_code(region_code)
    if code not in ("GH", "NG", "SN", "BF"):
        return None
    rec = admin_climate(code, admin_region)
    if not rec or not rec.get("rainy_months"):
        return None
    dry = 12 - len(rec["rainy_months"])
    if dry <= 3 and (rec.get("map_mm") or 0) >= 1500:
        return "tropical wet"
    if dry <= 5:
        return "tropical moist"
    if dry <= 8:
        return "tropical dry"
    return None


def climate_disclosure(region_code: str, admin_region: str | None) -> str:
    """One-line disclosure of the climate classification used for the farm."""
    code = _region_code(region_code) or str(region_code)
    rec = admin_climate(region_code, admin_region)
    zone = climate_zone_for(region_code, admin_region)
    if not admin_region:
        return (f"IPCC climate: region default '{zone}' for {code} (no admin region given; "
                f"{_IPCC_T11_1} footnote 4)")
    if not rec or rec.get("wetness") not in ("wet", "dry"):
        why = rec["source"] if rec else "admin region not in the climate table"
        return (f"IPCC climate: region default '{zone}' for {code}, admin region "
                f"'{admin_region}' ({why})")
    marg = (f"; MARGINAL: {rec['map_mm']:g} mm is within {MARGINAL_MM:g} mm of the 1000 mm "
            f"threshold") if rec.get("marginal") else ""
    return f"IPCC climate '{zone}' for {admin_region} ({rec['source']}){marg}"


if __name__ == "__main__":
    for r in REGIONS.values():
        print(f"{r.code}: {r.name:<13} zone={r.climate_zone:<20} EF1={r.ipcc_n2o_ef1} "
              f"EF4={r.ef4} Leach={r.frac_leach} grid={r.grid_ef_kgco2_per_kwh} "
              f"AWARE={r.aware_country:<13} method={r.default_method}")
