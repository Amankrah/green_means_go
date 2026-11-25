#!/usr/bin/env python3
"""
grid_calibration.py - correct grid-electricity climate to the official national factor.

The ecoinvent "Electricity, low voltage {GH}" market characterises to ~0.16 kg CO2e/kWh,
but Ghana's Energy Commission reports 0.35 kg CO2e/kWh for 2024. The gap is the ecoinvent
grid-mix DATA vintage, not the release: ecoinvent 3.11 is a 2025 release, but its GH
low-voltage dataset reflects an older, hydro-dominant mix. 0.16 is arithmetically only
possible at ~90% hydro (Ghana c. 2010); the actual 2024 mix is 61% thermal / 39% hydro
(2025 National Energy Statistical Bulletin, S3.2). Computing the attributional average
from that mix (thermal ~0.5, hydro ~0) plus Ghana's ~20% T&D losses lands at ~0.35-0.39
at low voltage - independently corroborating the official 0.35. So left uncorrected the
engine understates a facility's grid-electricity climate impact by ~2.2x.

(The Energy Commission figure is technically a CDM-style grid emission factor - hence the
"wind/solar vs all other projects" split - but it converges with the current attributional
average because the grid is now thermal-dominant, so it is a defensible attributional
value for this engine.)

How the gap is closed (choice and justification). The gap is missing THERMAL generation:
the official factor reflects a gas-dominated thermal share (Ghana 61 % thermal, 2025
Energy Statistical Bulletin S3.2; Nigeria 75 % gas, Ember 2024 in nigeria_grid_ef.json)
that the hydro-dominant ecoinvent vintage lacks. Three options were considered:
  (a) add bare fossil CO2 (the previous approach): climate is right, but SO2 / NOx / PM /
      fossil-resource use of that thermal generation are missing, so acidification, PM,
      photochemical ozone and fossil depletion stay at the hydro vintage;
  (b) scale the whole grid inventory by target/current: co-pollutants move, but so do the
      hydro-specific flows (reservoir evaporation, land transformation), which would be
      inflated 2x although the real mix has LESS hydro than the dataset;
  (c) top up with natural-gas generation (ecoinvent "electricity production, natural gas,
      combined cycle power plant | electricity, high voltage", RoW): add k kWh of its
      cradle-to-gate inventory, k chosen so climate lands exactly on the official factor
      (only the dataset's co-pollutant : climate ratio matters, not its absolute per-kWh
      scale; note the store's solve of the RoW NGCC dataset characterises to 0.146 kg CO2e/kWh
      although its direct CO2 exchange is 0.384 kg/kWh, flagged to the store owner). Co-pollutants and fossil resource use of the added thermal
      generation come with it; hydro flows are not inflated (they are not reduced either,
      a residual overstatement of hydro flows, disclosed).
(c) is used by default (GRID_CALIBRATION_MODE=thermal_topup). If the official factor is
BELOW the dataset (delta < 0), every flow is scaled down by target/current (proportional),
since removing generation of unknown technology has no better proxy. If the gas dataset
cannot be solved, it falls back to (a) and says so in the returned info.
GRID_CALIBRATION_MODE=co2_only restores (a). Residual simplifications (disclosed): the
thermal share also contains some liquid fuels (Ghana), and the top-up is at high voltage
(no extra T&D losses on the added generation).

Scope: ONLY electricity inputs, ONLY in regions that have a grid factor (Region field or
reference file; today GH and NG), only when USE_OFFICIAL_GRID_EF is on (default).

Per-region factor resolution (generic): getattr(region, "grid_ef_kgco2_per_kwh") and
getattr(region, "grid_ef_source") when the Region carries them; otherwise the per-country
reference file engine/recommend/reference/<country>_grid_ef.json (GH -> ghana_grid_ef.json,
NG -> nigeria_grid_ef.json). Nigeria has no official national factor; its file calibrates
to the Ember 2024 lifecycle intensity (0.496 kg CO2e/kWh) and says so.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

_REF_DIR = Path(__file__).resolve().parent / "recommend" / "reference"
_FALLBACK_FILES = {"GH": "ghana_grid_ef.json", "NG": "nigeria_grid_ef.json"}


@lru_cache(maxsize=16)
def _load(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _file_factor(region, filename: Optional[str] = None) -> tuple[Optional[float], Optional[str]]:
    code = getattr(region, "code", "") or ""
    name = (getattr(region, "name", "") or "").strip().lower().replace(" ", "_")
    for fn in (filename, _FALLBACK_FILES.get(code), f"{name}_grid_ef.json" if name else None):
        if not fn or not (_REF_DIR / fn).is_file():
            continue
        d = _load(str(_REF_DIR / fn))
        cal = d.get("calibration") or {}
        if cal.get("value") is not None:
            return float(cal["value"]), cal.get("source") or fn
        f = ((d.get("factors") or {}).get("all_other_projects") or {})
        if f.get("value") is not None:
            prov = d.get("provenance") or {}
            return float(f["value"]), f"{prov.get('publication', fn)}, {prov.get('table', '')}".strip(", ")
    return None, None


def grid_factor(region) -> tuple[Optional[float], Optional[str]]:
    """(kg CO2e/kWh, source) for the region's grid calibration, or (None, None)."""
    ef = getattr(region, "grid_ef_kgco2_per_kwh", None)
    src = getattr(region, "grid_ef_source", None)
    # The registry stores grid_ef_source either as a citation string or as the name of a
    # reference JSON under engine/recommend/reference/ holding the provenance.
    src_file = src if src and src.endswith(".json") else None
    if ef is not None:
        if not src or src_file:
            _, src = _file_factor(region, src_file)
        return float(ef), src or "Region.grid_ef_kgco2_per_kwh"
    return _file_factor(region, src_file)

