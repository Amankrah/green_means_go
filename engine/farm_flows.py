#!/usr/bin/env python3
"""
farm_flows.py: on-farm ELEMENTARY flows that come from wizard inputs rather than from the
Rust kernel, merged into the "Field emissions (on-farm)" source after the solve:

  * pesticide active ingredients emitted to agricultural soil (engine/pesticides.py), so the
    toxicity categories see them;
  * irrigation water withdrawal by source (groundwater "Water, well, in ground", surface
    "Water, river" / "Water, lake"; municipal supply is a purchased tap-water input instead).
    This replaces the Rust kernel's generic "Water" flow (uncited m3/ha by system, which also
    mis-reads several wizard system names), so the farm has one water number: the measured
    volume, or the FAO crop-water-need estimate from engine/crop_defaults.py;
  * composting emissions of compost made on the farm (IPCC 2006 Vol.5 Ch.4 Table 4.1);
  * field phosphorus to water, SALCA-P (engine/phosphorus.py): phosphate to ground water
    (leaching), phosphate to surface water (run-off), phosphorus to surface water (erosion),
    the ecoinvent compartments;
  * disclosures without flows: fertiliser cadmium (engine/heavy_metals.py) and soil carbon
    from management (engine/soil_carbon.py), the latter attached as
    `result.soc_management` and NOT added to the inventory (reported separately).

`apply(result, engine, assessment)` edits an orchestrator AssessmentResult in place and
re-characterises it, keeping per-source flows, the on-farm split and the merged total
consistent (and therefore method switches via stored per-source flows).
"""
from __future__ import annotations

try:
    from . import pesticides as pz
    from . import phosphorus as phos
    from . import heavy_metals as hm
    from . import soil_carbon as soc
    from .inputs import irrigation_water, is_municipal, _total_area, _norm
except ImportError:  # script use
    import pesticides as pz  # type: ignore
    import phosphorus as phos  # type: ignore
    import heavy_metals as hm  # type: ignore
    import soil_carbon as soc  # type: ignore
    from inputs import irrigation_water, is_municipal, _total_area, _norm  # type: ignore

FIELD_LABEL = "Field emissions (on-farm)"
RESOURCE_IN_WATER = "Elementary flows/Resource/in water"

# wizard water source -> store elementary flow name (resource, in water)
WATER_SOURCE_FLOWS = {
    "borehole": "Water, well, in ground", "well": "Water, well, in ground",
    "groundwater": "Water, well, in ground",
    "river": "Water, river", "stream": "Water, river",
    "dam": "Water, lake", "reservoir": "Water, lake", "lake": "Water, lake", "pond": "Water, lake",
}
UNSPECIFIED_WATER = "Water, unspecified natural origin"

# Consumptive use. In the ecoinvent 3.11 method pack in the store, ReCiPe / EF "Water use" is
# characterised on water EVAPORATED ("Water", emission to air), i.e. withdrawal minus
# return. The withdrawal flows above carry no water-use CF, so the evapotranspired share of
# the irrigation water is also emitted to air: applied volume x field application efficiency
# (the share taken up by the crop; field losses return to ground / surface water).
EVAPORATED_WATER = ("Water", "Elementary flows/Emission to air/unspecified")

# IPCC 2006 Vol.5 Ch.4 Table 4.1, composting: 4 g CH4 and 0.3 g N2O per kg of wet waste
# treated. Applied compost mass is used as the treated mass (lower bound: mass is lost during
# composting). Only compost made on the farm (farm-made, mixed sources, green waste / crop
# residues): purchased compost carries its composting in the "market for compost" dataset,
# and animal manure applied directly is not composted (its storage belongs to the livestock
# system).
COMPOST_CH4_KG_PER_KG = 0.004
COMPOST_N2O_KG_PER_KG = 0.0003
COMPOST_SOURCE = "IPCC 2006 Vol.5 Ch.4 Table 4.1 composting: 4 g CH4, 0.3 g N2O per kg wet waste"
ON_FARM_COMPOSTED = ("farm-made", "mixed", "green waste", "crop residue")

