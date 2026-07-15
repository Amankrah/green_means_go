"""
Farm assessment API on the NEW validated engine (Option A).

POST /farm/assess runs the region-aware cradle-to-gate LCA:
  Rust LCI kernel (IPCC-AFOLU field emissions) + supply-chain solver + canonical
  characterization, returning total impacts, the on-farm/upstream contribution split,
  and the input-match report.

This is the migration target that replaces the Rust hardcoded-LCIA path. The old
/assess route stays until the frontend is switched over.

Engines are cached per region (the matcher index is ~300 MB) and calls are serialised
per engine with a lock, since the SQLite connection is not thread-safe and farm
assessments are low-frequency.
"""
from __future__ import annotations

import sys
import threading
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

# make the repo-root packages (engine, ingestion) importable
_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

router = APIRouter(prefix="/farm", tags=["farm"])

_engines: dict[str, object] = {}
_locks: dict[str, threading.Lock] = {}
_build_lock = threading.Lock()


class PurchasedInput(BaseModel):
    name: str
    amount: float
    unit: str | None = None


class FarmAssessRequest(BaseModel):
    region: str = Field(..., description="GH | NG | CA (or name)")
    method: str | None = Field(None, description="LCIA method; defaults to the region's")
    assessment: dict = Field(..., description="Farm assessment in the Rust kernel format")
    purchased_inputs: list[PurchasedInput] = Field(default_factory=list)
    expand_matching: bool = False


def _get_engine(region: str, method: str | None):
    # Share the single per-region engine cache in engine/service.py so there is ONE
    # ~300 MB matcher per region across both /assess and /farm/assess.
    from engine.service import _engine
    return _engine(region, method)


@router.get("/regions")
async def regions():
    from engine.regions import REGIONS
    return [{"code": r.code, "name": r.name, "currency": r.currency,
             "default_method": r.default_method, "climate_zone": r.climate_zone}
            for r in REGIONS.values()]


@router.post("/assess")
async def assess(req: FarmAssessRequest):
    try:
        eng, lock = _get_engine(req.region, req.method)
    except KeyError as e:
        raise HTTPException(400, str(e))
    inputs = [i.model_dump() for i in req.purchased_inputs]
    try:
        with lock:                                   # serialise: sqlite conn not thread-safe
            res = eng.assess_farm(req.assessment, inputs, expand_matching=req.expand_matching)
    except FileNotFoundError as e:
        raise HTTPException(503, f"Rust LCI kernel not built: {e}")
    except Exception as e:
        raise HTTPException(500, f"assessment failed: {e}")
    return {
        "region": res.region,
        "method": res.method,
        "impacts": res.impacts,
        "contribution": res.contribution,
        "input_matches": res.input_matches,
        "notes": res.notes,
    }
