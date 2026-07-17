#!/usr/bin/env python3
"""
test_recommend.py - proves the measure library loads with every guarantee intact and
the matcher applies hard filters before ranking.

Run:  python3 test_recommend.py   (from engine/recommend/)
   or: python3 -m pytest engine/recommend/test_recommend.py

Dependency-free, mirrors ingestion/test_matching.py. The sample payloads below are
shaped exactly like the AssessmentResponse dict engine/adapter.py emits (and that lands
in Assessment.payload_json), so a passing test here means the matcher works on real
saved assessments.
"""
from __future__ import annotations

import sys
from datetime import date

try:
    from .schema import load_measures, MeasureValidationError, AbatementMeasure
    from .matcher import match_measures
except ImportError:
    from schema import load_measures, MeasureValidationError, AbatementMeasure
    from matcher import match_measures


# --- realistic payloads (subset of the real AssessmentResponse shape) -------------

def _ghana_maize_payload() -> dict:
    """A Ghana maize farm whose biggest climate driver is urea, then diesel."""
    return {
        "country": "Ghana",
        "breakdown_by_food": {"maize (1000kg)": {}},
        "input_matches": [
            {"input": "Urea 46-0-0 fertiliser", "kind": "fertiliser", "matched": "urea..."},
            {"input": "diesel, burned in agricultural machinery", "kind": "fuel", "matched": "diesel..."},
        ],
        "contribution_by_source": {
            "Urea 46-0-0 fertiliser": {"Climate change": {"value": 0.55, "unit": "kg CO2-eq"}},
            "diesel, burned in agricultural machinery": {"Climate change": {"value": 0.20, "unit": "kg CO2-eq"}},
            "Field emissions (on-farm)": {"Climate change": {"value": 0.25, "unit": "kg CO2-eq"}},
        },
        "iso_report": {"interpretation": {"contribution_analysis": {"by_source": [
            {"source": "Urea 46-0-0 fertiliser", "per_kg": 0.55, "share": 0.55},
            {"source": "Field emissions (on-farm)", "per_kg": 0.25, "share": 0.25},
            {"source": "diesel, burned in agricultural machinery", "per_kg": 0.20, "share": 0.20},
        ]}}},
    }


def _canada_payload() -> dict:
    """Same driver profile but a Canadian farm - every Ghana-scoped measure must drop."""
    p = _ghana_maize_payload()
    p["country"] = "Canada"
    return p


def _gari_processor_payload() -> dict:
    """A processing assessment: gari, fuelwood-driven."""
    return {
        "country": "Ghana",
        "breakdown_by_product": {"Gari": {}},
        "input_matches": [
            {"input": "fuelwood (facility fuel)", "kind": "fuel", "matched": "wood..."},
            {"input": "solid waste, landfill", "kind": "waste", "matched": "landfill..."},
        ],
        "contribution_by_source": {
            "fuelwood (facility fuel)": {"Climate change": {"value": 0.70, "unit": "kg CO2-eq"}},
            "solid waste, landfill": {"Climate change": {"value": 0.30, "unit": "kg CO2-eq"}},
        },
        "iso_report": {"interpretation": {"contribution_analysis": {"by_source": [
            {"source": "fuelwood (facility fuel)", "per_kg": 0.70, "share": 0.70},
            {"source": "solid waste, landfill", "per_kg": 0.30, "share": 0.30},
        ]}}},
    }


# --- tests ------------------------------------------------------------------------

def test_library_loads_with_guarantees() -> None:
    measures = load_measures()
    assert len(measures) >= 12, f"expected a populated library, got {len(measures)}"
    for m in measures:
        assert m.provenance.source, f"{m.id}: empty provenance.source"
        assert m.provenance.span, f"{m.id}: empty provenance.span (must quote source)"
        assert m.valid_from, f"{m.id}: missing valid_from"
        assert m.staleness_policy, f"{m.id}: missing staleness_policy"
    # every measure is unreviewed in v1 - the human gate has not run yet
    assert all(not m.is_reviewed for m in measures), "v1 measures must be unreviewed"
    print(f"[ok] library loads: {len(measures)} measures, all with provenance + freshness")


