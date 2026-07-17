#!/usr/bin/env python3
"""
test_economics.py — proves the economic screen against the REAL gathered price CSV.

Run:  python3 test_economics.py   (from engine/recommend/)

If the SRID CSV isn't present (data/ is untracked), the price-dependent tests skip
rather than fail — the code degrades to "no price data", and that path is tested too.
"""
from __future__ import annotations

import sys
from datetime import date

try:
    from .prices import PriceBook
    from .economics import (estimate_annual_revenue, screen_measures, build_action_plan,
                            recommend)
    from .schema import Horizon
except ImportError:
    from prices import PriceBook
    from economics import (estimate_annual_revenue, screen_measures, build_action_plan,
                           recommend)
    from schema import Horizon

_AS_OF = date(2026, 7, 15)


def _ghana_maize_payload() -> dict:
    return {
        "country": "Ghana",
        "breakdown_by_food": {"maize (2000kg)": {}, "cowpea (500kg)": {}},
        "input_matches": [
            {"input": "Urea 46-0-0 fertiliser", "kind": "fertiliser", "matched": "urea"},
            {"input": "diesel, burned in agricultural machinery", "kind": "fuel", "matched": "diesel"},
        ],
        "contribution_by_source": {
            "Urea 46-0-0 fertiliser": {"Climate change": {"value": 0.5, "unit": "kg CO2-eq"}},
            "diesel, burned in agricultural machinery": {"Climate change": {"value": 0.3, "unit": "kg CO2-eq"}},
            "Field emissions (on-farm)": {"Climate change": {"value": 0.2, "unit": "kg CO2-eq"}},
        },
        "iso_report": {"interpretation": {"contribution_analysis": {"by_source": [
            {"source": "Urea 46-0-0 fertiliser", "per_kg": 0.5, "share": 0.5},
            {"source": "diesel, burned in agricultural machinery", "per_kg": 0.3, "share": 0.3},
            {"source": "Field emissions (on-farm)", "per_kg": 0.2, "share": 0.2},
        ]}}},
    }


def _gari_processor_payload() -> dict:
    return {
        "country": "Ghana",
        "breakdown_by_product": {"Gari": {"output_kg": 50000}},
        "input_matches": [
            {"input": "fuelwood (facility fuel)", "kind": "fuel", "matched": "wood"},
        ],
        "contribution_by_source": {
            "fuelwood (facility fuel)": {"Climate change": {"value": 1.0, "unit": "kg CO2-eq"}},
        },
        "iso_report": {"interpretation": {"contribution_analysis": {"by_source": [
            {"source": "fuelwood (facility fuel)", "per_kg": 1.0, "share": 1.0},
        ]}}},
    }


def _has_prices(pb: PriceBook) -> bool:
    return pb.n_rows > 0


# --- price feed -------------------------------------------------------------------

def test_pricebook_loads_real_csv() -> None:
    pb = PriceBook.load()
    if not _has_prices(pb):
        print("[skip] SRID CSV not present; price tests skipped")
        return
    assert pb.n_rows > 5000, f"expected thousands of rows, got {pb.n_rows}"
    q = pb.price("maize", as_of=_AS_OF)
    assert q is not None, "no price for maize"
    assert 1 < q.price_ghs_per_kg < 100, f"implausible maize price {q.price_ghs_per_kg}"
    assert q.source in ("wholesale", "retail", "mixed")
    # Oct-2025 data vs Jul-2026 as_of -> must be flagged stale, not silently used as current
    assert q.stale is True, "9-month-old price not flagged stale"
    print(f"[ok] PriceBook: {pb.n_rows} rows, maize={q.price_ghs_per_kg} GHS/kg [{q.source}], stale={q.stale}")


def test_missing_commodity_returns_none() -> None:
    pb = PriceBook.load()
    if not _has_prices(pb):
        print("[skip] no CSV"); return
    # cocoa is a COCOBOD series, not in the MoFA food-crop feed
    assert pb.price("cocoa", as_of=_AS_OF) is None, "cocoa should not match the MoFA feed"
    print("[ok] missing commodity (cocoa) -> None, not a fabricated price")


# --- revenue ----------------------------------------------------------------------

def test_revenue_derivation() -> None:
    pb = PriceBook.load()
    if not _has_prices(pb):
        print("[skip] no CSV"); return
    rev = estimate_annual_revenue(_ghana_maize_payload(), pb, region="GH", as_of=_AS_OF)
    assert rev.total_ghs is not None and rev.total_ghs > 0, "no revenue derived"
    assert rev.basis == "derived from prices"
    assert rev.priced_fraction == 1.0, f"maize+cowpea should both price; got {rev.priced_fraction}"
    # 2000kg maize + 500kg cowpea at wholesale medians -> a few tens of thousands GHS
    assert 5000 < rev.total_ghs < 200000, f"implausible total {rev.total_ghs}"
    assert rev.stale_prices is True and any("older" in g for g in rev.gaps)
    assert rev.unit_assumption.startswith("GHS/kg"), "unit assumption not surfaced"
    print(f"[ok] revenue: {rev.total_ghs:.0f} GHS/yr from {len(rev.lines)} crops, stale flagged")


