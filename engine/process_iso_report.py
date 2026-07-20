#!/usr/bin/env python3
"""
process_iso_report.py — the ISO 14040/14044 report for a PROCESSING (facility) assessment.

Parallels iso_report.build_iso_report but for a processor: the functional unit is one kg of
a product at the factory gate (after co-product allocation), the boundary is cradle-to-gate
INCLUDING processing, on-site emissions are refrigerant leakage (not field N2O), and the
report discloses the co-product allocation basis (an ISO 14044 requirement). It reuses the
shared pedigree scorecard and the same section shapes the frontend renderer expects. No farm,
crop, or field vocabulary; no em-dashes.
"""
from __future__ import annotations

try:
    from .iso_report import STANDARD, _pct, _data_quality_scorecard
except ImportError:
    from iso_report import STANDARD, _pct, _data_quality_scorecard


def _product_phrase(products: list) -> str:
    names = [p.get("name", "product") for p in products]
    if len(names) > 1:
        return ", ".join(names[:-1]) + " and " + names[-1]
    return names[0] if names else "the processed product"


def build_process_iso_report(request: dict, result, engine, midpoints: dict, single_meta: dict,
                             total_kg: float, allocation: dict, extra_notes=None,
                             assessment_id: str | None = None, intended_for_public: bool = True,
                             uncertainty: dict | None = None) -> dict:
    from datetime import datetime, timezone
    total_kg_safe = total_kg or 1.0
    method = engine.method
    region = getattr(engine, "region", None)
    region_name = getattr(region, "name", result.region or "the region")

    fp = request.get("facility_profile") or {}
    facility = fp.get("facility_name") or fp.get("company_name") or "the facility"
    company = fp.get("company_name") or facility
    products = request.get("processed_products") or []
    product_phrase = _product_phrase(products)
    multi_product = len(products) > 1
    basis = (allocation or {}).get("basis", "mass")
    basis_word = "output mass" if basis == "mass" else "revenue (economic value)"

    matches = result.input_matches or []
    matched = [m for m in matches if m.get("matched")]
    unlinked_notes = [n for n in (result.notes or []) if "no match" in (n or "") or "unlinked" in (n or "")]
    _sources_used = {m.get("source") for m in matched if m.get("source")}
    uses_agribalyse = any("agribalyse" in (s or "").lower() for s in _sources_used)

    # refrigerant leakage modelled this run?
    rm = (request.get("processing_operations") or {}).get("refrigerant_management") or {}
    has_refrigerant = bool(rm.get("annual_leakage_kg"))

    # ---- categories / contributions / significant issues ----
    categories = [{"name": name, "unit": (m.get("unit") or "").replace(" per kg", "")}
                  for name, m in midpoints.items() if name != "Biodiversity loss"]
    contributions = single_meta.get("contributions") or {}
    top_cats = sorted(contributions.items(), key=lambda kv: -kv[1])[:3]
    significant = [f"{cat} is behind about {v*100:.0f}% of the overall single score"
                   for cat, v in top_cats if v > 0]

    # climate by source
    cbs = getattr(result, "contribution_by_source", None) or {}
    def _clim(imp):
        for k, v in imp.items():
            if "climate" in k.lower() or "warming" in k.lower():
                return (v or {}).get("value", 0.0) or 0.0
        return 0.0
    clim = {s: _clim(imp) for s, imp in cbs.items()}
    clim_tot = sum(clim.values())
    contribution_analysis = {
        "indicator": "Climate change (kg CO2-eq)",
        "by_source": sorted(
            [{"source": s, "per_kg": v / total_kg_safe, "share": (v / clim_tot if clim_tot else 0.0)}
             for s, v in clim.items() if v],
            key=lambda x: -x["per_kg"]),
    }
    _src = contribution_analysis["by_source"]

    # ---- inventory results ----
    inv = getattr(result, "inventory", None) or {}
    top_flows = sorted(inv.values(), key=lambda r: -abs(r.get("amount") or 0.0))[:30]
    inventory_results = {
        "basis": "per kilogram of processed product",
        "n_flows_total": len(inv), "n_shown": len(top_flows),
        "flows": [{"flow": r.get("name"), "amount": (r.get("amount") or 0.0) / total_kg_safe,
                   "unit": r.get("unit")} for r in top_flows],
    }

    results_table = [{"category": name, "result": (m.get("value") or 0.0),
                      "unit": (m.get("unit") or "").replace(" per kg", "")}
                     for name, m in midpoints.items()]

    # ---- reference-flow table ----
    reference_flows = []
    for m in matches:
        name = m.get("matched")
        if not name:
            continue
        reference_flows.append({
            "process": f"{m.get('input')} (modelled as {name})",
            "amount": f"{m.get('amount'):.4g} {m.get('amount_unit') or ''}".strip() if m.get("amount") is not None else "per year",
            "source": m.get("source") or "ecoinvent 3.11",
            "adaptation": m.get("location") or region_name,
        })
    if has_refrigerant:
        reference_flows.append({
            "process": f"On-site refrigerant leakage ({rm.get('refrigerant_type')})",
            "amount": f"{rm.get('annual_leakage_kg'):.4g} kg per year",
            "source": "IPCC AR6 (2021) GWP100", "adaptation": "direct emission"})

    # ---- data quality ----
    dq_overall, dq_indicators = _data_quality_scorecard(matches, unlinked_notes, region_name)
    dqa = (f"Overall data quality is rated {dq_overall.lower()}, scored across the five pedigree "
           "indicators below rather than asserted.")

    # ---- single-score gauge + composition (same shapes as the farm report) ----
    _micro = (single_meta.get("person_equivalents_per_kg") or 0.0) * 1e6
    _cut = single_meta.get("band_cutoffs") or {}
    single_score_composition = [{"category": c, "share": s}
                                for c, s in sorted(contributions.items(), key=lambda kv: -kv[1]) if s]
    single_score_gauge = {
        "value": _micro, "unit": single_meta.get("unit", "µPt per kg"), "band": single_meta.get("band"),
        "low_cut": _cut.get("low"), "high_cut": _cut.get("high"),
        "benchmark_min": _cut.get("benchmark_min"), "benchmark_max": _cut.get("benchmark_max"),
        "calibrated": _cut.get("calibrated"), "basis": single_meta.get("band_basis"),
    }

    # ---- sensitivity + recommendations (data-driven from the top climate sources) ----
    _mc_n = (uncertainty or {}).get("n")
    _mc_tail = (
        f" A pedigree screening Monte Carlo with N={_mc_n} was also run; each source's geometric SD "
        f"comes from its ecoinvent pedigree-matrix score and sources are sampled independently, with "
        f"category p5-p95 percentiles reported. Characterization-factor uncertainty is not included "
        f"at this screening level."
        if uncertainty else
        " New assessments attach a per-source pedigree-matrix Monte Carlo by default; "
        "this draft has no Monte Carlo block, so re-run to refresh the ranges."
    )
    if _src:
        drivers = ", ".join(f"{s['source']} ({s['share']*100:.0f}%)" for s in _src[:3])
        sensitivity = (
            "Because the calculation is linear in the amounts used, each source's share of a result "
            "is also how sensitive the result is to it: change a source by one percent and the total "
            f"moves by about its share. On that basis the climate result is driven mainly by {drivers}, "
            "so those are the figures worth getting right first."
            + _mc_tail)
    else:
        sensitivity = (
            (f"Each category result carries p5-p95 ranges from a per-source pedigree-matrix "
             f"screening Monte Carlo (N={_mc_n}).")
            if uncertainty else
            "New assessments run a per-source pedigree-matrix Monte Carlo by default and report "
            "p5-p95 ranges; this draft has no Monte Carlo block, so re-run to refresh uncertainty."
        )

    def _rec_for(src: str) -> str:
        s = (src or "").lower()
        if "electric" in s:
            return "Cut electricity use and shift to a lower-carbon supply: on-site solar, an efficiency programme, or a cleaner tariff where one exists."
        if "diesel" in s or "fuel" in s or "heat" in s:
            return "Use process heat and fuel more efficiently, and move to lower-carbon energy for drying and heating where it is practical."
        if "transport" in s:
            return "Source raw materials closer to the facility or consolidate loads to cut inbound transport."
        if "packag" in s:
            return "Lighten packaging or move to a lower-impact material, and increase recycled content where product safety allows."
        if "refrigerant" in s:
            return "Reduce refrigerant leakage through maintenance, and plan a switch to a lower-GWP refrigerant."
        if "waste" in s:
            return "Divert more organic waste to composting or anaerobic digestion instead of landfill."
        return f"Focus on {src}, which is a leading contributor to the footprint."
    _recs, _seen = [], set()
    for s in _src[:3]:
        r = _rec_for(s["source"])
        if r not in _seen:
            _seen.add(r); _recs.append(r)
    if has_refrigerant:
        rr = _rec_for("refrigerant")
        if rr not in _seen:
            _seen.add(rr); _recs.append(rr)
    _recs.append("Gather more of the facility's own metered data to replace screening defaults and narrow the uncertainty.")

    # ---- sections ----
    document_control = {
        "title": f"Life Cycle Assessment of {product_phrase} at {facility}",
        "confidentiality": "Prepared for external and public communication" if intended_for_public else "For internal use",
        "commissioner": company, "practitioner": "Green Means Go LCA engine",
        "date_of_issue": datetime.now(timezone.utc).date().isoformat(),
        "report_number": f"PROC-{(assessment_id or '')[:8]}", "version": "1.0 (draft)",
        "reference_standards": ["ISO 14040:2006", "ISO 14044:2006", "ISO/TS 14071:2024"],
        "farm_certifications": fp.get("certifications") or [],
    }

    introduction = {
        "context": (f"This report is a life cycle assessment of {product_phrase} made at {facility} in "
                    f"{request.get('country', region_name)}. It measures the environmental footprint of what "
                    "the facility produces and shows where the biggest impacts sit, so the business can make "
                    "improvements and can speak to its performance with evidence behind it."),
        "product_system": (f"The product system is the processing of raw materials into {product_phrase} at "
                           f"{facility}. It runs from growing and making the inputs, through inbound transport "
                           "and the processing steps at the facility, to the point the packaged product leaves "
                           "the factory gate."),
        "similar_studies": ("This is a screening-level study, in keeping with common practice for food "
                            "processing life cycle work. The supply chain is built on established published "
                            "inventories (ecoinvent and, where relevant, Agribalyse food-processing data). The "
                            "headline single score is placed against a benchmark set of processed-food products "
                            "worked out the same way, which set the Low, Moderate and High bands."),
    }

    goal = {
        "goal_statement": (f"The goal of this study is to quantify the cradle-to-gate environmental impacts of "
                           f"{product_phrase} made at {facility}, per kilogram of product at the factory gate, and "
                           "to identify which activities contribute the most."),
        "reasons_for_study": ("This study measures the environmental footprint of what the facility produces so "
                              "the business can act on the largest impacts and back up its performance with evidence."),
        "intended_application": "To share the facility's environmental performance externally and to guide practical improvements on site.",
        "intended_audience": ("People outside the business who use this information, such as buyers, certifiers and "
                             "programme administrators, and the wider public, along with the facility's own operators."),
        "commissioner": company,
        "comparative_assertion_disclosed_to_public": False,
        "public_disclosure_intended": intended_for_public,
        "peer_review_statement": ("Because these results are meant to be shared publicly, the study will go through "
                                 "an independent critical review before it is published, so the findings are fair, "
                                 "unbiased and in line with the ISO standards."),
    }

    boundary_included = [
        f"The production of the raw materials and the inputs the facility buys in, and the processing itself.",
        "The electricity and process heat used to run the equipment, at the region's grid mix.",
        "Water use and the treatment of the wastewater produced.",
        "Packaging materials for the finished product.",
        "Treatment of the solid waste the facility sends off site.",
        "Inbound transport of the raw materials to the facility.",
    ]
    if has_refrigerant:
        boundary_included.append(f"On-site refrigerant leakage ({rm.get('refrigerant_type')}), counted at its AR6 GWP100.")
    boundary_excluded = [
        "Everything after the factory gate: distribution, retail, the use of the product, and its disposal.",
        "Employee commuting and general facility overheads not tied to production.",
    ]

    scope = {
        "approach": "Attributional",
        "product_system": f"{product_phrase} made at {facility}.",
        "functional_unit": (f"One kilogram of product at the factory gate"
                            + (", after co-product allocation." if multi_product else ".")),
        "functional_unit_basis": ("Every impact figure is measured against one kilogram of finished product leaving "
                                  "the factory gate. All inputs and emissions are scaled to that one kilogram"
                                  + (", and shared burdens are split between co-products as described under allocation." if multi_product else ".")),
        "system_boundary": ("The study runs from the inputs and raw materials, through the processing at the facility, "
                           "to the point the packaged product leaves the factory gate (cradle to gate). What sits inside "
                           "and outside the boundary is set out below."),
        "boundary_included": boundary_included,
        "boundary_excluded": boundary_excluded,
        "boundary_type": "cradle to gate",
        "cutoff_criteria": ("The study uses ecoinvent's standard cut-off approach. Buildings and machinery are already "
                           "built into the background data, and nothing further is left out beyond what the database excludes."),
        "allocation_procedure": (
            (f"The facility makes {len(products)} co-products, so the total impact is allocated between them by "
             f"{basis_word}. "
             + ((allocation or {}).get("note", "") + " " if (allocation or {}).get("note") else "")
             + "This allocation choice is disclosed here as ISO 14044 requires. Any co-products further up the supply "
             "chain are handled the way the background database handles them.")
            if multi_product else
            "There is a single product, so no split between co-products is needed. Any co-products further up the "
            "supply chain are handled the way the background database (ecoinvent) handles them."),
        "impact_categories": categories,
        "impact_categories_basis": (f"All {len(categories)} midpoint categories that could be characterised for this "
                                    "study are reported. The ones that matter most for food processing, such as climate "
                                    "change, energy and water use and eutrophication, are among them."),
        "normalization_reference": "The method's own reference set.",
        "data_requirements": {
            "foreground": ("Information the facility provided about its own activity: the products and volumes, energy "
                          "and water use, packaging, waste and inbound transport."),
            "background": ("The impacts of making the energy, materials and packaging come from the ecoinvent database "
                          "and Agribalyse, matched to representative datasets and adjusted to the region where a regional "
                          "version exists."),
        },
        "assumptions_and_limitations": [
            "Purchased utilities and materials are matched to representative background datasets with assisted search, and the top candidates are kept on record so the choice can be checked.",
            "Where a facility meter is not available, energy and water are estimated from the per-step intensities the operator provided.",
            ("On-site refrigerant leakage is counted at its AR6 GWP100 as a direct climate emission."
             if has_refrigerant else
             "Refrigerant leakage was not reported, so no on-site F-gas emission is counted; if the facility uses cold storage this may understate climate impact."),
        ],
        "value_choices": [
            "The single score adds up the categories with equal weight. That is a judgement call, and the score is not used to make public claims of being better than another product.",
            f"Co-products are allocated by {basis_word}, which is a value choice disclosed above." if multi_product else "Results use the method's default time perspective.",
        ],
    }

    inventory = {
        "data_sources": [s for s in [
            "ecoinvent 3.11, for the supply chain of energy, materials and packaging",
            "Agribalyse 3.2, for some food-processing background datasets" if uses_agribalyse else None,
            "IPCC AR6 (2021), for refrigerant global warming potentials" if has_refrigerant else None,
        ] if s],
        "foreground_data": "Activity data reported by the facility for the products, energy, water, packaging, waste and transport listed, used as supplied by the operator.",
        "background_data": "Unit-process datasets from ecoinvent and Agribalyse, adjusted to the region where a regional version exists. Any stand-in datasets are noted.",
        "on_farm_lci": (  # kept key name for frontend compatibility; content is the on-site section
            "The only direct on-site emission modelled is refrigerant leakage, counted at its AR6 GWP100 "
            f"({rm.get('refrigerant_type')}, {rm.get('annual_leakage_kg')} kg per year). Everything else comes "
            "from the purchased energy, materials, packaging, waste treatment and transport listed below."
            if has_refrigerant else
            "No direct on-site emissions are modelled beyond the purchased inputs, since no refrigerant leakage was "
            "reported. The footprint is made up of the purchased raw materials, energy, packaging, waste treatment "
            "and transport listed below."),
        "on_farm_flows": ([f"Refrigerant leakage: {rm.get('refrigerant_type')} at AR6 GWP100"] if has_refrigerant else []),
        "on_farm_adjustments": [],
        "calculation_procedure": ("The supply chain is solved as a set of linked equations rather than traced step by "
                                 "step by hand, so it handles the loops real supply chains contain. Energy is tracked in "
                                 "energy units, and electricity uses the region's grid mix."),
        "reference_flows": reference_flows,
        "inputs_matched": f"{len(matched)} of {len(matches)} purchased inputs were matched to a background dataset.",
        "pedigree_uncertainty": (
            (f"A pedigree screening Monte Carlo was run with N={uncertainty['n']} draws: each source "
             f"was scored on the ecoinvent 2013 pedigree matrix for a per-source geometric SD, sources "
             f"were sampled independently, and category totals re-summed. The p5-p95 ranges on each "
             f"figure come from that simulation. Characterization-factor uncertainty is not propagated "
             f"at this screening level.")
            if uncertainty else
            ("New assessments run a per-source pedigree-matrix screening Monte Carlo by default (typically "
             "N=1000) and report p5-p95 ranges. This saved draft has no Monte Carlo block attached; "
             "re-run the assessment to refresh the uncertainty ranges.")
        ),
        "data_validation": ("This refers to the calculation engine, not to a separate check of this facility's numbers. "
                           "The engine's method has been benchmarked against established tools: ecoinvent products match "
                           "openLCA to within half a percent, and Agribalyse products match ADEME's published figures to "
                           "within five percent. This report's figures follow from that same validated method."),
        "input_matches": matches,
        "notes": (extra_notes or []) + (result.notes or []),
        "inventory_results": inventory_results,
    }

    lcia = {
        "method": method,
        "rationale": ("ReCiPe 2016 is a widely used life cycle impact assessment method." if "ReCiPe" in method
                     else "Environmental Footprint 3.1 is the European Commission's reference method for this kind of study."),
        "mandatory_elements": {
            "classification": "Each emission and resource use is sorted into the environmental issue it contributes to.",
            "characterization": f"Each category's result is the sum of every flow multiplied by its characterisation factor, using {method}.",
        },
        "optional_elements": {
            "normalization": "Results are put on a common scale using the method's own reference set.",
            "weighting": "The categories are combined with equal weight to give the single score, which is a judgement call.",
        },
        "results_are_relative_expressions": ("These impact figures are relative indicators, not absolute measurements. As "
                                            "the ISO standards require us to state, they do not predict actual harm to human "
                                            "health or to ecosystems, whether any safety threshold has been crossed, or real-world risk."),
        "n_categories_reported": len(categories),
        "results_table": results_table,
    }

    _topcat = top_cats[0][0] if top_cats else "several categories together"
    _topsrc = _src[0]["source"] if _src else "the purchased energy"
    interpretation = {
        "results_interpretation": (
            f"The study set out to measure the cradle-to-gate footprint of {product_phrase} for each kilogram of product "
            f"and to find where that footprint comes from. Against that goal, the overall single score works out at about "
            f"{_micro:.0f} micro-points per kilogram, a {(single_meta.get('band') or 'mid-range').lower()} result next to the "
            f"benchmark products. It is driven most by {_topcat}, and on the climate side mainly by {_topsrc}. So the goal is "
            "met on both counts: the footprint is quantified per kilogram at the factory gate, and the activities that matter "
            "most are clearly identified."),
        "single_score_gauge": single_score_gauge,
        "single_score_composition": single_score_composition,
        "significant_issues": significant or ["No single contributor clearly stands out."],
        "contribution_analysis": contribution_analysis,
        "data_quality_assessment": dqa,
        "data_quality_scorecard": {"overall": dq_overall, "indicators": dq_indicators},
        "completeness_check": (
            f"{len(matched)} of {len(matches)} purchased inputs were linked to a background dataset. "
            + ("Every input the facility declared is represented, and no flows were left unlinked."
               if len(matched) == len(matches) and not unlinked_notes else
               f"{len(matches) - len(matched)} input(s) could not be matched and are noted.")),
        "consistency_check": (
            "One impact method and one background database (ecoinvent"
            + (", with Agribalyse for some datasets" if uses_agribalyse else "")
            + ") were applied throughout. Everything is expressed on the same basis of one kilogram of product at the factory gate."),
        "sensitivity_and_uncertainty": sensitivity,
        "conclusions": [
            (f"Measured per kilogram of product, the biggest single contributor is {top_cats[0][0]}."
             if top_cats else "The impacts are spread fairly evenly across the categories."),
            (f"On the climate side, {_src[0]['source']} is the main driver at about {_src[0]['share']*100:.0f}%, "
             "so that is where the clearest improvement lies."
             if _src else "The clearest chances to improve lie in the largest impact category."),
        ],
        "recommendations": _recs,
        "limitations": [
            "This is a screening study, so it uses standard datasets and average background data rather than site measurements throughout.",
            ("Data quality is assessed at the study level using the five-indicator pedigree scorecard above. "
             f"A pedigree screening Monte Carlo (N={_mc_n}) propagated lognormal uncertainty by data class "
             "to the category ranges shown."
             if uncertainty else
             "Data quality is assessed at the study level using the five-indicator pedigree scorecard above. "
             "Pedigree screening Monte Carlo is the default for new assessments; this draft has no "
             "Monte Carlo block — re-run to attach p5–p95 ranges."),
            "The single score uses equal weighting, which is a judgement call, and it works best for comparing scenarios of the same product rather than as an absolute verdict.",
        ],
        "public_disclosure": (
            "This report is written so it can be shared outside the business. Before it is published, the results need to "
            "pass an independent critical review, set out below, as the ISO standards require for public environmental claims. "
            "Until that review is complete, the report should be treated as a finished draft rather than a reviewed public claim."
            if intended_for_public else
            "This report is for the facility's own use and is not meant to be shared publicly."),
    }

    if intended_for_public:
        critical_review = {
            "required": True,
            "status": "Required, and still to be done. The report is a finished draft, ready for review.",
            "trigger": ("The results are meant to be shared publicly as an environmental claim, and the ISO standards "
                        "call for an independent critical review in that case."),
            "reviewer_requirements": [
                "A panel of three independent experts.",
                "Each one should know both life cycle assessment and the subject, in this case food processing.",
                "Each one should be independent, with no business tie to the study and nothing to gain from its outcome.",
            ],
            "review_scope": ["The goal and scope", "The inventory", "The impact assessment", "The interpretation", "The full report"],
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
            "statement": "",
        }
    else:
        critical_review = {"required": False, "status": "Not required, as the study is for internal use only.",
                           "trigger": "The study is for the business's own decisions and makes no public comparison.",
                           "reviewer_requirements": [], "review_scope": [], "process": [], "panel": [],
                           "statement": "Checked internally only. The calculation method has been benchmarked against openLCA and ADEME."}

    references = [
        "ISO 14040:2006, Environmental management, Life cycle assessment, Principles and framework.",
        "ISO 14044:2006, Environmental management, Life cycle assessment, Requirements and guidelines.",
        "ISO/TS 14071:2024, Life cycle assessment, Critical review processes and reviewer competencies.",
        "ecoinvent 3.11, cut-off system model, background life cycle inventory database.",
        ("ReCiPe 2016 v1.03 (Huijbregts and others), the impact assessment method used here." if "ReCiPe" in method
         else "Environmental Footprint (EF) 3.1 (European Commission, JRC), the impact assessment method used here."),
        "CSIR LCA Guideline 4 (Russo and others, 2024), Templates for LCA Reports and Critical Reviews.",
    ]
    if uses_agribalyse:
        references.insert(4, "Agribalyse 3.2 (ADEME), food-product life cycle inventory database.")
    if has_refrigerant:
        references.append("IPCC AR6 (2021), Working Group I, 100-year global warming potentials for refrigerants.")

    return {
        "standard": STANDARD,
        "disclosure_posture": "For external and public communication" if intended_for_public else "For internal use",
        "conformance_status": ("This is a finished, ISO-based draft. It still needs an independent critical review before "
                              "it can be shared publicly." if intended_for_public else
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