def test_bad_record_rejected() -> None:
    """A record missing provenance.span must fail to load - not silently pass."""
    import json
    import tempfile
    import os
    bad = {
        "type": "abatement_measure", "id": "meas.bad", "title": "no span",
        "targets": {"driver_kind": "fertiliser", "impact_category": "Climate change"},
        "effect": {"value": -0.1, "unit": "fraction_of_driver_impact", "basis": "measured"},
        "horizon": {"band": "quick_win"},
        "provenance": {"source": "X"},  # <-- no span
        "valid_from": "2026-07-01", "staleness_policy": "annual",
    }
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(bad) + "\n")
        raised = False
        try:
            load_measures(__import__("pathlib").Path(path))
        except MeasureValidationError as e:
            raised = True
            assert "span" in str(e).lower()
        assert raised, "loader accepted a measure with no provenance span"
    finally:
        os.remove(path)
    print("[ok] loader rejects a measure with no provenance span")


def test_ghana_maize_ranks_fertiliser_first() -> None:
    """Urea is 55% of climate impact, so N measures must rank above the diesel measure."""
    res = match_measures(_ghana_maize_payload(), reviewed_only=False, as_of=date(2026, 7, 15))
    assert res, "no measures matched a Ghana maize farm"
    ids = [r.id for r in res]

    # a nitrogen measure targeting urea should be top (share 0.55 x |effect|)
    top = res[0]
    assert top.target_source == "Urea 46-0-0 fertiliser", f"top targets {top.target_source}"
    assert top.measure.driver_kind == "fertiliser", f"top is {top.id}"

    # the diesel-maintenance measure must appear but rank below the N measures
    assert "meas.fuel.machinery_maintenance.gh" in ids
    n_ranks = [i for i, r in enumerate(res) if r.measure.driver_kind == "fertiliser"]
    diesel_rank = ids.index("meas.fuel.machinery_maintenance.gh")
    assert min(n_ranks) < diesel_rank, "a fertiliser measure should outrank the diesel one"

    # the data-quality catch-all is present and ranked last
    assert res[-1].id == "meas.data.gather_farm_records.gh", f"last is {res[-1].id}"

    # processing-only measures must NOT match a farm
    assert "meas.proc.efficient_gari_stove.gh" not in ids
    print(f"[ok] Ghana maize -> {len(res)} measures, top = {top.id} on {top.target_source}")


def test_region_filter_excludes_canada() -> None:
    """Every measure in v1 is Ghana-scoped, so a Canadian farm gets nothing (except
    nothing - the region filter is hard)."""
    res = match_measures(_canada_payload(), reviewed_only=False, as_of=date(2026, 7, 15))
    assert res == [], f"Ghana-scoped measures leaked to a Canadian farm: {[r.id for r in res]}"
    print("[ok] region filter: Canada farm matches 0 Ghana measures")


def test_crop_filter_is_hard() -> None:
    """The AWD rice measure must not surface for a maize-only farm."""
    res = match_measures(_ghana_maize_payload(), reviewed_only=False, as_of=date(2026, 7, 15))
    assert "meas.rice.awd.gh" not in [r.id for r in res], "rice AWD leaked to a maize farm"
    print("[ok] crop filter: rice AWD excluded from a maize farm")


def test_processing_matches_fuel_and_waste() -> None:
    res = match_measures(_gari_processor_payload(), reviewed_only=False, as_of=date(2026, 7, 15))
    ids = [r.id for r in res]
    assert "meas.proc.efficient_gari_stove.gh" in ids, "gari stove didn't match a gari processor"
    assert "meas.proc.byproduct_utilisation.gh" in ids, "byproduct measure didn't match waste source"
    # the gari stove targets the fuelwood hotspot (70%), so it should outrank the waste measure
    stove = ids.index("meas.proc.efficient_gari_stove.gh")
    waste = ids.index("meas.proc.byproduct_utilisation.gh")
    assert stove < waste, "the 70%-hotspot stove should outrank the 30% waste measure"
    # farm-only fertiliser measures must not match a processor
    assert "meas.n.split_application.gh" not in ids
    print(f"[ok] gari processor -> {ids[:3]}... targets fuel + waste hotspots")


