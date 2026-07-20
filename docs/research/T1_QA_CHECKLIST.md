# Tier 1 QA checklist — Ghana maize–cowpea case study

Manual smoke path (local API + results UI):

1. Sign in as researcher; submit `engine/case_studies/ghana_maize_cowpea_intercrop.json` via assess/stream.
2. **Export** — Download JSON and CSV from results; confirm `input_matches` and midpoints present.
3. **Per-ha toggle** — Switch Per kg | Per ha; land per ha ≈ 10 000 m²a/ha when area/yield match the fixture; note about single-score bands stays per kg.
4. **Scenario** — Yield +20%; land per kg and single score decrease vs baseline; scenario saved with `Scenario:` title.
5. **Method** — Switch to EF v3.1; climate remains finite; methodology string updates; variant cached when not applied as primary.
6. **Monte Carlo** — Run screening MC; ranges become p5–p95; ISO sensitivity mentions N and pedigree basis.

Automated gate:

```bash
cd app
set PYTHONPATH=..;..
pytest test_research_export.py test_scenarios.py test_method_lab.py ../engine/test_functional_units.py ../engine/test_uncertainty.py ../engine/test_method_toggle.py test_auth_workspace.py test_recommendations_api.py -q
```
