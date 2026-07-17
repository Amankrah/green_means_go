#!/usr/bin/env python3
"""
licences.py — the licence status of each measure source, as a runtime gate.

docs/lca_engineer/LICENCES.md is the human-readable record; this is its enforceable
twin. A measure inherits its source's status, and the matcher can drop measures whose
licence blocks a commercial deployment. Keep the two in sync: when you add a source to
LICENCES.md, add its status here.

Status vocabulary (mirrors LICENCES.md):
  clean       reuse including commercial
  cite        derive numbers + attribute; do not redistribute the source text
  nc          non-commercial only (CC BY-NC) -> blocks a commercial build
  permission  written permission needed first (e.g. IPCC) -> blocks until granted
  unconfirmed verify before commercial use -> treated as blocking until resolved
"""
from __future__ import annotations

LICENCE_STATUS: dict[str, str] = {
    "IPCC-2019": "permission",
    "Ecological-Processes-EastGonja": "cite",
    "Ghana-CSAIP": "unconfirmed",
    "CCAFS-CSA-Ghana": "nc",
    "SNV-Ahotor": "cite",
    "SNV-gari": "cite",
    "UNDP-CleanerPalmOil": "cite",
    "IFC-EHS-FoodBeverage": "unconfirmed",
    "UNIDO-RECP": "unconfirmed",
    "internal-data-quality": "clean",
    "Ghana-EnergyCommission-2025-EnergyStatistics": "cite",
}

# Statuses that must NOT appear in a commercial deployment until resolved.
BLOCKED_FOR_COMMERCIAL = {"nc", "permission", "unconfirmed"}

# Unknown sources default to unconfirmed: safe-by-default, so a new source can't slip
# into a commercial build unreviewed just because nobody added a status row.
_DEFAULT = "unconfirmed"


def licence_status(source: str) -> str:
    return LICENCE_STATUS.get(source, _DEFAULT)


def is_commercial_ok(source: str) -> bool:
    """True if this source's licence permits commercial use as it stands."""
    return licence_status(source) not in BLOCKED_FOR_COMMERCIAL
