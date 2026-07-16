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


def build_iso_report(assessment: dict, result, engine, midpoints: dict,
                     single_meta: dict, total_kg: float, per_crop=None,
                     assessment_id: str | None = None, intended_for_public: bool = True) -> dict:
    """Assemble an ISO-conformant, review-ready report from the validated assessment.

    intended_for_public=True (default): the report is written for external or public use,
    which means an independent critical review is required and still to be done.
    """
    region = getattr(engine, "region", None)
    region_name = getattr(region, "name", result.region or "the region")
    ef1 = getattr(region, "ipcc_n2o_ef1", None)
    method = engine.method
    is_hierarchist = "(H)" in method
    foods = assessment.get("foods") or []
    multi_crop = bool(per_crop) and len(foods) > 1

    fp = assessment.get("farm_profile") or {}
    farmer = fp.get("farmer_name")
    farm = fp.get("farm_name") or assessment.get("company_name") or "the farm"
    commissioner = f"{farmer}, {farm}" if farmer else farm
    certifications = fp.get("certifications") or []
    # post-harvest losses reported per crop (affects impact per kg of marketable crop)
    losses = [f.get("post_harvest_losses") for f in foods if f.get("post_harvest_losses")]
    avg_loss = (sum(losses) / len(losses)) if losses else 0.0
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
    uses_defaults = any("estimated" in (n or "").lower() or "default" in (n or "").lower()
                        for n in (result.notes or []))
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
            f"Emissions released in the field make up about {_pct(clim_f, clim_f+clim_s):.0f}% "
            f"of the climate impact, and the inputs the farm buys in make up the other "
            f"{_pct(clim_s, clim_f+clim_s):.0f}%")

    total_kg_safe = total_kg or 1.0

    # Inventory results (openLCA "Inventory Results" tab): the dominant elementary flows in
    # the merged cradle-to-gate inventory, expressed per functional unit. On-farm flows are
    # stored under short kernel keys; give them readable names for the table.
    _flow_pretty = {"N2O": "Dinitrogen monoxide (N2O), air", "CO2": "Carbon dioxide, air",
                    "CH4_bio": "Methane, biogenic, air", "CH4": "Methane, air",
                    "NO3": "Nitrate, water", "land_occ": "Occupation, annual crop",
                    "water": "Water", "NH3": "Ammonia, air", "PO4": "Phosphate, water"}
    inv = getattr(result, "inventory", None) or {}
    # Which on-farm field flows are ACTUALLY in the inventory (stored under kernel keys), so
    # the boundary and reference-flow text list only what was modelled. Fuel/grid CO2 is
    # dropped upstream, so field CO2 normally is not present and should not be claimed.
    _inv_keys = {(r.get("name") or "") for r in inv.values()}
    has_field_ch4 = "CH4_bio" in _inv_keys or "CH4" in _inv_keys
    _field_subs = [label for key, label in [
        ("N2O", "nitrous oxide"), ("CH4_bio", "methane"), ("CH4", "methane"),
        ("CO2", "carbon dioxide"), ("NO3", "nitrate lost to water"),
        ("water", "water used"), ("land_occ", "the land occupied")] if key in _inv_keys]
    # de-duplicate (CH4/CH4_bio both map to "methane") while keeping order
    _seen: set = set()
    _field_subs = [s for s in _field_subs if not (s in _seen or _seen.add(s))]
    field_emissions_text = ", ".join(_field_subs) if _field_subs else "field emissions"
    top_flows = sorted(inv.values(), key=lambda r: -abs(r.get("amount") or 0.0))[:30]
    inventory_results = {
        "basis": "per kilogram of crop at the farm gate",
        "n_flows_total": len(inv),
        "n_shown": len(top_flows),
        "flows": [{"flow": _flow_pretty.get(r.get("name"), r.get("name")),
                   "amount": (r.get("amount") or 0.0) / total_kg_safe, "unit": r.get("unit")}
                  for r in top_flows],
    }

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
        "process": f"Field emissions and resource use ({field_emissions_text})",
        "amount": "per kilogram of crop",
        "source": "IPCC 2019, Volume 4 (Agriculture and Land Use)",
        "adaptation": f"{region_name}" + (f", nitrous-oxide factor {ef1} kg N2O-N per kg N" if ef1 else ""),
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
            "buys in, and the emissions given off in the field."),
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
    scope = {
        "approach": "Attributional",
        "product_system": f"The {crop_names} grown at {farm} in {region_name}.",
        "functional_unit": "One kilogram of crop, measured at the farm gate.",
        "functional_unit_basis": (
            "The functional unit is the reference that every impact figure is measured against. Here it "
            "is one kilogram of harvested crop leaving the farm, and all the inputs and emissions are "
            "scaled to that one kilogram."),
        "system_boundary": (
            "The study runs from the inputs used in the field through to the point the crop leaves the "
            "farm (cradle to gate). What sits inside and outside the boundary is set out below."),
        "boundary_included": [
            f"The emissions and resource use in the field ({field_emissions_text}), from the IPCC 2019 method and the on-farm inventory.",
            "The production of the inputs the farm buys in: mineral fertiliser, diesel and grid electricity "
            "(and any pesticides or purchased compost).",
            "The generation and grid transmission of the electricity used.",
            "Farm machinery and other capital goods, as they are already built into the background datasets "
            "(the fuel they burn is counted through the diesel above).",
        ],
        "boundary_excluded": [
            "Transport of the bought-in inputs to this particular farm is not added on top. The background "
            "datasets are taken at the plant or market, so the on-road delivery to the farm gate is not "
            "separately modelled (a screening simplification).",
            "Everything after the farm gate: processing, packaging, storage, distribution, the use of the "
            "crop, and its disposal.",
        ],
        "boundary_type": "cradle to gate",
        "cutoff_criteria": (
            "The study uses ecoinvent's standard cut-off approach. The making of buildings and "
            "machinery is already built into the background data, and nothing further is left out "
            "beyond what the database itself excludes."),
        "allocation_procedure": allocation,
        "lcia_method": method,
        "perspective": "Hierarchist" if is_hierarchist else "method default",
        "impact_categories": categories,
        "impact_categories_basis": (
            f"All {len(categories)} midpoint categories that could be characterised and mapped for this "
            f"study are reported ({'ReCiPe 2016' if 'ReCiPe' in method else 'Environmental Footprint 3.1'}), "
            "so that no major environmental issue is left out. The ones that matter most for growing crops, "
            "such as climate change, land use, eutrophication and fossil resource use, are among them."),
        "normalization_reference": (
            "ReCiPe 2016, using the world-average, hierarchist reference for the single score."
            if "ReCiPe" in method else "The method's own reference set."),
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
            "Change in soil organic carbon from tillage and cover cropping is deliberately excluded. It can be significant, but it is highly uncertain and strongly time-dependent, and common practice (IPCC, PAS 2050) is to exclude it or report it separately rather than fold an unreliable figure into the result.",
            (f"Post-harvest losses average about {avg_loss:.0f}%. Figures here are per kilogram at the farm gate; per kilogram of marketable crop they would be roughly {avg_loss:.0f}% higher."
             if avg_loss else None),
            "If a crop grown on the farm is not in the background database, a close stand-in is used, or the farm's own field data on its own, and this is noted.",
        ] if f],
        "value_choices": [
            "The single score adds up the categories with equal weight. That is a judgement call, and the score is not used to make public claims of being better than another product.",
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
         + (f", worked out with the region's IPCC factor of {ef1} kg N2O-N per kg of nitrogen "
            f"for a {climate_zone} climate." if ef1 else ".")),
        "A further, indirect share of nitrous oxide from the nitrogen that escapes as gas and later "
        "settles back onto the land, and from the nitrogen washed out by leaching and run-off "
        "(using the IPCC 2019 fractions with the EF4 and EF5 factors).",
        "Nitrate washed into water by leaching.",
    ]
    if has_field_ch4:
        on_farm_flows.append("Methane from the flooded rice paddy.")
    on_farm_flows.append("The land the crop occupies while it grows.")

    on_farm_adjustments = []
    if ef1 and ef1 != 0.01:
        on_farm_adjustments.append(
            f"We use the nitrous-oxide factor for the local climate ({ef1}) rather than the global default of 0.01.")
    if has_legume:
        on_farm_adjustments.append(
            "Where a legume is grown alongside the crop, we take 20% off the nitrous oxide from synthetic "
            "fertiliser, because the legume fixes some of its own nitrogen and less bought-in nitrogen is needed. "
            "This is a screening assumption and is flagged as such.")
    if compost_n_modelled:
        on_farm_adjustments.append(
            "The nitrogen in the compost or manure applied is counted towards the field nitrous oxide, using a "
            "screening estimate of how much nitrogen it holds.")

    inventory = {
        "data_sources": [f for f in [
            "ecoinvent 3.11, for the wider supply chain",
            "IPCC 2019, Volume 4 (Agriculture and Land Use), for the emissions released in the field",
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
        "on_farm_lci": ("We work out the emissions released in the field from the farm's own records: the "
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
            "The plus or minus 30 to 40 percent range shown on each category is an indicative screening "
            "figure applied across the board, not a value calculated for this particular farm. A proper, "
            "dataset-by-dataset uncertainty (pedigree or Monte-Carlo) has not been run and would be the "
            "next step for a fuller study."),
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
            "normalization": ("Results are put on a common scale against a world reference to build the single score."
                              if "ReCiPe" in method else "Results are put on a common scale using the method's own reference set."),
            "weighting": "The categories are combined with equal weight to give the single score, which is a judgement call.",
            "grouping": "Not used.",
        },
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
    # Sensitivity, derived from the computed contribution analysis rather than asserted. A
    # cradle-to-gate model is linear in the input amounts, so each source's share of a result
    # is also its elasticity: change that source by 1% and the total moves by about its share.
    # The largest contributors are therefore the most sensitive parameters.
    _src = (contribution_analysis or {}).get("by_source") or []
    if _src:
        sensitivity = (
            "Because the calculation is linear in the amounts used, each source's share of a result is "
            "also how sensitive the result is to it: change a source by one percent and the total moves "
            "by about its share. On that basis the climate result is driven mainly by "
            + ", ".join(f"{s['source']} ({s['share']*100:.0f}%)" for s in _src[:3])
            + ", so those are the figures worth getting right first. Separately, each category result "
            "carries an indicative pedigree uncertainty of roughly 30 to 40 percent (shown as the range "
            "on each figure), which is a screening estimate rather than a full Monte-Carlo propagation.")
    else:
        sensitivity = (
            "Each category result carries an indicative pedigree uncertainty of roughly 30 to 40 percent "
            "(shown as the range on each figure), a screening estimate rather than a full uncertainty propagation.")

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
        f"works out at about {_micro:.0f} micro-points per kilogram, a {_band or 'mid-range'} result next to "
        f"the benchmark crops. It is driven most by {_topcat}, and on the climate side mainly by {_topsrc}. "
        "So the goal is met on both counts: the footprint is quantified per kilogram at the farm gate, and "
        "the activities that matter most, which are the ones the farm can act on, are clearly identified.")

    interpretation = {
        "results_interpretation": results_interpretation,
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
        "sensitivity_and_uncertainty": sensitivity,
        "conclusions": [
            (f"Measured per kilogram of crop, the biggest single contributor is {top_cats[0][0]}."
             if top_cats else "The impacts are spread fairly evenly across the categories."),
            (f"On the climate side, {_src[0]['source']} is the main driver at about {_src[0]['share']*100:.0f}%, "
             "so that is where the clearest improvement lies."
             if _src else "The clearest chances to improve lie in the largest impact category."),
        ],
        "recommendations": _recs,
        "limitations": [
            "This is a screening study, so it uses standard emission factors and average background data rather than measurements from this farm.",
            "Data quality is assessed at the study level using the five-indicator pedigree scorecard above. A finer, dataset-by-dataset pedigree score with propagated uncertainty (rather than the indicative range shown) has not been carried out.",
            "The single score uses equal weighting, which is a judgement call, and it works best for comparing scenarios of the same crop rather than as an absolute verdict.",
        ],
        "public_disclosure": (
            "This report is written so it can be shared outside the farm. Before it is published, "
            "the results need to pass an independent critical review, set out below, as the ISO "
            "standards require for public environmental claims. Until that review is complete, the "
            "report should be treated as a finished draft rather than a reviewed public claim."
            if intended_for_public else
            "This report is for the farm's own use and is not meant to be shared publicly."),
    }

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
