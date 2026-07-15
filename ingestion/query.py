#!/usr/bin/env python3
"""
query.py — the read API over the canonical store.

Two layers:
  1. Lookups (pure SQL, no deps): find processes/flows, list methods, get exchanges.
     Used by the AI matching subsystem (free-text -> candidate processes) and the UI.
  2. Cradle-to-gate solver (needs numpy; scipy used if available): assembles the
     technosphere (T) and biosphere (B) matrices for the supply chain reachable
     from a target process and solves the inventory the *correct* way —
         T s = f ,  g = B s
     A linear solve (not a recursive walk) is required because ecoinvent's
     technosphere has cycles (electricity needs steel needs electricity); a DFS
     would loop forever, the solve does not.

Sign conventions (validated against openLCA — see RUNBOOK "Validation gate"):
  - technosphere: reference flow on the diagonal, signed by direction (waste-treatment
    activities carry their reference as an INPUT); inputs consume the provider's
    product (negative), outputs supply it (positive).
  - biosphere g_k: amounts are stored AS-IS, never negated for inputs. openLCA encodes
    direction in the flow itself ("Carbon dioxide, in air" is a distinct resource flow
    from "Carbon dioxide, fossil") and CFs are signed to match (biogenic CO2 uptake
    has a negative climate CF). Negating inputs here would double-count the sign and
    flip resource/land-use impacts negative.
  - characterization: impact = Σ g_k · CF_k  per category

CLI:
    python3 query.py find "maize"
    python3 query.py exchanges <process_uid>
    python3 query.py methods
    python3 query.py inventory <process_uid> [--method "ReCiPe..."] [--top 20]
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from canonical_store import DEFAULT_DB
from flowkey import medium_of


@dataclass
class InventoryResult:
    target_uid: str
    target_name: str
    n_processes: int
    n_unlinked_inputs: int
    elementary_flows: dict          # flow_uid -> {"name","unit","amount"}
    impacts: dict = field(default_factory=dict)  # category_name -> {"value","unit"}
    notes: list = field(default_factory=list)


class CanonicalQuery:
    def __init__(self, db_path: Path | str = DEFAULT_DB):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self._producers: Optional[dict] = None   # flow_uid -> [(process_uid, source_id)]
        self._source_of: Optional[dict] = None   # process_uid -> source_id
        self._units: Optional[dict] = None       # unit name -> conversion factor
        self._flowkeys: Optional[dict] = None     # flow_uid -> canonical flow_key
        self._fedids: Optional[dict] = None       # flow_uid -> FEDEFL fed_id (authoritative)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self): return self
    def __exit__(self, *exc): self.close()

    # ---- lookups -----------------------------------------------------------
    def find_processes(self, name_substr: str, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT uid, name, location, category FROM processes "
            "WHERE name LIKE ? ORDER BY length(name) LIMIT ?",
            (f"%{name_substr}%", limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_process(self, uid: str) -> Optional[dict]:
        r = self.conn.execute("SELECT * FROM processes WHERE uid=?", (uid,)).fetchone()
        return dict(r) if r else None

    def get_exchanges(self, process_uid: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT flow_uid, flow_name, is_input, is_elementary, is_reference, amount, unit, "
            "provider_process_uid FROM exchanges WHERE process_uid=?",
            (process_uid,),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_flows(self, name_substr: str, elementary_only: bool = False, limit: int = 20) -> list[dict]:
        q = "SELECT uid, name, category, flow_type, ref_unit FROM flows WHERE name LIKE ?"
        if elementary_only:
            q += " AND flow_type='ELEMENTARY_FLOW'"
        q += " ORDER BY length(name) LIMIT ?"
        return [dict(r) for r in self.conn.execute(q, (f"%{name_substr}%", limit)).fetchall()]

    def list_methods(self) -> list[dict]:
        return [dict(r) for r in self.conn.execute(
            "SELECT uid, name FROM impact_methods ORDER BY name").fetchall()]

    def find_method(self, name_substr: str) -> Optional[dict]:
        # Exact match wins. Otherwise prefer the SHORTEST name containing the query:
        # method names nest ("ReCiPe 2016 v1.03, midpoint (H)" is a substring of
        # "... (H) no LT"), and a bare LIKE would silently pick the no-long-term
        # variant — which quietly drops long-term emissions and understates
        # toxicity / ionising radiation / freshwater eutrophication.
        r = self.conn.execute(
            "SELECT uid, name FROM impact_methods WHERE name = ?", (name_substr,)
        ).fetchone()
        if r:
            return dict(r)
        r = self.conn.execute(
            "SELECT uid, name FROM impact_methods WHERE name LIKE ? "
            "ORDER BY length(name) LIMIT 1",
            (f"%{name_substr}%",),
        ).fetchone()
        return dict(r) if r else None

    def categories(self, method_uid: Optional[str] = None) -> list[dict]:
        if method_uid:
            rows = self.conn.execute(
                "SELECT uid, name, ref_unit FROM impact_categories WHERE method_uid=? ORDER BY name",
                (method_uid,)).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT uid, name, ref_unit FROM impact_categories ORDER BY name").fetchall()
        return [dict(r) for r in rows]

    # ---- cradle-to-gate inventory solve ------------------------------------
    def _reachable(self, target_uid: str, max_nodes: int = 50000) -> tuple[list[str], int, bool]:
        """BFS over default-provider links; returns (process_uids, unlinked_input_count, truncated).

        Follows EVERY technosphere exchange that carries a default provider — inputs
        AND outputs. ecoinvent links waste treatment through *output* exchanges
        (a process outputs "waste -> treatment" pointing at the landfill activity).
        Traversing inputs only silently drops every treatment activity, which wipes
        out long-term landfill/tailings leachate and understates toxicity, ionising
        radiation and freshwater eutrophication by ~95%.
        """
        seen = {target_uid}
        order = [target_uid]
        queue = [target_uid]
        unlinked = 0
        truncated = False
        while queue:
            cur = queue.pop()
            for r in self.conn.execute(
                "SELECT flow_uid, provider_process_uid FROM exchanges "
                "WHERE process_uid=? AND is_elementary=0 AND is_reference=0",
                (cur,),
            ):
                prov = r["provider_process_uid"]
                if not prov:  # Agribalyse: no default providers — link by product flow
                    prov, _ = self._resolve_provider(r["flow_uid"], cur)
                if not prov:
                    unlinked += 1
                    continue
                if prov not in seen:
                    if len(seen) >= max_nodes:
                        truncated = True
                        continue
                    seen.add(prov)
                    order.append(prov)
                    queue.append(prov)
        return order, unlinked, truncated

    def _unit_factor(self, unit: Optional[str]) -> float:
        """Convert an amount in `unit` to its unit-group reference unit (kg, MJ, m3 ...).

        Applied to TECHNOSPHERE amounts only (exchange + the reference exchange on the
        diagonal), so an input of 6411 kg against a provider whose reference is
        0.9966 t is scaled correctly instead of 1000x over. Elementary amounts are
        left untouched — their CFs are keyed to the flow's own unit, and ecoinvent
        validates exactly without conversion.
        """
        if self._units is None:
            try:
                self._units = {r["name"]: r["conversion_factor"]
                               for r in self.conn.execute("SELECT name, conversion_factor FROM units")}
            except sqlite3.OperationalError:
                self._units = {}
        return self._units.get(unit or "", 1.0)

    def _link_index(self) -> tuple[dict, dict]:
        """Lazily index which process produces which product flow.

        Needed because the two databases link supply chains DIFFERENTLY:
          - ecoinvent sets an explicit `default_provider` on every technosphere
            exchange (100% coverage).
          - Agribalyse sets NONE (0%); openLCA resolves them at product-system build
            time by matching the input's product flow to the process whose REFERENCE
            flow it is. Without this fallback an Agribalyse product has no supply
            chain at all — only its own direct emissions.
        """
        if self._producers is None:
            prod: dict[str, list[tuple[str, int]]] = {}
            src: dict[str, int] = {}
            for r in self.conn.execute("SELECT uid, source_id, ref_flow FROM processes"):
                src[r["uid"]] = r["source_id"]
                if r["ref_flow"]:
                    prod.setdefault(r["ref_flow"], []).append((r["uid"], r["source_id"]))
            self._producers, self._source_of = prod, src
        return self._producers, self._source_of

    def _resolve_provider(self, flow_uid: Optional[str], consumer_uid: str) -> tuple[Optional[str], bool]:
        """Return (provider_process_uid, was_ambiguous) for an exchange with no
        explicit default provider. Prefers a producer from the consumer's own database."""
        if not flow_uid:
            return None, False
        prod, src = self._link_index()
        cands = prod.get(flow_uid) or []
        if not cands:
            return None, False
        if len(cands) == 1:
            return cands[0][0], False
        same = [u for u, s in cands if s == src.get(consumer_uid)]
        if len(same) == 1:
            return same[0], False
        pool = sorted(same) if same else sorted(u for u, _ in cands)
        return pool[0], True

    def _exchanges_for(self, process_uids: list[str]) -> dict[str, list[dict]]:
        """Fetch all exchanges for a set of processes in chunked IN queries
        (one round-trip per ~900 processes instead of one per process)."""
        out: dict[str, list[dict]] = {u: [] for u in process_uids}
        CH = 900
        for i in range(0, len(process_uids), CH):
            chunk = process_uids[i:i + CH]
            q = (
                "SELECT process_uid, flow_uid, flow_name, is_input, is_elementary, "
                "is_reference, amount, unit, provider_process_uid FROM exchanges "
                f"WHERE process_uid IN ({','.join('?' * len(chunk))})"
            )
            for r in self.conn.execute(q, chunk):
                out[r["process_uid"]].append(dict(r))
        return out

    def cradle_to_gate(self, target_uid: str, method_name: Optional[str] = None,
                       max_nodes: int = 50000, amount: Optional[float] = None) -> InventoryResult:
        try:
            import numpy as np
        except ImportError:
            raise SystemExit(
                "The inventory solver needs numpy: pip install numpy scipy\n"
                "(lookups work without it; only cradle_to_gate requires it.)"
            )

        proc = self.get_process(target_uid)
        if not proc:
            raise ValueError(f"process not found: {target_uid}")

        procs, unlinked, truncated = self._reachable(target_uid, max_nodes)
        idx = {uid: i for i, uid in enumerate(procs)}
        n = len(procs)
        notes: list[str] = []
        if truncated:
            notes.append(f"supply chain truncated at max_nodes={max_nodes}; impacts are a lower bound.")
        if unlinked:
            notes.append(f"{unlinked} technosphere input(s) had no default provider and are unlinked.")

        # ---- assemble T (sparse) and B ------------------------------------
        # A dense n x n is untenable here (ecoinvent reaches ~13.5k processes ->
        # ~1.5 GB and an O(n^3) solve). Technosphere matrices are very sparse.
        from scipy.sparse import coo_matrix, csc_matrix
        from scipy.sparse.linalg import spsolve

        rows: list[int] = []
        cols: list[int] = []
        vals: list[float] = []
        bio: dict[str, dict] = {}     # flow_uid -> {"name","unit","idx":[], "amt":[]}
        diag_target = 1.0
        ambiguous = 0

        for ex_proc_uid, exs in self._exchanges_for(procs).items():
            j = idx[ex_proc_uid]
            diag = 0.0
            for ex in exs:
                amt = ex["amount"] or 0.0
                if ex["is_elementary"]:
                    key = ex["flow_uid"] or f"name::{ex['flow_name']}"
                    rec = bio.setdefault(key, {"name": ex["flow_name"], "unit": ex["unit"],
                                               "idx": [], "amt": []})
                    # NOTE: do NOT negate inputs. openLCA encodes direction in the
                    # FLOW ITSELF ("Carbon dioxide, in air" [resource] is a different
                    # flow from "Carbon dioxide, fossil" [emission]) and its CFs are
                    # signed accordingly (CO2-in-air has a negative climate CF for
                    # biogenic uptake). Negating here double-counts the sign and
                    # flips resource/land-use impacts negative.
                    rec["idx"].append(j)
                    rec["amt"].append(amt)
                elif ex["is_reference"]:
                    # Reference flow defines this process's own product row.
                    # Waste-treatment activities have the reference as an INPUT,
                    # so the diagonal must carry the direction.
                    tamt = amt * self._unit_factor(ex["unit"])
                    diag += -tamt if ex["is_input"] else tamt
                else:
                    prov = ex["provider_process_uid"]
                    if not prov:  # Agribalyse: resolve by product flow
                        prov, amb = self._resolve_provider(ex["flow_uid"], ex_proc_uid)
                        if amb:
                            ambiguous += 1
                    if prov and prov in idx:
                        # input  = consumption of provider's product (negative supply)
                        # output = supply back to that product row (rare: co-/waste flows)
                        tamt = amt * self._unit_factor(ex["unit"])
                        rows.append(idx[prov]); cols.append(j)
                        vals.append(-tamt if ex["is_input"] else tamt)
            if diag == 0.0:
                diag = 1.0  # process with no explicit reference exchange
            rows.append(j); cols.append(j); vals.append(diag)
            if ex_proc_uid == target_uid:
                diag_target = diag

        T = coo_matrix((vals, (rows, cols)), shape=(n, n)).tocsc()

        # Demand. Default = the process's NATIVE reference amount (one process run) —
        # note this is not always 1 (an Agribalyse crop can be ~10,672 kg = 1 ha yield).
        # Pass amount=1.0 to get results per kg.
        f = np.zeros(n)
        f[idx[target_uid]] = diag_target if amount is None else float(amount)
        if ambiguous:
            notes.append(f"{ambiguous} exchange(s) had multiple candidate producers; "
                         "picked deterministically (same-database preferred).")

        s = spsolve(T, f)
        if not np.all(np.isfinite(s)):
            raise RuntimeError("technosphere solve produced non-finite scaling factors "
                               "(singular matrix) — check provider links for this product")
        # residual check: a good solve should have ||T s - f|| ~ 0
        resid = float(np.linalg.norm(T @ s - f))
        scale = max(1.0, float(np.linalg.norm(f)))
        if resid / scale > 1e-6:
            notes.append(f"linear solve residual is high ({resid:.2e}); results may be unreliable.")

        elementary = {}
        for key, rec in bio.items():
            g = float(np.dot(np.array(rec["amt"]), s[np.array(rec["idx"])]))
            if abs(g) > 0:
                elementary[key] = {"name": rec["name"], "unit": rec["unit"], "amount": g}

        result = InventoryResult(
            target_uid=target_uid, target_name=proc["name"], n_processes=n,
            n_unlinked_inputs=unlinked, elementary_flows=elementary, notes=notes,
        )

        # optional characterization
        if method_name:
            m = self.find_method(method_name)
            if not m:
                notes.append(f"method '{method_name}' not found; skipped characterization.")
            else:
                self._characterize(elementary, m, result)
        return result

    def _flow_keys(self) -> tuple[dict, dict, dict]:
        if self._flowkeys is None:
            self._flowkeys, self._caskeys, self._fedids = {}, {}, {}
            has_fed = "fed_id" in {r[1] for r in self.conn.execute("PRAGMA table_info(flows)")}
            cols = "uid, flow_key, cas_key" + (", fed_id" if has_fed else "")
            for r in self.conn.execute(f"SELECT {cols} FROM flows"):
                self._flowkeys[r["uid"]] = r["flow_key"]
                if r["cas_key"]:
                    self._caskeys[r["uid"]] = r["cas_key"]
                if has_fed and r["fed_id"]:
                    self._fedids[r["uid"]] = r["fed_id"]
        return self._flowkeys, self._caskeys, self._fedids

    def _characterize(self, elementary: dict, method: dict, result: "InventoryResult") -> None:
        """Impact = Σ g·CF per category. Match a CF to an inventory flow by exact UID
        first; if the flow has no direct CF, fall back to the canonical flow_key
        (nomenclature bridge). The fallback is applied per key ONLY when every CF
        sharing that key agrees on a value — so it never guesses when compartment
        granularity actually matters, and databases whose CFs already line up by UID
        (ecoinvent) are unaffected."""
        fk, ck, fed = self._flow_keys()
        inv_key = {uid: fk.get(uid) for uid in elementary}
        inv_cas = {uid: ck.get(uid) for uid in elementary}
        inv_fed = {uid: fed.get(uid) for uid in elementary}

        # Flows the method ALREADY knows by UID (in any category). Their omission from
        # a given category is a deliberate CF=0 — never bridge them. This is what keeps
        # ecoinvent exact: all its inventory flows are known to its own method, so the
        # bridge only ever fires for foreign-nomenclature flows (Agribalyse background).
        known_uids = {r["flow_uid"] for r in self.conn.execute(
            "SELECT DISTINCT cf.flow_uid FROM characterization_factors cf "
            "JOIN impact_categories ic ON ic.uid = cf.category_uid WHERE ic.method_uid = ?",
            (method["uid"],),
        )}

        bridged_total = 0
        for cat in self.categories(method["uid"]):
            # Water use / scarcity CFs (AWARE) are NET consumption keyed to specific
            # water flows, not a per-substance factor. A coarse "water" key would apply
            # one deprivation factor to every water flow (river, cooling, turbine…) and
            # massively over-count. Characterize these by UID only — never bridge.
            cname = (cat["name"] or "").lower()
            is_water = ("water use" in cname or "water scarcity" in cname
                        or "water consumption" in cname or "water depletion" in cname)
            is_climate = ("climate" in cname or "global warming" in cname)
            bridge_name = not is_water                       # name bridge: not water
            bridge_cas = not is_water and not is_climate     # CAS bridge: substance-identity only

            # Two compartment tiers per bridge: FINE (medium/sub) for sub-compartment-
            # specific CFs (ecotoxicity, PM), then MEDIUM for coarse ones (eutrophication:
            # P-to-any-water = 1.0). Each tier keeps a value only when all CFs sharing that
            # key agree (unique-value guard) — so we never guess an ambiguous CF.
            by_uid: dict[str, float] = {}
            kf_v: dict[str, set] = {}; km_v: dict[str, set] = {}
            cf_v: dict[str, set] = {}; cm_v: dict[str, set] = {}
            ff_v: dict[str, set] = {}; fm_v: dict[str, set] = {}
            for cf in self.conn.execute(
                "SELECT flow_uid, factor FROM characterization_factors WHERE category_uid=?",
                (cat["uid"],),
            ):
                fu, fac = cf["flow_uid"], cf["factor"]
                by_uid[fu] = fac
                r = round(fac, 12)
                k = fk.get(fu)
                if k:
                    kf_v.setdefault(k, set()).add(r)
                    km_v.setdefault(medium_of(k), set()).add(r)
                ckf = ck.get(fu)
                if ckf:
                    cf_v.setdefault(ckf, set()).add(r)
                    cm_v.setdefault(medium_of(ckf), set()).add(r)
                fdf = fed.get(fu)
                if fdf and fdf != "__NOMAP__":
                    ff_v.setdefault(fdf, set()).add(r)
                    fm_v.setdefault(medium_of(fdf), set()).add(r)
            by_fed_fine = {k: next(iter(v)) for k, v in ff_v.items() if len(v) == 1}
            by_fed_med = {k: next(iter(v)) for k, v in fm_v.items() if len(v) == 1}
            by_key_fine = {k: next(iter(v)) for k, v in kf_v.items() if len(v) == 1}
            by_key_med = {k: next(iter(v)) for k, v in km_v.items() if len(v) == 1}
            by_cas_fine = {k: next(iter(v)) for k, v in cf_v.items() if len(v) == 1}
            by_cas_med = {k: next(iter(v)) for k, v in cm_v.items() if len(v) == 1}

            total = 0.0
            bridged = 0
            for uid, ef in elementary.items():
                fac = by_uid.get(uid)
                fdf = inv_fed.get(uid)
                if fac is None and fdf != "__NOMAP__" and uid not in known_uids:
                    # Tier 1 — authoritative FEDEFL id (GLAD/FEDEFL canonical flowable+
                    # compartment). Handles cross-naming the heuristic can't; NO_FLOW_MATCH
                    # (e.g. biogenic CO2) is blocked above via the __NOMAP__ sentinel.
                    if bridge_name and fdf:      # bridge_name==not-water; keep water out
                        fac = by_fed_fine.get(fdf)
                        if fac is None:
                            fac = by_fed_med.get(medium_of(fdf))
                    # Tiers 2-4 — heuristic fallback for flows FEDEFL didn't resolve.
                    if fac is None:
                        nf = inv_key.get(uid); cf_ = inv_cas.get(uid)
                        if bridge_name:
                            fac = by_key_fine.get(nf)
                        if fac is None and bridge_cas:
                            fac = by_cas_fine.get(cf_)
                        if fac is None and bridge_name:
                            fac = by_key_med.get(medium_of(nf))
                    if fac is not None:
                        bridged += 1
                if fac:
                    total += ef["amount"] * fac
            if total != 0.0:
                result.impacts[cat["name"]] = {"value": total, "unit": cat["ref_unit"]}
            bridged_total += bridged
        if bridged_total:
            result.notes.append(f"{bridged_total} flow→CF match(es) resolved via canonical "
                                 "flow key (nomenclature bridge).")


