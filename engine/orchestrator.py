#!/usr/bin/env python3
"""
orchestrator.py — the region-aware cradle-to-gate farm LCA engine (Option A).

Combines:
  • on-farm LCI  — field emissions from the Rust kernel (N2O, CH4, fuel CO2 …),
    mapped to canonical store flows (flowmap.py);
  • supply-chain LCI — each purchased input matched to a background process
    (matching.py) and solved cradle-to-gate (query.py);
then characterizes the MERGED inventory through the single validated canonical
path (query.characterize_flows), and reports the on-farm / upstream contribution split.

Region-parameterised via regions.py, so Ghana, Nigeria and Canada are registry
entries — Canada prefers ecoinvent CA backgrounds and the EF 3.1 method automatically.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
from ingestion.canonical_store import DEFAULT_DB          # noqa: E402
from ingestion.query import CanonicalQuery                # noqa: E402
from ingestion.matching import ProcessMatcher             # noqa: E402

# engine-local imports work both as a package (engine.orchestrator) and as a script
try:
    from .regions import get_region, location_rank
    from .flowmap import OnFarmFlowMap
except ImportError:
    from regions import get_region, location_rank
    from flowmap import OnFarmFlowMap


def _add(inv: dict, uid: str, amount: float, name: str = None, unit: str = None) -> None:
    rec = inv.get(uid)
    if rec:
        rec["amount"] += amount
    else:
        inv[uid] = {"name": name, "unit": unit, "amount": amount}


@dataclass
class AssessmentResult:
    region: str
    method: str
    impacts: dict = field(default_factory=dict)            # total midpoints
    contribution: dict = field(default_factory=dict)       # {"on_farm":{}, "supply_chain":{}}
    contribution_by_source: dict = field(default_factory=dict)  # {source label: {category: {value,unit}}}
    input_matches: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    inventory: dict = field(default_factory=dict)          # merged {flow_uid: {name,unit,amount}}


class FarmLCA:
    def __init__(self, region_code: str, method: str = None, db=DEFAULT_DB):
        self.region = get_region(region_code)
        self.q = CanonicalQuery(db)
        self.matcher = ProcessMatcher(self.q)
        self.matcher.build_index()
        self.fmap = OnFarmFlowMap(db)
        self.method = method or self.region.default_method

    def close(self):
        self.q.close(); self.fmap.close()

    def _match_input(self, text: str, expand: bool = False) -> dict | None:
        """Region-aware match. Retrieval is run twice — on the raw text AND on the text
        augmented with the region name — then the union is ranked by (location fit, score).
        The augmented query surfaces region-specific processes the raw query misses: the
        embedding text includes each process's location, so "electricity grid Canada"
        pulls up the Canadian grid that "electricity grid" alone ranks below foreign grids.
        """
        cands = self.matcher.match(text, top_k=12, expand=expand)
        cands += self.matcher.match(f"{text} {self.region.name}", top_k=12, expand=False)
        if not cands:
            return None
        by_uid = {}
        for c in cands:                      # dedupe, keep best score per process
            if c["uid"] not in by_uid or c["score"] > by_uid[c["uid"]]["score"]:
                by_uid[c["uid"]] = c
        best = max(c["score"] for c in by_uid.values())
        pool = [c for c in by_uid.values() if c["score"] >= max(0.35, 0.6 * best)] or list(by_uid.values())
        # rank: region-location fit first, then similarity
        pool.sort(key=lambda c: (location_rank(self.region, c.get("location")), -c["score"]))
        return pool[0]

    def assess_farm(self, rust_assessment: dict, purchased_inputs: list[dict],
                    expand_matching: bool = False) -> AssessmentResult:
        """Full Option-A path: run the Rust LCI kernel on `rust_assessment` for on-farm
        field emissions, then combine with the supply-chain LCI and characterize."""
        try:
            from .rust_kernel import onfarm_lci_from_assessment
            from .field_model import adjust_field_emissions
        except ImportError:
            from rust_kernel import onfarm_lci_from_assessment
            from field_model import adjust_field_emissions
        on_farm_lci, rust_notes = onfarm_lci_from_assessment(rust_assessment)
        # expert-level field-emission adjustments (regional climate N2O, legume intercrop credit)
        on_farm_lci, field_notes = adjust_field_emissions(on_farm_lci, rust_assessment, self.region)
        res = self.assess(on_farm_lci, purchased_inputs, expand_matching)
        res.notes = rust_notes + field_notes + res.notes
        return res

    def assess(self, on_farm_lci: list[dict], purchased_inputs: list[dict],
               expand_matching: bool = False) -> AssessmentResult:
        """on_farm_lci: [{substance, quantity, unit}]  (substance keys per flowmap.ONFARM_FLOWS)
        purchased_inputs: [{name, amount, unit}]  (amount in the process reference unit, usually kg)."""
        res = AssessmentResult(region=self.region.name, method=self.method)

        # 1) on-farm field emissions -> canonical store flows
        onfarm: dict = {}
        for f in on_farm_lci:
            uid = self.fmap.resolve(f["substance"])
            if not uid:
                res.notes.append(f"on-farm flow '{f['substance']}' not mappable; skipped")
                continue
            _add(onfarm, uid, float(f["quantity"]), f["substance"], f.get("unit"))

        # 2) supply chain: match + solve each purchased input
        supply: dict = {}
        for inp in purchased_inputs:
            # match_as: match against a representative dataset name but keep inp["name"]
            # as the display label (used for pesticides -> generic agrochemical).
            target = inp.get("match_as") or inp["name"]
            m = self._match_input(target, expand=expand_matching)
            if not m and inp.get("fallback"):
                m = self._match_input(inp["fallback"], expand=expand_matching)
                if m:
                    res.notes.append(f"'{inp['name']}' not found; used representative '{inp['fallback']}'")
            if inp.get("match_as") and m:
                res.notes.append(f"pesticide '{inp['name']}' modelled with a representative agrochemical dataset")
            if not m:
                res.input_matches.append({**inp, "matched": None})
                res.notes.append(f"input '{inp['name']}' had no match; excluded")
                continue
            proc = self.q.get_process(m["uid"]) or {}
            ref_unit = proc.get("ref_unit")
            try:
                sc = self.q.cradle_to_gate(m["uid"], amount=float(inp["amount"]))
                for uid, ef in sc.elementary_flows.items():
                    _add(supply, uid, ef["amount"], ef.get("name"), ef.get("unit"))
                # per-source contribution: characterize THIS input's flows on their own so
                # the report can attribute each impact category to the input that drove it.
                res.contribution_by_source[inp["name"]] = self.q.characterize_flows(
                    sc.elementary_flows, self.method)
            except Exception as e:
                res.notes.append(f"solve failed for '{inp['name']}' -> {m['name']}: {e}")
            # The amount MUST be in the matched process's reference unit. Surface it so a
            # kg amount against an MJ/kWh process is caught, not silently mis-scaled.
            if inp.get("unit") and ref_unit and inp["unit"] != ref_unit:
                res.notes.append(
                    f"unit mismatch for '{inp['name']}': amount given in "
                    f"'{inp['unit']}' but '{m['name']}' is per '{ref_unit}' — convert first.")
            res.input_matches.append({
                "input": inp["name"], "amount": inp["amount"], "amount_unit": inp.get("unit"),
                "matched": m["name"], "ref_unit": ref_unit, "kind": inp.get("kind"),
                "source": self.q.source_label(m["uid"]),
                "location": m.get("location"), "score": m["score"],
            })

        # 3) characterize: parts (for the split) + merged total, all via the validated path
        res.contribution["on_farm"] = self.q.characterize_flows(onfarm, self.method)
        res.contribution["supply_chain"] = self.q.characterize_flows(supply, self.method)
        # field emissions as a named contribution source alongside the purchased inputs
        res.contribution_by_source["Field emissions (on-farm)"] = res.contribution["on_farm"]
        merged = {uid: dict(r) for uid, r in onfarm.items()}
        for uid, r in supply.items():
            _add(merged, uid, r["amount"], r["name"], r["unit"])
        res.impacts = self.q.characterize_flows(merged, self.method)
        res.inventory = merged
        return res

    def characterize(self, inventory: dict, method_name: str) -> dict:
        """Characterize a merged inventory with another method (e.g. an endpoint method)."""
        return self.q.characterize_flows(inventory, method_name)


if __name__ == "__main__":
    import json, argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--region", default="GH")
    args = ap.parse_args()
    eng = FarmLCA(args.region)
    # tiny demo: on-farm N2O + fuel CO2, purchased urea + diesel
    r = eng.assess(
        on_farm_lci=[{"substance": "N2O", "quantity": 0.004, "unit": "kg"},
                     {"substance": "CO2", "quantity": 1.5, "unit": "kg"}],
        purchased_inputs=[{"name": "urea fertiliser", "amount": 0.03, "unit": "kg"},
                          {"name": "diesel, burned in agricultural machinery", "amount": 0.5, "unit": "kg"}],
    )
    print(json.dumps({"region": r.region, "method": r.method,
                      "impacts": {k: v for k, v in list(r.impacts.items())[:6]},
                      "matches": r.input_matches, "notes": r.notes}, indent=2, default=str))
