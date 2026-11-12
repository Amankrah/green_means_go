"""Unit tests for matching quality (WS4): product-identity gate, deterministic location rank,
live fallback chain, adjudication hook and the raw-material hint table. No store or API needed:
the matcher is faked."""
from __future__ import annotations

import pytest

from engine import orchestrator as orch
from engine import product_identity as pid
from engine.process_inputs import _raw_material_match
from engine.regions import get_region, location_rank


# ----------------------------------------------------------------- synonym table / gate
@pytest.mark.parametrize("a,b", [
    ("Groundnuts (shelled)", "peanut production"),
    ("Eggplant", "aubergine production, open field"),
    ("Brinjal", "aubergine"),
    ("Garden eggs", "aubergine"),
    ("Fresh fruit bunches (FFB)", "palm fruit bunch production"),
    ("Hot pepper", "chilli production"),
    ("Raw honey", "Honeycomb"),
    ("Seed-cotton", "seed cotton"),
    ("Benniseed", "sesame seed production"),
])
def test_synonyms_share_identity(a, b):
    assert pid.query_identity(a).concepts == pid.query_identity(b).concepts != []


def test_whole_word_and_longest_phrase():
    assert pid.detect("chilling of beef carcasses") == []          # chilli is not chilling
    assert pid.detect("Grapes") == ["grape"]                        # rape is not in grape
    assert pid.detect("Pineapple") == ["pineapple"]                 # apple is not pineapple
    assert pid.detect("cocoa butter") == ["cocoa_butter"]           # not cocoa
    assert pid.detect("urea ammonium nitrate mix") == ["uan"]       # not urea
    assert pid.detect("bell peppers") == ["bell_pepper"]            # not chilli
    assert pid.detect("fibre, cotton") == ["cotton_fibre"]          # not seed cotton


def test_candidate_identity_reads_reference_product():
    # ecoinvent multi-output activity: the reference product decides, not the activity name
    assert pid.candidate_concepts("palm oil mill operation", "palm kernel meal") == {"palm_kernel"}
    # service activities carry identity in the name
    got = pid.candidate_concepts("treatment of municipal solid waste, sanitary landfill",
                                 "municipal solid waste")
    assert {"msw", "landfill"} <= got


def test_proxy_and_generic_are_flagged():
    foliar = pid.query_identity("Foliar Fertilizer fertiliser")
    assert foliar.basis == "proxy" and foliar.needs_review
    assert pid.passes(foliar, frozenset({"npk"}))
    assert not pid.passes(foliar, frozenset({"cocoa"}))
    none = pid.query_identity("None fertiliser")
    assert none.basis == "generic" and none.needs_review
    assert pid.passes(none, frozenset({"urea"}))
    assert not pid.passes(none, frozenset({"cocoa"}))
    assert pid.query_identity("Urea fertiliser").needs_review is False


def test_token_fallback_for_unknown_products():
    ident = pid.query_identity("Baobab fruit pulp production")
    assert ident.basis == "token" and "baobab" in ident.tokens
    assert pid.passes(ident, frozenset(), "Baobab, dried {SN}")
    assert not pid.passes(ident, frozenset({"cocoa"}), "Cocoa beans, sun-dried {GH}")


# ------------------------------------------------------------------ location_rank (CA tie)
def test_location_rank_exact_beats_substring():
    ca = get_region("CA")
    assert location_rank(ca, "Canada") < location_rank(ca, "Canada, Ontario")
    assert location_rank(ca, "Canada") < location_rank(ca, "Canada, Quebec")
    assert location_rank(ca, "Canada, Ontario") < location_rank(ca, "Rest of World")
    assert location_rank(ca, "Rest of World") < location_rank(ca, "Narnia")
    assert location_rank(ca, None) == location_rank(ca, "Narnia")
    gh = get_region("GH")
    assert location_rank(gh, "Ghana") < location_rank(gh, "Rest of World") < location_rank(gh, "Global")


# --------------------------------------------------------------------- fake engine
class _FakeMatcher:
    def __init__(self, cands):
        self._c = cands
        self.uids = [c["uid"] for c in cands]
        self.meta = [{"name": c["name"], "location": c["location"]} for c in cands]

    def build_index(self):
        return len(self.uids)

    def match(self, text, top_k=5, expand=False):
        # every query returns the same pool, except the hidden recall-only datasets
        return [dict(c) for c in self._c if not c.get("hidden")][:top_k]

    def reference_product(self, uid):
        return next(c.get("reference_product") for c in self._c if c["uid"] == uid)

    def score_uids(self, text, uids, top_k=25):
        out = [dict(c) for c in self._c if c["uid"] in set(uids)]
        return sorted(out, key=lambda c: (-c["score"], c["uid"]))[:top_k]


class _FakeQ:
    def source_label(self, uid):
        return "ecoinvent 3.11"

    def get_process(self, uid):
        return {"ref_unit": "kg"}