_CO2_UID: dict[str, Optional[str]] = {}


def _fossil_co2_uid(q) -> Optional[str]:
    """A canonical 'Carbon dioxide, fossil' elementary-flow UID whose only characterization
    is Climate change = 1.0. Cached per store. Looked up via the query API rather than
    hardcoded so it survives a store rebuild."""
    key = id(q)
    if key not in _CO2_UID:
        uid = None
        for f in q.search_flows("Carbon dioxide, fossil", elementary_only=True, limit=40):
            if (f.get("name") or "").strip().lower() == "carbon dioxide, fossil":
                uid = f["uid"]
                break
        _CO2_UID[key] = uid
    return _CO2_UID[key]


def _climate_value(characterized: dict[str, Any]) -> float:
    for cat, v in characterized.items():
        if "climate" in cat.lower():
            return float(v.get("value") or 0.0)
    return 0.0


def enabled() -> bool:
    return os.getenv("USE_OFFICIAL_GRID_EF", "1") == "1"


def mode() -> str:
    return os.getenv("GRID_CALIBRATION_MODE", "thermal_topup")


THERMAL_TOPUP_DATASET = ("electricity production, natural gas, combined cycle power plant | "
                         "electricity, high voltage | Cutoff, U")
THERMAL_TOPUP_LOCATIONS = ("Ghana", "Nigeria", "Rest of World", "Global")
_TOPUP_CACHE: dict = {}


def _thermal_topup(q, method: str, region=None) -> Optional[tuple[dict, float, str]]:
    """(per-kWh elementary flows, climate per kWh, dataset label) of natural-gas combined
    cycle generation, region-specific if the store has it, else RoW. Cached per store."""
    loc_pref = (getattr(region, "name", None),) + THERMAL_TOPUP_LOCATIONS
    key = (id(q), method, loc_pref[0])
    if key in _TOPUP_CACHE:
        return _TOPUP_CACHE[key]
    out = None
    try:
        for loc in loc_pref:
            if not loc:
                continue
            row = q.conn.execute("SELECT uid, location FROM processes WHERE name = ? AND location = ? LIMIT 1",
                                 (THERMAL_TOPUP_DATASET, loc)).fetchone()
            if row:
                sc = q.cradle_to_gate(row[0], amount=1.0)
                clim = _climate_value(q.characterize_flows(sc.elementary_flows, method))
                if clim > 0:
                    out = ({u: dict(r) for u, r in sc.elementary_flows.items()}, clim,
                           f"{THERMAL_TOPUP_DATASET} {{{row[1]}}}")
                break
    except Exception:
        out = None
    _TOPUP_CACHE[key] = out
    return out


def apply(q, inp: dict, flows: dict, region, method: str) -> Optional[dict]:
    """If `inp` is grid electricity in a region with an official grid EF, edit `flows`
    in place so its climate impact equals ef x kWh. Returns a small info dict (for a
    provenance note) when it acts, else None. Never raises: a calibration failure must
    not break an assessment - it just leaves the raw number."""
    try:
        if not enabled():
            return None
        if (inp.get("kind") or "") != "electricity":
            return None
        ef, source = grid_factor(region)
        if ef is None:
            return None
        kwh = float(inp.get("amount") or 0.0)
        if kwh <= 0:
            return None

        target = ef * kwh
        current = _climate_value(q.characterize_flows(flows, method))
        delta = target - current
        if abs(delta) < 1e-9:
            return None

        info = {"ef": ef, "kwh": kwh, "climate_before": round(current, 4),
                "climate_after": round(target, 4), "source": source}

        if mode() != "co2_only":
            if delta < 0 and current > 0:
                factor = target / current
                for u in list(flows):
                    r = dict(flows[u])
                    r["amount"] = (r.get("amount") or 0.0) * factor
                    flows[u] = r
                return {**info, "mode": "proportional_down", "scale_factor": factor,
                        "note": ("official factor below the dataset: every grid flow scaled by "
                                 f"{factor:.3f}")}
            top = _thermal_topup(q, method, region)
            if top:
                gas_flows, gas_clim, label = top
                k = delta / gas_clim          # kWh of gas generation added (whole input)
                for u, r in gas_flows.items():
                    add = (r.get("amount") or 0.0) * k
                    if u in flows:
                        cur = dict(flows[u])
                        cur["amount"] = (cur.get("amount") or 0.0) + add
                        flows[u] = cur
                    else:
                        flows[u] = {**r, "amount": add}
                # Only the co-pollutant : climate RATIO of the gas dataset is used (k is set by
                # climate), so the result does not depend on the dataset's absolute kWh scaling.
                return {**info, "mode": "thermal_topup", "topup_dataset": label,
                        "topup_scale_per_kwh": k / kwh,
                        "note": ("thermal top-up: natural-gas combined-cycle generation inventory "
                                 f"({label}) added in proportion to the climate gap, so climate equals "
                                 "the official factor and the NOx, SO2, PM and fossil resource use of "
                                 "that thermal generation are included")}

        uid = _fossil_co2_uid(q)
        if not uid:
            return None
        if uid in flows:
            cur = dict(flows[uid])
            cur["amount"] = (cur.get("amount") or 0.0) + delta
            flows[uid] = cur
        else:
            flows[uid] = {"amount": delta, "name": "Carbon dioxide, fossil",
                          "unit": "kg"}
        return {**info, "mode": "co2_only",
                "note": ("fossil CO2 added to reach the official factor; co-pollutants of the "
                         "missing thermal generation are NOT represented")}
    except Exception:
        return None
