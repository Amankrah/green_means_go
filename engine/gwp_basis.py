#!/usr/bin/env python3
"""
gwp_basis.py: one GWP basis per LCIA method, stated in every ISO report.

Decision (see engine/lcia_reference/gwp_basis.json, built by ingestion/gmg_reference.py
from data/IPCC GWP/Global-Warming-Potential-Values (August 2024).pdf and the ReCiPe 2016
v1.1 CF workbook): each method keeps its NATIVE basis, exactly as published and as shipped
in the ecoinvent 3.11 method pack, so foreground and background are characterised with the
same factors inside a method.
  * ReCiPe 2016 v1.03 midpoint (H): IPCC AR5 GWP100 including climate-carbon feedbacks
    (Myhre et al. 2013, AR5 WG1 Table 8.7): CH4 non-fossil 34, CH4 fossil 36, N2O 298.
  * EF 3.1: IPCC AR6 GWP100 (Forster et al. 2021, AR6 WG1 Table 7.15): CH4 non-fossil 27.0,
    CH4 fossil 29.8, N2O 273.
The N2O / CH4 values reported are READ FROM THE STORE for the method actually used, so the
statement cannot drift from the numbers.
"""
from __future__ import annotations

_BASIS = {
    "ReCiPe": ("IPCC AR5 GWP100 including climate-carbon feedbacks (Myhre et al. 2013, "
               "IPCC AR5 WG1 Ch.8 Table 8.7), as published in ReCiPe 2016 (Hierarchist)"),
    "EF": ("IPCC AR6 GWP100 (Forster et al. 2021, IPCC AR6 WG1 Ch.7 Table 7.15), as published "
           "in EF 3.1"),
}
_REFRIGERANT_NOTE = ("On-site refrigerant leakage, where modelled, uses IPCC AR6 GWP100 "
                     "(engine/refrigerants.py) regardless of the method.")

_CACHE: dict = {}


def _store_values(q, method: str) -> dict:
    key = (id(q), method)
    if key in _CACHE:
        return _CACHE[key]
    out = {}
    try:
        m = q.find_method(method)
        if m:
            for label, name in (("N2O", "Dinitrogen monoxide"), ("CH4_non_fossil", "Methane, non-fossil"),
                                ("CH4_fossil", "Methane, fossil")):
                r = q.conn.execute(
                    "SELECT cf.factor FROM characterization_factors cf JOIN impact_categories ic "
                    "ON ic.uid=cf.category_uid JOIN flows f ON f.uid=cf.flow_uid WHERE ic.method_uid=? "
                    "AND ic.name='Climate change' AND f.name=? AND f.category LIKE '%Emission to air/unspecified' "
                    "LIMIT 1", (m["uid"], name)).fetchone()
                if r:
                    out[label] = r[0]
    except Exception:
        out = {}
    _CACHE[key] = out
    return out


def statement(engine, method: str) -> dict:
    """{'basis', 'n2o', 'ch4_non_fossil', 'ch4_fossil', 'text'} for the report."""
    fam = "EF" if (method or "").startswith("EF") else "ReCiPe" if "ReCiPe" in (method or "") else None
    basis = _BASIS.get(fam, "the method's own published characterisation factors")
    vals = _store_values(getattr(engine, "q", None), method) if getattr(engine, "q", None) else {}
    n2o, ch4, ch4f = vals.get("N2O"), vals.get("CH4_non_fossil"), vals.get("CH4_fossil")
    nums = ", ".join(f"{k} {v:g}" for k, v in (("N2O", n2o), ("CH4 non-fossil", ch4), ("CH4 fossil", ch4f))
                     if v is not None)
    text = (f"Climate change is characterised with {basis}" + (f": {nums} kg CO2-eq per kg" if nums else "")
            + ". Each method keeps its native GWP basis, so ReCiPe 2016 (AR5) and EF 3.1 (AR6) results "
            "differ for N2O- and CH4-dominated systems. " + _REFRIGERANT_NOTE)
    return {"basis": basis, "n2o": n2o, "ch4_non_fossil": ch4, "ch4_fossil": ch4f, "text": text}
