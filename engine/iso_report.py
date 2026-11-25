#!/usr/bin/env python3
"""
iso_report.py — build a deterministic, data-backed ISO 14040/14044 report from the real
assessment output, written to read like a person wrote it and formatted to be
ISO-conformant and review-ready for external / public communication.

Structure follows CSIR LCA Guideline 4 (Templates for LCA Reports and Critical Reviews,
2024) and the OCP LCA SOP, both built on ISO 14044 and ISO/TS 14071:
  document control, goal, scope, inventory, impact assessment, interpretation,
  critical review, references.

Integrity rule: a report meant for public or external communication needs an independent
critical review by a qualified panel before it can be shared (ISO 14044 and ISO/TS 14071).
This generator does not conduct that review, so the report is written as a finished,
ISO-based draft with the critical review marked as required and still to be done, and the
review statement left blank until a real panel signs it off. Every element is filled from
the actual assessment, and nothing is claimed that the data or the process cannot support.
"""
from __future__ import annotations

try:  # GWP basis statement (one basis per method, values read from the store)
    from .gwp_basis import statement as _gwp_statement
except ImportError:
    from gwp_basis import statement as _gwp_statement

from datetime import datetime, timezone

STANDARD = "ISO 14040:2006, ISO 14044:2006 and ISO/TS 14071:2024"
GENERATOR = "Green Means Go LCA Engine (McGill)"
VERSION = "1.0 (draft, pending independent critical review)"

RELATIVE_EXPRESSION = (
    "These impact figures are relative indicators, not absolute measurements. As the ISO "
    "standards require us to state, they do not predict actual harm to human health or to "
    "ecosystems, whether any safety threshold has been crossed, or real-world risk.")


def _pct(part, whole):
    return (100.0 * part / whole) if whole else None


def _fmt_gsd(gsd) -> str:
    """Format a study-aggregate geometric SD for prose, tolerating a missing value."""
    try:
        return f"{float(gsd):.2f}"
    except (TypeError, ValueError):
        return "n/a"


def _data_quality_scorecard(matches: list, unlinked_notes: list, region_name: str) -> tuple[str, list]:
    """Derive a pedigree-style data-quality assessment (Weidema indicators) from the ACTUAL
    matches and coverage, instead of asserting a rating. Returns (overall, indicators)."""
    matched = [m for m in matches if m.get("matched")]
    n, nm = len(matches), len(matched)
    rn = (region_name or "").lower()
    loc = lambda m: (m.get("location") or "").lower()

    # Completeness — how much of the declared inventory is actually represented.
    if n == 0:
        completeness = ("Good", "No purchased inputs to match; on-farm emissions modelled directly.")
    elif nm == n and not unlinked_notes:
        completeness = ("Good", f"All {n} purchased inputs matched to a background dataset; no unlinked flows.")
    elif nm >= 0.7 * n:
        completeness = ("Fair", f"{nm} of {n} inputs matched"
                        + (f"; {len(unlinked_notes)} flow(s) unlinked." if unlinked_notes else "."))
    else:
        completeness = ("Limited", f"only {nm} of {n} inputs matched to a dataset.")

    # Geographical representativeness — region-specific data vs global/RoW proxies. Match the
    # region name as a whole token (or prefix), so "Ghana"/"Canada" count but a stray substring
    # ("ca" inside "africa") does not.
    def _region_specific(m):
        l = loc(m)
        return bool(rn) and (l == rn or l.startswith(rn) or rn in l.replace(",", " ").split())
    region_hits = sum(1 for m in matched if _region_specific(m))
    frac_geo = (region_hits / nm) if nm else 0.0
    if frac_geo >= 0.5:
        geographical = ("Good", f"{region_hits} of {nm} datasets are specific to {region_name}.")
    elif region_hits > 0:
        geographical = ("Fair", f"{region_hits} of {nm} datasets are {region_name}-specific (e.g. the grid); "
                        f"the rest use global/Rest-of-World proxies where no {region_name} dataset exists.")
    else:
        geographical = ("Limited", "no region-specific background datasets were available; all use global/Rest-of-World proxies.")

    # Technological representativeness — specific vs generic/unspecified datasets.
    proxy = sum(1 for m in matched if any(k in (m.get("matched") or "").lower()
                for k in ("unspecified", "market for compost")))
    if proxy == 0:
        technological = ("Good", "Representative, specific datasets used for every input.")
    elif proxy <= 0.3 * max(nm, 1):
        technological = ("Fair", f"{proxy} input(s) modelled with a generic/unspecified dataset (e.g. pesticide or compost).")
    else:
        technological = ("Limited", f"{proxy} of {nm} inputs modelled with generic/unspecified datasets.")

    temporal = ("Good", "The background data is recent (ecoinvent 3.11 and the IPCC 2019 Refinement). "
                "The year of the farm's own activity data is not recorded, so its currency is taken on trust.")
    reliability = ("Fair", "Field emissions are modelled with IPCC Tier 1 factors, not measured on site; "
                   "purchased inputs are matched by assisted retrieval and not independently verified.")

    indicators = [("Reliability", *reliability), ("Completeness", *completeness),
                  ("Temporal representativeness", *temporal),
                  ("Geographical representativeness", *geographical),
                  ("Technological representativeness", *technological)]
    rate = {"Good": 3, "Fair": 2, "Limited": 1}
    avg = sum(rate[r] for _, r, _ in indicators) / len(indicators)
    overall = "Good" if avg >= 2.6 else "Medium" if avg >= 1.8 else "Limited"
    return overall, [{"indicator": i, "rating": r, "basis": b} for i, r, b in indicators]


def _flow_label(r: dict) -> str:
    return _FLOW_PRETTY.get(r.get("name"), r.get("name") or "flow")


_FLOW_PRETTY = {"N2O": "Dinitrogen monoxide (N2O), air", "CO2": "Carbon dioxide, fossil, air (urea / liming)",
                "CH4_bio": "Methane, biogenic, air", "CH4": "Methane, air",
                "NO3": "Nitrate, water", "land_occ": "Occupation, annual crop",
                "water": "Water", "NH3": "Ammonia, air", "NOx": "Nitrogen oxides, air",
                "PO4": "Phosphate, water", "P": "Phosphorus, water",
                "CO_bio": "Carbon monoxide, non-fossil, air (residue burning)",
                "NMVOC": "NMVOC, air (residue burning)", "PM25": "Particulates, < 2.5 um, air (residue burning)"}


