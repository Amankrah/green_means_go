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
        # 0 for rainfed); a northern farm should use with_climate(NG, "dry"). The wet
        # assignment mirrors Ghana's, so it is flagged in ghana_inherited.
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

    An EXACT match on preference i ranks 2*i (ecoinvent codes and store names are treated
    as equal: "GLO" == "Global", "RoW" == "Rest of World"). A SUB-NATIONAL form of a
    preference ("Canada, Ontario", "Canada without Quebec", "CA-QC" against "Canada"/"CA")
    ranks 2*i+1, so the national dataset outranks a sub-national one and the two never tie.
    A bare substring does NOT count: "Africa" (the RAF market groups) must not match
    "South Africa", which is another country. Callers break remaining ties by similarity
    score and then uid (see orchestrator.FarmLCA._match_input)."""
    same = {"glo": "global", "row": "rest of world"}

    def norm(s):
        s = (s or "").strip().lower()
        return same.get(s, s)

    loc = norm(location)
    prefs = [norm(p) for p in region.location_prefer]
    best = None
    for i, pref in enumerate(prefs):
        if not pref:
            continue
        if loc == pref:
            r = 2 * i
        elif loc.startswith((pref + ",", pref + " without ", pref + "-")):
            r = 2 * i + 1
        else:
            continue
        best = r if best is None else min(best, r)
    return best if best is not None else 2 * len(prefs) + 1


if __name__ == "__main__":
    for r in REGIONS.values():
        print(f"{r.code}: {r.name:<13} zone={r.climate_zone:<20} EF1={r.ipcc_n2o_ef1} "
              f"EF4={r.ef4} Leach={r.frac_leach} grid={r.grid_ef_kgco2_per_kwh} "
              f"AWARE={r.aware_country:<13} method={r.default_method}")
