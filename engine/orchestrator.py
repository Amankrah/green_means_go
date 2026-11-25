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
    from . import grid_calibration, regional_lcia
    from . import units
    from . import product_identity as pid
except ImportError:
    from regions import get_region, location_rank
    from flowmap import OnFarmFlowMap
    import grid_calibration
    import units
    import regional_lcia
    import product_identity as pid

import os

# Candidate adjudication (WS5 hook). When the gated candidates are a near tie between
# DIFFERENT reference products, or the identity gate overruled the most similar dataset
# (cross product family), an optional LLM adjudicator may pick among them. The threshold is
# calibrated on the 174 executed regression rows (engine/test_matcher_regression.py), with
# location variants of one dataset counted as one product (_product_key). Gaps observed
# between the top two DIFFERENT products: tomato paste vs tomato 0.0004, petrol per MJ vs
# per kg 0.004, honey small- vs large-scale 0.008, foliar NPK P2O5 vs NPK 0.009 (all
# genuinely ambiguous); clear wins such as cocoa bean (0.05+), peanut vs peanut seed
# (0.049) and urea 46% vs urea as N (0.044) are separated by far more. 0.01 sits between
# the two groups and 100x above the embedding-API jitter (4th decimal); at 0.01 about 18%
# of rows trigger (31 of 174), at 0.02 about 24% (42).
ADJUDICATE_GAP = 0.01
ADJUDICATE_MAX_CANDIDATES = 6
# Region recall window: identity-passing datasets within this cosine distance of the best
# retrieved passing candidate are added to the ranking pool even if the embedding top-k
# missed them. Same-product location variants of one dataset differ by about 0.01 to 0.03
# (only the location string in the embedded text differs), so 0.03 admits them while
# keeping out other products of the same family. Calibrated on the regression set.
REGION_RECALL_DELTA = 0.03
# Region fallback window: identity-passing datasets located better in the region's
# preference list than every retrieved candidate (e.g. Burkina Faso has no national grid in
# the store and only foreign or RoW grids were retrieved; the "Africa"/RAF market group is
# preferred) are admitted if within this distance of the candidate that would otherwise win.
# 0.10 is the spread observed on the six-region mapping between a
# country-specific grid or plant and its RAF/RoW variant (only the location words differ).
REGION_FALLBACK_DELTA = 0.10


def _product_key(ref: str | None) -> str:
    """Location- and database-neutral product label, so two location variants of one
    dataset ("Urea ... {RoW} - Adapted from WFLDB U" / "... {CN} ...") count as the same
    product when deciding whether candidates are a near tie between DIFFERENT products."""
    import re as _re
    t = (ref or "").lower()
    t = _re.sub(r"\{[^}]*\}", " ", t)
    t = t.split("|")[0].split(" - ")[0]
    t = _re.sub(r"\b(cut-?off|u|s)\s*$", " ", t.strip())
    return " ".join(t.replace(",", " ").split())


def _adjudicator():
    """Lazily import engine/llm/adjudicate.py (owned by WS5). None when disabled
    (GMG_LLM_ADJUDICATE=0) or not installed."""
    if os.getenv("GMG_LLM_ADJUDICATE", "1").strip() == "0":
        return None
    try:
        try:
            from engine.llm.adjudicate import adjudicate
        except ImportError:
            from llm.adjudicate import adjudicate  # engine/ run as a script directory
        return adjudicate
    except ImportError:
        return None


def _emit(cb, stage: str, detail: str = "", index=None, total=None) -> None:
    """Fire a progress callback if one was supplied. Never raises — progress reporting
    must not be able to break an assessment."""
    if cb is None:
        return
    try:
        cb(stage, detail=detail, index=index, total=total)
    except Exception:
        pass


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
    # Raw elementary flows per source (method-independent), so a later method switch can
    # re-characterize the per-source contribution instead of losing it. Same shape as
    # `inventory`: {source label: {flow_uid: {name,unit,amount}}}.
    contribution_flows_by_source: dict = field(default_factory=dict)
    input_matches: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    inventory: dict = field(default_factory=dict)          # merged {flow_uid: {name,unit,amount}}


