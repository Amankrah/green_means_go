"""Pedigree-matrix GSD derivation tests."""
from __future__ import annotations

from engine.pedigree import (
    BASIC_UNCERTAINTY,
    field_scores,
    gsd_from_pedigree,
    match_scores,
)
from engine.uncertainty import _match_gsd, _source_gsds


def test_perfect_pedigree_and_basic_is_unity():
    scores = {k: 1 for k in ("reliability", "completeness", "temporal", "geographical", "technological")}
    assert gsd_from_pedigree(scores, 1.0) == 1.0


def test_worse_scores_increase_gsd():
    best = {k: 1 for k in ("reliability", "completeness", "temporal", "geographical", "technological")}
    worst = {k: 5 for k in best}
    assert gsd_from_pedigree(worst, 1.2) > gsd_from_pedigree(best, 1.2) > 1.0


def test_estimated_input_wider_than_verified():
    region = "Ghana"
    verified = {"input": "urea", "matched": "Urea {RoW}", "score": 0.8, "estimated": False}
    estimated = {"input": "urea", "matched": "Urea {RoW}", "score": 0.8, "estimated": True}
    assert _match_gsd(estimated, region) > _match_gsd(verified, region)


def test_region_specific_match_tighter_than_row_proxy():
    good_geo = {"input": "grid", "matched": "electricity GH", "score": 0.8, "location": "Ghana"}
    row_proxy = {"input": "grid", "matched": "electricity RoW", "score": 0.8, "location": "RoW"}
    assert _match_gsd(good_geo, "Ghana") < _match_gsd(row_proxy, "Ghana")


def test_low_similarity_match_wider():
    strong = {"input": "x", "matched": "x", "score": 0.85, "estimated": False}
    weak = {"input": "x", "matched": "x", "score": 0.55, "estimated": False}
    assert _match_gsd(weak, "Ghana") > _match_gsd(strong, "Ghana")


def test_field_emissions_widest_source():
    field_gsd = gsd_from_pedigree(field_scores(), BASIC_UNCERTAINTY["field_ef"])
    typical_background = _match_gsd({"score": 0.8, "estimated": False}, "Ghana")
    assert field_gsd > typical_background


class _Result:
    def __init__(self, cbs, matches):
        self.contribution_by_source = cbs
        self.input_matches = matches
        self.region = "Ghana"


def test_source_gsds_cover_field_and_inputs():
    res = _Result(
        cbs={
            "Field emissions (on-farm)": {"Climate change": {"value": 1.0, "unit": "kg CO2-eq"}},
            "urea": {"Climate change": {"value": 0.5, "unit": "kg CO2-eq"}},
        },
        matches=[{"input": "urea", "matched": "Urea {RoW}", "score": 0.8, "estimated": False}],
    )
    gsds = _source_gsds(res, "Ghana")
    assert set(gsds) == {"Field emissions (on-farm)", "urea"}
    # Field emissions carry the widest screening uncertainty of the two.
    assert gsds["Field emissions (on-farm)"] > gsds["urea"] > 1.0