# SALCA-P pathways -> (store flow name, compartment, flowmap fallback key), ecoinvent convention
P_FLOWS = (
    ("po4_groundwater", "Phosphate", "Elementary flows/Emission to water/ground water", None),
    ("po4_surface", "Phosphate", "Elementary flows/Emission to water/surface water", "PO4"),
    ("p_erosion_surface", "Phosphorus", "Elementary flows/Emission to water/surface water", "P"),
)


def _compost_area(assessment: dict, sm: dict) -> float:
    ids = [str(i) for i in (sm.get("compost_crop_ids") or [])]
    return sum(float(f.get("area_allocated") or 0.0) for f in assessment.get("foods") or []
               if not ids or str(f.get("id")) in ids)


def _flow_uid(conn, name: str, category: str) -> str | None:
    row = conn.execute(
        "SELECT f.uid, (SELECT COUNT(*) FROM characterization_factors cf WHERE cf.flow_uid = f.uid) n "
        "FROM flows f WHERE f.flow_type = 'ELEMENTARY_FLOW' AND f.name = ? AND f.category = ? "
        "ORDER BY n DESC LIMIT 1", (name, category)).fetchone()
    return row[0] if row else None


def water_flow_name(source_text: str) -> str | None:
    """None means municipal supply (a purchased input, not an elementary withdrawal)."""
    if is_municipal(source_text):
        return None
    low = _norm(source_text)
    for kw, name in WATER_SOURCE_FLOWS.items():
        if kw in low:
            return name
    return UNSPECIFIED_WATER


def extra_flows(assessment: dict, conn, fmap=None, region=None,
                method: str | None = None) -> tuple[list[dict], list[str], bool]:
    """Return (flows, notes, replaces_rust_water). flows: {uid, name, unit, amount}.
    `method` selects the pesticide emission split (pesticides.emission_split)."""
    flows, notes = [], []
    total_area = _total_area(assessment)

    # 1) pesticide active ingredient -> field compartments (split by LCIA method)
    rows, _ = pz.applications(assessment, total_area)
    pflows, pnotes = pz.field_emission_flows(conn, rows, method=method)
    flows += pflows
    notes += pnotes
    if pflows:
        source = pz.emission_split(method)[1]
        notes.append(f"pesticide field emissions: {sum(f['amount'] for f in pflows):.3g} kg active "
                     f"ingredient emitted to the field ({source})")

    # 2) irrigation water withdrawal by source
    replaces = False
    w = irrigation_water(assessment)
    if w:
        replaces = True
        srcs = w["water_source"] or ["unspecified"]
        share = w["m3"] / len(srcs)
        for s in srcs:
            name = water_flow_name(s)
            if name is None:
                continue     # municipal: purchased tap water (engine/inputs.py)
            uid = _flow_uid(conn, name, RESOURCE_IN_WATER)
            if uid:
                flows.append({"uid": uid, "name": name, "unit": "m3", "amount": share})
        # Consumption is NOT added here: the orchestrator passes this same volume to
        # water_scarcity.apply, which books the consumed share (FAO application efficiency)
        # once, on the regional AWARE flow. Adding evaporated "Water" here as well would
        # double count it and characterise it with the world-average CF.
        notes.append(f"irrigation water: {w['m3']:.0f} m3 by source {srcs} "
                     f"({'estimated: ' + w['source'] if w['estimated'] else 'measured'})")

    # 3) compost made on the farm: composting process emissions
    sm = ((assessment.get("management_practices") or {}).get("soil_management")) or {}
    src = _norm(sm.get("compost_source"))
    rate = sm.get("compost_application_rate")
    area = _compost_area(assessment, sm)
    on_farm = any(k in src for k in ON_FARM_COMPOSTED) and "manure" not in src
    if sm.get("uses_compost") and on_farm and rate and area and fmap is not None:
        kg = rate * 1000.0 * area
        for key, ef in (("CH4_bio", COMPOST_CH4_KG_PER_KG), ("N2O", COMPOST_N2O_KG_PER_KG)):
            uid = fmap.resolve(key)
            if uid:
                flows.append({"uid": uid, "name": f"{key} (composting)", "unit": "kg", "amount": kg * ef})
        notes.append(f"on-farm composting emissions for {kg:.0f} kg compost "
                     f"('{sm.get('compost_source')}', {COMPOST_SOURCE})")
    elif sm.get("uses_compost") and "manure" in src:
        notes.append("animal manure applied directly: no composting-process emissions")

    # 4) field phosphorus to water (SALCA-P)
    pl, pnotes = phos.field_p_losses(assessment, region)
    notes += pnotes
    for key, name, cat, fallback in P_FLOWS:
        amount = pl.get(key) or 0.0
        if amount <= 0:
            continue
        uid = _flow_uid(conn, name, cat)
        if uid is None and fallback and fmap is not None:
            uid = fmap.resolve(fallback)
        if uid is None:
            notes.append(f"phosphorus flow '{name}' ({cat}) not found in the store; not booked")
            continue
        flows.append({"uid": uid, "name": f"{name} ({cat.rsplit('/', 1)[-1]}, field)",
                      "unit": "kg", "amount": amount})

    # 5) heavy metals: disclosure only (no defensible fertiliser Cd content)
    _, cd_notes = hm.cadmium_disclosure(assessment)
    notes += cd_notes
    return flows, notes, replaces


