# Green Means Go — Brief

**Date:** 25 May 2026

## What it is

An Africa-first life-cycle-assessment platform that produces a full **14-midpoint plus 3-endpoint environmental footprint** of a Ghanaian or Nigerian crop production system from a single farm questionnaire, and turns the numbers into a plain-language report a smallholder or extension officer can act on. Built from African farm structures and tropical impact factors upward — not retrofitted from a European LCA tool.

## Key technological features

- **14-midpoint + 3-endpoint LCA engine.** A Rust core computes global warming, blue water consumption, AWARE-adjusted water scarcity, land use, MSA-based biodiversity loss, soil degradation, terrestrial acidification, freshwater and marine eutrophication, fossil and mineral depletion, particulate-matter formation, and photochemical oxidation — then rolls them into Human Health (DALY), Ecosystem Quality (species·yr), and Resource Scarcity (USD) endpoints.
- **Sub-national water-scarcity differentiation.** Region-specific AWARE factors — Northern Ghana 30.0, Southern Ghana 15.0, Northern Nigeria 35.0, Southern Nigeria 18.0 — instead of a single country-level number. Water scarcity is the impact category that swings most across the Sahel-to-coast gradient, and almost every comparable tool collapses it to a national average.
- **Africa-weighted endpoint normalization.** The single-score collapse uses priorities calibrated for African development context (Human Health 40%, Ecosystem Quality 35%, Resource Scarcity 25%) rather than the default 33/33/33, and applies a 1.5× health-vulnerability adjustment at the endpoint stage.
- **Production-system biodiversity model.** Native-species loss is differentiated by management type — intensive 30%, conventional 20%, organic 10%, agroforestry 5% — so the engine actually rewards the practices smallholders are being pushed toward by certification schemes.
- **Dual-persona AI reporting.** Every assessment produces two parallel reports from the same numbers: an LCA-expert technical brief (the "Dr. Amara Okonkwo" persona) and a farmer-facing plain-language version (the "Kwame Mensah" persona), generated through Claude Haiku 4.5 with prompt-cached system personas and 11 controlled sections per report.
- **Two-mode assessment.** A 5-minute baseline for first-time screening and a 15–20 minute deep assessment covering soil, water, fertilizer, pest, fuel, and equipment management — both feed the same underlying engine.

## Major breakthroughs for the field

1. **First end-to-end LCA system designed from African inputs up, not bolted onto a European model.** Established tools (SimaPro, openLCA, Cool Farm Tool) require an LCA specialist and assume temperate-climate, large-farm defaults. Green Means Go starts from smallholder farm structures, tropical impact factors, and sub-regional water scarcity, and applies an Africa-specific health-vulnerability multiplier that other engines do not.
2. **Closes the LCA interpretation gap.** Output of conventional LCA tooling is a CSV of midpoint numbers that needs a consultant to read. The dual-persona AI report layer turns the same engine output into a document a farmer cooperative or ministry analyst can act on directly — without altering any of the underlying numbers.
3. **Region-resolved water-scarcity scoring on a Canadian-style multi-indicator chassis.** Distinguishing Northern vs Southern Ghana / Nigeria materially changes the result for irrigated crops, and to our knowledge no other public African LCA tool resolves below the national level on AWARE.

## What it unlocks

- **For farmers and agribusinesses** — a 5-minute self-served environmental footprint with a farmer-friendly written summary; a ranked list of which single practice change (drip irrigation, IPM, conservation tillage, compost) cuts their score the most; quantified benefit of shifting production system (intensive → agroforestry) in both midpoint impacts and the African endpoint score.
- **For policy makers** — a defensible single-number index for any commodity–region combination (cocoa from Ashanti, maize from Kano, cassava from Cross River); a tool that scores national crop-mix scenarios on the same yardstick used to score individual farms; sub-national water-scarcity treatment, which is the cleavage that determines whether an irrigation expansion or a fertilizer-subsidy programme makes sense at the basin level.
- **As a research tool** — a reproducible reference combining AWARE water scarcity, MSA-based biodiversity loss, and an Africa-weighted endpoint single score in one engine; a structured smallholder questionnaire schema that captures everything an LCA practitioner needs from a low-records farm; an extensible Rust core that can absorb new crops, new countries, or new impact categories without re-architecting, plus an AI report pipeline that decouples engine output from interpretation.

## Next step

The priority development is a **passive smallholder assessment layer**: combine a satellite-derived crop-and-area estimate (Sentinel-2 NDVI plus a crop-type classifier) with an SMS or voice-prompt practice questionnaire, so that a farmer with a basic phone and no written farm records can receive a full sustainability score in their own language without filling in a web form. The same Rust engine and dual-persona AI report layer run unchanged — only the input layer is new. This is what turns Green Means Go from a tool for the digitally-equipped minority into one that can be rolled out across a national extension service. Alongside this, wiring the already-defined pedigree-matrix scores into a real Monte Carlo loop would give every output an honest uncertainty band — closing the one credibility gap the engine still has relative to the academic LCA literature.