def test_freshness_filter() -> None:
    """A measure past its valid_until is excluded, not down-ranked."""
    measures = load_measures()
    # synthesize an expired copy of the first measure via a temp library
    import dataclasses
    m0 = measures[0]
    expired = dataclasses.replace(m0, valid_until="2020-01-01")
    fresh = dataclasses.replace(m0, valid_until="2099-01-01")
    payload = _ghana_maize_payload()
    got_expired = match_measures(payload, measures=[expired], reviewed_only=False, as_of=date(2026, 7, 15))
    got_fresh = match_measures(payload, measures=[fresh], reviewed_only=False, as_of=date(2026, 7, 15))
    assert got_expired == [], "an expired measure was not filtered out"
    assert len(got_fresh) == 1, "a fresh measure was wrongly filtered"
    print("[ok] freshness filter: expired measure excluded, fresh one kept")


def test_reviewed_only_gate() -> None:
    """With reviewed_only=True and an all-unreviewed v1 library, nothing ships."""
    res = match_measures(_ghana_maize_payload(), reviewed_only=True, as_of=date(2026, 7, 15))
    assert res == [], "unreviewed measures leaked through the production gate"
    print("[ok] reviewed_only gate: 0 measures until human sign-off")


def test_min_share_drops_negligible_source() -> None:
    """A pesticide contributing 0.5% of climate impact must not surface an IPM
    recommendation - that's noise, and the real engine produced exactly this case for a
    farm already practising IPM."""
    p = _ghana_maize_payload()
    p["input_matches"].append({"input": "Lambda-cyhalothrin", "kind": "pesticide", "matched": "..."})
    p["contribution_by_source"]["Lambda-cyhalothrin"] = {"Climate change": {"value": 0.005, "unit": "kg CO2-eq"}}
    p["iso_report"]["interpretation"]["contribution_analysis"]["by_source"].append(
        {"source": "Lambda-cyhalothrin", "per_kg": 0.005, "share": 0.005})
    res = match_measures(p, reviewed_only=False, as_of=date(2026, 7, 15))  # default min_share=0.02
    assert "meas.pest.ipm.gh" not in [r.id for r in res], "IPM surfaced on a 0.5% pesticide source"
    # lowering the floor lets it back in - proves the filter, not a missing measure
    res_low = match_measures(p, reviewed_only=False, as_of=date(2026, 7, 15), min_share=0.0)
    assert "meas.pest.ipm.gh" in [r.id for r in res_low]
    print("[ok] min_share drops a negligible (0.5%) pesticide source")


def test_context_scale_filter_is_hard() -> None:
    """When the caller supplies farm size, a measure whose scale window excludes it is
    dropped (not merely flagged as a data gap)."""
    p = _ghana_maize_payload()
    # meas.n.split_application.gh requires scale 0.2..50 ha. A 200 ha farm is out of range.
    big = match_measures(p, reviewed_only=False, as_of=date(2026, 7, 15),
                         context={"farm_size_ha": 200.0})
    assert "meas.n.split_application.gh" not in [r.id for r in big], "out-of-scale measure kept"
    # a 4 ha farm is in range and keeps it, with no scale data-gap recorded
    small = match_measures(p, reviewed_only=False, as_of=date(2026, 7, 15),
                           context={"farm_size_ha": 4.0})
    hit = next((r for r in small if r.id == "meas.n.split_application.gh"), None)
    assert hit is not None, "in-scale measure dropped"
    assert not any("farm size" in g for g in hit.data_gaps), "scale gap recorded despite context"
    print("[ok] context scale filter: 200ha drops sub-50ha measure, 4ha keeps it with no gap")


def test_off_axis_system_does_not_nuke_everything() -> None:
    """The request's primary_farming_system ('SemiCommercial') is a market-orientation
    axis, not the measure production-practice axis. Passing it must NOT drop every farm
    measure - it's simply not comparable, so it's a data gap, not a hard filter."""
    off = match_measures(_ghana_maize_payload(), reviewed_only=False, as_of=date(2026, 7, 15),
                         context={"system": "SemiCommercial"})
    assert len(off) >= 3, f"off-axis system collapsed the plan to {len(off)} measures"
    # a genuine in-vocabulary system still filters hard
    org = match_measures(_ghana_maize_payload(), reviewed_only=False, as_of=date(2026, 7, 15),
                         context={"system": "organic"})
    # split_application is conventional/intensive only -> dropped for an organic farm
    assert "meas.n.split_application.gh" not in [r.id for r in org]
    print(f"[ok] off-axis system kept {len(off)} measures; in-vocab 'organic' still filters")


def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as e:
            failed += 1
            print(f"[FAIL] {t.__name__}: {e}")
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"[ERROR] {t.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