def merge_elementary(result, engine, label: str, flows: list[dict]) -> None:
    """Add elementary flows to `result` as their own contribution source `label` (method-
    independent flows kept for re-characterisation) and re-characterise the total."""
    src = result.contribution_flows_by_source.setdefault(label, {})
    for f in flows:
        for bucket in (src, result.inventory):
            rec = bucket.get(f["uid"])
            if rec:
                rec["amount"] += f["amount"]
            else:
                bucket[f["uid"]] = {"name": f["name"], "unit": f["unit"], "amount": f["amount"]}
    result.contribution_by_source[label] = engine.q.characterize_flows(src, engine.method)
    result.impacts = engine.q.characterize_flows(result.inventory, engine.method)


def apply(result, engine, assessment: dict) -> list[str]:
    """Merge the extra on-farm flows into `result` (orchestrator AssessmentResult) and
    re-characterise. Returns the notes it added."""
    conn = engine.q.conn
    fmap = getattr(engine, "fmap", None)
    region = getattr(engine, "region", None)
    flows, notes, replaces = extra_flows(assessment, conn, fmap, region,
                                         method=getattr(engine, "method", None))
    # Soil carbon from management: reported separately, never merged into the inventory.
    try:
        rec = soc.soc_management(assessment, region)
        result.soc_management = rec
        notes.append(soc.note(rec))
    except Exception as e:   # disclosure must never break a run
        notes.append(f"soil carbon from management not computed ({type(e).__name__}: {e})")
    if not flows and not replaces:
        result.notes += notes
        return notes
    src = result.contribution_flows_by_source.setdefault(FIELD_LABEL, {})
    if replaces and fmap is not None:
        rust_water = fmap.resolve("water")
        old = src.pop(rust_water, None) if rust_water else None
        if old:
            inv = result.inventory.get(rust_water)
            if inv:
                inv["amount"] -= old.get("amount") or 0.0
                if abs(inv["amount"]) < 1e-12:
                    result.inventory.pop(rust_water, None)
            notes.append("Rust kernel generic irrigation water flow replaced by the source-specific "
                         "withdrawal above")
    for f in flows:
        for bucket in (src, result.inventory):
            rec = bucket.get(f["uid"])
            if rec:
                rec["amount"] += f["amount"]
            else:
                bucket[f["uid"]] = {"name": f["name"], "unit": f["unit"], "amount": f["amount"]}
    method = engine.method
    on_farm = engine.q.characterize_flows(src, method)
    result.contribution["on_farm"] = on_farm
    result.contribution_by_source[FIELD_LABEL] = on_farm
    result.impacts = engine.q.characterize_flows(result.inventory, method)
    result.notes += notes
    return notes
