//! Field (soil-N) reference data for the LCI kernel:
//!
//! 1. Fertiliser N content lookup (replaces the old silent 10% fallback). Unknown types get
//!    ZERO N plus a validation warning; they never generate N2O from an invented N content.
//! 2. IPCC 2019 Tier 1 crop-residue parameters (Vol 4 Ch 11, Table 11.1A, Eq 11.6/11.7) and
//!    the F_CR calculation.
//!
//! Every value carries a source string. Where Table 11.1A has no row for a crop, the closest
//! IPCC row is used and the citation says which (and why), per note "e" of Table 11.1A:
//! "The most appropriate generic value can be used based on expert judgment".

/// How the N in a fertiliser behaves in the IPCC 2019 soil-N2O method.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum NForm {
    /// Synthetic N (F_SN): EF1 synthetic, FracGASF.
    Synthetic,
    /// Organic N (F_ON): EF1 "other N inputs", FracGASM.
    Organic,
}

#[derive(Debug, Clone, PartialEq)]
pub struct FertiliserN {
    /// kg N per kg product.
    pub n_fraction: f64,
    pub form: NForm,
    pub source: &'static str,
    /// Validation warning to surface (unknown type, assumed grade, ...).
    pub warning: Option<String>,
}

const SRC_FAO_IFA: &str = "FAO & IFA (2000) Fertilizers and their use, 4th ed., Rome, \
    nutrient content of straight N fertilisers";

/// Parse a declared N-P2O5-K2O grade ("15-15-15", "20:10:10", "23 10 5") into percent.
/// Same rule as engine/inputs.py `_parse_grade`: three numbers separated by - : / or
/// space, each <= 100, 0 < sum <= 100; anything else is not a grade (None).
pub fn parse_grade(npk_ratio: &Option<String>) -> Option<(f64, f64, f64)> {
    let r = npk_ratio.as_ref()?.trim();
    let mut parts = r.split(|c: char| c == '-' || c == ':' || c == '/' || c.is_whitespace())
        .filter(|s| !s.is_empty());
    let mut g = [0.0f64; 3];
    for slot in g.iter_mut() {
        *slot = parts.next()?.parse::<f64>().ok()?;
    }
    if g.iter().any(|v| !v.is_finite() || *v < 0.0 || *v > 100.0) {
        return None;
    }
    let sum: f64 = g.iter().sum();
    if !(sum > 0.0 && sum <= 100.0) {
        return None;
    }
    Some((g[0], g[1], g[2]))
}

/// N share of a declared grade (e.g. "15-15-15" -> 0.15); None when not a valid grade.
pub fn n_from_ratio(npk_ratio: &Option<String>) -> Option<f64> {
    parse_grade(npk_ratio).map(|g| g.0 / 100.0)
}

/// Placeholder rows that carry no fertiliser (engine/inputs.py `is_none_fertiliser`).
pub fn is_none_fertiliser(fertilizer_type: &str) -> bool {
    matches!(fertilizer_type.trim().to_lowercase().as_str(),
             "" | "none" | "no fertilizer" | "no fertiliser" | "not used")
}

/// Straight products identified from their standard grade alone when the declared name is
/// free text ("white prills" 46-0-0 is urea), mirroring engine/inputs.py
/// `_fertiliser_product` / FERTILISER_PRODUCTS (FAO & IFA 2000 grades).
const STRAIGHT_GRADES: [((f64, f64, f64), &str); 7] = [
    ((27.0, 0.0, 0.0), "calcium ammonium nitrate"),
    ((30.0, 0.0, 0.0), "urea ammonium nitrate"),
    ((21.0, 0.0, 0.0), "ammonium sulphate"),
    ((33.5, 0.0, 0.0), "ammonium nitrate"),
    ((18.0, 46.0, 0.0), "diammonium phosphate"),
    ((11.0, 52.0, 0.0), "monoammonium phosphate"),
    ((46.0, 0.0, 0.0), "urea"),
];

fn is_organic_type(t: &str) -> bool {
    t.contains("organic") || t.contains("manure") || t.contains("compost")
        || t.contains("poultry") || t.contains("dung") || t.contains("guano") || t.contains("vermi")
}

/// The product whose N form decides FracGASF and urea CO2: the declared type when it names
/// a product; for an otherwise unrecognised free-text name, the straight product its grade
/// identifies (not for NPK / compound, foliar or organic rows).
pub fn n_form_type(fertilizer_type: &str, npk_ratio: &Option<String>) -> String {
    let t = fertilizer_type.trim().to_lowercase();
    if n_volatilisation_class(&t) != NVolClass::Unclassified
        || t.contains("npk") || t.contains("compound") || t.contains("foliar") || is_organic_type(&t)
    {
        return fertilizer_type.to_string();
    }
    if let Some(g) = parse_grade(npk_ratio) {
        for (grade, name) in STRAIGHT_GRADES {
            if (g.0 - grade.0).abs() < 1e-9 && (g.1 - grade.1).abs() < 1e-9 && (g.2 - grade.2).abs() < 1e-9 {
                return name.to_string();
            }
        }
    }
    fertilizer_type.to_string()
}

