#!/usr/bin/env python3
"""
fetch_data.py — scripted, version-pinned fetch of LCA background databases from
the McGill OneDrive/SharePoint share, using rclone.

Why rclone: it streams/resumes multi-GB files reliably (browser downloads of the
3+ GB ecoinvent system-process packages routinely stall), works headless on Linux,
and lets the project treat SharePoint as the *source of truth* while caching a
pinned copy locally for reproducible research.

ONE-TIME SETUP (authorise your McGill account):
    rclone config
        n) New remote
        name> mcgill
        Storage> onedrive            (choose OneDrive / SharePoint)
        ... follow the browser auth, pick the McGill account / site ...
    # verify:
    rclone lsd "mcgill:2 - Teaching/BREE 505 - 2026/6 - Tutorials/Database"

USAGE:
    python3 fetch_data.py --list                 # show manifest items
    python3 fetch_data.py --list-remote          # list what's actually on the share
    python3 fetch_data.py --only P0              # fetch just P0 (essential) items
    python3 fetch_data.py --only agribalyse-3.2  # fetch one item by name
    python3 fetch_data.py --dry-run --only P0   # show the rclone commands only
    python3 fetch_data.py --mount               # print an rclone mount command (no download)

Notes:
- File names on the share are truncated in the web UI (e.g. "...2025-01-..."). Run
  --list-remote and update manifest.json 'remote' fields with the exact names.
- This does NOT make ecoinvent/Agribalyse queryable by itself: the bytes must be
  parsed/imported once (see ingest.py). Fetch = pinned local cache, nothing more.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
MANIFEST = HERE / "manifest.json"
RAW_DIR = REPO / "data" / "raw"
LOG = RAW_DIR / "_fetch_log.json"


def load_manifest() -> dict:
    with open(MANIFEST, "r", encoding="utf-8") as fh:
        return json.load(fh)


def rclone_available() -> bool:
    return shutil.which("rclone") is not None


def print_install_help() -> None:
    print(
        "\nrclone is not installed. Install it, then run `rclone config` once:\n"
        "  Linux:  sudo -v ; curl https://rclone.org/install.sh | sudo bash\n"
        "  (or)    sudo apt install rclone\n"
        "Then configure a remote named 'mcgill' (Storage type: onedrive).\n"
        "Docs: https://rclone.org/onedrive/\n",
        file=sys.stderr,
    )


def select_items(items: list[dict], only: str | None) -> list[dict]:
    if not only:
        return items
    only = only.strip()
    # priority filter (P0/P1/P2/P3) or exact name match
    if only.upper() in {"P0", "P1", "P2", "P3"}:
        return [it for it in items if it.get("priority", "").upper() == only.upper()]
    return [it for it in items if it.get("name") == only]


def remote_path(remote: str, base: str, item_remote: str) -> str:
    return f"{remote}:{base}/{item_remote}"


def run_rclone(args: list[str], dry_run: bool) -> int:
    printable = "rclone " + " ".join(
        (f'"{a}"' if " " in a else a) for a in args
    )
    print(f"  $ {printable}")
    if dry_run:
        return 0
    return subprocess.call(["rclone", *args])


def cmd_list(manifest: dict) -> None:
    print(f"Remote base: {manifest['remote_base']}\n")
    print(f"{'name':<32} {'pri':<4} {'size':>8}  note")
    print("-" * 90)
    for it in manifest["items"]:
        size = f"{it.get('size_mb', '?')}MB"
        print(f"{it['name']:<32} {it.get('priority',''):<4} {size:>8}  {it.get('note','')[:48]}")


def cmd_list_remote(manifest: dict, remote: str, dry_run: bool) -> None:
    base = manifest["remote_base"]
    print(f"Listing {remote}:{base}\n")
    run_rclone(["lsf", "--max-depth", "1", f"{remote}:{base}"], dry_run)


def cmd_mount(manifest: dict, remote: str) -> None:
    mountpoint = "/mnt/mcgill"
    print(
        "To access files on-demand WITHOUT a full download, mount the share\n"
        "(rclone fetches + caches each file on first access):\n\n"
        f"  mkdir -p {mountpoint}\n"
        f"  rclone mount {remote}: {mountpoint} --vfs-cache-mode full --daemon\n\n"
        f"Your code then reads e.g.:\n"
        f"  {mountpoint}/{manifest['remote_base']}/agribalyse 3.2.zolca\n\n"
        "Unmount with:  fusermount -u " + mountpoint + "\n"
    )


def cmd_fetch(manifest: dict, remote: str, only: str | None, dry_run: bool) -> int:
    base = manifest["remote_base"]
    items = select_items(manifest["items"], only)
    if not items:
        print(f"No manifest items matched --only={only!r}.", file=sys.stderr)
        return 2

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    rc_total = 0
    for it in items:
        src = remote_path(remote, base, it["remote"])
        dest = RAW_DIR / it["target"]
        dest.mkdir(parents=True, exist_ok=True)
        print(f"\n>> {it['name']}  ({it.get('size_mb','?')} MB, {it.get('priority','')})")
        rc = run_rclone(
            ["copy", src, str(dest), "--progress", "--multi-thread-streams", "4"],
            dry_run,
        )
        rc_total |= rc
        results.append(
            {
                "name": it["name"],
                "src": src,
                "dest": str(dest),
                "returncode": rc,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            }
        )

    if not dry_run:
        log = []
        if LOG.exists():
            try:
                log = json.loads(LOG.read_text())
            except json.JSONDecodeError:
                log = []
        log.extend(results)
        LOG.write_text(json.dumps(log, indent=2))
        print(f"\nFetch log appended to {LOG}")
    if rc_total != 0:
        print("\nOne or more rclone commands failed (see output above).", file=sys.stderr)
    return rc_total


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch LCA databases from McGill SharePoint via rclone.")
    p.add_argument("--remote", default="mcgill", help="rclone remote name (default: mcgill)")
    p.add_argument("--only", help="Filter by priority (P0/P1/P2/P3) or exact item name")
    p.add_argument("--list", action="store_true", help="List manifest items and exit")
    p.add_argument("--list-remote", action="store_true", help="List files actually on the share")
    p.add_argument("--mount", action="store_true", help="Print an rclone mount command (no download)")
    p.add_argument("--dry-run", action="store_true", help="Show rclone commands without running them")
    args = p.parse_args(argv)

    manifest = load_manifest()

    if args.list:
        cmd_list(manifest)
        return 0
    if args.mount:
        cmd_mount(manifest, args.remote)
        return 0

    if not rclone_available() and not args.dry_run:
        print_install_help()
        return 1

    if args.list_remote:
        cmd_list_remote(manifest, args.remote, args.dry_run)
        return 0

    return cmd_fetch(manifest, args.remote, args.only, args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
