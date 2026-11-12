#!/usr/bin/env python3
"""
land_use_regional.py: country-specific EF soil-quality-index (LANCA-based) CFs for
ON-FARM land occupation.

EF 3.1 "Land use" (Pt, soil quality index) as shipped in the ecoinvent 3.11 method pack
carries only the WORLD-average SQI occupation CFs of De Laurentiis et al. (2019)
(e.g. "Occupation, annual crop" = 50.191 Pt/m2a, the 'arable' world average in mmc2,
sheet Occupation_SQI). The same source gives country CFs (Ghana arable 83.52, Nigeria
70.94, Senegal 30.39, Burkina Faso 38.63, South Africa 45.47, Canada 26.72).

ingestion/gmg_reference.py adds, per country, a regionalised copy of each ecoinvent
"Occupation, annual/permanent crop..." flow whose EF v3.x Land use CF is the country SQI
and whose CFs in every other method (ReCiPe m2a crop-eq, endpoints...) are copied from the
base flow. Here we move the on-farm occupation amount from the base flow to that copy, so
EF 3.1 land use becomes country-specific while ReCiPe is unchanged (ReCiPe 2016 land
occupation CFs are not regionalised: Huijbregts et al. 2017, Sec. 2.9).

Background (supply-chain) land occupation keeps the world CFs: ecoinvent elementary
flows are not located, so a country CF cannot be assigned to them.
"""
from __future__ import annotations


def _regional_map(q, country: str) -> dict:
    """base_flow_name -> regionalised flow uid for `country` (empty if not ingested)."""
    try:
        rows = q.conn.execute(
            "SELECT base_flow_name, flow_uid FROM gmg_regionalised_flows WHERE kind='land' AND country=?",
            (country,)).fetchall()
    except Exception:
        return {}
    return {r[0]: r[1] for r in rows}


def apply(q, region, onfarm: dict, res) -> dict | None:
    """Re-book on-farm land occupation on the country-regionalised flow (edits `onfarm`).
    Never raises."""
    try:
        country = (getattr(region, "aware_country", None) or getattr(region, "name", "") or "").strip()
        reg = _regional_map(q, country)
        occ = {}
        for uid in list(onfarm):
            r = q.conn.execute("SELECT name, category FROM flows WHERE uid=?", (uid,)).fetchone()
            if not r or not (r[1] or "").endswith("Resource/land"):
                continue
            name = r[0] or ""
            if not name.startswith(("Occupation, annual crop", "Occupation, permanent crop")):
                continue
            if not reg:
                res.notes.append(f"land occupation: no country soil-quality CFs for '{country}'; "
                                 "EF land use uses the world-average SQI")
                return None
            target = reg.get(name) or reg.get(
                "Occupation, permanent crop" if "permanent" in name else "Occupation, annual crop")
            if not target or target == uid:
                continue
            amt = onfarm.pop(uid)["amount"]
            rec = onfarm.get(target)
            if rec:
                rec["amount"] += amt
            else:
                onfarm[target] = {"name": f"{name}, {country} (EF soil quality index)",
                                  "unit": "m2a", "amount": amt}
            occ[name] = occ.get(name, 0.0) + amt
        if occ:
            res.notes.append(
                "on-farm land occupation characterised with country EF soil-quality-index CFs "
                f"for {country} (De Laurentiis et al. 2019); ReCiPe land use unchanged")
            return {"country": country, "m2a": occ}
        return None
    except Exception as e:
        try:
            res.notes.append(f"regional land-use step skipped: {e}")
        except Exception:
            pass
        return None
