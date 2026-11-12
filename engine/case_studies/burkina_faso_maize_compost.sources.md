# Provenance: burkina_faso_maize_compost.json

Illustrative smallholder near Bobo-Dioulasso (Hauts-Bassins) using compost pits (fosses
fumieres) with reduced mineral fertiliser. Not a real farm.

| Field | Value | Source |
|---|---|---|
| country / region | "Global" / "BF" | Kernel country bucket "Global"; engine region via `region`. |
| area, yield | 2.0 ha, 3600 kg (1800 kg/ha) | FAOSTAT QCL, Burkina Faso, maize, mean 2021-2023 = 1606 kg/ha (flag A, DGESS official series); set ~12% above the mean for a composting farm in the higher-rainfall south-west. |
| compost | farm-made, 5 t/ha | Burkina Faso CDN 2021-2025 lists "l'utilisation du compost" among agriculture co-benefits; 5 t/ha is a common extension rate for pit compost (screening). Farm-made, so no purchase burden; its N feeds field N2O. |
| fertiliser | NPK 14-23-14 at 150 kg/ha + urea 75 kg/ha | 14-23-14 is the standard cotton/maize compound sold in Burkina Faso; rates are below the full extension dose to reflect compost substitution (screening). |
| herbicide | glyphosate 1.5 kg/ha | Common pre-plant burndown in the cotton/maize zone (screening rate). |
| energy | none; animal traction | Activity-default row `rainfed_manual` (0 L, 0 kWh), `reference/burkina_faso_farm_activity_defaults.json`. |
| post-harvest loss | 12% | Screening value. |
| climate parameters | EF1 0.005, EF4 0.005, FracLEACH 0 | IPCC 2019 Tables 11.1 / 11.3, dry climate (Bobo-Dioulasso ~1000 mm/yr is at the threshold; national default kept dry). |