def _irrigation_override(on_farm_lci: list[dict], assessment: dict) -> tuple[list[dict], list[str]]:
    """Single source of truth for irrigation volume. engine/inputs.irrigation_water gives the
    farmer's measured volume or the cited FAO crop-water-need estimate; it replaces the
    kernel's generic m3/ha-by-system withdrawal so that water_scarcity.apply books the
    consumed share once, on the regional AWARE flow (farm_flows only re-labels the
    withdrawal by source, which is characterisation-neutral)."""
    try:
        from .inputs import irrigation_water
    except ImportError:
        from inputs import irrigation_water
    w = irrigation_water(assessment)
    if not w:
        return on_farm_lci, []
    kept = [f for f in on_farm_lci if f.get("substance") != "water"]
    kernel_m3 = sum(float(f.get("quantity") or 0.0) for f in on_farm_lci if f.get("substance") == "water")
    kept.append({"substance": "water", "quantity": w["m3"], "unit": "m3", "source": w["system"]})
    basis = "measured by the farmer" if not w["estimated"] else f"estimated ({w['source']})"
    return kept, [f"irrigation withdrawal {w['m3']:.0f} m3 ({w['system']}), {basis}; replaces the "
                  f"kernel default of {kernel_m3:.0f} m3"]


# Production-system qualifiers that ecoinvent writes as a separate comma-delimited
# attribute of the reference product ("maize seed, organic, for sowing"). A dataset carrying
# one the user did not ask for (or lacking one the user asked for) is a different
# production system: ranked after datasets that fit. Matching whole attributes only, so "inorganic potassium fertiliser" and
# "compost (for organic fertiliser)" are not affected.
_SYSTEM_QUALIFIERS = ("organic", "swiss integrated production", "integrated production")


def _system_mismatch(text: str, cand: dict) -> int:
    import re as _re
    q = (text or "").lower()
    prod = (cand.get("reference_product") or cand.get("name") or "").lower().split("|")[0]
    attrs = {a.strip() for a in prod.split(",")[1:]}
    asked = {k for k in _SYSTEM_QUALIFIERS if _re.search(r"\b" + _re.escape(k) + r"\b", q)}
    has = {k for k in _SYSTEM_QUALIFIERS if k in attrs}
    return int(asked != has)


