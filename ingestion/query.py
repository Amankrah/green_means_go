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

Sign conventions (document + validate against openLCA before trusting absolutes):
  - technosphere: production (ref output) positive, consumption (input) negative
  - biosphere g_k: emissions (outputs) positive, resource uptake (inputs) negative
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
        r = self.conn.execute(
            "SELECT uid, name FROM impact_methods WHERE name LIKE ? LIMIT 1",
            (f"%{name_substr}%",)).fetchone()
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
        """BFS over default-provider links; returns (process_uids, unlinked_input_count, truncated)."""
        seen = {target_uid}
        order = [target_uid]
        queue = [target_uid]
        unlinked = 0
        truncated = False
        while queue:
            cur = queue.pop()
            for r in self.conn.execute(
                "SELECT provider_process_uid FROM exchanges "
                "WHERE process_uid=? AND is_input=1 AND is_elementary=0",
                (cur,),
            ):
                prov = r["provider_process_uid"]
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

    def cradle_to_gate(self, target_uid: str, method_name: Optional[str] = None,
                       max_nodes: int = 50000) -> InventoryResult:
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

        # technosphere T (n x n) and biosphere rows
        T = np.zeros((n, n), dtype=float)
        bio: dict[str, dict] = {}     # flow_uid -> {"name","unit","row": np.array(n)}
        for uid in procs:
            j = idx[uid]
            ref_amt = self.get_process(uid).get("ref_amount")
            T[j, j] += float(ref_amt) if ref_amt not in (None, 0) else 1.0
            for ex in self.get_exchanges(uid):
                amt = ex["amount"] or 0.0
                if ex["is_elementary"]:
                    key = ex["flow_uid"] or f"name::{ex['flow_name']}"
                    rec = bio.setdefault(key, {"name": ex["flow_name"], "unit": ex["unit"],
                                               "row": np.zeros(n)})
                    rec["row"][j] += amt if not ex["is_input"] else -amt
                else:
                    if ex["is_reference"]:
                        continue  # ref output already on diagonal
                    prov = ex["provider_process_uid"]
                    if prov and prov in idx:
                        # consumption: negative output of the provider's product
                        T[idx[prov], j] -= amt

        # demand: 1 functional unit of the target's reference product
        f = np.zeros(n)
        tgt_ref = proc.get("ref_amount")
        f[idx[target_uid]] = float(tgt_ref) if tgt_ref not in (None, 0) else 1.0

        # solve T s = f  (scipy if available for robustness, else numpy)
        try:
            from scipy.linalg import solve as _solve
            s = _solve(T, f)
        except Exception:
            s = np.linalg.solve(T, f)

        elementary = {}
        for key, rec in bio.items():
            g = float(rec["row"] @ s)
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
                for cat in self.categories(m["uid"]):
                    total = 0.0
                    for cf in self.conn.execute(
                        "SELECT flow_uid, factor FROM characterization_factors WHERE category_uid=?",
                        (cat["uid"],),
                    ):
                        ef = elementary.get(cf["flow_uid"])
                        if ef:
                            total += ef["amount"] * cf["factor"]
                    if total != 0.0:
                        result.impacts[cat["name"]] = {"value": total, "unit": cat["ref_unit"]}
        return result


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

    args = ap.parse_args(argv)
    with CanonicalQuery(args.db) as q:
        if args.cmd == "find":
            print(json.dumps(q.find_processes(args.name, args.limit), indent=2))
        elif args.cmd == "exchanges":
            print(json.dumps(q.get_exchanges(args.uid), indent=2))
        elif args.cmd == "methods":
            print(json.dumps(q.list_methods(), indent=2))
        elif args.cmd == "inventory":
            res = q.cradle_to_gate(args.uid, args.method)
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