def _engine(region, cands):
    eng = orch.FarmLCA.__new__(orch.FarmLCA)
    eng.region = get_region(region)
    eng.matcher = _FakeMatcher(cands)
    eng.q = _FakeQ()
    return eng


def _c(uid, name, loc, score, ref=None, hidden=False):
    return {"uid": uid, "name": name, "location": loc, "score": score,
            "reference_product": ref or name, "hidden": hidden}


GH_POOL = [
    _c("cocoa-gh", "cocoa bean production, sun-dried", "Ghana", 0.57, "cocoa bean"),
    _c("aub-row", "aubergine production, open field", "Rest of World", 0.55, "aubergine"),
    _c("aub-in", "aubergine production, open field", "India", 0.56, "aubergine"),
    _c("maize-gh", "maize grain production", "Ghana", 0.50, "maize grain"),
]


@pytest.fixture(autouse=True)
def _no_llm(monkeypatch):
    monkeypatch.setenv("GMG_LLM_ADJUDICATE", "0")


def test_identity_gate_before_region():
    eng = _engine("GH", GH_POOL)
    m = eng._match_input("aubergine production, open field")
    # region preference only among aubergines: RoW (in GH preference list) beats India
    assert m["uid"] == "aub-row"
    assert m["needs_review"] is False and m["identity"]["basis"] == "concept"


def test_no_identity_returns_global_best_flagged():
    eng = _engine("GH", GH_POOL)
    m = eng._match_input("okra production")
    assert m["uid"] == "cocoa-gh"             # best similarity, not region-first choice
    assert m["needs_review"] is True and "okra" in m["review_reason"]
    eng = _engine("GH", [_c("x-gh", "maize grain production", "Ghana", 0.40, "maize grain"),
                         _c("y-glo", "cabbage white production", "Global", 0.60, "cabbage")])
    m = eng._match_input("okra production")
    assert m["uid"] == "y-glo"               # the Ghana dataset no longer wins on region


def test_recall_path_finds_product_outside_top_k():
    pool = GH_POOL[:1] + [_c("cuc-glo", "cucumber production, in heated greenhouse",
                             "Global", 0.52, "cucumber", hidden=True)]
    m = _engine("GH", pool)._match_input("cucumber production")
    assert m["uid"] == "cuc-glo" and m["identity"]["recall_path"] is True


def test_region_recall_admits_location_variant():
    pool = [_c("lf-row", "treatment of municipal solid waste, sanitary landfill", "Rest of World",
               0.75, "municipal solid waste"),
            _c("lf-qc", "treatment of municipal solid waste, sanitary landfill", "Canada, Quebec",
               0.74, "municipal solid waste", hidden=True)]
    m = _engine("CA", pool)._match_input("treatment of municipal solid waste, sanitary landfill")
    assert m["uid"] == "lf-qc"


def test_ca_tie_is_deterministic():
    pool = [_c("b-on", "electricity, low voltage", "Canada, Ontario", 0.70, "electricity, low voltage"),
            _c("a-ca", "electricity, low voltage", "Canada", 0.69, "electricity, low voltage"),
            _c("c-qc", "electricity, low voltage", "Canada, Quebec", 0.70, "electricity, low voltage")]
    for perm in (pool, pool[::-1], pool[1:] + pool[:1]):
        assert _engine("CA", perm)._match_input("electricity low voltage")["uid"] == "a-ca"


def test_fallback_chain_is_live():
    eng = _engine("GH", GH_POOL)
    m, used = eng.resolve_input({"name": "Aubergine", "match_as": "garden produce production",
                                 "fallback": "aubergine production", "kind": "raw_material"})
    assert used == "aubergine production" and m["uid"] == "aub-row"
    m, used = eng.resolve_input({"name": "Aubergine", "match_as": "aubergine production",
                                 "fallback": "garden produce production"})
    assert used is None and m["uid"] == "aub-row"


# --------------------------------------------------------------------- adjudication hook
def test_adjudicator_called_on_close_scores(monkeypatch):
    calls = []

    def fake(query, context, candidates):
        calls.append((query, context, candidates))
        assert {"uid", "name", "reference_product", "location", "source", "ref_unit",
                "score"} <= set(candidates[0])
        return {"uid": "aub-in", "rationale": "Indian open-field aubergine is closer to "
                "West African practice", "model": "fake-model"}

    monkeypatch.setattr(orch, "_adjudicator", lambda: fake)
    pool = [_c("aub-row", "aubergine production, open field", "Rest of World", 0.55, "aubergine"),
            _c("aub-in", "aubergine production, open field", "India", 0.56, "aubergine"),
            _c("aub-gh", "aubergine production, in heated greenhouse", "Global", 0.555,
               "aubergine, greenhouse")]
    m = _engine("GH", pool)._match_input("aubergine production", context={"kind": "raw_material"})
    assert calls and calls[0][1]["region"] == "GH" and calls[0][1]["kind"] == "raw_material"
    assert m["uid"] == "aub-in"
    assert m["adjudication"]["adjudicated"] is True
    assert "West African" in m["adjudication"]["rationale"]
    assert m["adjudication"]["model"] == "fake-model"