# ------------------------------- CLI ---------------------------------------
def _main(argv=None) -> int:
    import argparse, json
    ap = argparse.ArgumentParser(description="Query the LCA Engineer canonical store.")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    sub = ap.add_subparsers(dest="cmd", required=True)

    pf = sub.add_parser("find"); pf.add_argument("name"); pf.add_argument("--limit", type=int, default=20)
    pe = sub.add_parser("exchanges"); pe.add_argument("uid")
    sub.add_parser("methods")
    pi = sub.add_parser("inventory")
    pi.add_argument("uid"); pi.add_argument("--method"); pi.add_argument("--top", type=int, default=20)
    pi.add_argument("--amount", type=float, default=None,
                    help="demand in the reference unit (default: the process's own reference amount)")

    args = ap.parse_args(argv)
    with CanonicalQuery(args.db) as q:
        if args.cmd == "find":
            print(json.dumps(q.find_processes(args.name, args.limit), indent=2))
        elif args.cmd == "exchanges":
            print(json.dumps(q.get_exchanges(args.uid), indent=2))
        elif args.cmd == "methods":
            print(json.dumps(q.list_methods(), indent=2))
        elif args.cmd == "inventory":
            res = q.cradle_to_gate(args.uid, args.method, amount=args.amount)
            print(f"# {res.target_name}  ({res.n_processes} processes in supply chain)")
            for note in res.notes:
                print(f"  ! {note}")
            if res.impacts:
                print("\nImpacts:")
                for cat, v in sorted(res.impacts.items(), key=lambda kv: -abs(kv[1]['value']))[:args.top]:
                    print(f"  {cat:45s} {v['value']:.6g} {v['unit'] or ''}")
            print(f"\nTop elementary flows ({min(args.top, len(res.elementary_flows))} of {len(res.elementary_flows)}):")
            for k, v in sorted(res.elementary_flows.items(), key=lambda kv: -abs(kv[1]['amount']))[:args.top]:
                print(f"  {v['name'][:45]:45s} {v['amount']:.6g} {v['unit'] or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