def test_revenue_context_override() -> None:
    pb = PriceBook.load()
    rev = estimate_annual_revenue(_ghana_maize_payload(), pb, region="GH", as_of=_AS_OF,
                                  context={"annual_revenue_ghs": 42000})
    assert rev.total_ghs == 42000 and rev.basis == "user-provided"
    print("[ok] revenue: user-provided figure overrides price derivation")


def test_revenue_unpriced_crop_is_a_gap_not_a_guess() -> None:
    pb = PriceBook.load()
    if not _has_prices(pb):
        print("[skip] no CSV"); return
    payload = _ghana_maize_payload()
    payload["breakdown_by_food"]["cocoa (300kg)"] = {}
    rev = estimate_annual_revenue(payload, pb, region="GH", as_of=_AS_OF)
    assert any("cocoa" in g for g in rev.gaps), "unpriced cocoa not reported as a gap"
    assert rev.priced_fraction < 1.0
    cocoa_line = next(l for l in rev.lines if l.crop == "cocoa")
    assert cocoa_line.revenue_ghs is None and not cocoa_line.priced
    print("[ok] revenue: unpriced cocoa -> gap + null line, never a fabricated number")


# --- screen -----------------------------------------------------------------------

def test_screen_payback_for_capex_measure() -> None:
    """The gari stove has capex 1800 GHS and saves 62 GHS/month -> payback ~29 months."""
    pb = PriceBook.load()
    from matcher import match_measures
    matched = match_measures(_gari_processor_payload(), reviewed_only=False, as_of=_AS_OF)
    screened = screen_measures(matched, _gari_processor_payload(), pb, as_of=_AS_OF)
    stove = next((s for s in screened if s.measure.id == "meas.proc.efficient_gari_stove.gh"), None)
    assert stove is not None, "gari stove not in screened set"
    assert stove.capex_ghs == 1800
    assert stove.annual_saving_ghs == 62 * 12, f"expected 744 saving/yr, got {stove.annual_saving_ghs}"
    assert stove.payback_months is not None and 25 < stove.payback_months < 35, \
        f"payback {stove.payback_months} not ~29 months"
    assert stove.cost_tier == "MediumCost"
    print(f"[ok] screen: gari stove payback={stove.payback_months}mo, tier={stove.cost_tier}, "
          f"afford={stove.affordability}")


def test_per_ha_opex_needs_farm_size() -> None:
    """A per-hectare opex can't be annualised without a farm size — it must be a gap,
    not a silently-wrong annual figure."""
    pb = PriceBook.load()
    from matcher import match_measures
    payload = _ghana_maize_payload()
    matched = match_measures(payload, reviewed_only=False, as_of=_AS_OF)
    # without size
    no_size = screen_measures(matched, payload, pb, as_of=_AS_OF)
    ipm_like = next((s for s in no_size if s.measure.economics.opex_per == "ha/season"
                     and s.measure.economics.opex_delta), None)
    if ipm_like is not None:
        assert ipm_like.annual_saving_ghs is None
        assert any("farm size" in g for g in ipm_like.econ_gaps)
    # with size, the same measure annualises
    with_size = screen_measures(matched, payload, pb, as_of=_AS_OF,
                                context={"farm_size_ha": 4.0})
    same = next((s for s in with_size if ipm_like and s.measure.id == ipm_like.measure.id), None)
    if same is not None:
        assert same.annual_saving_ghs is not None, "per-ha opex didn't annualise with a size"
    print("[ok] screen: per-ha opex is a gap without farm size, resolves with it")


# --- plan -------------------------------------------------------------------------

def test_action_plan_is_sequenced() -> None:
    pb = PriceBook.load()
    rec = recommend(_ghana_maize_payload(), pricebook=pb, region_code="GH", as_of=_AS_OF,
                    reviewed_only=False, context={"farm_size_ha": 4.0})
    phases = rec.plan["phases"]
    assert phases, "empty action plan"
    keys = [p["key"] for p in phases]
    # phases must appear in do-now -> this-year -> plan-ahead order
    order = {"start_now": 0, "this_year": 1, "plan_ahead": 2}
    assert keys == sorted(keys, key=lambda k: order[k]), f"phases out of order: {keys}"
    # every screened measure lands in exactly one phase
    n_in_plan = sum(len(p["measures"]) for p in phases)
    assert n_in_plan == len(rec.screened), "measures lost or duplicated in the plan"
    print(f"[ok] plan: {len(rec.screened)} measures across phases {keys}")


def test_end_to_end_recommend_shape() -> None:
    pb = PriceBook.load()
    rec = recommend(_gari_processor_payload(), pricebook=pb, region_code="GH", as_of=_AS_OF,
                    reviewed_only=False)
    assert hasattr(rec, "revenue") and hasattr(rec, "screened") and hasattr(rec, "plan")
    assert isinstance(rec.screened, list)
    print(f"[ok] recommend(): revenue basis={rec.revenue.basis}, "
          f"{len(rec.screened)} measures, {len(rec.plan['phases'])} phases")


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
            import traceback
            print(f"[ERROR] {t.__name__}: {type(e).__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
