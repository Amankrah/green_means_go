# Provenance: south_africa_irrigated_maize.json

Illustrative commercial centre-pivot maize farm near Douglas (Northern Cape). Not a real farm.

| Field | Value | Source |
|---|---|---|
| country / region | "Global" / "ZA" | Kernel country bucket "Global"; engine region via `region`. |
| area, yield | 50 ha, 600 t (12 t/ha) | Irrigated commercial maize assumption. FAOSTAT's national mean (6057 kg/ha, 2021-2023, flag A) is dominated by dryland maize, so it is not used; 12 t/ha is a typical pivot yield. Reviewer to verify against Crop Estimates Committee irrigated maize statistics. |
| fertiliser | MAP 11-52-0 at 150 kg/ha + urea 175 kg/ha x 2 | ~178 kg N/ha total, in line with a 12 t/ha target; split urea as recommended in the DAFF (2018) CSA framework ("properly timed or split application of mineral fertilizers"). |
| electricity | 6875 kWh/month (82 500 kWh/yr, 1650 kWh/ha) | Activity-default row `irrigated_full` in `reference/south_africa_farm_activity_defaults.json`: 6000 m3/ha x 60 m head / 0.6 wire-to-water efficiency. Grid factor calibrated to Eskom 1.04 kgCO2/kWh (Integrated Report 2024, p 122). |
| diesel | 290 L/month (3480 L/yr, ~70 L/ha) | Same activity-default row (field operations ~70 L/ha). |
| pesticides | atrazine 1.5, glyphosate 2.0, lambda-cyhalothrin 0.1 kg/ha | Typical commercial maize herbicide and stalk-borer programme (screening rates). |
| irrigation | sprinkler (centre pivot) | Not drip, so IPCC 2019 Ch 11 sets FracLEACH-(H) to 0.24 even in the dry climate (`regions.frac_leach_for`). |
| climate parameters | EF1 0.005, EF4 0.005 | IPCC 2019 Tables 11.1 / 11.3, warm temperate dry (P:PET < 1). Note: the kernel's own FracLEACH is still the fixed 0.24, which coincides with the irrigated value here. |
