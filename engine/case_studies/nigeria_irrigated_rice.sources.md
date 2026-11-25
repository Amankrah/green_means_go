# Provenance: nigeria_irrigated_rice.json

Illustrative commercial dry-season irrigated rice farm in a Kano surface-irrigation scheme. Not a real farm.

| Field | Value | Source / reasoning |
|---|---|---|
| admin region | `study_meta.admin_region` "Kano" | Engine climate: WMO 1991-2020 normal at Kano (65046) 1149.2 mm -> IPCC wet (engine/regions.py). |
| irrigation system | "Flood Irrigation" (was "Sprinkler") | Kano schemes are surface (gravity/basin) irrigated; sprinkler rice is inferred as upland (no flooding CH4) under CONTRACT §1, which contradicted the irrigated-paddy intent. |
| water regime | `irrigated_continuously_flooded` (explicit) | IPCC 2019 Vol 4 Ch 5 Table 5.12. The previous "Alternate wetting and drying" practice was removed: it contradicted continuous flooding and matches the wizard's Nigeria example (lead's instruction). |
| irrigation volume | blank | Estimated by engine/crop_defaults.py: FAO Manual No. 3 rice 575 mm/season, surface efficiency 0.60, DrySeason share 1.0 (team assumption, disclosed) -> ~115 000 m3 for 12 ha. |
| crops_per_year | 1 | Dry-season crop only (`seasonal_factor` DrySeason); 50.4 t on 12 ha = 4.2 t/ha, within FARO 44's 4.0-8.0 t/ha potential (NCRI catalogue). |
| growing_period_days | 115 | NCRI Badeggi released-variety catalogue: FARO 44 maturity 110-120 days (midpoint). Includes the nursery period, so it is an upper bound on the flooded days used in IPCC Eq 5.1. |
| energy | diesel 220 L/month as `fuel_consumption` only | The same 220 L/month (same cost) was also entered as a "Diesel Generator" energy source: a double entry, removed. |
| fertiliser, pesticides, equipment | unchanged | Screening values (original case). |
