#!/usr/bin/env python3
"""
phosphorus.py: field phosphorus losses to water, SALCA-P (Prasuhn 2006, "Erfassung der
PO4-Austräge für die Ökobilanzierung SALCA-Phosphor", Agroscope FAL Reckenholz), as used
for the ecoinvent agricultural inventories (Nemecek & Kägi 2007, ecoinvent report No. 15,
"Phosphorus emissions to water" section; carried into ecoinvent v3 by Nemecek & Schnetzer
2011 and applied worldwide in the World Food LCA Database, Nemecek et al. 2015).

Three pathways, per ha and year, for open arable land:

  leaching to ground water   Pgw = Pgwl x Fgw,  Pgwl = 0.07 kg P/ha/yr
                              Fgw = 1 + 0.2/80 x P2O5_sl
  run-off to surface water   Pro = Prol x Fro,  Prol = 0.175 kg P/ha/yr
                              Fro = 1 + 0.2/80 x P2O5_min + 0.7/80 x P2O5_sl + 0.4/80 x P2O5_man
  erosion to surface water   Per = Ser x Pcl x Fr x Ferw
                              Pcl = 0.00095 kg P/kg soil, Fr = 1.86, Ferw = 0.2

P2O5_min / _sl / _man = kg P2O5/ha/yr applied as mineral fertiliser / slurry / solid manure.
Booked as in ecoinvent: Pgw and Pro as "Phosphate" (PO4, ground water / surface water), Per
as "Phosphorus" (surface water). Pgwl and Prol are Swiss average losses; applying them to
African fields is the ecoinvent / WFLDB convention but a screening choice (disclosed).

Erosion needs the soil loss Ser. RUSLE (Renard et al. 1997, USDA Agriculture Handbook 703)
A = R x K x LS x C x P (t/ha/yr) is evaluated only when R, K, LS and C are supplied (region
attributes `rusle_r`, `rusle_k`, `rusle_ls`, `rusle_c`, or `assessment["erosion"]`), or a
soil loss `soil_loss_t_per_ha_per_year` is given. No citable default R/K/LS/C exists for the
regions served, so otherwise erosion P is NOT modelled and that is disclosed. The support
practice factor P comes from conservation_practices + slope (Wischmeier & Smith 1978, USDA
Agriculture Handbook 537, Table 14, contouring); C-factor credits for mulching / cover crops /
no-till are not applied (no generic citable values; disclosed).

Fertiliser P2O5 content: declared N-P-K grade (second number) wins; otherwise standard
grades from FAO & IFA (2000) "Fertilizers and their use", 4th ed.: DAP 18-46-0, MAP 11-52-0,
TSP 46 % P2O5, SSP 16-20 % P2O5 (18 % midpoint used, disclosed); undeclared compound "NPK"
15-15-15 (same assumption as the Rust kernel's N lookup, african_lca_backend field.rs).
Local helper: engine/inputs.py exposes no nutrient-grade helper.
"""
from __future__ import annotations

# --- SALCA-P constants (Prasuhn 2006; Nemecek & Kägi 2007 ecoinvent report 15) -----------
PGWL_ARABLE = 0.07        # kg P/ha/yr, average leaching to ground water, arable land
PROL_ARABLE = 0.175       # kg P/ha/yr, average run-off to surface water, open arable land
FGW_SLURRY = 0.2 / 80.0   # Fgw slurry term, per kg P2O5/ha
FRO_MIN = 0.2 / 80.0      # Fro mineral-fertiliser term, per kg P2O5/ha
FRO_SLURRY = 0.7 / 80.0   # Fro slurry term, per kg P2O5/ha
FRO_MANURE = 0.4 / 80.0   # Fro solid-manure term, per kg P2O5/ha
P_SOIL = 0.00095          # Pcl, kg P/kg top soil
ENRICHMENT = 1.86         # Fr, P enrichment of eroded soil (Wilke & Schaub 1996, via report 15)
FERW = 0.2                # Ferw, fraction of eroded soil reaching surface water
SRC_SALCA = ("SALCA-P, Prasuhn (2006); ecoinvent report No. 15, Nemecek & Kägi (2007); "
             "ecoinvent v3, Nemecek & Schnetzer (2011)")

# Molar masses (IUPAC 2013 standard atomic weights): P 30.974, O 15.999.
P_TO_PO4 = 94.971 / 30.974
P2O5_TO_P = 2 * 30.974 / 141.943

