#!/usr/bin/env python3
"""
glad_fetch.py — download GLAD elementary-flow mapping files that are stored as
Git-LFS objects (the repo on disk is a ZIP extract, so the .xlsx are 130-byte LFS
pointers). Resolves each pointer's oid/size and fetches the real object via the
GitHub LFS batch API. Public, Apache-2.0 open data (UNEP/JRC).

Usage:
    python3 glad_fetch.py            # fetch the mapped files the FEDEFL layer needs
    python3 glad_fetch.py --list    # show what's a stub vs real, no download
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = "UNEP-Economy-Division/GLAD-ElementaryFlowResources"
BATCH_URL = f"https://github.com/{REPO}.git/info/lfs/objects/batch"

GLAD = (Path(__file__).resolve().parent.parent
        / "data" / "References_C" / "GLAD-ElementaryFlowResources-master")
MAPPED = GLAD / "Mapping" / "Output" / "Mapped_files"

# The mapped files needed to normalise our flows to FEDEFL:
#  - ecoinvent flows (our ecoinvent 3.11 + Agribalyse ecoinvent-derived background)
#  - ILCD/EF flows (the LCIA method characterization-factor flows)
NEEDED = [
    MAPPED / "ecoinventEFv3.7-FEDEFLv1.0.3.xlsx",
    MAPPED / "ILCD-EFv3.0-FEDEFLv1.0.3.xlsx",
]


def is_pointer(path: Path) -> bool:
    if not path.exists() or path.stat().st_size > 2000:
        return False
    try:
        return path.read_text(errors="ignore").startswith("version https://git-lfs")
    except Exception:
        return False


def parse_pointer(path: Path) -> tuple[str, int]:
    oid = size = None
    for line in path.read_text().splitlines():
        if line.startswith("oid sha256:"):
            oid = line.split(":", 1)[1].strip()
        elif line.startswith("size "):
            size = int(line.split()[1])
    if not oid or not size:
        raise ValueError(f"not an LFS pointer: {path}")
    return oid, size


def curl(args: list[str]) -> bytes:
    return subprocess.run(["curl", "-sL", *args], capture_output=True, check=True).stdout


def fetch_lfs(oid: str, size: int, dest: Path) -> None:
    payload = json.dumps({
        "operation": "download", "transfer": ["basic"],
        "objects": [{"oid": oid, "size": size}],
    })
    resp = curl([
        "-X", "POST",
        "-H", "Accept: application/vnd.git-lfs+json",
        "-H", "Content-Type: application/vnd.git-lfs+json",
        "-d", payload, BATCH_URL,
    ])
    obj = json.loads(resp)["objects"][0]
    if "actions" not in obj:
        raise RuntimeError(f"LFS API returned no download action: {obj.get('error', obj)}")
    href = obj["actions"]["download"]["href"]
    data = curl([href])
    if len(data) != size:
        raise RuntimeError(f"size mismatch: got {len(data)}, expected {size}")
    dest.write_bytes(data)


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="show status, don't download")
    ap.add_argument("files", nargs="*", help="specific mapped-file paths (default: FEDEFL set)")
    args = ap.parse_args(argv)

    targets = [Path(f) for f in args.files] if args.files else NEEDED
    for path in targets:
        if not path.exists():
            print(f"  MISSING   {path.name}")
            continue
        if args.list:
            print(f"  {'STUB' if is_pointer(path) else 'REAL'}  {path.stat().st_size:>9}b  {path.name}")
            continue
        if not is_pointer(path):
            print(f"  ok (already real)  {path.name}")
            continue
        try:
            oid, size = parse_pointer(path)
            print(f"  fetching {path.name} ({size} bytes) ...", flush=True)
            fetch_lfs(oid, size, path)
            print(f"  ✓ {path.name} -> {path.stat().st_size} bytes")
        except Exception as e:
            print(f"  ✗ {path.name}: {e}", file=sys.stderr)
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