fn has_word(hay: &str, word: &str) -> bool {
    hay.split(|c: char| !c.is_ascii_alphanumeric())
        .any(|w| w == word)
}

/// Explicit fertiliser N lookup. A declared N-P-K grade is authoritative (it is the label
/// on the bag) and wins over the type lookup; otherwise the type decides.
pub fn fertiliser_n(fertilizer_type: &str, npk_ratio: &Option<String>) -> FertiliserN {
    let t = fertilizer_type.trim().to_lowercase();
    let declared = n_from_ratio(npk_ratio);

    if is_organic_type(&t) {
        return match declared {
            Some(n) => FertiliserN {
                n_fraction: n,
                form: NForm::Organic,
                source: "declared N-P-K grade of the organic fertiliser",
                warning: None,
            },
            // Matches the definition of the background dataset the organic fertiliser is
            // modelled with ("Organic fertiliser, >3% N, granulate", AGRIBALYSE 3.2): 3% N
            // is that dataset's lower bound, so field N and supply-chain burden describe the
            // same product.
            None => FertiliserN {
                n_fraction: 0.03,
                form: NForm::Organic,
                source: "AGRIBALYSE 3.2 'Organic fertiliser, >3% N, granulate' (matched \
                         background dataset), lower-bound 3% N",
                warning: Some(format!(
                    "organic fertiliser '{}' has no declared N content: assumed 3% N (the \
                     matched AGRIBALYSE organic fertiliser dataset); declare its N-P-K grade",
                    fertilizer_type)),
            },
        };
    }
    if let Some(n) = declared {
        return FertiliserN {
            n_fraction: n,
            form: NForm::Synthetic,
            source: "declared N-P-K grade",
            warning: None,
        };
    }

    let syn = |n: f64, source: &'static str| FertiliserN {
        n_fraction: n, form: NForm::Synthetic, source, warning: None,
    };
    // Order matters: UAN before urea, "calcium ammonium nitrate" before "ammonium nitrate";
    // phosphates before the generic "phosphate" no-N family.
    if has_word(&t, "uan") || t.contains("urea ammonium nitrate") || t.contains("urea-ammonium nitrate") {
        // Same default as engine/inputs.py FERTILISER_PRODUCTS ("UAN", 30-0-0).
        return syn(0.30, "UAN 30% N, default grade of engine/inputs.py FERTILISER_PRODUCTS; declare the grade (28-32% N)");
    }
    if t.contains("urea") {
        return syn(0.46, SRC_FAO_IFA);
    }
    if t.contains("calcium ammonium nitrate") || has_word(&t, "can") {
        return syn(0.27, SRC_FAO_IFA);
    }
    if t.contains("ammonium sulphate") || t.contains("ammonium sulfate")
        || t.contains("sulphate of ammonia") || t.contains("sulfate of ammonia")
        || has_word(&t, "as") || has_word(&t, "sa")
    {
        return syn(0.21, SRC_FAO_IFA);
    }
    if t.contains("ammonium nitrate") || has_word(&t, "an") {
        return syn(0.335, SRC_FAO_IFA);
    }
    if t.contains("diammonium phosphate") || t.contains("di-ammonium phosphate")
        || has_word(&t, "dap")
    {
        return syn(0.18, SRC_FAO_IFA);
    }
    if t.contains("monoammonium phosphate") || t.contains("mono-ammonium phosphate")
        || has_word(&t, "map")
    {
        return syn(0.11, SRC_FAO_IFA);
    }
    if t.contains("npk") || t.contains("compound") {
        // No grade declared: NPK 15-15-15 is the standard compound recommended for maize
        // and vegetables in Ghana (MoFA) and the grade of the matched background dataset.
        return FertiliserN {
            n_fraction: 0.15,
            form: NForm::Synthetic,
            source: "NPK 15-15-15 (matched background dataset grade); grade not declared",
            warning: Some(format!(
                "compound fertiliser '{}' has no declared N-P-K grade: assumed 15-15-15",
                fertilizer_type)),
        };
    }
    // Fertilisers that contain no nitrogen (straight P and K sources, lime, inoculants).
    let no_n = t.contains("superphosphate") || t.contains("super phosphate") || has_word(&t, "ssp") || has_word(&t, "tsp")
        || t.contains("rock phosphate") || t.contains("muriate") || t.contains("potash")
        || t.contains("potassium chloride") || t.contains("potassium sulphate")
        || t.contains("potassium sulfate") || has_word(&t, "mop") || has_word(&t, "sop")
        || t.contains("lime") || t.contains("dolomite") || t.contains("gypsum")
        || t.contains("bio-fert") || t.contains("biofert") || t.contains("inoculant")
        || is_none_fertiliser(&t);
    if no_n {
        return syn(0.0, "straight P/K source, liming material, microbial inoculant or none: \
                         no fertiliser N (FAO & IFA 2000)");
    }
    FertiliserN {
        n_fraction: 0.0,
        form: NForm::Synthetic,
        source: "unrecognised fertiliser type",
        warning: Some(format!(
            "fertiliser type '{}' is not recognised: its N content was set to 0, so it \
             produces no field N2O; declare an N-P-K grade to include it",
            fertilizer_type)),
    }
}

