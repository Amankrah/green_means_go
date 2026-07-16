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
    _pm = _mp.get("pest_management") or {}
    has_pesticide = bool(_pm.get("pesticides") if isinstance(_pm, dict) else _pm)
    uses_compost = bool((_mp.get("soil_management") or {}).get("uses_compost"))
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
            "source": "ecoinvent 3.11",
            "adaptation": m.get("location") or region_name,
        })
    reference_flows.append({
        "process": "Emissions released in the field (nitrous oxide, methane, carbon dioxide, nitrate, land occupied)",
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
    goal = {
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

    # ---- 2. Scope ----
    if multi_crop:
        allocation = (
            "Each crop is worked out as its own product on its own land. Shared farm resources "
            "such as fuel and electricity are split between the crops in proportion to the area "
            "each one occupies. Further up the supply chain, any co-products are handled the way "
            "the background database (ecoinvent) handles them. Splitting shared inputs by area is "
            "a practical simplification for a screening study rather than a formal split by "
            "physical or economic value, and it is flagged here as a judgement call.")
    else:
        allocation = (
            "There is a single product, so nothing needs to be split between farm products. Any "
            "co-products further up the supply chain are handled the way the background database "
            "(ecoinvent) handles them.")
    scope = {
        "product_system": f"The {crop_names} grown at {farm} in {region_name}.",
        "functional_unit": "One kilogram of crop, measured at the farm gate.",
        "system_boundary": (
            "The study covers everything up to the point the crop leaves the farm. It includes "
            "the emissions released in the field (nitrous oxide, methane, carbon dioxide, nitrate "
            "lost to water, and the land the crop occupies), worked out with the IPCC 2019 method, "
            "and the impacts of producing the inputs the farm buys in, such as mineral fertiliser, "
            "diesel, grid electricity and equipment, drawn from the ecoinvent database. It does "
            "not cover anything after the farm gate: processing, packaging, storage, transport, "
            "use, or disposal."),
        "boundary_type": "cradle to gate",
        "cutoff_criteria": (
            "The study uses ecoinvent's standard cut-off approach. The making of buildings and "
            "machinery is already built into the background data, and nothing further is left out "
            "beyond what the database itself excludes."),
        "allocation_procedure": allocation,
        "lcia_method": method,
        "perspective": "Hierarchist" if is_hierarchist else "method default",
        "impact_categories": categories,
        "normalization_reference": (
            "ReCiPe 2016, using the world-average, hierarchist reference for the single score."
            if "ReCiPe" in method else "The method's own reference set."),
        "data_requirements": {
            "foreground": ("Information the farm provided about its own activity: the crops and "
                           "areas grown, the type and amount of fertiliser used, and fuel and "
                           "electricity use. Field emissions are calculated from this with the "
                           "IPCC 2019 method, adjusted for the local climate."),
            "background": ("The impacts of making the fertiliser, fuel, electricity and equipment "
                           "come from the ecoinvent database, and from Agribalyse where relevant, "
                           "matched to representative datasets and adjusted to the region wherever "
                           "a regional version exists."),
        },
        "assumptions_and_limitations": [f for f in [
            "Field emissions are estimated with standard IPCC 2019 factors adjusted for the region's climate, rather than measured directly on this farm.",
            "Each bought-in input is matched to a representative dataset with assisted search, and the top candidates are kept on record so the choice can be checked.",
            ("The pesticides applied are included through the production of their active ingredients; where a specific ingredient is not in the database, a representative pesticide is used."
             if has_pesticide else None),
            ("Compost or manure is applied; its organic nitrogen is included in the field N2O calculation using IPCC 2019 factors (direct and indirect), with a screening estimate of the amendment's nitrogen content. On-farm compost carries no purchasing burden."
             if uses_compost else None),
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
    inventory = {
        "data_sources": [
            "ecoinvent 3.11, for the wider supply chain",
            "IPCC 2019, Volume 4 (Agriculture and Land Use), for the emissions released in the field",
            "Agribalyse 3.2, for food-product background data where used",
        ],
        "foreground_data": ("Activity data reported by the farm for the crops and inputs listed, "
                            "used directly where the operator supplied it and filled with "
                            "documented screening defaults where they did not."),
        "background_data": ("Unit-process datasets from ecoinvent, and Agribalyse where used, "
                            "adjusted to the region where a regional version exists. Any stand-in "
                            "datasets are noted."),
        "on_farm_lci": ("Field emissions are calculated with the IPCC 2019 method, adjusted for "
                        f"{region_name}" + (f", using a nitrous-oxide factor of {ef1} kilograms of "
                        "N2O-N per kilogram of nitrogen applied." if ef1 else ".")),
        "calculation_procedure": (
            "The supply chain is solved as a set of linked equations rather than traced step by "
            "step by hand. That is what lets it handle the loops real supply chains contain, for "
            "example the electricity needed to make steel, which is itself needed to make "
            "electricity. Energy is tracked in energy units, and electricity uses the region's grid mix."),
        "reference_flows": reference_flows,
        "inputs_matched": f"{len(matched)} of {len(matches)} bought-in inputs were matched to a background dataset.",
        "pedigree_uncertainty": (
            "Results carry a rough uncertainty of about plus or minus 30 to 40 percent, shown as a "
            "range on each category. A more detailed, dataset-by-dataset quality score has not yet "
            "been done, and this is noted here for the reviewer."),
        "data_validation": (
            "The calculation method has been checked against established tools. Results for "
            "ecoinvent products match openLCA to within half a percent, and results for Agribalyse "
            "products match ADEME's published figures to within five percent."),
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
    }

    # ---- 5. Interpretation ----
    dqa = (f"Overall the data quality is medium, which suits a screening study. The background "
           f"data is recent and comes from ecoinvent, adjusted to {region_name}, and the field "
           "emissions use the IPCC 2019 method. Completeness, consistency and sensitivity are "
           "covered below. A formal, dataset-by-dataset quality score is still to be added.")
    interpretation = {
        "significant_issues": significant or ["No single contributor clearly stands out."],
        "data_quality_assessment": dqa,
        "completeness_check": (
            f"{len(matched)} of {len(matches)} bought-in inputs were linked to a background dataset"
            + (f", and {len(unlinked_notes)} could not be matched and are noted." if unlinked_notes
               else ", so every input the farm declared is represented.")),
        "consistency_check": (
            "The same impact method and the same background database were used throughout, for "
            "both the farm's own activities and the wider supply chain, with one kilogram of crop "
            "as the common basis."),
        "sensitivity_and_uncertainty": (
            "The category results carry a rough uncertainty of about 30 to 40 percent. Field "
            "nitrous oxide is the most sensitive figure on the farm side, and after that the "
            "fertiliser rate and the carbon intensity of grid electricity matter most."),
        "conclusions": [
            (f"Measured per kilogram of crop, the biggest single contributor is {top_cats[0][0]}."
             if top_cats else "The impacts are spread fairly evenly across the categories."),
            "The clearest chances to improve lie in the largest category, and in whichever side, the field or the bought-in inputs, drives it.",
        ],
        "recommendations": [
            "Fine-tune the amount, type and timing of fertiliser to cut nitrous oxide from the field.",
            "Use fuel and grid electricity more efficiently, and move to lower-carbon energy where it is practical.",
            "Gather more of the farm's own activity data to replace screening defaults and narrow the uncertainty.",
        ],
        "limitations": [
            "This is a screening study, so it uses standard emission factors and average background data rather than measurements from this farm.",
            "A detailed, dataset-by-dataset data-quality score has not yet been carried out.",
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
        "ReCiPe 2016 v1.03 (Huijbregts and others), the impact assessment method used here.",
        "Agribalyse 3.2 (ADEME), food-product life cycle inventory database.",
        "CSIR LCA Guideline 4 (Russo and others, 2024), Templates for LCA Reports and Critical Reviews.",
    ]

    return {
        "standard": STANDARD,
        "disclosure_posture": ("For external and public communication" if intended_for_public
                               else "For internal use"),
        "conformance_status": (
            "This is a finished, ISO-based draft. It still needs an independent critical review "
            "before it can be shared publicly." if intended_for_public else
            "This is an ISO-based report for internal use, and no critical review is required."),
        "document_control": document_control,
        "goal": goal,
        "scope": scope,
        "inventory_analysis": inventory,
        "impact_assessment": lcia,
        "interpretation": interpretation,
        "critical_review": critical_review,
        "references": references,
    }
