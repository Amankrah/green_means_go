#!/usr/bin/env python3
import json
import os
import subprocess
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
exe = root / "african_lca_backend" / "target" / "release" / ("server.exe" if os.name == "nt" else "server")
api = {
    "company_name": "Test",
    "country": "Ghana",
    "region": "GH",
    "foods": [
        {
            "name": "Maize",
            "quantity_kg": 3500,
            "area_allocated": 2.5,
            "category": "Cereals",
            "production_system": "Rainfed",
        }
    ],
    "management_practices": {},
    "equipment_energy": {
        "fuel_consumption": [],
        "energy_sources": [],
        "equipment": [],
    },
}
fd, tmp = tempfile.mkstemp(suffix=".json")
os.close(fd)
Path(tmp).write_text(json.dumps(api), encoding="utf-8")
try:
    p = subprocess.run(
        [str(exe), tmp],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(root / "african_lca_backend"),
    )
finally:
    os.remove(tmp)
start = p.stdout.find("{")
print("binary", exe, "exists", exe.exists(), "mtime", exe.stat().st_mtime if exe.exists() else None)
print("returncode", p.returncode)
if start < 0:
    print("no json", p.stderr[-500:])
    raise SystemExit(1)
r = json.loads(p.stdout[start:])
inv = (r.get("results") or {}).get("lci_inventory")
print("lci_inventory", "MISSING" if inv is None else f"len={len(inv)}")
if inv:
    for i in inv:
        if "Land" in (i.get("substance") or "") or "Nitrate" in (i.get("substance") or ""):
            print(" ", i.get("substance"), i.get("quantity"), i.get("unit"))