def test_adjudicator_invalid_uid_is_ignored(monkeypatch):
    monkeypatch.setattr(orch, "_adjudicator",
                        lambda: (lambda q, c, cands: {"uid": "invented", "rationale": "x",
                                                      "model": "m"}))
    m = _engine("GH", GH_POOL)._match_input("okra production")
    assert m["uid"] == "cocoa-gh" and m["adjudication"]["adjudicated"] is False


def test_adjudication_disabled_by_env(monkeypatch):
    monkeypatch.setenv("GMG_LLM_ADJUDICATE", "0")
    assert orch._adjudicator() is None
    m = _engine("GH", GH_POOL)._match_input("okra production")
    assert m["adjudication"]["adjudicated"] is False
    assert "needs_review" in m["adjudication"]["trigger"]


def test_no_adjudication_when_unambiguous(monkeypatch):
    monkeypatch.setattr(orch, "_adjudicator", lambda: pytest.fail("must not be called"))
    pool = [_c("u", "Urea (with 46% N), at plant {RoW}", "Rest of World", 0.70),
            _c("npk", "NPK (15-15-15), at plant {RoW}", "Rest of World", 0.60)]
    m = _engine("GH", pool)._match_input("Urea fertiliser")
    assert m["uid"] == "u" and m["adjudication"] == {"adjudicated": False, "rationale": None}


# --------------------------------------------------------------------- hint table
@pytest.mark.parametrize("name,hint", [
    ("Groundnuts (shelled)", "peanut production"),
    ("Peanuts", "peanut production"),
    ("Eggplant", "aubergine production, open field"),
    ("Garden eggs", "aubergine production, open field"),
    ("Cucumber", "cucumber production"),
    ("Chilli peppers", "chilli production"),
    ("Bell peppers", "bell pepper production, open field"),
    ("Fresh fruit bunches (FFB)", "palm fruit bunch production"),
    ("Raw honey", "Honey, raw, small-scale production, unpackaged, at farm"),
    ("Pearl millet", "millet production"),
    ("Sorghum", "sorghum grain, at farm gate"),
    ("Sesame", "sesame seed production"),
    ("Seed cotton", "seed-cotton production, conventional"),
    ("Onions", "onion production"),
    ("Sugar cane", "sugarcane production"),
    ("Oranges", "orange production, fresh grade"),
    ("Grapes", "grape production"),
    ("Apples", "apple production"),
    ("Pears", "pear production"),
    ("Pineapple", "pineapple production"),
])
def test_raw_material_hints(name, hint):
    assert _raw_material_match(name) == (hint, False)


def test_refined_hint_not_inside_crop_phrase():
    assert _raw_material_match("Sugar cane")[1] is False
    assert _raw_material_match("raw sugar")[1] is True
    assert _raw_material_match("groundnut oil") == ("peanut oil, at oil mill", True)


# ------------------------------------------------- "Africa" must not match "South Africa"
def _bf_like():
    """A Burkina Faso style region (WS3b adds the real one); built here so the test runs on
    any branch. Preference strings follow the store's location names."""
    from engine.regions import Region
    return Region(code="BF", name="Burkina Faso", currency="XOF", climate_zone="dry tropical",
                  ipcc_n2o_ef1=0.005, aware_country="Burkina Faso",
                  default_method="ReCiPe 2016 v1.03, midpoint (H)",
                  location_prefer=("BF", "Burkina Faso", "Africa", "Rest of World", "RoW",
                                   "Global", "GLO"))


def test_location_rank_africa_is_not_south_africa():
    bf = _bf_like()
    assert location_rank(bf, "South Africa") == location_rank(bf, "Narnia")
    assert location_rank(bf, "Africa") < location_rank(bf, "Rest of World")
    assert location_rank(bf, "Global") == location_rank(bf, "GLO")
    ca = get_region("CA")
    assert location_rank(ca, "Canada without Quebec") < location_rank(ca, "Rest of World")


def test_bf_electricity_does_not_resolve_to_za():
    eng = _engine("GH", [
        _c("za", "market for electricity, low voltage", "South Africa", 0.75,
           "electricity, low voltage"),
        _c("raf", "market group for electricity, low voltage", "Africa", 0.72,
           "electricity, low voltage"),
        _c("glo", "market group for electricity, low voltage", "Global", 0.70,
           "electricity, low voltage")])
    eng.region = _bf_like()
    m = eng._match_input("electricity low voltage")
    assert m["uid"] == "raf" and m["location"] != "South Africa"
