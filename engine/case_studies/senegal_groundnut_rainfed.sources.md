# Provenance: senegal_groundnut_rainfed.json

Illustrative smallholder in the Groundnut Basin (Kaolack). Not a real farm; values are set
to national statistics and extension practice so the case is representative.

| Field | Value | Source |
|---|---|---|
| country / region | "Global" / "SN" | The Rust kernel accepts only Ghana/Nigeria/Global; the engine region is carried by `region` (same pattern as the Canada case). |
| area, yield | 3.0 ha, 3900 kg (1300 kg/ha) | FAOSTAT QCL, Senegal, groundnuts excluding shelled, mean 2021-2023 = 1314 kg/ha (flag A, DAPSA official series). `engine/recommend/reference/senegal_yield_guides.json`. |
| fertiliser | NPK 6-20-10 at 150 kg/ha, once | The subsidised "engrais arachide" formula and rate recommended for groundnut in Senegal's input subsidy programme (ISRA recommendation; 150 kg/ha). Screening assumption; reviewer to confirm against the current campaign circular. |
| cost | 30000 XOF (field kept for schema completeness, not used by the engine) | Subsidised price order of magnitude; not used in any calculation. |
| energy | none; animal traction | CIAT; BFS/USAID (2016) Climate-Smart Agriculture in Senegal: rainfed cultivation by hand and animal traction dominates. Activity-default row `rainfed_manual` (0 L, 0 kWh). |
| pesticides | none | Most smallholder groundnut in the basin receives no field pesticide; seed treatment omitted (cut-off). |
| post-harvest loss | 10% | Screening value, same order as the other West African cases. |
| climate parameters | EF1 0.005, EF4 0.005, FracLEACH 0 | IPCC 2019 Vol 4 Ch 11 Tables 11.1 and 11.3, dry climate (Kaolack ~600-800 mm/yr < 1000 mm). |