// ----------------------------------------------------------------------------------------
// Crop residues (IPCC 2019 Refinement, Vol 4, Ch 11, Eq 11.6 (updated), Eq 11.7,
// Table 11.1A (new); combustion factor from Vol 4 Ch 2 Table 2.6 (updated))
// ----------------------------------------------------------------------------------------

#[derive(Debug, Clone, PartialEq)]
pub struct ResidueParams {
    pub crop: &'static str,
    /// N content of above-ground residues, kg N / kg d.m. (N_AG)
    pub n_ag: f64,
    /// N content of below-ground residues, kg N / kg d.m. (N_BG)
    pub n_bg: f64,
    /// Ratio of above-ground residue d.m. to harvested yield d.m. (R_AG)
    pub r_ag: f64,
    /// Ratio of below-ground root biomass to above-ground shoot biomass (RS)
    pub rs: f64,
    /// Dry-matter fraction of the harvested product (DRY)
    pub dry: f64,
    /// Combustion factor C_f for field burning (Ch 2 Table 2.6 updated)
    pub cf: f64,
    pub source: &'static str,
    /// true when Table 11.1A has no row for this crop and a proxy row is used.
    pub proxy: bool,
}

const T11_1A: &str = "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A";
const CF_OTHER: f64 = 0.85; // Vol 4 Ch 2 Table 2.6 (updated): agricultural residues, "Other"

/// Table 11.1A row "Generic value for crops not indicated below".
fn generic(crop: &'static str, dry: f64, source: &'static str) -> ResidueParams {
    ResidueParams { crop, n_ag: 0.008, n_bg: 0.009, r_ag: 1.0, rs: 0.22, dry, cf: CF_OTHER,
                    source, proxy: true }
}