def ranked_inventory(inv: dict, engine, total_kg: float, top_n: int = 30,
                     max_flows: int = 4000) -> dict:
    """Inventory table ranked by each flow's contribution to the method's single score
    (each flow characterised on its own with the study's method, normalised and weighted
    exactly like the headline score), not by raw amount across mixed units. Falls back to
    amount ranking when the engine cannot characterise flows."""
    try:
        from .adapter import MIDPOINT_MAP, single_score, _flow_meta
    except ImportError:
        from adapter import MIDPOINT_MAP, single_score, _flow_meta
    per_kg = total_kg or 1.0
    q = getattr(engine, "q", None)
    method = getattr(engine, "method", "") or ""
    scored = []
    ranked_by = "amount (fallback: flows could not be characterised individually)"
    if q is not None and hasattr(q, "characterize_flows") and inv:
        try:
            cands = sorted(inv.items(), key=lambda kv: -abs(kv[1].get("amount") or 0.0))[:max_flows]
            dummy = {"low": 0.0, "high": 0.0, "calibrated": False, "basis": ""}
            for uid, r in cands:
                if not r.get("amount"):
                    continue
                imp = q.characterize_flows({uid: r}, method) or {}
                mids = {}
                for c, v in imp.items():
                    m = MIDPOINT_MAP.get(c)
                    if m:
                        mids[m[0]] = {"value": (v.get("value") or 0.0) / per_kg}
                _, meta = single_score(mids, {}, method, bands=dummy)
                pe = meta.get("person_equivalents_per_kg") or 0.0
                gw = (mids.get("Global warming") or {}).get("value")
                scored.append((uid, r, pe, gw))
            ranked_by = "contribution to the single score (normalised, method-weighted)"
        except Exception:
            scored = []
    if not scored:
        scored = [(uid, r, None, None) for uid, r in inv.items()]
        scored.sort(key=lambda x: -abs(x[1].get("amount") or 0.0))
    else:
        scored.sort(key=lambda x: -abs(x[2] or 0.0))
    tot = sum(abs(x[2] or 0.0) for x in scored) or None
    rows = scored[:top_n]
    meta = _flow_meta(engine, [uid for uid, *_ in rows])
    return {
        "basis": "per kilogram of crop at the farm gate",
        "ranked_by": ranked_by,
        "n_flows_total": len(inv),
        "n_shown": len(rows),
        "flows": [{"flow": _flow_label(r), "uid": uid,
                   "compartment": (meta.get(uid) or {}).get("compartment"),
                   "amount": (r.get("amount") or 0.0) / per_kg, "unit": r.get("unit"),
                   "single_score_upt": (pe * 1e6 if pe is not None else None),
                   "share_of_single_score": ((abs(pe) / tot) if (pe is not None and tot) else None),
                   "global_warming_kg_co2e": gw}
                  for uid, r, pe, gw in rows],
    }


def _boundary_from_inputs(matches: list, notes: list) -> tuple[list, list, dict]:
    """System-boundary text generated from the inputs ACTUALLY in this run's product system
    (matched input rows by kind / name, and run notes)."""
    rows = [m for m in matches if m.get("matched")]
    kinds = {}
    for m in rows:
        kinds.setdefault((m.get("kind") or "other").lower(), []).append(m)
    names = " ".join(str(m.get("input") or "").lower() for m in rows)

    def _has(*keys):
        return any(k in names for k in keys)

    included, excluded = [], []
    flags = {
        "input_transport": any("transport of inputs" in str(m.get("input") or "").lower() for m in rows),
        "market_transport": any("first point of sale" in str(m.get("input") or "").lower()
                                or "to market" in str(m.get("input") or "").lower() for m in rows),
        "seed": "seed" in kinds or _has("seed"),
        "packaging": "packaging" in kinds or _has("packaging", "sack", "bag"),
        "diesel": _has("diesel", "machinery", "tractor"),
        "electricity": "electricity" in kinds or _has("electric", "grid"),
        "fertiliser": "fertiliser" in kinds,
        "pesticide": "pesticide" in kinds,
        "compost": "compost" in kinds,
        "irrigation": "irrigation_energy" in kinds or "water" in kinds,
        "lime": _has("lime", "limestone", "dolomite"),
        "refrigerant_topup": "refrigerant" in kinds,
        "storage_refrigerant": any("refrigerant" in (n or "").lower() and "leakage" in (n or "").lower()
                                   for n in notes),
    }
    if flags["fertiliser"]:
        included.append("Production of the mineral fertilisers applied (matched background datasets; "
                        "market datasets already include average transport to the regional market).")
    if flags["lime"]:
        included.append("Production of the agricultural lime (limestone / dolomite) applied.")
    if flags["pesticide"]:
        included.append("Production of the pesticide active ingredients applied.")
    if flags["compost"]:
        included.append("Production of purchased compost.")
    if flags["seed"]:
        included.append("Production of the seed or planting material sown.")
    if flags["diesel"]:
        included.append("Diesel burned in field operations, through ecoinvent's 'diesel, burned in "
                        "agricultural machinery' dataset, which carries the machinery's manufacture, "
                        "maintenance and shed per unit of fuel. Machinery is included ONLY through this "
                        "dataset; no separate machinery inventory is added.")
    else:
        excluded.append("Farm machinery: no fuel use was declared or estimated, so machinery "
                        "manufacture and use are not represented.")
    if flags["electricity"]:
        included.append("Grid electricity: generation and transmission for the region's grid mix.")
    if flags["irrigation"]:
        included.append("Irrigation: water withdrawal and, for pumped systems, pumping energy.")
    if flags["packaging"]:
        included.append("Packaging of the harvest leaving the farm.")
    else:
        excluded.append("Packaging of the harvest (none declared).")
    if flags["refrigerant_topup"]:
        included.append("Production of the refrigerant topped up to replace cold-storage leakage.")
    if flags["input_transport"]:
        included.append("Transport of bought-in inputs to the farm (road, tkm; 230 km default unless the "
                        "farmer gave a distance), applied only to inputs matched to PRODUCTION datasets; "
                        "inputs matched to 'market for' datasets already carry average transport and get "
                        "no extra transport.")
    else:
        excluded.append("Transport of bought-in inputs from the regional market to this farm (only the "
                        "transport already inside the background market datasets is counted).")
    if flags["market_transport"]:
        included.append("Transport of the harvest to the first point of sale (boundary extended).")
    if flags["storage_refrigerant"]:
        included.append("Refrigerant leakage from on-farm cold storage (charge x IPCC 2006 Vol 3 Ch 7 "
                        "Table 7.9 operating emission factor x GWP100 of the method's basis).")
    excluded.append("Everything after the farm gate (or after the first point of sale where "
                    "declared): processing, storage off-farm, distribution, use and disposal.")
    excluded.append("Buildings and other capital goods beyond what the background datasets embed "
                    "(ecoinvent cut-off).")
    return included, excluded, flags


