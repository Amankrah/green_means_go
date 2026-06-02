#!/usr/bin/env python3
"""
test_query.py — proves the cradle-to-gate solver on a synthetic system with a
KNOWN analytical answer, including a technosphere loop (which would break a
recursive walk but not a matrix solve).

System (functional unit = 1 kg of product P_grain):
  P_grain : ref out 1 kg; inputs 2 kWh electricity; emits 0.5 kg CO2 directly
  P_elec  : ref out 1 kWh; inputs 0.1 kg steel;       emits 0.8 kg CO2 / kWh
  P_steel : ref out 1 kg;  inputs 3 kWh electricity;  emits 1.0 kg CO2 / kg
            ^ steel needs electricity needs steel -> a LOOP

Solve T s = f, g = B s.  We also characterize with a one-flow "GWP" method
(CF: CO2 = 1 kg CO2-eq/kg).

Run:  python3 test_query.py
"""
from __future__ import annotations

import os
import tempfile

from canonical_store import CanonicalStore
from query import CanonicalQuery

CO2 = "flow-co2"


def build_synthetic(db_path: str) -> dict:
    with CanonicalStore(db_path) as store:
        sid = store.upsert_source("synthetic", "v1", "test")
        run = store.start_run(sid, "test", "memory")

        store.add_flows(sid, [
            {"uid": CO2, "name": "Carbon dioxide", "flow_type": "ELEMENTARY_FLOW", "ref_unit": "kg"},
            {"uid": "f-grain", "name": "grain", "flow_type": "PRODUCT_FLOW", "ref_unit": "kg"},
            {"uid": "f-elec", "name": "electricity", "flow_type": "PRODUCT_FLOW", "ref_unit": "kWh"},
            {"uid": "f-steel", "name": "steel", "flow_type": "PRODUCT_FLOW", "ref_unit": "kg"},
        ])

        def proc(uid, name, ref_flow, ref_unit, exchanges):
            store.add_process(sid, {"uid": uid, "name": name, "ref_flow": ref_flow,
                                    "ref_amount": 1.0, "ref_unit": ref_unit})
            store.add_exchanges([{"process_uid": uid, **e} for e in exchanges])

        proc("P_grain", "grain production", "f-grain", "kg", [
            {"flow_uid": "f-grain", "is_input": 0, "is_reference": 1, "amount": 1.0, "unit": "kg"},
            {"flow_uid": "f-elec", "is_input": 1, "amount": 2.0, "unit": "kWh", "provider_process_uid": "P_elec"},
            {"flow_uid": CO2, "is_input": 0, "is_elementary": 1, "amount": 0.5, "unit": "kg"},
        ])
        proc("P_elec", "electricity", "f-elec", "kWh", [
            {"flow_uid": "f-elec", "is_input": 0, "is_reference": 1, "amount": 1.0, "unit": "kWh"},
            {"flow_uid": "f-steel", "is_input": 1, "amount": 0.1, "unit": "kg", "provider_process_uid": "P_steel"},
            {"flow_uid": CO2, "is_input": 0, "is_elementary": 1, "amount": 0.8, "unit": "kg"},
        ])
        proc("P_steel", "steel", "f-steel", "kg", [
            {"flow_uid": "f-steel", "is_input": 0, "is_reference": 1, "amount": 1.0, "unit": "kg"},
            {"flow_uid": "f-elec", "is_input": 1, "amount": 3.0, "unit": "kWh", "provider_process_uid": "P_elec"},
            {"flow_uid": CO2, "is_input": 0, "is_elementary": 1, "amount": 1.0, "unit": "kg"},
        ])

        # one-flow GWP method
        store.add_impact_method(sid, "m-gwp", "GWP test")
        store.add_impact_category(sid, "c-gwp", "Climate change", "kg CO2-eq", "m-gwp")
        store.add_cfs("c-gwp", [{"flow_uid": CO2, "factor": 1.0, "unit": "kg CO2-eq"}])
        store.finish_run(run, "ok", {"flows": 4, "processes": 3})
        store.commit()
    return {"target": "P_grain"}


def analytical():
    # Solve the loop by hand.
    # Let e = total kWh electricity, t = total kg steel, per 1 kg grain.
    # elec demanded: grain needs 2; steel needs 3 per kg steel; steel needs 0.1 kg per kWh elec.
    #   e = 2 + 3*t
    #   t = 0.1 * e
    # => e = 2 + 3*(0.1 e) = 2 + 0.3 e => 0.7 e = 2 => e = 2/0.7
    e = 2.0 / 0.7
    t = 0.1 * e
    # CO2: grain 0.5 (x1) + elec 0.8*e + steel 1.0*t
    co2 = 0.5 + 0.8 * e + 1.0 * t
    return {"elec_kWh": e, "steel_kg": t, "co2_kg": co2}


def main() -> int:
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    try:
        build_synthetic(path)
        with CanonicalQuery(path) as q:
            res = q.cradle_to_gate("P_grain", method_name="GWP")
        got_co2 = res.elementary_flows[CO2]["amount"]
        got_impact = res.impacts.get("Climate change", {}).get("value")
        exp = analytical()

        ok = True
        def check(label, got, want, tol=1e-9):
            nonlocal ok
            good = abs(got - want) < tol
            ok = ok and good
            print(f"  {'PASS' if good else 'FAIL'}  {label}: got {got:.6f}, want {want:.6f}")

        print(f"Synthetic cradle-to-gate (target=grain, supply chain={res.n_processes} processes, has loop):")
        check("total CO2 (elementary)", got_co2, exp["co2_kg"])
        check("characterized GWP", got_impact, exp["co2_kg"])
        print(f"  (analytical: elec={exp['elec_kWh']:.4f} kWh, steel={exp['steel_kg']:.4f} kg, CO2={exp['co2_kg']:.4f} kg)")
        print("\nRESULT:", "ALL PASS ✅" if ok else "FAILURES ❌")
        return 0 if ok else 1
    finally:
        for ext in ("", "-wal", "-shm"):
            try: os.remove(path + ext)
            except OSError: pass


if __name__ == "__main__":
    raise SystemExit(main())