class FarmLCA:
    def __init__(self, region_code: str, method: str = None, db=DEFAULT_DB, matcher=None,
                 query=None):
        self.region = get_region(region_code)
        # `query` / `matcher` let a caller share one store connection and one loaded
        # ~300 MB index across regions and methods (engine/service.py, tests, batch runs).
        self.q = query or CanonicalQuery(db)
        self.matcher = matcher or ProcessMatcher(self.q)
        if self.matcher.matrix is None:
            self.matcher.build_index()
        self.fmap = OnFarmFlowMap(db)
        self.method = method or self.region.default_method

    def close(self):
        self.q.close(); self.fmap.close()

    # ---- matching ------------------------------------------------------------------
    def _provided(self, c: dict) -> frozenset:
        """Concepts a candidate dataset provides (cached per uid on the shared matcher)."""
        cache = self.matcher.__dict__.setdefault("_identity_cache", {})
        got = cache.get(c["uid"])
        if got is None:
            ref = c.get("reference_product") or self.matcher.reference_product(c["uid"])
            got = pid.candidate_concepts(c.get("name"), ref)
            cache[c["uid"]] = got
        return got

    def _passes(self, ident, c: dict) -> bool:
        ref = c.get("reference_product") or ""
        return pid.passes(ident, self._provided(c), f"{c.get('name') or ''} {ref}")

    def _identity_recall(self, text: str, ident, top_k: int = 40, where=None) -> list[dict]:
        """Every dataset in the store that passes the gate, scored against `text`. Used only
        when the embedding top-k holds no candidate of the right product."""
        if ident.basis == "none":
            return []
        if ident.basis == "token":
            uids = [u for u, meta in zip(self.matcher.uids, self.matcher.meta)
                    if self._passes(ident, {"uid": u, "name": meta.get("name"),
                                            "reference_product": self.matcher.reference_product(u)})]
        else:
            # inverted index concept -> uids, built once per (shared) matcher
            inv = self.matcher.__dict__.get("_concept_index")
            if inv is None:
                inv = {}
                for u, meta in zip(self.matcher.uids, self.matcher.meta):
                    for cid in self._provided({"uid": u, "name": meta.get("name")}):
                        inv.setdefault(cid, set()).add(u)
                self.matcher._concept_index = inv
            sets = []
            for cid in ident.concepts:
                ok = set()
                for prov, us in inv.items():
                    if pid.satisfied(cid, frozenset({prov})):
                        ok |= us
                sets.append(ok)
            uids = sorted(set.intersection(*sets)) if sets else []
            # full gate (symmetric qualifiers, waste streams) on the index hits
            meta = dict(zip(self.matcher.uids, self.matcher.meta))
            uids = [u for u in uids
                    if self._passes(ident, {"uid": u, "name": meta[u].get("name"),
                                            "reference_product": self.matcher.reference_product(u)})]
        if where is not None:
            meta = dict(zip(self.matcher.uids, self.matcher.meta))
            uids = [u for u in uids if where(meta[u])]
        return self.matcher.score_uids(text, uids, top_k=top_k)

    def _rank(self, pool: list[dict], text: str = "") -> list[dict]:
        """Production-system fit first (a conventional query must not land on an organic or
        Swiss-IP variant of the same product), then region preference, then similarity,
        then uid (fully deterministic)."""
        best = max(c["score"] for c in pool)
        kept = [c for c in pool if c["score"] >= max(0.35, 0.6 * best)] or list(pool)
        kept.sort(key=lambda c: (_system_mismatch(text, c),
                                 location_rank(self.region, c.get("location")),
                                 -c["score"], c["uid"]))
        return kept

    def _region_fallback(self, text: str, ident, passing: list[dict]) -> list[dict]:
        """Admit identity-passing store datasets located BETTER in the region's preference
        list than every retrieved passing candidate (e.g. the "Africa"/RAF market group
        when only RoW or foreign grids were retrieved for Burkina Faso), if within
        REGION_FALLBACK_DELTA of the candidate region ranking would otherwise pick."""
        # Step down the preference tiers: each admitted tier becomes the new reference, so
        # foreign -> RoW -> Africa/RAF is reached in steps of at most REGION_FALLBACK_DELTA.
        passing = list(passing)
        for _ in range(len(self.region.location_prefer) + 1):
            best_rank = min(location_rank(self.region, c.get("location")) for c in passing)
            if best_rank == 0:
                break
            # reference = the candidate region ranking would otherwise pick (best tier)
            top = max(c["score"] for c in passing
                      if location_rank(self.region, c.get("location")) == best_rank)
            have = {c["uid"] for c in passing}
            better = lambda meta, br=best_rank: location_rank(self.region, meta.get("location")) < br  # noqa: E731
            extra = [c for c in self._identity_recall(text, ident, top_k=200, where=better)
                     if c["uid"] not in have
                     and c["score"] >= max(0.35, top - REGION_FALLBACK_DELTA)]
            if not extra:
                break
            passing += extra
        return passing

    def _unit_compatible(self, passing: list[dict], context: dict, text: str) -> list[dict]:
        """Prefer datasets whose reference unit the input amount can be converted to
        (engine/units.py). An ecoinvent multi-output treatment activity exists once per
        product ("treatment of biowaste by anaerobic digestion | biogas" per m3 and "... |
        biowaste" per kg); a kg of waste must take the kg-referenced one, not be dropped at
        solve time for a unit mismatch. If no candidate is compatible, all are kept and the
        solve reports the mismatch as before."""
        unit = context.get("amount_unit")
        if not unit:
            return passing
        try:
            from . import units
        except ImportError:
            import units
        probe = {"name": context.get("input_name") or text, "match_as": text, "unit": unit,
                 "amount": 1.0}
        if context.get("substance"):
            probe["substance"] = context["substance"]
        ok = []
        for c in passing:
            ref_unit = c.get("ref_unit")
            if ref_unit is None:
                ref_unit = (self.q.get_process(c["uid"]) or {}).get("ref_unit")
                c["ref_unit"] = ref_unit
            try:
                units.to_ref_unit(probe, ref_unit)
                ok.append(c)
            except units.UnitMismatchError:
                continue
        return ok or passing

    def _match_input(self, text: str, expand: bool = False, context: dict | None = None) -> dict | None:
        """Region-aware match behind a product-identity gate.

        1. Retrieval runs twice, on the raw text AND on the text augmented with the region
           name (the embedding text includes each process's location, so "electricity grid
           Canada" surfaces the Canadian grid the raw query ranks below foreign grids).
        2. Identity gate (engine/product_identity.py): a candidate must carry the query's
           product (controlled synonym table, read from its reference product) before region
           preference may choose it. If none of the retrieved candidates passes, every store
           dataset that passes is scored against the query (recall path).
        3. Passing candidates are ranked by (region fit, similarity, uid).
        4. If nothing in the store passes, the best GLOBAL similarity match is returned with
           needs_review=True instead of a wrong-product regional match.
        5. Optional adjudication (WS5 hook) on near ties between different products or
           when the gate overruled the most similar dataset.
        The returned candidate carries needs_review / review_reason / identity /
        adjudication keys for the input match report.
        """
        cands = self.matcher.match(text, top_k=12, expand=expand)
        cands += self.matcher.match(f"{text} {self.region.name}", top_k=12, expand=False)
        if not cands:
            return None
        by_uid = {}
        for c in cands:                      # dedupe, keep best score per process
            if c["uid"] not in by_uid or c["score"] > by_uid[c["uid"]]["score"]:
                by_uid[c["uid"]] = c
        allc = sorted(by_uid.values(), key=lambda c: (-c["score"], c["uid"]))
        ident = pid.query_identity(text)
        passing = [c for c in allc if self._passes(ident, c)]
        recalled = False
        if not passing:
            passing = self._identity_recall(text, ident)
            recalled = bool(passing)
        elif ident.basis != "token":
            # Region recall: a same-product dataset with (near) the best passing similarity
            # can sit just outside the embedding top-k (the cut-off jitters between API
            # calls). Admit such datasets so region preference sees every location variant
            # of the product, not only those that happened to be retrieved.
            top_pass = max(c["score"] for c in passing)
            have = {c["uid"] for c in passing}
            for c in self._identity_recall(text, ident):
                if c["uid"] not in have and c["score"] >= top_pass - REGION_RECALL_DELTA:
                    passing.append(c)
                    have.add(c["uid"])
        if passing:
            # unit fit first (so the region check sees only usable datasets), then the
            # region fallback, then unit fit again on what the fallback added
            passing = self._unit_compatible(passing, context or {}, text)
            if ident.basis in ("concept", "proxy"):   # not for loose (generic/token) identities
                passing = self._region_fallback(text, ident, passing)
                passing = self._unit_compatible(passing, context or {}, text)
        if passing:
            ranked = self._rank(passing, text)
            needs_review = ident.needs_review
            reason = pid.review_reason(ident)
        else:
            ranked = allc                    # best global similarity, NOT region-first
            needs_review = True
            reason = (f"no dataset in the store carries the product identity of '{text}' "
                      f"({ident.describe()}); returned the most similar dataset, which is "
                      f"a different product. Confirm or replace it.")
        chosen = dict(ranked[0])
        global_best = allc[0]
        cross_family = (global_best["uid"] != chosen["uid"]
                        and not self._passes(ident, global_best)) if passing else False
        chosen["needs_review"] = needs_review
        chosen["review_reason"] = reason
        chosen["identity"] = {"basis": ident.basis if passing else "none",
                              "concepts": list(ident.concepts),
                              "recall_path": recalled}
        chosen["adjudication"] = self._maybe_adjudicate(text, ranked, chosen, cross_family,
                                                        context or {})
        adj = chosen["adjudication"]
        if adj.get("adjudicated"):
            pick = next(c for c in ranked if c["uid"] == adj["uid"])
            keep = {k: chosen[k] for k in ("needs_review", "review_reason", "identity",
                                           "adjudication")}
            chosen = {**pick, **keep}
        return chosen

    def _maybe_adjudicate(self, text: str, ranked: list[dict], chosen: dict,
                          cross_family: bool, context: dict) -> dict:
        """Call the optional adjudicator on genuine ambiguity. Always returns the record
        {"adjudicated": bool, "rationale": str|None, ...} for the match report."""
        rec = {"adjudicated": False, "rationale": None}
        # distinct reference products among the ranked candidates, best score first
        seen, distinct = set(), []
        for c in sorted(ranked, key=lambda c: (-c["score"], c["uid"])):
            key = _product_key(c.get("reference_product") or c.get("name"))
            if key not in seen:
                seen.add(key)
                distinct.append(c)
        close = len(distinct) > 1 and (distinct[0]["score"] - distinct[1]["score"]) < ADJUDICATE_GAP
        triggers = [t for t, on in (("close_scores", close), ("cross_family", cross_family),
                                    ("needs_review", chosen.get("needs_review"))) if on]
        if not triggers:
            return rec
        rec["trigger"] = triggers
        fn = _adjudicator()
        if fn is None:
            return rec
        offered = ranked[:ADJUDICATE_MAX_CANDIDATES]
        payload = [{"uid": c["uid"], "name": c.get("name"),
                    "reference_product": c.get("reference_product"),
                    "location": c.get("location"),
                    "source": self.q.source_label(c["uid"]),
                    "ref_unit": (self.q.get_process(c["uid"]) or {}).get("ref_unit"),
                    "score": c["score"]} for c in offered]
        ctx = {"region": self.region.code, "region_name": self.region.name,
               "match_target": text, "triggers": triggers,
               "identity": chosen.get("identity"), **context}
        try:
            out = fn(text, ctx, payload)
        except Exception as e:               # an adjudicator failure must not break a run
            rec["error"] = f"{type(e).__name__}: {e}"
            return rec
        if not out or out.get("uid") not in {c["uid"] for c in offered}:
            return rec
        rec.update({"adjudicated": True, "uid": out["uid"],
                    "rationale": out.get("rationale"), "model": out.get("model"),
                    "changed_pick": out["uid"] != chosen["uid"]})
        return rec

    def resolve_input(self, inp: dict, expand: bool = False) -> tuple[dict | None, str | None]:
        """Match one purchased input: its match_as hint (or name) first; when that match
        has no candidate of the right product (needs_review), the input's declared
        fallbacks are tried and the first identity-passing one is used.
        Returns (match or None, fallback text used or None)."""
        target = inp.get("match_as") or inp["name"]
        ctx = {"input_name": inp.get("name"), "kind": inp.get("kind"),
               "amount_unit": inp.get("unit"), "substance": inp.get("substance")}
        m = self._match_input(target, expand=expand, context=ctx)
        chain = list(inp.get("fallbacks") or [])
        if inp.get("fallback") and inp["fallback"] not in chain:
            chain.append(inp["fallback"])
        chain = [fb for fb in chain if fb and fb != target]
        used = None
        if (m is None or m.get("needs_review")) and chain:
            for fb in chain:
                m2 = self._match_input(fb, expand=expand, context=ctx)
                if m2 is None:
                    continue
                if m is None or (not m2.get("needs_review")):
                    m, used = m2, fb
                if not m2.get("needs_review"):
                    break
        return m, used

    def assess_farm(self, rust_assessment: dict, purchased_inputs: list[dict],
                    expand_matching: bool = False, on_progress=None) -> AssessmentResult:
        """Full Option-A path: run the Rust LCI kernel on `rust_assessment` for on-farm
        field emissions, then combine with the supply-chain LCI and characterize."""
        try:
            from .rust_kernel import onfarm_lci_from_assessment
            from .field_model import adjust_field_emissions
        except ImportError:
            from rust_kernel import onfarm_lci_from_assessment
            from field_model import adjust_field_emissions
        _emit(on_progress, "inventory", "Field emissions (IPCC 2019)")
        on_farm_lci, rust_notes = onfarm_lci_from_assessment(rust_assessment)
        # expert-level field-emission adjustments (regional climate N2O, legume intercrop credit)
        on_farm_lci, field_notes = adjust_field_emissions(on_farm_lci, rust_assessment, self.region)
        on_farm_lci, water_notes = _irrigation_override(on_farm_lci, rust_assessment)
        field_notes = field_notes + water_notes
        res = self.assess(on_farm_lci, purchased_inputs, expand_matching, on_progress=on_progress)
        res.notes = rust_notes + field_notes + res.notes
        return res

    def assess(self, on_farm_lci: list[dict], purchased_inputs: list[dict],
               expand_matching: bool = False, on_progress=None) -> AssessmentResult:
        """on_farm_lci: [{substance, quantity, unit}]  (substance keys per flowmap.ONFARM_FLOWS)
        purchased_inputs: [{name, amount, unit}]  (amount in the process reference unit, usually kg).

        on_progress(stage, detail, index, total): optional callback fired at each stage
        (match / solve per input / characterize) so a caller can stream live progress."""
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
        _emit(on_progress, "match", "Matching inputs to background datasets")
        supply: dict = {}
        _n_inputs = len(purchased_inputs)
        for _i, inp in enumerate(purchased_inputs):
            _emit(on_progress, "solve", detail=inp.get("name", ""), index=_i + 1, total=_n_inputs)
            # match_as: match against a representative dataset name but keep inp["name"]
            # as the display label (used for pesticides -> generic agrochemical).
            target = inp.get("match_as") or inp["name"]
            # Live fallback chain: the declared fallbacks are tried when the primary target
            # has no dataset of the right product (identity gate), see resolve_input.
            m, used_fallback = self.resolve_input(inp, expand=expand_matching)
            if used_fallback:
                note = (f"'{inp['name']}' has no dataset of the right product as '{target}'; "
                        f"used fallback '{used_fallback}'")
                if "agricultural machinery" in used_fallback.lower():
                    note += (": agricultural machinery combustion is a last-resort proxy "
                             "for facility fuel and may misrepresent industrial emissions")
                res.notes.append(note)
            if m and m.get("needs_review"):
                res.notes.append(f"match for '{inp['name']}' needs review: {m.get('review_reason')}")
            if inp.get("match_as") and m:
                # match_as steers to a representative dataset while keeping the declared name.
                # Word the note by kind so non-pesticide inputs (raw materials, packaging,
                # utilities on the processing side) are not mislabelled as pesticides.
                _kind = inp.get("kind") or "input"
                if _kind == "raw_material" and inp.get("refined"):
                    _phrase = "a representative refined-ingredient dataset"
                else:
                    _phrase = {"pesticide": "a representative agrochemical dataset",
                               "raw_material": "a representative production dataset",
                               "packaging": "a representative packaging dataset",
                               "waste": "a representative waste-treatment dataset",
                               "transport": "a representative freight dataset",
                               "fuel": "a representative fuel-combustion dataset"}.get(
                                   _kind, "a representative dataset")
                res.notes.append(f"'{inp['name']}' modelled with {_phrase}")
            if not m:
                res.input_matches.append({**inp, "matched": None})
                res.notes.append(f"input '{inp['name']}' had no match; excluded")
                continue
            proc = self.q.get_process(m["uid"]) or {}
            ref_unit = proc.get("ref_unit")
            # The amount MUST be in the matched dataset's reference unit: convert it
            # (engine/units.py, cited LHV/density) or exclude the input, never pass through.
            try:
                solve_amount, unit_note = units.to_ref_unit(inp, ref_unit)
            except units.UnitMismatchError as e:
                res.notes.append(f"validation warning: {e}")
                res.input_matches.append({"input": inp["name"], "amount": inp["amount"],
                                          "amount_unit": inp.get("unit"), "matched": m["name"],
                                          "ref_unit": ref_unit, "kind": inp.get("kind"),
                                          "excluded": "unit mismatch", "score": m["score"]})
                continue
            if unit_note:
                res.notes.append(unit_note)
            try:
                sc = self.q.cradle_to_gate(m["uid"], amount=solve_amount)
                # Correct grid electricity to the official national grid EF (climate-only,
                # inventory-level) before the flows are consumed, so the per-source
                # contribution, the merged total, and the single score are all consistent.
                cal = grid_calibration.apply(self.q, inp, sc.elementary_flows, self.region, self.method)
                if cal:
                    res.notes.append(
                        f"grid electricity climate calibrated to the official "
                        f"{cal['ef']} kg CO2e/kWh national factor "
                        f"({cal['climate_before']} -> {cal['climate_after']} kg CO2e)")
                for uid, ef in sc.elementary_flows.items():
                    _add(supply, uid, ef["amount"], ef.get("name"), ef.get("unit"))
                # per-source contribution: characterize THIS input's flows on their own so
                # the report can attribute each impact category to the input that drove it.
                res.contribution_by_source[inp["name"]] = self.q.characterize_flows(
                    sc.elementary_flows, self.method)
                # keep the raw (method-independent) flows so a method switch can
                # re-characterize this source rather than losing its contribution.
                src_flows = res.contribution_flows_by_source.setdefault(inp["name"], {})
                for uid, ef in sc.elementary_flows.items():
                    _add(src_flows, uid, ef["amount"], ef.get("name"), ef.get("unit"))
            except Exception as e:
                res.notes.append(f"solve failed for '{inp['name']}' -> {m['name']}: {e}")
            match_row = {
                "input": inp["name"], "amount": inp["amount"], "amount_unit": inp.get("unit"),
                "matched": m["name"], "ref_unit": ref_unit, "kind": inp.get("kind"),
                "source": self.q.source_label(m["uid"]),
                "location": m.get("location"), "score": m["score"],
                "solved_amount": solve_amount,
            }
            if inp.get("estimated"):
                match_row["estimated"] = True
                if inp.get("estimate_meta"):
                    match_row["estimate_meta"] = inp["estimate_meta"]
            # matching-quality record: identity gate outcome, review flag, adjudication
            match_row.update({
                "uid": m["uid"],
                "reference_product": m.get("reference_product"),
                "needs_review": bool(m.get("needs_review")),
                "review_reason": m.get("review_reason"),
                "identity": m.get("identity"),
                "adjudication": m.get("adjudication") or {"adjudicated": False, "rationale": None},
            })
            if used_fallback:
                match_row["fallback_used"] = used_fallback
            res.input_matches.append(match_row)

        # regionalise foreground water (AWARE) and land (EF SQI) before characterising
        regional_lcia.apply(self.q, self.region, on_farm_lci, purchased_inputs, onfarm, supply, res, self.method)
        # 3) characterize: parts (for the split) + merged total, all via the validated path
        _emit(on_progress, "characterize", "Characterizing impacts")
        res.contribution["on_farm"] = self.q.characterize_flows(onfarm, self.method)
        res.contribution["supply_chain"] = self.q.characterize_flows(supply, self.method)
        # field emissions as a named contribution source alongside the purchased inputs
        res.contribution_by_source["Field emissions (on-farm)"] = res.contribution["on_farm"]
        # raw on-farm flows too, so a method switch re-characterizes them (see above).
        res.contribution_flows_by_source["Field emissions (on-farm)"] = {
            uid: dict(r) for uid, r in onfarm.items()
        }
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
