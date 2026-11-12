#!/usr/bin/env python3
"""A conventional query must not land on an organic / Swiss-IP variant of the same product,
and an organic query must prefer the organic variant (orchestrator._system_mismatch)."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent))

from orchestrator import _system_mismatch  # noqa: E402


def _c(ref):
    return {"reference_product": ref}


def test_conventional_query_penalises_organic_variant():
    assert _system_mismatch("maize seed, for sowing", _c("maize seed, organic, for sowing")) == 1
    assert _system_mismatch("maize seed, for sowing", _c("maize seed, for sowing")) == 0


def test_organic_query_penalises_conventional_variant():
    assert _system_mismatch("organic maize seed", _c("maize seed, for sowing")) == 1
    assert _system_mismatch("organic maize seed", _c("maize seed, organic, for sowing")) == 0


def test_words_inside_other_words_or_products_do_not_count():
    assert _system_mismatch("Muriate of Potash", _c("inorganic potassium fertiliser, as K2O")) == 0
    assert _system_mismatch("Bio-fertilizer", _c("Compost, of manure (for organic fertiliser) (amendment)")) == 0
    assert _system_mismatch("barley seed", _c("barley seed, Swiss integrated production, for sowing")) == 1