SRC_FAO_IFA = "FAO & IFA (2000) Fertilizers and their use, 4th ed., Rome"
# keyword -> (kg P2O5 / kg product, source). Order matters (most specific first).
P2O5_TYPE_DEFAULTS = (
    (("diammonium phosphate", "di-ammonium phosphate", "dap"), 0.46, f"{SRC_FAO_IFA}: DAP 18-46-0"),
    (("monoammonium phosphate", "mono-ammonium phosphate", "map"), 0.52, f"{SRC_FAO_IFA}: MAP 11-52-0"),
    (("triple superphosphate", "triple super phosphate", "tsp"), 0.46, f"{SRC_FAO_IFA}: TSP 46% P2O5"),
    (("single superphosphate", "single super phosphate", "superphosphate", "ssp"), 0.18,
     f"{SRC_FAO_IFA}: SSP 16-20% P2O5, 18% midpoint"),
    (("npk", "compound"), 0.15, "NPK 15-15-15 (grade not declared; Rust kernel assumption)"),
)
NO_P_WORDS = ("urea", "ammonium nitrate", "calcium ammonium", "ammonium sulphate",
              "ammonium sulfate", "muriate", "potash", "potassium", "lime", "dolomite",
              "gypsum", "inoculant", "bio-fert", "biofert")
ORGANIC_WORDS = ("organic", "manure", "compost", "poultry", "dung", "slurry")

# Wischmeier & Smith (1978) Table 14, P values for contouring by land slope (%).
# Upper slope bound -> P (classes 1-2, 3-8, 9-12, 13-16, 17-20, 21-25 %). Outside 1-25 %
# contouring has no tabulated effect (P = 1).
CONTOUR_P = ((2.0, 0.60), (8.0, 0.50), (12.0, 0.60), (16.0, 0.70), (20.0, 0.80), (25.0, 0.90))
SRC_PFACTOR = "Wischmeier & Smith (1978) USDA Agriculture Handbook 537, Table 14 (contouring)"


def _has_word(text: str, word: str) -> bool:
    return word in "".join(c if c.isalnum() else " " for c in text).split()


def _match(text: str, keys) -> bool:
    return any((_has_word(text, k) if len(k) <= 4 else k in text) for k in keys)


def p2o5_fraction(fertilizer_type: str | None, npk_ratio: str | None) -> tuple[float, str, str]:
    """(kg P2O5 per kg product, kind 'min'|'man'|'sl', source). Unknown P content -> 0."""
    t = str(fertilizer_type or "").strip().lower()
    organic = any(w in t for w in ORGANIC_WORDS)
    kind = ("sl" if ("slurry" in t or "liquid" in t) else "man") if organic else "min"
    if npk_ratio:
        parts = [p for p in str(npk_ratio).replace(":", "-").replace("/", "-").split("-")]
        if len(parts) >= 2:
            try:
                v = float(parts[1])
                if 0.0 <= v <= 100.0:
                    return v / 100.0, kind, "declared N-P-K grade"
            except ValueError:
                pass
    if organic:
        return 0.0, kind, "organic fertiliser without declared grade: P not counted"
    for keys, frac, src in P2O5_TYPE_DEFAULTS:
        if _match(t, keys):
            return frac, kind, src
    if any(w in t for w in NO_P_WORDS):
        return 0.0, kind, "straight N/K source or liming material: no P"
    return 0.0, kind, "unrecognised fertiliser type: P content unknown, not counted"


def p2o5_by_crop(assessment: dict) -> tuple[dict, list[str]]:
    """{food index: {'min','man','sl'} kg P2O5/ha/yr} following the CONTRACT rate basis:
    kg product/ha per application x applications_per_season x crops_per_year, rows filtered
    by crop_ids ([] = all crops). Returns (per-crop dict, notes)."""
    fert = ((assessment.get("management_practices") or {}).get("fertilization")) or {}
    if isinstance(fert, list):
        fert = {"fertilizer_applications": fert}
    apps = fert.get("fertilizer_applications") or [] if isinstance(fert, dict) else []
    foods = assessment.get("foods") or []
    out = {i: {"min": 0.0, "man": 0.0, "sl": 0.0} for i in range(len(foods))}
    notes: list[str] = []
    for app in apps:
        if not isinstance(app, dict):
            continue
        ftype = str(app.get("fertilizer_type") or "")
        if ftype.strip().lower() == "none":
            continue
        rate = max(float(app.get("application_rate") or 0.0), 0.0)
        n = app.get("applications_per_season")
        n = 1 if n is None else max(int(n), 0)
        if rate <= 0 or n == 0:
            continue
        frac, kind, src = p2o5_fraction(ftype, app.get("npk_ratio"))
        if frac <= 0:
            if "unrecognised" in src or "organic" in src:
                notes.append(f"phosphorus: fertiliser '{ftype}': {src}")
            continue
        ids = [str(i) for i in (app.get("crop_ids") or [])]
        for i, food in enumerate(foods):
            if ids and str(food.get("id")) not in ids:
                continue
            cpy = max(int(food.get("crops_per_year") or 1), 1)
            out[i][kind] += rate * n * cpy * frac
        if src != "declared N-P-K grade":
            notes.append(f"phosphorus: '{ftype}' assumed {frac*100:g}% P2O5 ({src})")
    return out, notes