/// Look up residue parameters by crop name (case-insensitive substring match). Returns the
/// Table 11.1A generic row (flagged as proxy) for crops the table does not cover.
pub fn residue_params(crop_name: &str) -> ResidueParams {
    let n = crop_name.to_lowercase();
    let has = |k: &str| n.contains(k);

    // ---- cereals (Table 11.1A rows; N_BG / RS marked "-" use Generic Grains per note e) ----
    if has("maize") || has("corn") {
        return ResidueParams { crop: "maize", n_ag: 0.006, n_bg: 0.007, r_ag: 1.0, rs: 0.22,
            dry: 0.87, cf: 0.80, proxy: false,
            source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Maize'; C_f Vol 4 Ch 2 Table 2.6 'Maize' 0.80" };
    }
    if has("rice") || has("paddy") {
        return ResidueParams { crop: "rice", n_ag: 0.007, n_bg: 0.009, r_ag: 1.4, rs: 0.16,
            dry: 0.89, cf: 0.80, proxy: false,
            source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Rice' (N_BG not given: 'Generic Grains' 0.009 per note e); C_f Ch 2 Table 2.6 'Rice' 0.80" };
    }
    if has("millet") {
        return ResidueParams { crop: "millet", n_ag: 0.007, n_bg: 0.009, r_ag: 1.4, rs: 0.22,
            dry: 0.90, cf: CF_OTHER, proxy: false,
            source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Millet' (N_BG and RS not given: 'Generic Grains' 0.009 / 0.22 per note e)" };
    }
    if has("sorghum") {
        return ResidueParams { crop: "sorghum", n_ag: 0.007, n_bg: 0.006, r_ag: 1.4, rs: 0.22,
            dry: 0.89, cf: CF_OTHER, proxy: false,
            source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Sorghum' (RS not given: 'Generic Grains' 0.22 per note e)" };
    }
    if has("wheat") {
        if has("winter") {
            return ResidueParams { crop: "winter wheat", n_ag: 0.006, n_bg: 0.009, r_ag: 1.3,
                rs: 0.23, dry: 0.89, cf: 0.90, proxy: false,
                source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Winter Wheat'; C_f Ch 2 Table 2.6 'Wheat' 0.90" };
        }
        return ResidueParams { crop: "spring wheat", n_ag: 0.006, n_bg: 0.009, r_ag: 1.3,
            rs: 0.28, dry: 0.89, cf: 0.90, proxy: false,
            source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Spring Wheat' (default when the season is not stated); C_f Ch 2 Table 2.6 'Wheat' 0.90" };
    }
    if has("barley") {
        return ResidueParams { crop: "barley", n_ag: 0.007, n_bg: 0.014, r_ag: 1.2, rs: 0.22,
            dry: 0.89, cf: CF_OTHER, proxy: false, source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Barley'" };
    }
    if has_word(&n, "oat") || has_word(&n, "oats") {
        return ResidueParams { crop: "oats", n_ag: 0.007, n_bg: 0.008, r_ag: 1.3, rs: 0.25,
            dry: 0.89, cf: CF_OTHER, proxy: false, source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Oats'" };
    }
    // ---- legumes (residue N counted; BNF itself is NOT an N input, IPCC 2019 Ch 11 fn 1) ----
    if has("groundnut") || has("peanut") {
        return ResidueParams { crop: "groundnut", n_ag: 0.016, n_bg: 0.008, r_ag: 1.0, rs: 0.19,
            dry: 0.94, cf: CF_OTHER, proxy: false,
            source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Peanuts' (N_BG and RS not given: 'Beans and Pulses' 0.008 / 0.19, the closest N-fixing row, per note e)" };
    }
    if has("soy") {
        return ResidueParams { crop: "soybean", n_ag: 0.008, n_bg: 0.008, r_ag: 2.1, rs: 0.19,
            dry: 0.91, cf: CF_OTHER, proxy: false, source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Soybeans'" };
    }
    if has("cowpea") || has("bean") || has_word(&n, "pea") || has_word(&n, "peas")
        || has("lentil") || has("chickpea")
        || has("bambara") || has("pulse")
    {
        return ResidueParams { crop: "beans and pulses", n_ag: 0.008, n_bg: 0.008, r_ag: 2.1,
            rs: 0.19, dry: 0.91, cf: CF_OTHER, proxy: false,
            source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Beans and Pulses' (cowpea is listed in the Table 11.2 note b data set for this class)" };
    }
    // ---- roots and tubers ----
    if has("cassava") || has("manioc") {
        return ResidueParams { crop: "cassava", n_ag: 0.019, n_bg: 0.014, r_ag: 0.4, rs: 0.20,
            dry: 0.40, cf: CF_OTHER, proxy: true,
            source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Potatoes and Tubers' for N_AG, N_BG, R_AG, RS; DRY 0.40 from USDA FoodData Central SR Legacy 'Cassava, raw' (water 59.68 g/100 g), as the IPCC DRY 0.22 is for potato" };
    }
    if has("yam") {
        return ResidueParams { crop: "yam", n_ag: 0.019, n_bg: 0.014, r_ag: 0.4, rs: 0.20,
            dry: 0.30, cf: CF_OTHER, proxy: true,
            source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Potatoes and Tubers'; DRY 0.30 from USDA FoodData Central SR Legacy 'Yam, raw' (water 69.60 g/100 g)" };
    }
    if has("potato") || has("tuber") || has("cocoyam") || has("taro") {
        return ResidueParams { crop: "potatoes and tubers", n_ag: 0.019, n_bg: 0.014, r_ag: 0.4,
            rs: 0.20, dry: 0.22, cf: CF_OTHER, proxy: false,
            source: "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Potatoes and Tubers'" };
    }
    // ---- perennials: no Table 11.1A row. Generic row; below-ground term scaled by
    //      Frac_Renew = 1/lifetime supplied by the Python engine (engine/perennials.py). ----
    if has("cocoa") || has("cacao") {
        return generic("cocoa", 0.925,
            "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Generic value for crops not indicated' (no cocoa row); DRY 0.925 for dry beans traded at the ICCO 7.5% maximum moisture; below-ground term renewed at 1/plantation lifetime (Eq 11.6 Frac_Renew)");
    }
    if has("palm") || has("ffb") || has("fresh fruit bunch") {
        return generic("oil palm", 0.85,
            "IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1A row 'Generic value for crops not indicated' (no oil palm row, generic DRY kept); below-ground term renewed at 1/plantation lifetime (Eq 11.6 Frac_Renew)");
    }
    if has("sugarcane") || has("sugar cane") {
        // Generic N contents and RS. Residue (trash) mass from Hassuani, Leal & Macedo (2005)
        // 'Biomass power generation: sugar cane bagasse and trash', CTC/UNDP: 140 kg dry trash
        // per tonne of cane. With stalk dry matter 0.27 (Hugot 1986, Handbook of Cane Sugar
        // Engineering: fibre ~13% + soluble solids ~14%) this is R_AG = 0.14 / 0.27 = 0.52.
        return ResidueParams { crop: "sugarcane", n_ag: 0.008, n_bg: 0.009, r_ag: 0.52, rs: 0.22,
            dry: 0.27, cf: 0.80, proxy: true,
            source: "IPCC 2019 Table 11.1A generic N_AG/N_BG/RS; R_AG 0.52 from Hassuani et al. 2005 (140 kg dry trash/t cane) and DRY 0.27 (Hugot 1986); C_f Ch 2 Table 2.6 'Sugarcane' 0.80" };
    }
    // ---- vegetables: no Table 11.1A row. Generic N/R_AG/RS, crop-specific DRY because the
    //      generic DRY 0.85 would treat a 94%-water fruit as grain. ----
    let veg = |crop: &'static str, dry: f64, source: &'static str| generic(crop, dry, source);
    if has("tomato") {
        return veg("tomato", 0.055, "IPCC 2019 Table 11.1A 'Generic value for crops not indicated' (no vegetable row); DRY 0.055 from USDA FoodData Central SR Legacy 'Tomatoes, red, ripe, raw' (water 94.52 g/100 g)");
    }
    if has("chili") || has("chilli") || has("hot pepper") || has("pepper, hot") {
        return veg("chilli pepper", 0.12, "IPCC 2019 Table 11.1A 'Generic value for crops not indicated'; DRY 0.12 from USDA FoodData Central SR Legacy 'Peppers, hot chili, green, raw' (water 87.74 g/100 g)");
    }
    if has("pepper") || has("capsicum") {
        return veg("sweet pepper", 0.061, "IPCC 2019 Table 11.1A 'Generic value for crops not indicated'; DRY 0.061 from USDA FoodData Central SR Legacy 'Peppers, sweet, green, raw' (water 93.89 g/100 g)");
    }
    if has("eggplant") || has("aubergine") || has("garden egg") {
        return veg("eggplant", 0.077, "IPCC 2019 Table 11.1A 'Generic value for crops not indicated'; DRY 0.077 from USDA FoodData Central SR Legacy 'Eggplant, raw' (water 92.30 g/100 g)");
    }
    if has("cucumber") {
        return veg("cucumber", 0.048, "IPCC 2019 Table 11.1A 'Generic value for crops not indicated'; DRY 0.048 from USDA FoodData Central SR Legacy 'Cucumber, with peel, raw' (water 95.23 g/100 g)");
    }
    if has("onion") {
        return veg("onion", 0.109, "IPCC 2019 Table 11.1A 'Generic value for crops not indicated'; DRY 0.109 from USDA FoodData Central SR Legacy 'Onions, raw' (water 89.11 g/100 g)");
    }
    if has("okra") {
        return veg("okra", 0.104, "IPCC 2019 Table 11.1A 'Generic value for crops not indicated'; DRY 0.104 from USDA FoodData Central SR Legacy 'Okra, raw' (water 89.58 g/100 g)");
    }
    if has("sesame") {
        return generic("sesame", 0.953, "IPCC 2019 Table 11.1A 'Generic value for crops not indicated' (no sesame row); DRY 0.953 from USDA FoodData Central SR Legacy 'Seeds, sesame seeds, whole, dried' (water 4.69 g/100 g)");
    }
    if has("cotton") {
        return generic("cotton", 0.85, "IPCC 2019 Table 11.1A 'Generic value for crops not indicated' (no cotton row; generic DRY applied to seed cotton)");
    }
    generic("generic crop", 0.85, T11_1A)
}

/// Result of IPCC 2019 Eq 11.6 for one crop on its harvested area.
#[derive(Debug, Clone, PartialEq)]
pub struct ResidueN {
    pub params: ResidueParams,
    /// Crop(T): harvested dry-matter yield, kg d.m./ha (Eq 11.7)
    pub crop_dm_per_ha: f64,
    /// AG_DM(T), kg d.m./ha
    pub ag_dm_per_ha: f64,
    /// F_CR above-ground part (kg N, whole area), after removal and burning
    pub n_above: f64,
    /// F_CR below-ground part (kg N, whole area)
    pub n_below: f64,
    /// residue dry matter burnt in the field (kg d.m., whole area): M_B x C_f
    pub dm_burnt: f64,
    /// above-ground residue d.m. left on the field (kg d.m., whole area):
    /// AGR x (1 - Frac_Remove - Frac_Burnt x C_f)
    pub ag_dm_retained: f64,
}

impl ResidueN {
    pub fn f_cr(&self) -> f64 {
        self.n_above + self.n_below
    }
}

fn clamp01(x: f64) -> f64 {
    if x.is_finite() { x.max(0.0).min(1.0) } else { 0.0 }
}

/// IPCC 2019 Eq 11.6 (updated) + Eq 11.7 for one crop.
///   Crop      = Yield_fresh x DRY                                   (Eq 11.7)
///   AG_DM     = Crop x R_AG
///   AGR       = AG_DM x Area x Frac_Renew
///   BGR       = (Crop + AG_DM) x RS x Area x Frac_Renew
/// Frac_Renew multiplies BOTH the above- and below-ground terms in Eq 11.6 (1 for annual
/// crops; 1/X for stands renewed every X years).
///   F_CR      = AGR x N_AG x (1 - Frac_Remove - Frac_Burnt x C_f) + BGR x N_BG
/// `fresh_yield_kg_ha` is the harvested product as reported (fresh weight).
pub fn residue_n(crop_name: &str, fresh_yield_kg_ha: f64, area_ha: f64,
                 frac_remove: f64, frac_burnt: f64, frac_renew: f64) -> ResidueN {
    let p = residue_params(crop_name);
    let crop_dm = fresh_yield_kg_ha.max(0.0) * p.dry;
    let ag_dm = crop_dm * p.r_ag;
    let area = area_ha.max(0.0);
    let frac_remove = clamp01(frac_remove);
    let frac_burnt = clamp01(frac_burnt);
    let frac_renew = clamp01(frac_renew);
    let ag_left = (1.0 - frac_remove - frac_burnt * p.cf).max(0.0);
    let agr = ag_dm * area * frac_renew;
    let bgr = (crop_dm + ag_dm) * p.rs * area * frac_renew;
    ResidueN {
        crop_dm_per_ha: crop_dm,
        ag_dm_per_ha: ag_dm,
        n_above: agr * p.n_ag * ag_left,
        n_below: bgr * p.n_bg,
        dm_burnt: agr * frac_burnt * p.cf,
        ag_dm_retained: agr * ag_left,
        params: p,
    }
}

/// Field burning emission factors for agricultural residues, g per kg d.m. burnt
/// (IPCC 2006 Vol 4 Ch 2 Table 2.5, row 'Agricultural residues'; Eq 2.27). CO2 from
/// burning residues is biogenic and not counted (regrows within the year).
pub const BURN_CH4_G_PER_KG_DM: f64 = 2.7;
pub const BURN_N2O_G_PER_KG_DM: f64 = 0.07;
/// Same table and row: CO 92 (+/- 84) and NOx 2.5 (+/- 1.0) g/kg d.m. burnt. CO from
/// residue burning is biogenic carbon.
pub const BURN_CO_G_PER_KG_DM: f64 = 92.0;
pub const BURN_NOX_G_PER_KG_DM: f64 = 2.5;
/// EMEP/EEA air pollutant emission inventory guidebook 2019, 3.F Field burning of
/// agricultural residues, Table 3-1 Tier 1 default EFs (Jenkins et al. 1996a):
/// PM2.5 0.0054 kg/kg d.m. (0.0042-0.0067), NMVOC 0.0005 kg/kg d.m. (0.0002-0.0008).
pub const BURN_PM25_G_PER_KG_DM: f64 = 5.4;
pub const BURN_NMVOC_G_PER_KG_DM: f64 = 0.5;

// ----------------------------------------------------------------------------------------
// NH3 + NOx volatilisation class of synthetic N (IPCC 2019 Refinement Vol 4 Ch 11
// Table 11.3 (updated) FracGASF disaggregation; class membership per Annex 11A.7:
// "urea, ammonium-based (ammonia-direct application, AS, and AP), nitrate-based (N K
// compound N) and ammonium-nitrate-based (AN, CAN, Nitrogen solutions, Other N straight,
// Other NP-N and N P K compound-N)").
// ----------------------------------------------------------------------------------------

#[derive(Debug, Clone, Copy, PartialEq)]
pub enum NVolClass {
    Urea,
    AmmoniumBased,
    NitrateBased,
    AmmoniumNitrateBased,
    /// N form not identifiable from the type (e.g. NPK of undeclared composition): the
    /// aggregated FracGASF 0.11 applies. Annex 11A.7 Table 7A.2 assumes NPK N = AN/CAN only
    /// to weight the global aggregate; that is not guidance for an unknown compound, so the
    /// Table 11.3 aggregated default is used.
    Unclassified,
}

/// Classify a synthetic fertiliser by its N form. UAN / nitrogen solutions are
/// ammonium-nitrate-based per Annex 11A.7 even though they contain urea.
pub fn n_volatilisation_class(fertilizer_type: &str) -> NVolClass {
    let t = fertilizer_type.trim().to_lowercase();
    if has_word(&t, "uan") || t.contains("urea ammonium nitrate") || t.contains("urea-ammonium nitrate")
        || t.contains("nitrogen solution")
    {
        return NVolClass::AmmoniumNitrateBased;
    }
    if t.contains("urea") {
        return NVolClass::Urea;
    }
    if t.contains("ammonium nitrate") || has_word(&t, "can") || has_word(&t, "an") {
        return NVolClass::AmmoniumNitrateBased;
    }
    if t.contains("ammonium sulphate") || t.contains("ammonium sulfate")
        || t.contains("sulphate of ammonia") || t.contains("sulfate of ammonia")
        || has_word(&t, "as") || has_word(&t, "sa")
        || t.contains("ammonium phosphate") || has_word(&t, "dap") || has_word(&t, "map")
        || t.contains("anhydrous ammonia")
    {
        return NVolClass::AmmoniumBased;
    }
    if t.contains("nitrate") {
        return NVolClass::NitrateBased;
    }
    NVolClass::Unclassified
}

/// Urea as a straight product (IPCC 2006 Vol 4 Ch 11 Eq 11.13 applies to its mass). UAN
/// solutions are excluded: their urea share is not known from the type.
pub fn is_straight_urea(fertilizer_type: &str) -> bool {
    n_volatilisation_class(fertilizer_type) == NVolClass::Urea
}

/// IPCC 2006 Guidelines Vol 4 Ch 11 Section 11.4.1, Eq 11.13 (unchanged in the 2019
/// Refinement): CO2-C = M_urea x 0.20 t C / t urea (carbon content of CO(NH2)2).
pub const UREA_EF_C_PER_T: f64 = 0.20;
/// IPCC 2006 Vol 4 Ch 11 Section 11.3.1, Eq 11.12: EF 0.12 t C / t limestone (CaCO3) and
/// 0.13 t C / t dolomite (CaMg(CO3)2).
pub const LIMESTONE_EF_C_PER_T: f64 = 0.12;
pub const DOLOMITE_EF_C_PER_T: f64 = 0.13;
pub const CO2_PER_C: f64 = 44.0 / 12.0;

// ----------------------------------------------------------------------------------------
// Rice CH4 (IPCC 2019 Refinement Vol 4 Ch 5 Section 5.5, Eq 5.1-5.3, Tier 1)
//   CH4 = EFc x SFw x SFp x SFo x t x Area   (per season; x crops per year)
// ----------------------------------------------------------------------------------------

/// Table 5.12 (updated), disaggregated case SFw.
pub fn rice_sfw(regime: &str) -> Option<f64> {
    Some(match regime {
        "upland" => 0.0,
        "irrigated_continuously_flooded" => 1.00,
        "irrigated_single_drainage" => 0.71,
        "irrigated_multiple_drainage" => 0.55, // includes AWD (Table 5.12 note b)
        "rainfed_regular" => 0.54,
        "rainfed_drought_prone" => 0.16,
        "deep_water" => 0.06,
        _ => return None,
    })
}

/// Table 5.13 (updated), disaggregated case SFp.
pub fn rice_sfp(status: &str) -> Option<f64> {
    Some(match status {
        "non_flooded_lt_180d" => 1.00,
        "non_flooded_gt_180d" => 0.89,
        "flooded_gt_30d" => 2.41,
        "non_flooded_gt_365d" => 0.59,
        _ => return None,
    })
}

/// Table 5.14 (updated) conversion factors CFOA. ROA is t DRY weight/ha for straw and
/// t FRESH weight/ha for the other amendments (Eq 5.3 definitions).
pub const CFOA_STRAW_SHORT: f64 = 1.00; // straw incorporated < 30 d before cultivation
pub const CFOA_STRAW_LONG: f64 = 0.19;  // straw incorporated > 30 d before cultivation
pub const CFOA_COMPOST: f64 = 0.17;
pub const CFOA_FYM: f64 = 0.21;          // farmyard manure
pub const CFOA_GREEN_MANURE: f64 = 0.45;

/// Eq 5.3: SFo = (1 + sum_i ROA_i x CFOA_i)^0.59.
pub fn rice_sfo(sum_roa_cfoa: f64) -> f64 {
    (1.0 + sum_roa_cfoa.max(0.0)).powf(0.59)
}

/// Rice crop (paddy) by name.
pub fn is_rice(name: &str) -> bool {
    let n = name.to_lowercase();
    n.contains("rice") || n.contains("paddy")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn straight_fertilisers_use_the_lookup() {
        assert_eq!(fertiliser_n("Urea", &None).n_fraction, 0.46);
        assert_eq!(fertiliser_n("Calcium Ammonium Nitrate", &None).n_fraction, 0.27);
        assert_eq!(fertiliser_n("CAN", &None).n_fraction, 0.27);
        assert_eq!(fertiliser_n("Ammonium Sulfate", &None).n_fraction, 0.21);
        assert_eq!(fertiliser_n("Ammonium sulphate", &None).n_fraction, 0.21);
        assert_eq!(fertiliser_n("Diammonium Phosphate (DAP)", &None).n_fraction, 0.18);
        assert_eq!(fertiliser_n("MAP", &None).n_fraction, 0.11);
        assert_eq!(fertiliser_n("Ammonium nitrate", &None).n_fraction, 0.335);
    }

    #[test]
    fn no_n_fertilisers_are_zero_without_warning() {
        for t in ["Single Super Phosphate", "Triple Super Phosphate", "TSP", "SSP",
                  "Muriate of Potash", "MOP", "Bio-fertilizer", "None"] {
            let f = fertiliser_n(t, &None);
            assert_eq!(f.n_fraction, 0.0, "{t}");
            assert!(f.warning.is_none(), "{t}");
        }
    }

    #[test]
    fn unknown_type_is_zero_n_with_warning_never_ten_percent() {
        let f = fertiliser_n("Foliar Fertilizer", &None);
        assert_eq!(f.n_fraction, 0.0);
        assert!(f.warning.as_deref().unwrap().contains("not recognised"));
        let g = fertiliser_n("Mystery blend", &None);
        assert_eq!(g.n_fraction, 0.0);
        assert!(g.warning.is_some());
    }

    #[test]
    fn declared_grade_wins_and_npk_parses() {
        assert_eq!(fertiliser_n("NPK", &Some("20-10-10".into())).n_fraction, 0.20);
        assert_eq!(fertiliser_n("Foliar Fertilizer", &Some("10-5-5".into())).n_fraction, 0.10);
        let npk = fertiliser_n("NPK Compound", &None);
        assert_eq!(npk.n_fraction, 0.15);
        assert!(npk.warning.is_some());
    }

    #[test]
    fn organic_uses_declared_n_or_dataset_default() {
        let o = fertiliser_n("Organic Fertilizer", &Some("2-1-1".into()));
        assert_eq!(o.form, NForm::Organic);
        assert_eq!(o.n_fraction, 0.02);
        let d = fertiliser_n("Organic Fertilizer", &None);
        assert_eq!(d.form, NForm::Organic);
        assert_eq!(d.n_fraction, 0.03);
        assert!(d.warning.is_some());
    }

    #[test]
    fn maize_residue_n_matches_eq_11_6_by_hand() {
        // 3000 kg/ha fresh maize grain on 1 ha, IPCC Table 11.1A 'Maize'.
        let r = residue_n("Maize", 3000.0, 1.0, 0.0, 0.0, 1.0);
        let crop = 3000.0 * 0.87;
        let ag = crop * 1.0;
        let expect = ag * 0.006 + (crop + ag) * 0.22 * 0.007;
        assert!((r.f_cr() - expect).abs() < 1e-9, "{} vs {}", r.f_cr(), expect);
        assert!(!r.params.proxy);
    }

    #[test]
    fn removal_and_burning_reduce_above_ground_n() {
        let full = residue_n("Rice", 4000.0, 1.0, 0.0, 0.0, 1.0);
        let managed = residue_n("Rice", 4000.0, 1.0, 0.5, 0.2, 1.0);
        let expect_above = full.n_above * (1.0 - 0.5 - 0.2 * 0.80);
        assert!((managed.n_above - expect_above).abs() < 1e-9);
        assert_eq!(managed.n_below, full.n_below);
        assert!((managed.dm_burnt - full.ag_dm_per_ha * 0.2 * 0.80).abs() < 1e-9);
    }

    #[test]
    fn legume_and_vegetable_rows() {
        let g = residue_params("Groundnut");
        assert_eq!((g.n_ag, g.r_ag, g.dry), (0.016, 1.0, 0.94));
        let c = residue_params("Cowpea");
        assert_eq!((c.n_ag, c.r_ag, c.rs), (0.008, 2.1, 0.19));
        let t = residue_params("Tomato");
        assert!(t.proxy && t.dry < 0.1);
        let cocoa = residue_params("Cocoa");
        assert!(cocoa.proxy);
        let unknown = residue_params("Dragonfruit");
        assert_eq!((unknown.n_ag, unknown.n_bg, unknown.r_ag, unknown.rs, unknown.dry),
                   (0.008, 0.009, 1.0, 0.22, 0.85));
    }

    #[test]
    fn frac_renew_scales_above_and_below_ground() {
        // IPCC 2019 Eq 11.6: AGR and BGR both carry Frac_Renew.
        let annual = residue_n("Cocoa", 450.0, 1.0, 0.0, 0.0, 1.0);
        let perennial = residue_n("Cocoa", 450.0, 1.0, 0.0, 0.0, 1.0 / 25.0);
        assert!((perennial.n_below - annual.n_below / 25.0).abs() < 1e-12);
        assert!((perennial.n_above - annual.n_above / 25.0).abs() < 1e-12);
    }

    #[test]
    fn volatilisation_classes_follow_annex_11a7() {
        assert_eq!(n_volatilisation_class("Urea"), NVolClass::Urea);
        assert_eq!(n_volatilisation_class("UAN 32"), NVolClass::AmmoniumNitrateBased);
        assert_eq!(n_volatilisation_class("Calcium Ammonium Nitrate"), NVolClass::AmmoniumNitrateBased);
        assert_eq!(n_volatilisation_class("Ammonium Sulphate"), NVolClass::AmmoniumBased);
        assert_eq!(n_volatilisation_class("DAP"), NVolClass::AmmoniumBased);
        assert_eq!(n_volatilisation_class("Calcium nitrate"), NVolClass::NitrateBased);
        assert_eq!(n_volatilisation_class("NPK 15-15-15"), NVolClass::Unclassified);
        assert!(!is_straight_urea("UAN"));
    }

    #[test]
    fn grade_parsing_and_product_from_grade_match_inputs_py() {
        assert_eq!(parse_grade(&Some("23 10 5".into())), Some((23.0, 10.0, 5.0)));
        assert_eq!(parse_grade(&Some("20:10:10".into())), Some((20.0, 10.0, 10.0)));
        assert_eq!(parse_grade(&Some("46".into())), None);
        assert_eq!(parse_grade(&Some("0-0-0".into())), None);
        assert_eq!(parse_grade(&Some("60-60-0".into())), None);
        assert_eq!(n_form_type("White prills", &Some("46-0-0".into())), "urea");
        assert_eq!(n_form_type("Blend X", &Some("18-46-0".into())), "diammonium phosphate");
        assert_eq!(n_form_type("NPK", &Some("46-0-0".into())), "NPK");
        assert_eq!(n_form_type("Foliar feed", &Some("46-0-0".into())), "Foliar feed");
        assert_eq!(fertiliser_n("UAN", &None).n_fraction, 0.30);
        assert!(is_none_fertiliser("Not used") && is_none_fertiliser(" NONE "));
        assert_eq!(fertiliser_n("Guano", &None).form, NForm::Organic);
    }

    #[test]
    fn rice_scaling_factors() {
        assert_eq!(rice_sfw("upland"), Some(0.0));
        assert_eq!(rice_sfw("irrigated_multiple_drainage"), Some(0.55));
        assert_eq!(rice_sfp("flooded_gt_30d"), Some(2.41));
        assert!((rice_sfo(0.0) - 1.0).abs() < 1e-12);
        assert!((rice_sfo(2.0 * CFOA_STRAW_SHORT) - 3f64.powf(0.59)).abs() < 1e-12);
    }
}
