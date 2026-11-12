#!/usr/bin/env python3
"""Run every engine/case_studies/*.json end to end through engine.service and write
per-case midpoint results to a JSON file, for before/after comparison.

Usage: python scripts/run_case_studies.py OUT.json [case_name ...]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.service import run_farm_assessment  # noqa: E402


def main():
    out = Path(sys.argv[1])
    only = set(sys.argv[2:])
    results = {}
    for p in sorted((ROOT / "engine" / "case_studies").glob("*.json")):
        if only and p.stem not in only:
            continue
        case = json.loads(p.read_text(encoding="utf-8"))
        try:
            r = run_farm_assessment(case, run_uncertainty=False)
        except Exception as e:  # report, keep going
            results[p.stem] = {"error": f"{type(e).__name__}: {e}"}
            continue
        results[p.stem] = {
            "region": case.get("region") or case.get("country"),
            "midpoints": {k: {"value": v.get("value"), "unit": v.get("unit")}
                          for k, v in (r.get("midpoint_impacts") or {}).items()
                          if isinstance(v, dict)},
            "single_score": (r.get("single_score") or {}).get("value")
            if isinstance(r.get("single_score"), dict) else r.get("single_score"),
        }
        print(p.stem, "ok", flush=True)
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