def support_practice_factor(practices, slope_pct: float | None) -> tuple[float, str]:
    """RUSLE support-practice factor P from conservation_practices (CONTRACT keywords
    'terrac', 'contour', 'bund'/'ridge'). Terraces and contour bunds/ridges are contour
    farmed; their effect via shorter slope length (LS) is not modelled (conservative)."""
    ps = [str(p).lower() for p in (practices or [])]
    contoured = any(k in p for p in ps for k in ("terrac", "contour", "bund", "ridge"))
    if not contoured:
        return 1.0, "no support practice (P = 1)"
    if slope_pct is None:
        return 1.0, "support practice declared but slope unknown: P = 1 (Table 14 needs slope)"
    if slope_pct < 1.0 or slope_pct > CONTOUR_P[-1][0]:
        return 1.0, f"slope {slope_pct:g}% outside {SRC_PFACTOR}: P = 1"
    for upper, p in CONTOUR_P:
        if slope_pct <= upper:
            return p, f"contour farming at {slope_pct:g}% slope: P = {p} ({SRC_PFACTOR})"
    return 1.0, "P = 1"


def _erosion_inputs(assessment: dict, region) -> dict:
    e = dict(assessment.get("erosion") or {})
    for k in ("rusle_r", "rusle_k", "rusle_ls", "rusle_c", "slope_pct", "soil_loss_t_per_ha_per_year"):
        if e.get(k) is None and getattr(region, k, None) is not None:
            e[k] = getattr(region, k)
    return e


def soil_loss(assessment: dict, region) -> tuple[float | None, str]:
    """(soil loss t/ha/yr or None, explanation)."""
    e = _erosion_inputs(assessment, region)
    if e.get("soil_loss_t_per_ha_per_year") is not None:
        return float(e["soil_loss_t_per_ha_per_year"]), "declared soil loss"
    if all(e.get(k) is not None for k in ("rusle_r", "rusle_k", "rusle_ls", "rusle_c")):
        sm = ((assessment.get("management_practices") or {}).get("soil_management")) or {}
        p, pwhy = support_practice_factor(sm.get("conservation_practices"), e.get("slope_pct"))
        a = float(e["rusle_r"]) * float(e["rusle_k"]) * float(e["rusle_ls"]) * float(e["rusle_c"]) * p
        return a, f"RUSLE A = R x K x LS x C x P (Renard et al. 1997); {pwhy}"
    return None, ("erosion P not modelled: no soil-loss estimate or RUSLE R/K/LS/C inputs "
                  "for this region (no citable defaults)")


def field_p_losses(assessment: dict, region=None) -> tuple[dict, list[str]]:
    """Farm totals (kg/yr): {'po4_groundwater', 'po4_surface', 'p_erosion_surface',
    'p_leach', 'p_runoff', 'p_erosion' (as P), 'area_ha'} and notes."""
    foods = assessment.get("foods") or []
    p2o5, notes = p2o5_by_crop(assessment)
    ser, ser_why = soil_loss(assessment, region)
    leach = runoff = erosion = area_tot = 0.0
    for i, food in enumerate(foods):
        area = float(food.get("area_allocated") or 0.0)
        if area <= 0:
            continue
        area_tot += area
        f = p2o5[i]
        leach += PGWL_ARABLE * (1.0 + FGW_SLURRY * f["sl"]) * area
        runoff += PROL_ARABLE * (1.0 + FRO_MIN * f["min"] + FRO_SLURRY * f["sl"]
                                 + FRO_MANURE * f["man"]) * area
        if ser is not None:
            erosion += ser * 1000.0 * P_SOIL * ENRICHMENT * FERW * area
    out = {"p_leach": leach, "p_runoff": runoff, "p_erosion": erosion,
           "po4_groundwater": leach * P_TO_PO4, "po4_surface": runoff * P_TO_PO4,
           "p_erosion_surface": erosion, "area_ha": area_tot,
           "erosion_modelled": ser is not None}
    if area_tot > 0:
        notes.append(
            f"field phosphorus (SALCA-P screening, Swiss average base losses applied as in "
            f"ecoinvent/WFLDB): leaching {leach:.3g} kg P, run-off {runoff:.3g} kg P"
            + (f", erosion {erosion:.3g} kg P ({ser_why})" if ser is not None else f"; {ser_why}")
            + f" on {area_tot:g} ha ({SRC_SALCA}); compost P not counted (no cited P content)")
    return out, notes