def build_iso_report(assessment: dict, result, engine, midpoints: dict,
                     single_meta: dict, total_kg: float, per_crop=None,
                     assessment_id: str | None = None, intended_for_public: bool = True,
                     uncertainty: dict | None = None, sensitivity: dict | None = None) -> dict:
    """Assemble an ISO-conformant, review-ready report from the validated assessment.

    intended_for_public=True (default): the report is written for external or public use,
    which means an independent critical review is required and still to be done.
    """
    region = getattr(engine, "region", None)
    region_name = getattr(region, "name", result.region or "the region")
    ef1 = getattr(region, "ipcc_n2o_ef1", None)
    ef1_scale = assessment.get("ipcc_ef1_scale")
    try:
        ef1_scale_f = float(ef1_scale) if ef1_scale is not None else None
    except (TypeError, ValueError):
        ef1_scale_f = None
    effective_ef1 = (ef1 * ef1_scale_f) if (ef1 and ef1_scale_f is not None) else ef1
    method = engine.method
    is_hierarchist = "(H)" in method
    foods = assessment.get("foods") or []
    multi_crop = bool(per_crop) and len(foods) > 1
    # different products (not just several plots of one crop): no product per-kg headline
    multi_product = len({(f.get("name") or "").strip().lower() for f in foods}) > 1

    fp = assessment.get("farm_profile") or {}
    farmer = fp.get("farmer_name")
    farm = fp.get("farm_name") or assessment.get("company_name") or "the farm"
    commissioner = f"{farmer}, {farm}" if farmer else farm
    certifications = fp.get("certifications") or []
    # post-harvest losses, only where the farmer actually reported them (percent, 0-100).
    # Per kg of MARKETABLE crop the burden rises by 1/(1-L) - 1, not by L.
    loss_rows = []
    for f in foods:
        L = f.get("post_harvest_losses")
        try:
            L = float(L) if L is not None else None
        except (TypeError, ValueError):
            L = None
        if L is not None and 0 < L < 100:
            loss_rows.append((f.get("name", "crop"), L, 100.0 * (1.0 / (1.0 - L / 100.0) - 1.0)))
    _mp = assessment.get("management_practices") or {}
    _sm = _mp.get("soil_management") or {}
    # Report a thing as INCLUDED only when it was actually modelled/matched for this run,
    # not merely declared. Pesticides count only if a match succeeded; compost N2O only if a
    # rate was given (that is what field_model._compost_n2o requires).
    _matches_all = result.input_matches or []
    has_pesticide = any(m.get("kind") == "pesticide" and m.get("matched") for m in _matches_all)
    # field N2O from compost fires only when a rate is given; the supply-chain burden fires
    # only when a purchased-compost dataset was actually matched. Keep them separate so each
    # claim is gated on what was really modelled.
    compost_n_modelled = bool(_sm.get("uses_compost")) and bool(_sm.get("compost_application_rate"))
    purchased_compost = any(m.get("kind") == "compost" and m.get("matched") for m in _matches_all)
    # what background databases were actually used, and whether any input relied on defaults
    _sources_used = {m.get("source") for m in _matches_all if m.get("matched") and m.get("source")}
    uses_agribalyse = any("agribalyse" in (s or "").lower() for s in _sources_used)
    uses_defaults = (
        any("estimated" in (n or "").lower() or "default" in (n or "").lower()
            for n in (result.notes or []))
        or any(m.get("estimated") for m in _matches_all)
    )
    # read the crop list naturally: "maize", "maize and cassava", "maize, cassava and yam"
    _names = [f.get("name", "crop").lower() for f in foods]
    if len(_names) > 1:
        crop_names = ", ".join(_names[:-1]) + " and " + _names[-1]
    else:
        crop_names = _names[0] if _names else "crop production"

    # ---- categories, matches, contributions (all from real data) ----
    categories = [{"name": name, "unit": (m.get("unit") or "").replace(" per kg", "")}
                  for name, m in midpoints.items() if name != "Biodiversity loss"]
    matches = result.input_matches or []
    matched = [m for m in matches if m.get("matched")]
    unlinked_notes = [n for n in (result.notes or []) if "no match" in n or "unlinked" in n]
    contributions = single_meta.get("contributions") or {}
    top_cats = sorted(contributions.items(), key=lambda kv: -kv[1])[:3]

    significant = [f"{cat} is behind about {v*100:.0f}% of the overall single score"
                   for cat, v in top_cats if v > 0]
    onf = (result.contribution or {}).get("on_farm", {})
    sup = (result.contribution or {}).get("supply_chain", {})
    clim_f = onf.get("Climate change", {}).get("value", 0.0) or 0.0
    clim_s = sup.get("Climate change", {}).get("value", 0.0) or 0.0
    if (clim_f + clim_s):
        significant.append(
            f"Field emissions make up about {_pct(clim_f, clim_f+clim_s):.0f}% "
            f"of the climate impact, and the inputs the farm buys in make up the other "
            f"{_pct(clim_s, clim_f+clim_s):.0f}%")

    total_kg_safe = total_kg or 1.0

    # Inventory results (openLCA "Inventory Results" tab): the dominant elementary flows in
    # the merged cradle-to-gate inventory, expressed per functional unit. On-farm flows are
    # stored under short kernel keys; give them readable names for the table.
    inv = getattr(result, "inventory", None) or {}
    # Which on-farm field flows are ACTUALLY in the field source (kernel / flowmap keys or
    # store names), so the boundary and reference-flow text list only what was modelled. The
    # merged inventory also holds background flows (e.g. "Ammonia" from fertiliser
    # production), which must not be claimed as field emissions.
    _field_flows = ((getattr(result, "contribution_flows_by_source", None) or {})
                    .get("Field emissions (on-farm)") or {})
    _inv_keys = ({(r.get("name") or "") for r in _field_flows.values()} if _field_flows
                 else {(r.get("name") or "") for r in inv.values()})
    _low_keys = " | ".join(k.lower() for k in _inv_keys)
    has_field_ch4 = "CH4_bio" in _inv_keys or "CH4" in _inv_keys
    _burning = bool({"CO_bio", "NMVOC", "PM25"} & _inv_keys) or "residue burning" in _low_keys
    _has_p = "P" in _inv_keys or "PO4" in _inv_keys or "phosphate" in _low_keys
    _field_subs = [label for present, label in [
        ("N2O" in _inv_keys, "nitrous oxide"),
        (has_field_ch4, "methane"),
        ("NH3" in _inv_keys or "ammonia" in _low_keys, "ammonia"),
        ("NOx" in _inv_keys, "nitrogen oxides"),
        ("CO2" in _inv_keys, "fossil CO2 from urea hydrolysis and liming"),
        ("NO3" in _inv_keys, "nitrate lost to water"),
        (_has_p, "phosphorus lost to water"),
        (_burning, "residue-burning pollutants"),
        ("water" in _inv_keys or "water, well" in _low_keys or "water, river" in _low_keys, "water used"),
        ("land_occ" in _inv_keys, "the land occupied")] if present]
    field_emissions_text = ", ".join(_field_subs) if _field_subs else "field emissions"
    inventory_results = ranked_inventory(inv, engine, total_kg_safe)

    # LCIA results table: every reported midpoint category, per functional unit.
    results_table = [{"category": name, "result": (m.get("value") or 0.0),
                      "unit": (m.get("unit") or "").replace(" per kg", "")}
                     for name, m in midpoints.items()]

    # Contribution analysis (openLCA contribution-tree, lite): share of the climate result
    # by source, so the reader sees which input drove it.
    cbs = getattr(result, "contribution_by_source", None) or {}
    clim = {s: ((imp.get("Climate change") or {}).get("value", 0.0) or 0.0) for s, imp in cbs.items()}
    clim_tot = sum(clim.values())
    contribution_analysis = {
        "indicator": "Climate change (kg CO2-eq)",
        "by_source": sorted(
            [{"source": s, "per_kg": v / total_kg_safe, "share": (v / clim_tot if clim_tot else 0.0)}
             for s, v in clim.items() if v],
            key=lambda x: -x["per_kg"]),
    }

    # reference-flow table (Process / Material, Amount, Source, Adaptation)
    reference_flows = []
    for m in matches:
        name = m.get("matched")            # matched process name, or None
        if not name:
            continue
        amt = m.get("amount")
        unit = m.get("amount_unit") or m.get("ref_unit") or ""
        reference_flows.append({
            "process": f"{m.get('input', 'input')} (modelled as {name})",
            "amount": (f"{amt:g} {unit}".strip() if isinstance(amt, (int, float)) else str(amt or "not stated")),
            "source": m.get("source") or "background database",
            "adaptation": m.get("location") or region_name,
        })
    reference_flows.append({
        "process": f"Field emissions ({field_emissions_text})",
        "amount": "per kilogram of crop",
        "source": "IPCC 2019, Volume 4 (Agriculture and Land Use)",
        "adaptation": f"{region_name}" + (
            f", nitrous-oxide factor {effective_ef1:g} kg N2O-N per kg N"
            + (f" (literature-linked scale {ef1_scale_f:g}× on regional EF1 {ef1:g})"
               if ef1_scale_f is not None and ef1_scale_f != 1.0 and ef1 else "")
            if effective_ef1 else ""
        ),
    })

    # ---- document control ----
    document_control = {
        "title": f"Life Cycle Assessment of {crop_names} grown at {farm} (to the farm gate)",
        "confidentiality": "For external review and public release once the critical review is complete.",
        "commissioner": commissioner,
        "practitioner": GENERATOR,
        "date_of_issue": datetime.now(timezone.utc).date().isoformat(),
        "report_number": assessment_id or "not assigned",
        "version": VERSION,
        "reference_standards": ["ISO 14040:2006", "ISO 14044:2006", "ISO/TS 14071:2024"],
        "farm_certifications": certifications,
    }

    # ---- 1. Goal ----
    if intended_for_public:
        application = ("To share the farm's environmental performance with people outside the "
                       "farm, and to guide practical improvements on the ground.")
        audience = ("People outside the farm who use this information, such as buyers, "
                    "certifiers and programme administrators, and the wider public, along with "
                    "the farm's own operators and advisors.")
        peer = ("Because these results are meant to be shared publicly, the study will go "
                "through an independent critical review before it is published, so the findings "
                "are fair, unbiased and in line with the ISO standards for life cycle assessment.")
    else:
        application = "To support the farm's own decisions and screen for environmental improvements."
        audience = "The farm's operators and advisors, and researchers at Green Means Go and McGill."
        peer = "This study is for internal use, so an independent critical review is not required."
    # ---- 1. Introduction (CSIR Guideline 4 §1) ----
    introduction = {
        "context": (
            f"This report is a life cycle assessment of the {crop_names} grown at {farm} in "
            f"{region_name}, prepared for {commissioner}. It measures the environmental footprint of "
            "what the farm grows and shows where the biggest impacts sit, so the farm can make "
            "improvements and can speak to its performance with evidence behind it."),
        "product_system": (
            f"The product system studied is the on-farm production of {crop_names} at {farm}. It runs "
            "from the inputs used in the field through to the point the crop leaves the farm gate, and "
            "takes in the crops themselves, the fertiliser, fuel, electricity and other inputs the farm "
            "buys in, and the field emissions."),
        "similar_studies": (
            "This is a screening-level study, in keeping with common practice for farm and food life "
            "cycle work. The wider supply chain is built on established published inventories (ecoinvent"
            + (" and, where relevant, Agribalyse" if uses_agribalyse else "")
            + "). To give the headline single score some meaning, the farm's result is placed against a "
            "benchmark set of farm-gate crop products worked out the same way (these set the Low, Moderate "
            "and High bands)."),
    }

    # ---- 2. Goal (CSIR Guideline 4 §2.1) ----
    goal = {
        "goal_statement": (
            f"The goal of this study is to quantify the cradle-to-gate environmental impacts of the "
            f"{crop_names} grown at {farm}, per kilogram of crop at the farm gate, and to identify which "
            "activities contribute the most."),
        "reasons_for_study": (
            f"This study measures the environmental footprint of the {crop_names} grown at "
            f"{farm}, from the inputs used in the field through to the point the crop leaves the "
            "farm. It sets out to show clearly where the largest impacts come from, so the farm "
            "can act on them and can back up its environmental performance with evidence."),
        "intended_application": application,
        "intended_audience": audience,
        "commissioner": commissioner,
        "comparative_assertion_disclosed_to_public": False,
        "public_disclosure_intended": intended_for_public,
        "peer_review_statement": peer,
    }

    # ---- Scope ----
    _eol_note = (" End-of-life recycling does not come into it here, because the boundary stops at "
                 "the farm gate; where the background datasets involve recycled materials, they follow "
                 "ecoinvent's standard cut-off (recycled-content) convention.")
    if multi_crop:
        allocation = (
            "This is an attributional study. Each crop is worked out as its own product on its own "
            "land, and shared farm resources such as fuel and electricity are split between the crops "
            "in proportion to the area each one occupies. Further up the supply chain, any co-products "
            "are handled the way the background database (ecoinvent) handles them. Splitting shared "
            "inputs by area is a practical simplification for a screening study rather than a formal "
            "split by physical or economic value, and it is flagged here as a judgement call." + _eol_note)
    else:
        allocation = (
            "This is an attributional study. There is a single product, so nothing needs to be split "
            "between farm products. Any co-products further up the supply chain are handled the way the "
            "background database (ecoinvent) handles them." + _eol_note)
    _alloc = single_meta.get("allocation") or {}
    _alloc_applied = [a for a in _alloc.values() if a.get("applied")]
    if _alloc_applied:
        allocation += (" Where removed crop residues are sold or fed (a co-product), the crop's burden "
                       "is split between grain and straw by economic allocation (ISO 14044 §4.3.4.2): "
                       + " ".join(a["note"] for a in _alloc_applied))
    _alloc_not = [a["note"] for a in _alloc.values() if not a.get("applied") and a.get("note")]
    if _alloc_not:
        allocation += " " + " ".join(_alloc_not)
    _bnd_in, _bnd_out, _bnd_flags = _boundary_from_inputs(matches, result.notes or [])

    # Soil organic carbon from management (engine/soil_carbon.py, owner E): reported
    # SEPARATELY (ISO 14067), never folded into the headline climate result.
    soc = getattr(result, "soc_management", None)
    if soc is None and isinstance(assessment.get("_engine_meta"), dict):
        soc = assessment["_engine_meta"].get("soc_management")
    if isinstance(soc, dict) and soc.get("booked") and soc.get("value") is not None:
        soc_text = (
            f"Soil carbon from management, reported separately (ISO 14067), not included in the "
            f"headline: {soc['value']:+.0f} {soc.get('unit', 'kg CO2/yr')} "
            f"({soc.get('sign_convention') or '+ = emission, - = removal'}; "
            f"{soc.get('method') or 'IPCC 2019 Tier 1 stock-change'}"
            + (f"; {soc['years_remaining_in_transition']:.0f} years remain in the 20-year transition"
               if isinstance(soc.get("years_remaining_in_transition"), (int, float)) else "") + ").")
    elif isinstance(soc, dict):
        _why = (soc.get("assumptions") or ["inputs for the stock-change calculation were incomplete"])[0]
        soc_text = (f"Soil carbon from management, reported separately (ISO 14067), is not booked for "
                    f"this farm ({_why}); it would not be included in the headline in any case.")
    else:
        soc_text = ("Change in soil organic carbon from tillage, residues and cover cropping is not "
                    "included in the headline; it is reported separately when the inputs for the IPCC "
                    "Tier 1 stock-change method are available.")

    # Climate zone actually used for the IPCC wet/dry factors (D2: classification text in
    # region.field_sources["climate_zone"]).
    _zone = getattr(region, "climate_zone", None) or getattr(result, "climate_zone_used", None)
    _admin = (assessment.get("study_meta") or {}).get("admin_region")
    _zone_src = (getattr(region, "field_sources", None) or {}).get("climate_zone")
    climate_text = ((f"IPCC climate zone used for the field factors: {_zone}"
                     + (f" (from the farm's admin region '{_admin}')" if _admin else
                        " (national default; no admin region given)") + "."
                     + (f" Classification: {_zone_src}" if isinstance(_zone_src, str) and _zone_src else ""))
                    if _zone else None)

    # Publication gate: background datasets flagged for review (incl. excluded rows).
    _nr = [m for m in matches if m.get("needs_review")]
    _nr_flag = bool(getattr(result, "needs_review", False)) or bool(_nr)
    needs_review_text = (
        (f"{len(_nr)} input(s) were matched to background datasets that are flagged for review"
         + (f" ({', '.join(str(m.get('input')) for m in _nr[:5])})" if _nr else "")
         + "; the report stays a draft and should not be published until those choices are confirmed.")
        if _nr_flag else None)

    # Per-crop results (true per-crop product systems), when provided.
    per_crop_results = []
    for label, res_c in (per_crop or {}).items():
        imp = getattr(res_c, "impacts", None) or {}
        gw = next((v.get("value") for k, v in imp.items() if k == "Climate change"), None)
        f_match = next((f for f in foods if label.startswith(f"{f.get('name', 'crop')} (")), {})
        kg = f_match.get("quantity_kg")
        per_crop_results.append({
            "crop": label, "quantity_kg": kg, "area_ha": f_match.get("area_allocated"),
            "global_warming_total_kg_co2e": gw,
            "global_warming_per_kg": (gw / kg) if (gw is not None and kg) else None,
        })

    _fu_crops = ", ".join(f.get("name", "crop") for f in foods) or "the crop"
    scope = {
        "approach": "Attributional",
        "product_system": f"The {crop_names} grown at {farm} in {region_name}.",
        "functional_unit": (
            "One kilogram of harvested crop at the farm gate, as weighed by the farmer (fresh "
            "mass as harvested; no moisture standardisation applied)."
            if not multi_product else
            "1 ha of farm area per year, with per-crop results per kg (each crop's fresh mass as "
            "harvested at the farm gate; no moisture standardisation)."),
        "functional_unit_basis": (
            "Every impact figure is scaled to this reference. Moisture basis: the reference flow is "
            "the farmer-reported harvested mass at its as-harvested moisture; it is not converted to a "
            "standard moisture (e.g. 14 % for cereal grain), so comparisons with datasets on a "
            "standardised or dry-matter basis need that conversion first."
            + (f" With several crops ({_fu_crops}) a single per-kilogram figure across different crops "
               "has no meaning, so per-kilogram results are given per crop and the farm as a whole is "
               "reported per hectare; any farm-total per-kilogram figure in the data is a farm "
               "aggregate, not a product footprint." if multi_product else "")),
        "system_boundary": (
            "The study runs from the inputs used in the field through to the point the crop leaves the "
            "farm (cradle to gate). The lists below are generated from the inputs actually included in "
            "this run."),
        "boundary_included": [
            f"The field emissions ({field_emissions_text}), from the IPCC 2019 method and the on-farm inventory.",
            *_bnd_in,
        ],
        "boundary_excluded": _bnd_out,
        "boundary_type": "cradle to gate",
        "cutoff_criteria": (
            "The study uses ecoinvent's standard cut-off approach. The making of buildings and "
            "machinery is already built into the background data, and nothing further is left out "
            "beyond what the database itself excludes."),
        "allocation_procedure": allocation,
        "lcia_method": method,
        "gwp_basis": _gwp_statement(engine, method),
        "perspective": "Hierarchist" if is_hierarchist else "method default",
        "impact_categories": categories,
        "impact_categories_basis": (
            f"All {len(categories)} midpoint categories that could be characterised and mapped for this "
            f"study are reported ({'ReCiPe 2016' if 'ReCiPe' in method else 'Environmental Footprint 3.1'}), "
            "so that no major environmental issue is left out. The ones that matter most for growing crops, "
            "such as climate change, land use, eutrophication and fossil resource use, are among them."),
        "normalization_reference": (
            "ReCiPe 2016 v1.1 normalisation, World 2010, Hierarchist (10 categories in the "
            "equal-weighted sum; toxicity, ozone depletion, ionising radiation and terrestrial ozone "
            "normalised for display only)."
            if "ReCiPe" in method else
            "EF 3.1 global normalisation factors per person (Andreasson et al. 2024, JRC130796, "
            "Table 2) and the EF 3.1 weighting set (Sala et al. 2018, JRC109878), all 16 categories."),
        "weighting_disclosure": single_meta.get("iso_14044_disclosure"),
        "data_requirements": {
            "foreground": ("Information the farm provided about its own activity: the crops and "
                           "areas grown, the type and amount of fertiliser used, and fuel and "
                           "electricity use. Field emissions are calculated from this with the "
                           "IPCC 2019 method, adjusted for the local climate."),
            "background": ("The impacts of making the fertiliser, fuel and electricity (and any pesticides or "
                           "purchased compost) come from the ecoinvent database"
                           + (" and Agribalyse" if uses_agribalyse else "")
                           + ", matched to representative datasets and adjusted to the region wherever a regional "
                           "version exists. Farm machinery is captured through the fuel it burns and is otherwise "
                           "embedded in the background datasets."),
        },
        "assumptions_and_limitations": [f for f in [
            "Field emissions are estimated with standard IPCC 2019 factors adjusted for the region's climate, rather than measured directly on this farm.",
            "Each bought-in input is matched to a representative dataset with assisted search, and the top candidates are kept on record so the choice can be checked.",
            ("The pesticides applied are included through the production of their active ingredients; where a specific ingredient is not in the database, a representative pesticide is used."
             if has_pesticide else None),
            (("Compost or manure is applied, and its organic nitrogen is counted in the field N2O calculation "
              "using IPCC 2019 factors (direct and indirect), with a screening estimate of its nitrogen content."
              + (" The compost is bought in, so its production is also included through a representative compost dataset."
                 if purchased_compost else " The compost is made on the farm, so it carries no purchasing burden."))
             if compost_n_modelled else
             ("Purchased compost is bought in; its production burden is included through a representative compost dataset."
              if purchased_compost else None)),
            soc_text,
            *[(f"Post-harvest losses reported for {n}: {L:g}%. Figures here are per kilogram harvested at "
               f"the farm gate; per kilogram of marketable {n} they would be {inc:.1f}% higher "
               f"(1/(1 - {L/100:g}) - 1).") for n, L, inc in loss_rows],
            climate_text,
            needs_review_text,
            "If a crop grown on the farm is not in the background database, a close stand-in is used, or the farm's own field data on its own, and this is noted.",
        ] if f],
        "value_choices": [
            ("The single score applies the official EF 3.1 normalisation and weighting factors (e.g. "
             "climate change 21.06 %, particulate matter 8.96 %, water use 8.51 %). Weighting is a value "
             "choice. " if "EF" in method and "ReCiPe" not in method else
             "The single score is an equal-weighted sum of ReCiPe-normalised midpoints; ReCiPe 2016 "
             "publishes no weighting, so this is not an official ReCiPe single score. Equal weighting is "
             "a value choice. ")
            + "Per ISO 14044 §4.4.5, weighting is not used for comparative assertions disclosed to the public.",
            ("Results use the hierarchist time perspective." if is_hierarchist else "Results use the method's default time perspective."),
            ("Shared farm inputs are split between crops by area, a screening simplification." if multi_crop else None),
        ],
    }
    scope["value_choices"] = [v for v in scope["value_choices"] if v]

    # ---- 3. Inventory ----
    # Comprehensive on-farm field-emission description: state exactly what the IPCC Tier 1
    # model computes for THIS farm (not just the N2O factor), per CSIR Guideline 4 §3.1.
    climate_zone = getattr(region, "climate_zone", "regional")
    try:
        from .field_model import _has_legume_partner
    except ImportError:
        from field_model import _has_legume_partner
    has_legume = _has_legume_partner(assessment)

    on_farm_flows = [
        ("Nitrous oxide given off directly from all the nitrogen applied (synthetic fertiliser"
         + (", plus any compost or manure)" if compost_n_modelled else ")")
         + (f", worked out with the region's IPCC factor of {effective_ef1:g} kg N2O-N per kg of nitrogen "
            f"for a {climate_zone} climate."
            + (f" (literature-linked scale {ef1_scale_f:g}× applied to regional EF1 {ef1:g})"
               if ef1_scale_f is not None and ef1_scale_f != 1.0 and ef1 else "")
            if effective_ef1 else ".")),
        "A further, indirect share of nitrous oxide from the nitrogen that escapes as gas and later "
        "settles back onto the land, and from the nitrogen washed out by leaching and run-off "
        "(using the IPCC 2019 fractions with the EF4 and EF5 factors).",
    ]
    if "NO3" in _inv_keys:
        on_farm_flows.append("Nitrate washed into water by leaching and run-off (IPCC 2019 FracLEACH), "
                             "from synthetic and organic nitrogen.")
    if "NH3" in _inv_keys or "ammonia" in _low_keys:
        on_farm_flows.append("Ammonia volatilised from fertiliser, compost and manure nitrogen: IPCC 2019 "
                             "Table 11.3 FracGASF by fertiliser type (urea 0.15, ammonium-based 0.08, "
                             "nitrate-based 0.01, ammonium-nitrate-based 0.05, unknown 0.11) and FracGASM "
                             "0.21 for organic N, x 17/14. Application method (incorporation / placement) "
                             "is recorded but not modelled.")
    if "NOx" in _inv_keys:
        on_farm_flows.append("Nitrogen oxides from soil (0.21 x N2O, Nemecek & Schnetzer 2011) and, where "
                             "residues are burnt, from burning (2.5 g/kg d.m., IPCC 2006 Vol 4 Ch 2 Table 2.5).")
    if "CO2" in _inv_keys:
        on_farm_flows.append("Fossil CO2 from urea hydrolysis (IPCC Eq 11.13, 0.20 t C per t urea) and liming "
                             "(Eq 11.12, 0.12 limestone / 0.13 dolomite t C per t), where applied.")
    if _has_p:
        on_farm_flows.append("Phosphorus lost to ground and surface water (SALCA-P, Prasuhn 2006); erosion P "
                             "only where soil-loss inputs exist.")
    if "composting" in _low_keys:
        on_farm_flows.append("Methane and nitrous oxide from composting on the farm (IPCC 2006 Vol 5 Ch 4 Table 4.1).")
    if _burning:
        on_farm_flows.append("Pollutants from burning crop residues: CO 92 g/kg d.m. (IPCC 2006 Vol 4 Ch 2 "
                             "Table 2.5), PM2.5 5.4 and NMVOC 0.5 g/kg d.m. (EMEP/EEA 2019 3.F Table 3-1 Tier 1).")
    if has_field_ch4:
        on_farm_flows.append("Methane from the rice paddy (IPCC 2019 Vol 4 Ch 5 Eq 5.1-5.3: EFc 1.19 kg CH4/ha/day "
                             "x cultivation days (default 113, Table 5.11a) x water-regime SFw (Table 5.12), "
                             "pre-season SFp (Table 5.13) and organic-amendment SFo (Table 5.14); upland rice = 0).")
    on_farm_flows.append("The land the crop occupies while it grows.")

    on_farm_adjustments = []
    if ef1_scale_f is not None and ef1_scale_f != 1.0:
        on_farm_adjustments.append(
            f"A literature-linked EF1 scale of {ef1_scale_f:g}× was applied to the regional "
            f"IPCC direct N2O factor ({ef1:g} -> {effective_ef1:g} kg N2O-N per kg N)."
        )
    elif ef1 and ef1 != 0.01:
        on_farm_adjustments.append(
            f"We use the nitrous-oxide factor for the local climate ({ef1}) rather than the global default of 0.01.")
    if has_legume:
        on_farm_adjustments.append(
            "Legume intercrops/rotations are recorded but give no N2O credit: IPCC 2019 Eq 11.1 counts the "
            "nitrogen actually applied.")
    if compost_n_modelled:
        on_farm_adjustments.append(
            "The nitrogen in the compost or manure applied is counted towards the field nitrous oxide, using a "
            "screening estimate of how much nitrogen it holds.")

    inventory = {
        "data_sources": [f for f in [
            "ecoinvent 3.11, for the wider supply chain",
            "IPCC 2019, Volume 4 (Agriculture and Land Use), for the field emissions",
            ("Agribalyse 3.2, for some of the background datasets" if uses_agribalyse else None),
        ] if f],
        "foreground_data": ("Activity data reported by the farm for the crops and inputs listed"
                            + (", used directly where the operator supplied it and filled with documented "
                               "screening defaults where they did not." if uses_defaults else
                               ", used as supplied by the operator.")),
        "background_data": ("Unit-process datasets from ecoinvent"
                            + (" and Agribalyse" if uses_agribalyse else "")
                            + ", adjusted to the region where a regional version exists. Any stand-in "
                              "datasets are noted."),
        "on_farm_lci": ("We work out the field emissions from the farm's own records: the "
                        "areas cropped, the fertiliser type and rate"
                        + (", and any compost or manure applied" if compost_n_modelled else "")
                        + ". These go through the IPCC 2019 method (Volume 4). The flows we account for, and "
                        "the adjustments we make, are listed below."),
        "on_farm_flows": on_farm_flows,
        "on_farm_adjustments": on_farm_adjustments,
        "calculation_procedure": (
            "The supply chain is solved as a set of linked equations rather than traced step by "
            "step by hand. That is what lets it handle the loops real supply chains contain, for "
            "example the electricity needed to make steel, which is itself needed to make "
            "electricity. Energy is tracked in energy units, and electricity uses the region's grid mix."),
        "reference_flows": reference_flows,
        "inventory_results": inventory_results,
        "inputs_matched": f"{len(matched)} of {len(matches)} bought-in inputs were matched to a background dataset.",
        "pedigree_uncertainty": (
            (f"A pedigree screening Monte Carlo was run with N={uncertainty['n']} draws. Each "
             f"contribution source was scored on the ecoinvent 2013 pedigree matrix (the same "
             f"five indicators as the data-quality scorecard above) to give a per-source "
             f"geometric standard deviation (study aggregate GSD "
             f"{_fmt_gsd(uncertainty.get('gsd'))}); sources were then sampled independently and "
             f"the category totals re-summed. The p5-p95 ranges on each figure come from that "
             f"simulation. Screening scope: characterization-factor uncertainty is not "
             f"propagated, so the ranges reflect inventory magnitude only.")
            if uncertainty
            else (
                "New assessments run a per-source pedigree-matrix screening Monte Carlo by default "
                "(typically N=1000) and report p5-p95 ranges. This saved draft has no Monte Carlo "
                "block attached; re-run the assessment to refresh the uncertainty ranges.")),
        "data_validation": (
            "This refers to the calculation engine, not to a separate check of this farm's numbers. The "
            "engine's method has been benchmarked once against established tools: ecoinvent products match "
            "openLCA to within half a percent, and Agribalyse products match ADEME's published figures to "
            "within five percent. This report's figures follow from that same validated method."),
        "input_matches": matches,
        "notes": result.notes or [],
    }
    if unlinked_notes:
        inventory["unlinked_flows"] = unlinked_notes

    # ---- 4. Impact assessment ----
    lcia = {
        "method": method,
        "rationale": (
            "ReCiPe 2016 is a widely used, internationally recognised method that reports impacts "
            "both at the midpoint level and as damage to health, ecosystems and resources. The "
            "hierarchist perspective is its common default."
            if "ReCiPe" in method else
            "Environmental Footprint 3.1 is the European Commission's reference method for this kind of study."),
        "mandatory_elements": {
            "classification": "Each emission and resource use is sorted into the environmental issue it contributes to.",
            "characterization": f"Each category's result is the sum of every flow multiplied by its characterisation factor, using {method}.",
        },
        "optional_elements": {
            "normalization": ("Results are normalised against the ReCiPe 2016 World 2010 (Hierarchist) per-person reference."
                              if "ReCiPe" in method else
                              "Results are normalised against the EF 3.1 global per-person reference (Andreasson et al. 2024)."),
            "weighting": (
                ("The 16 EF 3.1 categories are weighted with the official EF 3.1 weighting factors "
                 "(Sala et al. 2018) to give the EF single score."
                 if "EF" in method and "ReCiPe" not in method else
                 "Ten normalised ReCiPe midpoints are summed with equal weight. ReCiPe 2016 has no official "
                 "weighting, so this is a screening aggregate, not an official ReCiPe single score.")
                + " " + (single_meta.get("iso_14044_disclosure") or "")),
            "grouping": "Not used.",
        },
        "normalised_results": single_meta.get("normalised_midpoints"),
        "categories_not_mapped": single_meta.get("unmapped_categories") or [],
        "results_are_relative_expressions": RELATIVE_EXPRESSION,
        "n_categories_reported": len(categories),
        "results_table": results_table,
    }

    # ---- 5. Interpretation ----
    dq_overall, dq_indicators = _data_quality_scorecard(matches, unlinked_notes, region_name)
    _worst = [x for x in dq_indicators if x["rating"] != "Good"]
    dqa = (f"Overall data quality is rated {dq_overall.lower()}, scored across the five pedigree "
           "indicators below rather than asserted. "
           + ("It is held back mainly by "
              + ", ".join(f"{x['indicator'].lower()} ({x['rating'].lower()})" for x in _worst)
              + "." if _worst else "All indicators rate good at this screening level."))
    # Region registry values still at the Ghana number (engine/regions.py ghana_inherited).
    _inherited = tuple(getattr(region, "ghana_inherited", None) or ())
    if _inherited and getattr(region, "code", "GH") != "GH":
        dqa += (f" Some {region_name} regional parameters are not yet region-specific and still "
                f"use the Ghana value: {', '.join(_inherited)}.")
    # Sensitivity, derived from the computed contribution analysis rather than asserted. A
    # cradle-to-gate model is linear in the input amounts, so each source's share of a result
    # is also its elasticity: change that source by 1% and the total moves by about its share.
    # The largest contributors are therefore the most sensitive parameters.
    _src = (contribution_analysis or {}).get("by_source") or []
    _mc_n = (uncertainty or {}).get("n")
    _mc_basis = (
        f" A pedigree screening Monte Carlo with N={_mc_n} was also run; each source's "
        f"geometric SD comes from its ecoinvent pedigree-matrix score and sources are sampled "
        f"independently, with category p5-p95 percentiles reported. Characterization-factor "
        f"uncertainty is not included at this screening level."
        if uncertainty else
        " New assessments attach a per-source pedigree-matrix Monte Carlo by default; "
        "this draft has no Monte Carlo block, so re-run to refresh the ranges.")
    if _src:
        sensitivity_text = (
            "Because the calculation is linear in the amounts used, each source's share of a result is "
            "also how sensitive the result is to it: change a source by one percent and the total moves "
            "by about its share. On that basis the climate result is driven mainly by "
            + ", ".join(f"{s['source']} ({s['share']*100:.0f}%)" for s in _src[:3])
            + ", so those are the figures worth getting right first."
            + _mc_basis)
    else:
        sensitivity_text = (
            (f"Each category result carries p5-p95 ranges from a per-source pedigree-matrix "
             f"screening Monte Carlo (N={_mc_n})."
             if uncertainty else
             "New assessments run a per-source pedigree-matrix Monte Carlo by default and report "
             "p5-p95 ranges; this draft has no Monte Carlo block, so re-run to refresh uncertainty."))
    _oat_cases = (sensitivity or {}).get("cases") or []
    _oat_text = ""
    if _oat_cases:
        _parts = [f"{c['case']}: {c['global_warming_change_pct']:+.0f}%"
                  for c in _oat_cases if c.get("global_warming_change_pct") is not None]
        _oat_text = (" One-at-a-time sensitivity on climate change per kg (IPCC 2019 bounds for EF1 "
                     "and FracLEACH, yield ±20 %): " + "; ".join(_parts) + ".")
        _ms = (sensitivity or {}).get("method_sensitivity")
        if _ms and _ms.get("change_pct") is not None:
            _oat_text += (f" Re-characterising the same inventory with {_ms['alternative_method']} "
                          f"changes climate change per kg by {_ms['change_pct']:+.0f}%.")

    # Recommendations driven by the actual hotspots (the top climate contributors), not a
    # fixed list, so the advice points at what is really moving this farm's result.
    def _rec_for(src_name: str):
        s = (src_name or "").lower()
        if "field emission" in s:
            return "Cut the nitrous oxide coming off the field: fine-tune the fertiliser rate, type and timing, and lean on legumes where you can."
        if "diesel" in s or "fuel" in s or "machinery" in s:
            return "Use fuel more efficiently and move to lower-carbon machinery or energy where it is practical."
        if "electric" in s:
            return "Reduce grid electricity use, or switch to a lower-carbon supply."
        if any(k in s for k in ("fertil", "npk", "urea", "dap", "phosphate")):
            return "Match the fertiliser rate and type more closely to what the crop actually needs."
        if "pesticide" in s or "compost" in s:
            return "Review the agrochemicals and amendments used, and cut back what is not needed."
        return None
    _recs = []
    for row in _src[:3]:
        r = _rec_for(row.get("source"))
        if r and r not in _recs:
            _recs.append(r)
    if not _recs:
        _recs.append("Focus on the largest impact category and the activities behind it.")
    _recs.append("Gather more of the farm's own activity data to replace screening defaults and narrow the uncertainty.")

    # Results interpretation tied back to the goal and scope (CSIR Guideline 4 §5, item 1):
    # restate what the study set out to do and what the numbers actually say about it.
    _band = (single_meta.get("band") or "").lower()
    _micro = (single_meta.get("person_equivalents_per_kg") or 0.0) * 1e6
    _topcat = top_cats[0][0] if top_cats else "several categories together"
    _topsrc = _src[0]["source"] if _src else "the field emissions"
    results_interpretation = (
        f"The study set out to measure the cradle-to-gate footprint of the {crop_names} for each kilogram "
        "of crop and to find where that footprint comes from. Against that goal, the overall single score "
        f"({single_meta.get('label') or 'single score'}) works out at about {_micro:.0f} micro-points per "
        "kilogram"
        + (f", a {_band} result next to the benchmark crops. "
           if _band and _band not in ("unavailable", "not banded") else
           "; it is a farm aggregate over several products, not a product footprint, so it is not banded. "
           if _band == "not banded" else
           "; no calibrated benchmark band exists for this method, so it is not banded. ")
        + f"It is driven most by {_topcat}, and on the climate side mainly by {_topsrc}. "
        "So the goal is met on both counts: the footprint is quantified per kilogram at the farm gate, and "
        "the activities that matter most, which are the ones the farm can act on, are clearly identified.")

    # Structured chart data (derived from the same numbers as the prose, so the figures
    # cannot drift from the text). The frontend renders these; if absent it falls back to text.
    _cutoffs = single_meta.get("band_cutoffs") or {}
    single_score_composition = [
        {"category": c, "share": s}
        for c, s in sorted(contributions.items(), key=lambda kv: -kv[1]) if s
    ]
    single_score_gauge = {
        "value": _micro,
        "unit": single_meta.get("unit", "µPt per kg"),
        "band": single_meta.get("band"),
        "low_cut": _cutoffs.get("low"),
        "high_cut": _cutoffs.get("high"),
        "benchmark_min": _cutoffs.get("benchmark_min"),
        "benchmark_max": _cutoffs.get("benchmark_max"),
        "calibrated": _cutoffs.get("calibrated"),
        "basis": single_meta.get("band_basis"),
    }

    interpretation = {
        "results_interpretation": results_interpretation,
        "single_score_gauge": single_score_gauge,
        "single_score_composition": single_score_composition,
        "significant_issues": significant or ["No single contributor clearly stands out."],
        "contribution_analysis": contribution_analysis,
        "data_quality_assessment": dqa,
        "data_quality_scorecard": {"overall": dq_overall, "indicators": dq_indicators},
        "completeness_check": (
            (lambda gaps: (
                f"{len(matched)} of {len(matches)} bought-in inputs were linked to a background dataset. "
                + ("Some declared things are not fully represented: " + "; ".join(gaps) + "."
                   if gaps else "Every input the farm declared is represented, and no flows were left unlinked.")))(
                [g for g in [
                    (f"{len(unlinked_notes)} input(s) could not be matched" if unlinked_notes else None),
                    ("compost is used but no application rate was given, so its field nitrogen is not counted"
                     if (_sm.get("uses_compost") and not _sm.get("compost_application_rate")) else None),
                    ("purchased compost was reported without a rate, so its production burden is not counted"
                     if any("purchased compost reported but no application rate" in (n or "").lower()
                            for n in (result.notes or [])) else None),
                    ("some inputs were given in a different unit from the matched dataset (see notes)"
                     if any("unit mismatch" in (n or "").lower() for n in (result.notes or [])) else None),
                ] if g])),
        "consistency_check": (
            "One impact method and one background database (ecoinvent"
            + (", with Agribalyse for some datasets" if uses_agribalyse else "")
            + ") were applied throughout the supply chain, and the field emissions use the IPCC 2019 "
            "method throughout. Everything is expressed on the same basis of one kilogram of crop at "
            "the farm gate."),
        "sensitivity_and_uncertainty": sensitivity_text + _oat_text,
        "one_at_a_time_sensitivity": (sensitivity or {}).get("cases"),
        "method_sensitivity": (sensitivity or {}).get("method_sensitivity"),
        "soil_carbon_reported_separately": soc if isinstance(soc, dict) else None,
        "soil_carbon_statement": soc_text,
        "per_crop_results": per_crop_results or None,
        "needs_review": _nr_flag,
        "conclusions": [
            (f"Measured per kilogram of crop, the biggest single contributor is {top_cats[0][0]}."
             + (
                 " Land use here means land intensity (square metres occupied per kilogram of "
                 "product), not that using farmland is wrong — higher yield lowers land use per kg."
                 if top_cats and "land" in str(top_cats[0][0]).lower()
                 else ""
             )
             if top_cats else "The impacts are spread fairly evenly across the categories."),
            (f"On the climate side, {_src[0]['source']} is the main driver at about {_src[0]['share']*100:.0f}%, "
             "so that is where the clearest improvement lies."
             if _src else "The clearest chances to improve lie in the largest impact category."),
        ],
        "recommendations": _recs,
        "limitations": [
            "This is a screening study, so it uses standard emission factors and average background data rather than measurements from this farm.",
            ("Data quality is assessed with the five-indicator pedigree scorecard above, and the same "
             f"pedigree scoring drives the screening Monte Carlo (N={_mc_n}): a per-source geometric SD, "
             "sampled independently, propagated to the category ranges shown. Characterization-factor "
             "uncertainty is not propagated at this screening level."
             if uncertainty else
             "Data quality is assessed at the study level using the five-indicator pedigree scorecard above. "
             "A per-source pedigree-matrix Monte Carlo is the default for new assessments; this draft has "
             "no Monte Carlo block, so re-run to attach p5-p95 ranges."),
            ("The single score uses the EF 3.1 weighting factors" if "EF" in method and "ReCiPe" not in method
             else "The single score uses equal weighting (not an official ReCiPe score)")
            + "; weighting is a value choice, best used to compare scenarios of the same crop, and per "
            "ISO 14044 §4.4.5 it is not used for comparative assertions disclosed to the public.",
            (single_meta.get("band_basis") if single_meta.get("band") != "Unavailable" else
             "No calibrated band is available for this method's single score, so none is shown."),
            ("Phosphorus lost through soil erosion is modelled only where soil-loss inputs exist; "
             "otherwise only runoff and leaching P are counted." if _has_p else
             "Field phosphorus losses are not represented in this run."),
            "Heavy metals (e.g. cadmium) from fertilisers reaching soil (SALCA-SM) are not modelled.",
            ("Where the land-use history is unknown, no land-use change is assumed; the PAS 2050-1 "
             "statistical dLUC default is not applied."
             if not any(f.get("land_use_change") for f in foods) else None),
            needs_review_text,
        ],
        "public_disclosure": (
            "This report is written so it can be shared outside the farm. Before it is published, "
            "the results need to pass an independent critical review, set out below, as the ISO "
            "standards require for public environmental claims. Until that review is complete, the "
            "report should be treated as a finished draft rather than a reviewed public claim."
            if intended_for_public else
            "This report is for the farm's own use and is not meant to be shared publicly."),
    }
    interpretation["limitations"] = [x for x in interpretation["limitations"] if x]

    # ---- Critical review ----
    if intended_for_public:
        critical_review = {
            "required": True,
            "status": "Required, and still to be done. The report is a finished draft, ready for review.",
            "trigger": ("The results are meant to be shared publicly as an environmental claim, "
                        "and the ISO standards call for an independent critical review in that case."),
            "reviewer_requirements": [
                "A panel of three independent experts.",
                "Each one should know both life cycle assessment and the subject, in this case crop and farm production.",
                "Each one should be independent, with no business tie to the study and nothing to gain from its outcome.",
            ],
            "review_scope": [
                "The goal and scope", "The inventory", "The impact assessment",
                "The interpretation", "The full report",
            ],
            "process": [
                "Appoint the panel chair, who then helps choose the other two members.",
                "The panel reviews the goal and scope, and the practitioner responds to their comments.",
                "The panel reviews the full study, and the practitioner responds.",
                "The panel reviews once more and, if satisfied, issues its review statement.",
            ],
            "panel": [
                {"role": "Chair", "name": "", "affiliation": "", "status": "To be appointed"},
                {"role": "Reviewer", "name": "", "affiliation": "", "status": "To be appointed"},
                {"role": "Reviewer", "name": "", "affiliation": "", "status": "To be appointed"},
            ],
            "statement": "",  # a real panel fills this in on acceptance; left blank on purpose
        }
    else:
        critical_review = {
            "required": False,
            "status": "Not required, as the study is for internal use only.",
            "trigger": "The study is for the farm's own decisions and makes no public comparison.",
            "reviewer_requirements": [], "review_scope": [], "process": [], "panel": [],
            "statement": ("Checked internally only. The calculation method has been benchmarked "
                          "against openLCA and against ADEME's published results."),
        }

    references = [
        "ISO 14040:2006, Environmental management, Life cycle assessment, Principles and framework.",
        "ISO 14044:2006, Environmental management, Life cycle assessment, Requirements and guidelines.",
        "ISO/TS 14071:2024, Life cycle assessment, Critical review processes and reviewer competencies.",
        "IPCC 2019, Refinement to the 2006 Guidelines, Volume 4 (Agriculture, Forestry and Other Land Use), Chapter 11 on nitrous oxide from managed soils.",
        "ecoinvent 3.11, cut-off system model, background life cycle inventory database.",
        ("ReCiPe 2016 v1.03 (Huijbregts and others), the impact assessment method used here."
         if "ReCiPe" in method else
         "Environmental Footprint (EF) 3.1 (European Commission, JRC), the impact assessment method used here."),
        "CSIR LCA Guideline 4 (Russo and others, 2024), Templates for LCA Reports and Critical Reviews.",
    ]
    if uses_agribalyse:
        references.insert(5, "Agribalyse 3.2 (ADEME), food-product life cycle inventory database.")

    return {
        "standard": STANDARD,
        "disclosure_posture": ("For external and public communication" if intended_for_public
                               else "For internal use"),
        "conformance_status": (
            "This is a finished, ISO-based draft. It still needs an independent critical review "
            "before it can be shared publicly." if intended_for_public else
            "This is an ISO-based report for internal use, and no critical review is required."),
        # Publication gate (audit rec 27): while any background choice needs review the report
        # stays a draft (adapter keeps review_status "draft") and must not be published.
        "review_required": _nr_flag,
        "review_statement": (needs_review_text if _nr_flag else
                             "No background dataset choice is flagged for review."),
        "document_control": document_control,
        "introduction": introduction,
        "goal": goal,
        "scope": scope,
        "inventory_analysis": inventory,
        "impact_assessment": lcia,
        "interpretation": interpretation,
        "critical_review": critical_review,
        "references": references,
    }
