/**
 * Life Cycle Inventory (LCI) Module - ISO 14040/14044 Compliant
 *
 * This module implements proper LCI calculations by computing environmental
 * burdens from actual user inputs (inventory data) rather than using generic
 * category-level factors.
 *
 * LCA Methodology Flow (ISO 14040/14044):
 * 1. Goal & Scope Definition
 * 2. Life Cycle Inventory (LCI) ← THIS MODULE
 *    - Collect input data (fertilizers, fuels, pesticides, etc.)
 *    - Calculate elementary flows (emissions, resource use)
 *    - Apply emission factors
 * 3. Life Cycle Impact Assessment (LCIA)
 *    - Characterization (midpoint impacts)
 *    - Normalization
 *    - Weighting (endpoint impacts)
 * 4. Interpretation
 *
 * References:
 * - IPCC 2019 Refinement to 2006 Guidelines (N2O emissions from N inputs)
 * - IPCC AR6 (GWP values)
 * - Ecoinvent 3.8 database (emission factors)
 * - GREET model (fuel combustion factors)
 */

use crate::models::*;
use crate::production::field::{self, NForm};
use std::collections::HashMap;
use log::{info, warn};

// ======================================================================
// EMISSION FACTORS DATABASE - Based on Scientific Literature
// ======================================================================

/// Emission factors for agricultural inputs and activities
/// All factors are peer-reviewed and cited
pub struct EmissionFactorsDatabase {
    /// N2O emissions from nitrogen fertilizers (kg N2O-N per kg N applied)
    /// Source: IPCC 2019 Refinement, Volume 4, Chapter 11
    pub n2o_from_n_fertilizer: EmissionFactor,

    /// CO2 from diesel combustion (kg CO2 per liter)
    /// Source: GREET 2021 model, EPA
    pub co2_from_diesel: EmissionFactor,

    /// CO2 from petrol/gasoline combustion (kg CO2 per liter)
    /// Source: GREET 2021 model, EPA
    pub co2_from_petrol: EmissionFactor,

    /// CO2 from grid electricity - Ghana (kg CO2 per kWh)
    /// Source: Ghana Energy Commission 2021
    pub co2_from_electricity_ghana: EmissionFactor,

    /// CO2 from grid electricity - Nigeria (kg CO2 per kWh)
    /// Source: Nigerian Electricity Regulatory Commission
    pub co2_from_electricity_nigeria: EmissionFactor,

    /// CO2 from urea production and transport (kg CO2 per kg urea)
    /// Source: Ecoinvent 3.8
    pub co2_from_urea_production: EmissionFactor,

    /// CO2 from NPK production and transport (kg CO2 per kg NPK)
    /// Source: Ecoinvent 3.8
    pub co2_from_npk_production: EmissionFactor,

    /// Pesticide production impacts (kg CO2-eq per kg active ingredient)
    /// Source: Ecoinvent 3.8, averaged for common pesticides
    pub pesticide_production_impact: EmissionFactor,

    /// Water consumption factor for irrigation (no emission, but resource use)
    pub water_use_factor: f64, // Typically 1:1 for direct use

    /// Indirect N2O parameters for synthetic fertiliser N (IPCC 2019 Refinement, Vol 4,
    /// Ch 11, Table 11.3). Volatilisation and leaching are SEPARATE pathways, each with its
    /// own loss fraction and emission factor; they must not be conflated.
    /// FracGASF: fraction of applied synthetic N volatilised as NH3 and NOx.
    pub frac_gasf: f64,
    /// FracLEACH-(H): fraction of applied N lost to leaching/runoff in wet climates.
    pub frac_leach: f64,
    /// EF4: kg N2O-N per kg N volatilised (then redeposited).
    pub ef4_volatilisation: f64,
    /// EF5: kg N2O-N per kg N lost to leaching/runoff.
    pub ef5_leaching: f64,
}

#[derive(Debug, Clone)]
pub struct EmissionFactor {
    pub value: f64,
    pub unit: String,
    pub source: String,
    pub year: i32,
    pub uncertainty: f64, // ±% uncertainty
    pub geographical_validity: String,
}

impl Default for EmissionFactorsDatabase {
    fn default() -> Self {
        Self {
            // IPCC 2019: Default N2O emission factor for direct emissions
            // EF1 = 0.01 kg N2O-N per kg N applied (1% of applied N)
            n2o_from_n_fertilizer: EmissionFactor {
                value: 0.01, // 1% of applied N converted to N2O-N
                unit: "kg N2O-N per kg N".to_string(),
                source: "IPCC 2019 Refinement, Vol 4, Ch 11, Table 11.1".to_string(),
                year: 2019,
                uncertainty: 70.0, // ±70% uncertainty range
                geographical_validity: "Global default, tropical conditions".to_string(),
            },

            // Diesel combustion: 2.68 kg CO2 per liter
            // Source: EPA, GREET model
            co2_from_diesel: EmissionFactor {
                value: 2.68,
                unit: "kg CO2 per liter".to_string(),
                source: "GREET 2021 Model, EPA".to_string(),
                year: 2021,
                uncertainty: 5.0, // Well-established factor
                geographical_validity: "Global".to_string(),
            },

            // Petrol/gasoline combustion: 2.31 kg CO2 per liter
            // Source: EPA, GREET model
            co2_from_petrol: EmissionFactor {
                value: 2.31,
                unit: "kg CO2 per liter".to_string(),
                source: "GREET 2021 Model, EPA".to_string(),
                year: 2021,
                uncertainty: 5.0,
                geographical_validity: "Global".to_string(),
            },

            // Ghana electricity grid: 0.45 kg CO2 per kWh
            // Mix of thermal, hydro, and imports
            co2_from_electricity_ghana: EmissionFactor {
                value: 0.45,
                unit: "kg CO2 per kWh".to_string(),
                source: "Ghana Energy Commission, 2021 Grid Factor".to_string(),
                year: 2021,
                uncertainty: 20.0, // Grid mix varies
                geographical_validity: "Ghana national grid".to_string(),
            },

            // Nigeria electricity grid: 0.58 kg CO2 per kWh
            // Heavily thermal-based (gas, coal)
            co2_from_electricity_nigeria: EmissionFactor {
                value: 0.58,
                unit: "kg CO2 per kWh".to_string(),
                source: "Nigerian Electricity Regulatory Commission, 2020".to_string(),
                year: 2020,
                uncertainty: 25.0,
                geographical_validity: "Nigeria national grid".to_string(),
            },

            // Legacy screening value for urea production (category Upstream: dropped by the
            // served path, where the supply-chain solver owns production). Field CO2 from
            // urea hydrolysis is a separate flow (IPCC Eq 11.13, "Carbon dioxide (CO2) -
            // urea hydrolysis") that the legacy GWP below does not sum, so it is not
            // counted twice there.
            co2_from_urea_production: EmissionFactor {
                value: 1.2,
                unit: "kg CO2 per kg urea".to_string(),
                source: "Ecoinvent 3.8, Urea production GLO".to_string(),
                year: 2021,
                uncertainty: 15.0,
                geographical_validity: "Global average".to_string(),
            },

            // NPK compound fertilizer production: 1.5 kg CO2 per kg NPK
            co2_from_npk_production: EmissionFactor {
                value: 1.5,
                unit: "kg CO2 per kg NPK".to_string(),
                source: "Ecoinvent 3.8, NPK fertilizer production".to_string(),
                year: 2021,
                uncertainty: 20.0,
                geographical_validity: "Global average".to_string(),
            },

            // Pesticide production: 10 kg CO2-eq per kg active ingredient
            // High energy intensity for chemical synthesis
            pesticide_production_impact: EmissionFactor {
                value: 10.0,
                unit: "kg CO2-eq per kg a.i.".to_string(),
                source: "Ecoinvent 3.8, Pesticide production average".to_string(),
                year: 2021,
                uncertainty: 50.0, // High variation between pesticide types
                geographical_validity: "Global average".to_string(),
            },

            // Water use: Direct measurement
            water_use_factor: 1.0,

            // IPCC 2019 Refinement, Vol 4, Ch 11, Table 11.3 (synthetic fertiliser N).
            frac_gasf: 0.11,          // fraction of applied synthetic N volatilised
            frac_leach: 0.24,         // fraction of applied N leached/run off (wet climate)
            ef4_volatilisation: 0.010, // kg N2O-N per kg N volatilised
            ef5_leaching: 0.011,      // kg N2O-N per kg N leached
        }
    }
}

// ======================================================================
// LIFE CYCLE INVENTORY CALCULATOR
// ======================================================================

pub struct LCICalculator {
    emission_factors: EmissionFactorsDatabase,
    inventory: HashMap<String, InventoryItem>,
    /// IPCC 2019 soil-N parameters for this assessment (region/climate; defaults = IPCC
    /// aggregated Tier 1 values).
    params: FieldParameters,
    /// Validation warnings raised while building the inventory.
    warnings: Vec<String>,
    /// Modelling disclosures (assumptions, inferred values) raised while building it.
    notes: Vec<String>,
    /// Water management of the assessment, for the rice water-regime inference.
    water: Option<WaterManagement>,
}

/// IPCC 2019 Refinement Vol 4 Ch 11 Table 11.1 (updated): EF1FR for flooded rice fields,
/// aggregated default 0.004 kg N2O-N/kg N (applies to all N inputs on flooded rice; "The EF1
/// should be used for upland rice").
pub const EF1_FLOODED_RICE: f64 = 0.004;

const N2O_PER_N2O_N: f64 = 44.0 / 28.0;
const NO3_PER_N: f64 = 62.0 / 14.0;
const NH3_PER_N: f64 = 17.0 / 14.0;

/// ecoinvent field-emission model: NOx = 0.21 x N2O (kg NOx per kg N2O), applied to the
/// total soil N2O (direct + indirect). Nemecek T. & Schnetzer J. (2011) Methods of
/// assessment of direct field emissions for LCIs of agricultural production systems,
/// Data v3.0, Agroscope Reckenholz-Taenikon ART, Zurich, section on nitrogen oxides.
/// FracGASF/FracGASM (IPCC) already include NOx-N, so NH3-N computed as N x FracGAS
/// overlaps this NOx-N by < 2% of the volatilised N; the overlap is not netted out.
pub const NOX_PER_N2O: f64 = 0.21;

/// Soil N2O flows that NOX_PER_N2O applies to (not residue burning, which has its own NOx).
const SOIL_N2O_SUBSTANCES: [&str; 4] = [
    "Dinitrogen monoxide (N2O)",
    "Dinitrogen monoxide (N2O) - indirect",
    "Dinitrogen monoxide (N2O) - crop residues",
    "Dinitrogen monoxide (N2O) - organic fertiliser",
];

/// What an inventory flow represents. The Python engine keeps `Field` flows only; inventory
/// items are merged by (substance, compartment, category), never across categories, and the
/// category, not the free-text source, decides what is kept.
#[derive(Debug, Clone, Copy, PartialEq)]
pub enum FlowCategory {
    /// Direct on-farm field emission or resource use.
    Field,
    /// Production of a purchased input (owned by the supply-chain solver in Python).
    Upstream,
    /// On-farm fuel / electricity combustion (owned by the supply-chain solver in Python).
    Energy,
    /// Pre-characterised CO2-eq (legacy).
    Aggregated,
}

impl FlowCategory {
    pub fn as_str(&self) -> &'static str {
        match self {
            FlowCategory::Field => "field",
            FlowCategory::Upstream => "upstream",
            FlowCategory::Energy => "energy",
            FlowCategory::Aggregated => "aggregated",
        }
    }
}

/// Foods a row (fertiliser / lime / compost) applies to: those with area, restricted to
/// `crop_ids` when given (CONTRACT §1: [] = all crops).
fn target_foods<'a>(foods: &'a [FoodItem], crop_ids: &[String]) -> Vec<&'a FoodItem> {
    foods.iter()
        .filter(|f| f.area_allocated.unwrap_or(0.0) > 0.0)
        .filter(|f| crop_ids.is_empty() || crop_ids.iter().any(|id| id.trim() == f.id))
        .collect()
}

/// Rice water regime (CONTRACT §1 vocabulary) and, when inferred, how. Order: declared
/// value; name containing "upland"; production system Rainfed; irrigation system
/// (flood/furrow -> continuously flooded, or multiple drainage when alternate wetting and
/// drying is declared; sprinkler/drip -> upland, the field is not flooded; "None
/// (Rainfed)" -> regular rainfed); production system Irrigated; otherwise the IPCC 2019
/// Table 5.11 baseline (continuously flooded).
pub fn rice_water_regime(food: &FoodItem, water: Option<&WaterManagement>) -> (String, Option<String>) {
    if let Some(r) = food.water_regime.as_deref().map(|s| s.trim().to_lowercase()) {
        if field::rice_sfw(&r).is_some() {
            return (r, None);
        }
    }
    let infer = |r: &str, why: String| (r.to_string(), Some(why));
    if food.name.to_lowercase().contains("upland") {
        return infer("upland", "crop name contains 'upland'".to_string());
    }
    if matches!(food.production_system, Some(ProductionSystem::Rainfed)) {
        return infer("rainfed_regular", "production system Rainfed".to_string());
    }
    let irr = water.and_then(|w| w.irrigation_system.clone()).unwrap_or_default();
    let irr_l = irr.to_lowercase();
    let awd = water.map(|w| w.water_conservation_practices.iter().any(|p| {
        let p = p.to_lowercase();
        p.contains("alternate wetting") || p.contains("awd") || p.contains("intermittent")
    })).unwrap_or(false);
    let flooded = |why: String| if awd {
        infer("irrigated_multiple_drainage",
              format!("{why} with alternate wetting and drying declared (Table 5.12 note b: AWD is multiple drainage)"))
    } else {
        infer("irrigated_continuously_flooded", why)
    };
    if irr_l.contains("flood") || irr_l.contains("furrow") {
        return flooded(format!("irrigation system '{irr}'"));
    }
    if irr_l.contains("sprinkler") || irr_l.contains("drip") {
        return infer("upland", format!("irrigation system '{irr}' does not flood the field"));
    }
    if irr_l.contains("none") || irr_l.contains("rainfed") {
        return infer("rainfed_regular", format!("irrigation system '{irr}'"));
    }
    if matches!(food.production_system, Some(ProductionSystem::Irrigated)) {
        return flooded("production system Irrigated".to_string());
    }
    let why = if irr.is_empty() {
        "no water regime, production system or irrigation system declared".to_string()
    } else {
        format!("irrigation system '{irr}' has no IPCC water-regime equivalent")
    };
    infer("irrigated_continuously_flooded",
          format!("{why}: IPCC 2019 Table 5.11 baseline (continuously flooded) assumed"))
}

#[derive(Debug, Clone)]
pub struct InventoryItem {
    pub substance: String,
    pub quantity: f64,
    pub unit: String,
    pub compartment: EnvironmentalCompartment, // Air, Water, Soil
    pub source: String, // Which input caused this emission
    pub category: FlowCategory,
}

#[derive(Debug, Clone, PartialEq)]
pub enum EnvironmentalCompartment {
    Air,
    Water,
    Soil,
    Resource, // For resource extraction/use
}

impl LCICalculator {
    pub fn new() -> Self {
        Self {
            emission_factors: EmissionFactorsDatabase::default(),
            inventory: HashMap::new(),
            params: FieldParameters::default(),
            warnings: Vec::new(),
            notes: Vec::new(),
            water: None,
        }
    }

    /// Validation warnings from the last `calculate_inventory` call.
    pub fn warnings(&self) -> &[String] {
        &self.warnings
    }

    /// Modelling disclosures from the last `calculate_inventory` call.
    pub fn notes(&self) -> &[String] {
        &self.notes
    }

    fn warn_once(&mut self, msg: String) {
        if !self.warnings.contains(&msg) {
            self.warnings.push(msg);
        }
    }

    fn note_once(&mut self, msg: String) {
        if !self.notes.contains(&msg) {
            self.notes.push(msg);
        }
    }

    /// Flooded rice (EF1FR for N2O, IPCC 2019 Table 11.1): rice whose water regime (the
    /// same one the CH4 model uses) is anything but upland.
    fn is_flooded_rice(&self, food: &FoodItem) -> bool {
        field::is_rice(&food.name) && rice_water_regime(food, self.water.as_ref()).0 != "upland"
    }

    /// Calculate complete life cycle inventory from user inputs
    pub fn calculate_inventory(
        &mut self,
        assessment: &Assessment,
    ) -> Result<HashMap<String, InventoryItem>, Box<dyn std::error::Error>> {

        info!("Starting LCI calculation for assessment {}", assessment.id);

        // Clear previous inventory
        self.inventory.clear();
        self.warnings.clear();
        self.notes.clear();
        self.params = assessment.field_parameters.clone().unwrap_or_default();
        self.water = assessment.management_practices.as_ref().map(|m| m.water_management.clone());

        // 1. Calculate emissions from fertilizers (N2O, NH3, NO3, urea CO2, production CO2)
        if let Some(ref mgmt) = assessment.management_practices {
            self.calculate_fertilizer_emissions(&mgmt.fertilization, &assessment.foods)?;
            // 1b. Liming CO2 (IPCC 2006 Vol 4 Ch 11 Eq 11.12)
            self.calculate_lime_emissions(&mgmt.soil_management, &assessment.foods)?;
        }

        // 2. Calculate emissions from fuel consumption (CO2)
        // TODO: This requires EquipmentEnergy data from frontend
        // For now, we'll use a simplified approach based on farm size
        self.calculate_energy_emissions(assessment)?;

        // 3. Calculate emissions from pesticide production
        if let Some(ref mgmt) = assessment.management_practices {
            self.calculate_pesticide_emissions(&mgmt.pest_management)?;
        }

        // 4. Calculate water consumption
        if let Some(ref mgmt) = assessment.management_practices {
            self.calculate_water_consumption(&mgmt.water_management, &assessment.foods)?;
        }

        // 5. Calculate crop-specific emissions (CH4 from rice, IPCC 2019 Eq 5.1-5.3)
        self.calculate_crop_specific_emissions(assessment)?;

        // 6. Calculate land use
        self.calculate_land_use(&assessment.foods)?;

        // 7. N2O from crop residues returned to soil (IPCC 2019 Eq 11.6, F_CR). Runs whether
        //    or not fertiliser is used: residue N is an N input in its own right.
        self.calculate_crop_residue_emissions(&assessment.foods)?;

        // 8. Soil NOx from the soil N2O (ecoinvent NOx = 0.21 x N2O). Last: needs all N2O.
        self.calculate_soil_nox();

        info!("LCI calculation completed. {} inventory items generated", self.inventory.len());

        Ok(self.inventory.clone())
    }

    /// Calculate N2O and CO2 emissions from fertilizer use
    /// Following IPCC 2019 methodology
    fn calculate_fertilizer_emissions(
        &mut self,
        fertilization: &FertilizationPractices,
        foods: &[FoodItem],
    ) -> Result<(), Box<dyn std::error::Error>> {

        if !fertilization.uses_fertilizers {
            return Ok(());
        }
        let p = self.params.clone();

        for app in &fertilization.fertilizer_applications {
            // CONTRACT §1: type "None", rate 0 or 0 applications -> no burden at all.
            let type_l = app.fertilizer_type.trim().to_lowercase();
            if field::is_none_fertiliser(&type_l) || !(app.application_rate > 0.0)
                || app.applications_per_season == 0
            {
                continue;
            }
            let targets = target_foods(foods, &app.crop_ids);
            if targets.is_empty() {
                if app.crop_ids.is_empty() {
                    warn!("No area allocated for crops, cannot calculate fertilizer emissions");
                } else {
                    info!("fertiliser '{}' is assigned to crop id(s) {:?} absent from this assessment",
                          app.fertilizer_type, app.crop_ids);
                }
                continue;
            }

            // Explicit N lookup (declared grade first). Unknown types get ZERO N and a
            // validation warning instead of the former silent 10%.
            let fert = field::fertiliser_n(&app.fertilizer_type, &app.npk_ratio);
            if let Some(w) = fert.warning.clone() {
                self.warn_once(w);
            }
            let organic = fert.form == NForm::Organic;
            // Product deciding the N form (free-text name + straight grade, e.g. 46-0-0 = urea).
            let n_form = field::n_form_type(&app.fertilizer_type, &app.npk_ratio);

            // application_rate = kg PRODUCT / ha / application (CONTRACT §1): annual product
            // = rate x applications per season x crops per year x area, per target crop.
            // Flooded rice takes EF1FR for all N inputs (IPCC 2019 Table 11.1).
            let apps = app.applications_per_season as f64;
            let (mut product_kg, mut n_applied, mut n2o_n_direct, mut area_ha) = (0.0, 0.0, 0.0, 0.0);
            for f in &targets {
                let area = f.area_allocated.unwrap_or(0.0);
                let product = app.application_rate * apps * f.crops_per_year() * area;
                let n = product * fert.n_fraction;
                let ef1 = if self.is_flooded_rice(f) { EF1_FLOODED_RICE }
                          else if organic { p.ef1_other } else { p.ef1_synthetic };
                product_kg += product;
                n_applied += n;
                n2o_n_direct += n * ef1;
                area_ha += area;
            }
            info!("Fertilizer {}: {:.1} kg product, {:.1} kg N/year on {:.2} ha",
                  app.fertilizer_type, product_kg, n_applied, area_ha);

            if let Some(m) = app.application_method.as_deref() {
                let m = m.trim().to_lowercase();
                if matches!(m.as_str(), "incorporated" | "band_placement" | "side_dressing") {
                    self.note_once(format!(
                        "fertiliser '{}' application method '{}' recorded but not modelled: \
                         NH3 uses the IPCC 2019 Tier 1 FracGAS default (no cited Tier 1 \
                         reduction factor for incorporation or placement of mineral fertiliser)",
                        app.fertilizer_type, m));
                }
            }

            // Volatilisation (NH3 + NOx) fraction: FracGASM for organic N; FracGASF by
            // fertiliser N form for synthetic N (IPCC 2019 Vol 4 Ch 11 Table 11.3).
            let (frac_gas, frac_label) = if organic {
                (p.frac_gasm, "FracGASM (organic N)".to_string())
            } else {
                match field::n_volatilisation_class(&n_form) {
                    field::NVolClass::Urea => (p.frac_gasf_urea, "FracGASF urea".to_string()),
                    field::NVolClass::AmmoniumBased => (p.frac_gasf_ammonium, "FracGASF ammonium-based".to_string()),
                    field::NVolClass::NitrateBased => (p.frac_gasf_nitrate, "FracGASF nitrate-based".to_string()),
                    field::NVolClass::AmmoniumNitrateBased => (p.frac_gasf_ammonium_nitrate, "FracGASF ammonium-nitrate-based".to_string()),
                    field::NVolClass::Unclassified => (p.frac_gasf, "FracGASF aggregated (N form not identified)".to_string()),
                }
            };
            // The SAME volatilised N drives NH3 and the EF4 indirect N2O (Eq 11.9).
            let n_volatilised = n_applied * frac_gas;
            let n_leached = n_applied * p.frac_leach;
            let n2o_n_indirect = n_volatilised * p.ef4 + n_leached * p.ef5;

            if n_applied > 0.0 {
                if organic {
                    self.add_inventory_item(InventoryItem {
                        substance: "Dinitrogen monoxide (N2O) - organic fertiliser".to_string(),
                        quantity: (n2o_n_direct + n2o_n_indirect) * N2O_PER_N2O_N,
                        unit: "kg".to_string(),
                        compartment: EnvironmentalCompartment::Air,
                        source: format!("Direct and indirect N2O from {} ({:.1} kg organic N; {})",
                                        app.fertilizer_type, n_applied, fert.source),
                        category: FlowCategory::Field,
                    });
                } else {
                    // IPCC 2019 Eq 11.1: direct N2O-N = N x EF1; N2O = N2O-N x 44/28.
                    self.add_inventory_item(InventoryItem {
                        substance: "Dinitrogen monoxide (N2O)".to_string(),
                        quantity: n2o_n_direct * N2O_PER_N2O_N,
                        unit: "kg".to_string(),
                        compartment: EnvironmentalCompartment::Air,
                        source: format!("Direct N2O emissions from {} application", app.fertilizer_type),
                        category: FlowCategory::Field,
                    });
                    // Indirect N2O (IPCC 2019 Eq 11.9 & 11.10): volatilisation (EF4) and
                    // leaching (EF5) are separate pathways with their own loss fractions.
                    self.add_inventory_item(InventoryItem {
                        substance: "Dinitrogen monoxide (N2O) - indirect".to_string(),
                        quantity: n2o_n_indirect * N2O_PER_N2O_N,
                        unit: "kg".to_string(),
                        compartment: EnvironmentalCompartment::Air,
                        source: format!("Indirect N2O emissions from {} (volatilisation + leaching)", app.fertilizer_type),
                        category: FlowCategory::Field,
                    });
                }
                self.add_inventory_item(InventoryItem {
                    substance: "Ammonia (NH3)".to_string(),
                    quantity: n_volatilised * NH3_PER_N,
                    unit: "kg".to_string(),
                    compartment: EnvironmentalCompartment::Air,
                    source: format!("NH3 volatilisation from {} ({:.1} kg N x {} {:.2}; IPCC 2019 Vol 4 Ch 11 Table 11.3)",
                                    app.fertilizer_type, n_applied, frac_label, frac_gas),
                    category: FlowCategory::Field,
                });
                // Nitrate to water: ONLY the leached fraction (the volatilised N leaves to air).
                self.add_inventory_item(InventoryItem {
                    substance: "Nitrate (NO3-)".to_string(),
                    quantity: n_leached * NO3_PER_N,
                    unit: "kg".to_string(),
                    compartment: EnvironmentalCompartment::Water,
                    source: format!("Nitrate leaching from {} application", app.fertilizer_type),
                    category: FlowCategory::Field,
                });
            }
            if organic {
                continue;
            }

            // Urea hydrolysis CO2 at the field: IPCC 2006 Vol 4 Ch 11 Eq 11.13,
            // CO2 = M_urea x 0.20 t C/t x 44/12. Fossil carbon fixed at the urea plant.
            if field::is_straight_urea(&n_form) && product_kg > 0.0 {
                self.add_inventory_item(InventoryItem {
                    substance: "Carbon dioxide (CO2) - urea hydrolysis".to_string(),
                    quantity: product_kg * field::UREA_EF_C_PER_T * field::CO2_PER_C,
                    unit: "kg".to_string(),
                    compartment: EnvironmentalCompartment::Air,
                    source: format!("Urea hydrolysis CO2 from {:.1} kg {} (IPCC 2006 Vol 4 Ch 11 Eq 11.13, 0.20 t C/t urea)",
                                    product_kg, app.fertilizer_type),
                    category: FlowCategory::Field,
                });
            } else if type_l.contains("urea") || type_l.split(|c: char| !c.is_ascii_alphanumeric()).any(|w| w == "uan") {
                self.note_once(format!(
                    "'{}' is a urea-containing solution: its urea share is unknown, so IPCC Eq 11.13 \
                     urea CO2 is not booked", app.fertilizer_type));
            }

            // CO2 from fertilizer production (legacy screening factors; Upstream, dropped by
            // the served path, which takes production from the supply-chain solver).
            let production_co2 = match app.fertilizer_type.as_str() {
                "Urea" => product_kg * self.emission_factors.co2_from_urea_production.value,
                "NPK Compound" | "NPK" => product_kg * self.emission_factors.co2_from_npk_production.value,
                _ => product_kg * 1.0, // Generic factor
            };

            self.add_inventory_item(InventoryItem {
                substance: "Carbon dioxide (CO2)".to_string(),
                quantity: production_co2,
                unit: "kg".to_string(),
                compartment: EnvironmentalCompartment::Air,
                source: format!("Production and transport of {}", app.fertilizer_type),
                category: FlowCategory::Upstream,
            });

            // Mineral depletion from fertilizer production
            // NPK requires phosphate rock (P) and potash (K) mining
            // Urea requires natural gas (but that's fossil depletion, not mineral)
            let total_fertilizer_kg = product_kg;

            match app.fertilizer_type.as_str() {
                "NPK Compound" | "NPK" => {
                    // Extract P and K content from NPK ratio (e.g., "15-15-15")
                    if let Some(ref npk_ratio) = app.npk_ratio {
                        let parts: Vec<&str> = npk_ratio.split('-').collect();
                        if parts.len() == 3 {
                            // Phosphate (P2O5) content - converted to Fe-eq
                            // 1 kg P2O5 ≈ 0.3 kg Fe-eq (phosphate rock mining)
                            if let Ok(p_percent) = parts[1].parse::<f64>() {
                                let p2o5_kg = total_fertilizer_kg * (p_percent / 100.0);
                                let phosphate_depletion = p2o5_kg * 0.3;

                                self.add_inventory_item(InventoryItem {
                                    substance: "Phosphate rock".to_string(),
                                    quantity: phosphate_depletion,
                                    unit: "kg Fe-eq".to_string(),
                                    compartment: EnvironmentalCompartment::Resource,
                                    source: format!("Phosphate mining for {} production", app.fertilizer_type),
                                    category: FlowCategory::Upstream,
                                });
                            }

                            // Potash (K2O) content - converted to Fe-eq
                            // 1 kg K2O ≈ 0.2 kg Fe-eq (potash mining)
                            if let Ok(k_percent) = parts[2].parse::<f64>() {
                                let k2o_kg = total_fertilizer_kg * (k_percent / 100.0);
                                let potash_depletion = k2o_kg * 0.2;

                                self.add_inventory_item(InventoryItem {
                                    substance: "Potash".to_string(),
                                    quantity: potash_depletion,
                                    unit: "kg Fe-eq".to_string(),
                                    compartment: EnvironmentalCompartment::Resource,
                                    source: format!("Potash mining for {} production", app.fertilizer_type),
                                    category: FlowCategory::Upstream,
                                });
                            }
                        }
                    }
                }
                _ => {
                    // Other fertilizers have minimal mineral depletion
                    // (Urea is from natural gas, organic fertilizers don't deplete minerals)
                }
            }
        }

        Ok(())
    }

    /// Liming CO2, IPCC 2006 Guidelines Vol 4 Ch 11 Section 11.3.1, Eq 11.12 (unchanged in
    /// the 2019 Refinement): CO2-C = M_limestone x 0.12 + M_dolomite x 0.13 (t C / t);
    /// x 44/12. All carbonate C is emitted as CO2 (mineral, i.e. fossil carbon). Rates are
    /// per year, so crops_per_year does not apply.
    fn calculate_lime_emissions(
        &mut self,
        soil: &SoilManagement,
        foods: &[FoodItem],
    ) -> Result<(), Box<dyn std::error::Error>> {
        for lime in &soil.lime_applications {
            if !(lime.rate_t_per_ha_per_year > 0.0) {
                continue;
            }
            let m = lime.material.trim().to_lowercase();
            let (ef, label) = if m.contains("dolomit") {
                (field::DOLOMITE_EF_C_PER_T, "dolomite, 0.13 t C/t")
            } else if m.contains("limestone") || m.contains("calcium carbonate") || m.contains("caco3") {
                (field::LIMESTONE_EF_C_PER_T, "limestone, 0.12 t C/t")
            } else {
                self.warn_once(format!(
                    "lime material '{}' is not limestone or dolomite: no IPCC Eq 11.12 CO2 booked",
                    lime.material));
                continue;
            };
            let area: f64 = target_foods(foods, &lime.crop_ids).iter()
                .map(|f| f.area_allocated.unwrap_or(0.0)).sum();
            if area <= 0.0 {
                continue;
            }
            let mass_t = lime.rate_t_per_ha_per_year * area;
            self.add_inventory_item(InventoryItem {
                substance: "Carbon dioxide (CO2) - liming".to_string(),
                quantity: mass_t * 1000.0 * ef * field::CO2_PER_C,
                unit: "kg".to_string(),
                compartment: EnvironmentalCompartment::Air,
                source: format!("Liming CO2 from {:.2} t {} ({}; IPCC 2006 Vol 4 Ch 11 Eq 11.12)",
                                mass_t, lime.material, label),
                category: FlowCategory::Field,
            });
        }
        Ok(())
    }

    /// Soil NOx = 0.21 x soil N2O (NOX_PER_N2O, ecoinvent / Nemecek & Schnetzer 2011).
    fn calculate_soil_nox(&mut self) {
        let n2o: f64 = self.inventory.values()
            .filter(|i| i.category == FlowCategory::Field
                    && SOIL_N2O_SUBSTANCES.contains(&i.substance.as_str()))
            .map(|i| i.quantity)
            .sum();
        if n2o > 0.0 {
            self.add_inventory_item(InventoryItem {
                substance: "Nitrogen oxides (NOx)".to_string(),
                quantity: n2o * NOX_PER_N2O,
                unit: "kg".to_string(),
                compartment: EnvironmentalCompartment::Air,
                source: format!("Soil NOx = 0.21 x {:.3} kg soil N2O (Nemecek & Schnetzer 2011, ecoinvent v3 field-emission model)", n2o),
                category: FlowCategory::Field,
            });
        }
    }

    /// Calculate CO2 emissions from energy use
    fn calculate_energy_emissions(
        &mut self,
        assessment: &Assessment,
    ) -> Result<(), Box<dyn std::error::Error>> {

        // Check if we have actual equipment/energy data
        if let Some(ref equipment_energy) = assessment.equipment_energy {
            info!("🔥 Using actual equipment and energy consumption data");
            info!("🔥 Fuel consumption items: {}", equipment_energy.fuel_consumption.len());

            // Calculate fuel consumption from actual data
            for fuel in &equipment_energy.fuel_consumption {
                info!("🔥 Processing fuel: {} - {} L/month", fuel.fuel_type, fuel.monthly_consumption);
                let annual_consumption_l = fuel.monthly_consumption * 12.0;

                let emission_factor = match fuel.fuel_type.as_str() {
                    "Diesel" => self.emission_factors.co2_from_diesel.value,
                    "Petrol" | "Petrol/Gasoline" | "Gasoline" => self.emission_factors.co2_from_petrol.value,
                    _ => 2.5, // Conservative default
                };

                let co2_from_fuel = annual_consumption_l * emission_factor;

                self.add_inventory_item(InventoryItem {
                    substance: "Carbon dioxide (CO2)".to_string(),
                    quantity: co2_from_fuel,
                    unit: "kg".to_string(),
                    compartment: EnvironmentalCompartment::Air,
                    source: format!("{} consumption: {} L/month ({:.1} L/year)",
                                   fuel.fuel_type, fuel.monthly_consumption, annual_consumption_l),
                    category: FlowCategory::Energy,
                });
            }

            // Calculate electricity emissions from actual data
            for energy in &equipment_energy.energy_sources {
                if energy.energy_type.contains("Electricity") || energy.energy_type.contains("Grid") {
                    let annual_consumption_kwh = energy.monthly_consumption * 12.0;

                    let electricity_ef = match assessment.country {
                        Country::Ghana => self.emission_factors.co2_from_electricity_ghana.value,
                        Country::Nigeria => self.emission_factors.co2_from_electricity_nigeria.value,
                        _ => 0.50, // Global average
                    };

                    let co2_from_electricity = annual_consumption_kwh * electricity_ef;

                    self.add_inventory_item(InventoryItem {
                        substance: "Carbon dioxide (CO2)".to_string(),
                        quantity: co2_from_electricity,
                        unit: "kg".to_string(),
                        compartment: EnvironmentalCompartment::Air,
                        source: format!("{} consumption: {} kWh/month ({:.1} kWh/year) for {}",
                                       energy.energy_type, energy.monthly_consumption,
                                       annual_consumption_kwh, energy.primary_use),
                        category: FlowCategory::Energy,
                    });
                }
            }

            info!("Energy emissions calculated from actual user data");
            return Ok(());
        }

        // No equipment_energy object: do NOT invent flat 80 L diesel/ha + 200 kWh/ha.
        // Provenanced Ghana activity defaults are applied in the Python supply-chain path
        // (engine/activity_defaults.py) so estimates go through ecoinvent matching + grid
        // calibration. Leaving zeros here avoids double-count and rainfed/manual overstatement.
        warn!(
            "No equipment/energy data on assessment; skipping Rust energy fallback \
             (Python activity defaults own screening estimates when applicable)."
        );

        Ok(())
    }

    /// Calculate emissions from pesticide production
    fn calculate_pesticide_emissions(
        &mut self,
        pest_management: &PestManagement,
    ) -> Result<(), Box<dyn std::error::Error>> {

        for pesticide in &pest_management.pesticides_used {
            // Calculate total active ingredient applied
            // application_rate is typically in kg or L per ha
            // We need to estimate total area treated

            // For now, assume pesticide is applied to all crop area
            // TODO: Get actual treated area from user input
            let total_ai_kg = pesticide.application_rate * pesticide.applications_per_season as f64;

            let production_impact = total_ai_kg * self.emission_factors.pesticide_production_impact.value;

            self.add_inventory_item(InventoryItem {
                substance: "Carbon dioxide (CO2) equivalent".to_string(),
                quantity: production_impact,
                unit: "kg CO2-eq".to_string(),
                compartment: EnvironmentalCompartment::Air,
                source: format!("Production of {} pesticide ({})",
                               pesticide.pesticide_type, pesticide.active_ingredient),
                category: FlowCategory::Aggregated,
            });
        }

        Ok(())
    }

    /// Calculate water consumption
    fn calculate_water_consumption(
        &mut self,
        water_management: &WaterManagement,
        foods: &[FoodItem],
    ) -> Result<(), Box<dyn std::error::Error>> {

        // Get total area
        let total_area_ha: f64 = foods.iter()
            .filter_map(|f| f.area_allocated)
            .sum();

        // Estimate irrigation water use based on system type
        let water_use_m3_per_ha = match water_management.irrigation_system.as_deref() {
            Some("Drip irrigation") | Some("Drip Irrigation") => 3000.0, // Efficient
            Some("Sprinkler") | Some("Sprinkler System") => 5000.0, // Moderate
            Some("Flood irrigation") | Some("Furrow irrigation") => 8000.0, // Inefficient
            None | Some("None (Rainfed)") => 0.0, // Rainfed
            _ => 4000.0, // Default moderate use
        };

        let total_water_m3 = water_use_m3_per_ha * total_area_ha;

        if total_water_m3 > 0.0 {
            self.add_inventory_item(InventoryItem {
                substance: "Water".to_string(),
                quantity: total_water_m3,
                unit: "m3".to_string(),
                compartment: EnvironmentalCompartment::Resource,
                source: format!("Irrigation water ({})",
                               water_management.irrigation_system.as_deref().unwrap_or("Unknown")),
                category: FlowCategory::Field,
            });
        }

        Ok(())
    }

    /// Rice CH4, IPCC 2019 Refinement Vol 4 Ch 5 Section 5.5, Tier 1:
    ///   Eq 5.1  CH4 = EF_i x t x A                 (per season; x crops per year)
    ///   Eq 5.2  EF_i = EFc x SFw x SFp x SFo       (SFs,r = 1 at Tier 1)
    ///   Eq 5.3  SFo = (1 + sum ROA_i x CFOA_i)^0.59
    /// EFc Table 5.11, SFw Table 5.12, SFp Table 5.13, CFOA Table 5.14 (field.rs). Each
    /// season is assumed to have the same water regime and amendments.
    fn calculate_crop_specific_emissions(
        &mut self,
        assessment: &Assessment,
    ) -> Result<(), Box<dyn std::error::Error>> {
        let p = self.params.clone();
        let mgmt = assessment.management_practices.as_ref();
        for food in &assessment.foods {
            if !field::is_rice(&food.name) {
                continue;
            }
            let area = food.area_allocated.unwrap_or(0.0);
            if area <= 0.0 {
                continue;
            }
            let (regime, inferred) = rice_water_regime(food, self.water.as_ref());
            if let Some(why) = inferred {
                self.note_once(format!("rice '{}': water regime '{}' inferred ({}); declare water_regime to refine CH4",
                                       food.name, regime, why));
            }
            let sfw = field::rice_sfw(&regime).unwrap_or(1.0);
            if sfw == 0.0 {
                self.note_once(format!("rice '{}' is upland (never flooded): no CH4 (IPCC 2019 Table 5.12 SFw = 0)",
                                       food.name));
                continue;
            }
            let pre = food.preseason_water_status.as_deref().map(|s| s.trim().to_lowercase())
                .filter(|s| field::rice_sfp(s).is_some());
            let pre = match pre {
                Some(s) => s,
                None => {
                    self.note_once(format!("rice '{}': pre-season water status not declared, \
                        non-flooded < 180 d assumed (SFp 1.00, IPCC 2019 Table 5.13)", food.name));
                    "non_flooded_lt_180d".to_string()
                }
            };
            let sfp = field::rice_sfp(&pre).unwrap_or(1.0);
            let cpy = food.crops_per_year();
            let days = match food.growing_period_days.filter(|d| *d > 0.0) {
                Some(d) => d,
                None => {
                    self.note_once(format!("rice '{}': growing period not declared, IPCC 2019 Table 5.11a \
                        default cultivation period {} d used", food.name, p.rice_cultivation_days));
                    p.rice_cultivation_days
                }
            };

            // SFo: organic amendments per season (t/ha; straw dry, others fresh weight).
            let mut sum_roa_cfoa = 0.0;
            let mut parts: Vec<String> = Vec::new();
            if food.quantity_kg > 0.0 {
                let rm = food.residue_management.clone().unwrap_or_default();
                let r = field::residue_n(&food.name, food.quantity_kg / area, area,
                                         rm.fraction_removed.unwrap_or(0.0),
                                         rm.fraction_burnt.unwrap_or(0.0),
                                         rm.frac_renew.unwrap_or(1.0));
                let straw_t_ha = r.ag_dm_retained / area / cpy / 1000.0;
                if straw_t_ha > 0.0 {
                    // Timing is not collected: with >= 2 crops a year the previous straw is
                    // incorporated shortly (< 30 d) before the next season, else long before.
                    let (cfoa, timing) = if cpy >= 2.0 {
                        (field::CFOA_STRAW_SHORT, "< 30 d")
                    } else {
                        (field::CFOA_STRAW_LONG, "> 30 d")
                    };
                    sum_roa_cfoa += straw_t_ha * cfoa;
                    parts.push(format!("straw {:.2} t d.m./ha x {:.2} (incorporated {})", straw_t_ha, cfoa, timing));
                    self.note_once(format!("rice '{}': retained straw treated as incorporated {} before \
                        the next season (CFOA {:.2}, IPCC 2019 Table 5.14); timing not collected",
                        food.name, timing, cfoa));
                }
            }
            if let Some(m) = mgmt {
                let s = &m.soil_management;
                let applies = s.compost_crop_ids.is_empty()
                    || s.compost_crop_ids.iter().any(|id| id.trim() == food.id);
                if s.uses_compost && applies {
                    if let Some(rate) = s.compost_application_rate.filter(|r| *r > 0.0) {
                        let src = s.compost_source.clone().unwrap_or_default();
                        let (cfoa, kind) = if src.to_lowercase().contains("manure") {
                            (field::CFOA_FYM, "farmyard manure")
                        } else {
                            (field::CFOA_COMPOST, "compost")
                        };
                        let roa = rate / cpy; // t fresh/ha/year spread over the seasons
                        sum_roa_cfoa += roa * cfoa;
                        parts.push(format!("{} {:.2} t fresh/ha x {:.2}", kind, roa, cfoa));
                    }
                }
                if m.fertilization.uses_fertilizers {
                    for app in &m.fertilization.fertilizer_applications {
                        if app.application_rate <= 0.0 || app.applications_per_season == 0 {
                            continue;
                        }
                        if !(app.crop_ids.is_empty() || app.crop_ids.iter().any(|id| id.trim() == food.id)) {
                            continue;
                        }
                        if field::fertiliser_n(&app.fertilizer_type, &app.npk_ratio).form != NForm::Organic {
                            continue;
                        }
                        let t = app.fertilizer_type.to_lowercase();
                        let (cfoa, kind) = if t.contains("compost") {
                            (field::CFOA_COMPOST, "compost")
                        } else if t.contains("manure") || t.contains("dung") || t.contains("poultry") {
                            (field::CFOA_FYM, "farmyard manure")
                        } else {
                            self.note_once(format!("organic fertiliser '{}' has no IPCC 2019 Table 5.14 \
                                amendment class: not included in the rice CH4 factor SFo", app.fertilizer_type));
                            continue;
                        };
                        let roa = app.application_rate * app.applications_per_season as f64 / 1000.0;
                        sum_roa_cfoa += roa * cfoa;
                        parts.push(format!("{} {:.2} t fresh/ha x {:.2}", kind, roa, cfoa));
                    }
                }
            }
            let sfo = field::rice_sfo(sum_roa_cfoa);

            let ef = p.rice_ch4_efc * sfw * sfp * sfo;
            let ch4 = ef * days * area * cpy;
            self.add_inventory_item(InventoryItem {
                substance: "Methane (CH4)".to_string(),
                quantity: ch4,
                unit: "kg".to_string(),
                compartment: EnvironmentalCompartment::Air,
                source: format!(
                    "Rice CH4 for {} (IPCC 2019 Vol 4 Ch 5 Eq 5.1-5.3): EFc {:.2} kg/ha/d x SFw {:.2} ({}) \
                     x SFp {:.2} ({}) x SFo {:.3} [{}] x {:.0} d x {:.2} ha x {} season(s)",
                    food.name, p.rice_ch4_efc, sfw, regime, sfp, pre, sfo,
                    if parts.is_empty() { "no organic amendment".to_string() } else { parts.join("; ") },
                    days, area, cpy),
                category: FlowCategory::Field,
            });
        }

        Ok(())
    }

    /// Calculate land use
    fn calculate_land_use(
        &mut self,
        foods: &[FoodItem],
    ) -> Result<(), Box<dyn std::error::Error>> {

        let total_land_m2: f64 = foods.iter()
            .filter_map(|f| f.area_allocated.map(|a| a * 10000.0)) // Convert ha to m2
            .sum();

        if total_land_m2 > 0.0 {
            self.add_inventory_item(InventoryItem {
                substance: "Land occupation, annual crop".to_string(),
                quantity: total_land_m2,
                unit: "m2*year".to_string(),
                compartment: EnvironmentalCompartment::Resource,
                source: "Agricultural land occupation".to_string(),
                category: FlowCategory::Field,
            });
        }

        Ok(())
    }

    /// N2O from crop residues returned to soil, IPCC 2019 Refinement Vol 4 Ch 11:
    /// F_CR by Eq 11.6 (updated) with Table 11.1A parameters (field::residue_params), direct
    /// N2O at EF1 for "other N inputs" (Table 11.1; EF1FR on flooded rice), indirect N2O from
    /// leaching (Eq 11.10, F_CR x FracLEACH x EF5). Residue N is NOT in the volatilisation
    /// term (Eq 11.9 covers F_SN and F_ON/F_PRP only). Field burning of residues (if
    /// declared) adds CH4, N2O, CO and NOx by IPCC 2006 Vol 4 Eq 2.27 / Table 2.5 and PM2.5
    /// and NMVOC by EMEP/EEA 2019 3.F Table 3-1.
    /// Biological N fixation is not an N input (IPCC 2019 Ch 11 footnote 1: legume N2O is
    /// estimated solely from their residue N), so legumes contribute only through F_CR.
    fn calculate_crop_residue_emissions(
        &mut self,
        foods: &[FoodItem],
    ) -> Result<(), Box<dyn std::error::Error>> {
        for food in foods {
            let area = food.area_allocated.unwrap_or(0.0);
            if area <= 0.0 || food.quantity_kg <= 0.0 {
                continue;
            }
            let rm = food.residue_management.clone().unwrap_or_default();
            let r = field::residue_n(
                &food.name,
                food.quantity_kg / area,
                area,
                rm.fraction_removed.unwrap_or(0.0),
                rm.fraction_burnt.unwrap_or(0.0),
                rm.frac_renew.unwrap_or(1.0),
            );
            if r.params.proxy && r.params.crop == "generic crop" {
                self.warn_once(format!(
                    "crop '{}' has no IPCC 2019 Table 11.1A residue row: the generic row was used",
                    food.name));
            }
            let f_cr = r.f_cr();
            if f_cr > 0.0 {
                let ef1 = if self.is_flooded_rice(food) { EF1_FLOODED_RICE } else { self.params.ef1_other };
                let n2o_n = f_cr * ef1 + f_cr * self.params.frac_leach * self.params.ef5;
                self.add_inventory_item(InventoryItem {
                    substance: "Dinitrogen monoxide (N2O) - crop residues".to_string(),
                    quantity: n2o_n * N2O_PER_N2O_N,
                    unit: "kg".to_string(),
                    compartment: EnvironmentalCompartment::Air,
                    source: format!(
                        "Crop residue N2O for {}: F_CR {:.1} kg N ({:.1} above + {:.1} below ground; {})",
                        food.name, f_cr, r.n_above, r.n_below, r.params.source),
                    category: FlowCategory::Field,
                });
                let no3 = f_cr * self.params.frac_leach * NO3_PER_N;
                if no3 > 0.0 {
                    self.add_inventory_item(InventoryItem {
                        substance: "Nitrate (NO3-)".to_string(),
                        quantity: no3,
                        unit: "kg".to_string(),
                        compartment: EnvironmentalCompartment::Water,
                        source: format!("Nitrate leaching from {} crop residues", food.name),
                        category: FlowCategory::Field,
                    });
                }
            }
            if r.dm_burnt > 0.0 {
                // g per kg d.m. burnt: CH4, N2O, CO, NOx from IPCC 2006 Vol 4 Ch 2 Table 2.5
                // ('Agricultural residues'); PM2.5 and NMVOC from EMEP/EEA 2019 3.F Table 3-1.
                let ipcc = "IPCC 2006 Vol 4 Ch 2 Table 2.5, agricultural residues";
                let emep = "EMEP/EEA Guidebook 2019 3.F Table 3-1 Tier 1";
                let burn: [(&str, f64, &str); 6] = [
                    ("Methane (CH4) - residue burning", field::BURN_CH4_G_PER_KG_DM, ipcc),
                    ("Dinitrogen monoxide (N2O) - residue burning", field::BURN_N2O_G_PER_KG_DM, ipcc),
                    ("Carbon monoxide - residue burning", field::BURN_CO_G_PER_KG_DM, ipcc),
                    ("NOx - residue burning", field::BURN_NOX_G_PER_KG_DM, ipcc),
                    ("Particulates, < 2.5 um - residue burning", field::BURN_PM25_G_PER_KG_DM, emep),
                    ("NMVOC - residue burning", field::BURN_NMVOC_G_PER_KG_DM, emep),
                ];
                for (substance, g_per_kg, src) in burn {
                    self.add_inventory_item(InventoryItem {
                        substance: substance.to_string(),
                        quantity: r.dm_burnt * g_per_kg / 1000.0,
                        unit: "kg".to_string(),
                        compartment: EnvironmentalCompartment::Air,
                        source: format!("Field burning of {} residues ({:.0} kg d.m. burnt x {} g/kg; {})",
                                        food.name, r.dm_burnt, g_per_kg, src),
                        category: FlowCategory::Field,
                    });
                }
            }
        }
        Ok(())
    }

    /// Add inventory item to the collection. Items merge only within the same (substance,
    /// compartment, category): a field emission never merges with an upstream or energy
    /// flow of the same substance.
    fn add_inventory_item(&mut self, item: InventoryItem) {
        let key = format!("{}_{:?}_{:?}", item.substance, item.compartment, item.category);

        // If item already exists, aggregate quantities
        if let Some(existing) = self.inventory.get_mut(&key) {
            existing.quantity += item.quantity;
            existing.source = format!("{}, {}", existing.source, item.source);
        } else {
            self.inventory.insert(key, item);
        }
    }

    /// Get the complete inventory
    pub fn get_inventory(&self) -> &HashMap<String, InventoryItem> {
        &self.inventory
    }
}

#[cfg(test)]
mod n_balance_tests {
    use super::*;

    fn maize(area_ha: f64) -> FoodItem {
        FoodItem {
            id: "1".to_string(),
            name: "Maize".to_string(),
            quantity_kg: 1000.0,
            category: FoodCategory::Cereals,
            crop_type: None,
            origin_country: None,
            production_system: None,
            seasonal_factor: None,
            variety: None,
            area_allocated: Some(area_ha),
            cropping_pattern: None,
            intercropping_partners: None,
            post_harvest_losses: None,
            residue_management: None,
            crops_per_year: None,
            growing_period_days: None,
            water_regime: None,
            preseason_water_status: None,
        }
    }

    fn urea_100kg() -> FertilizationPractices {
        FertilizationPractices {
            uses_fertilizers: true,
            fertilizer_applications: vec![FertilizerApplication {
                fertilizer_type: "Urea".to_string(), // 46% N
                npk_ratio: None,
                application_rate: 100.0, // kg/ha/application
                applications_per_season: 1,
                cost: None,
                currency: None,
                application_method: None,
                brand_name: None,
                crop_ids: vec![],
            }],
            soil_test_based: false,
            follows_nutrient_plan: false,
        }
    }

    fn flow_by_source<'a>(calc: &'a LCICalculator, needle: &str) -> f64 {
        calc.get_inventory()
            .values()
            .find(|i| i.source.contains(needle))
            .unwrap_or_else(|| panic!("no inventory flow with source containing '{needle}'"))
            .quantity
    }

    // The mass-balance fix: indirect N2O and nitrate must be derived from the SEPARATE IPCC
    // volatilisation (FracGASF/EF4) and leaching (FracLEACH/EF5) pathways, and the volatilised
    // N must not also be counted as leached nitrate.
    #[test]
    fn indirect_n2o_and_nitrate_use_separate_ipcc_pathways() {
        let mut calc = LCICalculator::new();
        calc.calculate_fertilizer_emissions(&urea_100kg(), &vec![maize(1.0)])
            .expect("fertiliser emissions");

        let n_applied = 100.0 * 0.46; // 46 kg N
        // FracGASF for urea, IPCC 2019 Table 11.3 (disaggregated).
        let (frac_gasf, frac_leach, ef4, ef5) = (0.15, 0.24, 0.010, 0.011);
        let n2o_ratio = 44.0 / 28.0;

        let direct = flow_by_source(&calc, "Direct N2O");
        let indirect = flow_by_source(&calc, "Indirect N2O");
        let nitrate = flow_by_source(&calc, "Nitrate leaching");

        assert!((direct - n_applied * 0.01 * n2o_ratio).abs() < 1e-9);

        let expect_indirect =
            (n_applied * frac_gasf * ef4 + n_applied * frac_leach * ef5) * n2o_ratio;
        assert!((indirect - expect_indirect).abs() < 1e-9, "indirect {indirect} != {expect_indirect}");

        // Nitrate reflects the leached fraction ONLY (FracLEACH), not the volatilised N.
        let expect_nitrate = n_applied * frac_leach * (62.0 / 14.0);
        assert!((nitrate - expect_nitrate).abs() < 1e-9, "nitrate {nitrate} != {expect_nitrate}");

        // Regression guard against the old bug (single 20% loss reused for both pathways):
        // nitrate must equal the leaching-only value, not the lumped-loss value.
        let old_lumped = n_applied * 0.20 * (62.0 / 14.0);
        assert!((nitrate - old_lumped).abs() > 1e-9, "nitrate still uses the lumped 20% loss");
    }

    fn sum_substance(calc: &LCICalculator, substance: &str) -> f64 {
        calc.get_inventory().values().filter(|i| i.substance == substance).map(|i| i.quantity).sum()
    }

    // Region parameters are honoured end to end: a dry climate (FracLEACH 0, EF1 0.005,
    // EF4 0.005) produces no leaching N2O or nitrate and uses the dry EF1.
    #[test]
    fn dry_climate_parameters_remove_leaching() {
        let mut calc = LCICalculator::new();
        calc.params = FieldParameters { ef1_synthetic: 0.005, ef1_other: 0.005, frac_gasf: 0.11,
            frac_gasm: 0.21, frac_leach: 0.0, ef4: 0.005, ef5: 0.011, ..FieldParameters::default() };
        calc.calculate_fertilizer_emissions(&urea_100kg(), &vec![maize(1.0)]).unwrap();
        let n = 46.0;
        let direct = flow_by_source(&calc, "Direct N2O");
        assert!((direct - n * 0.005 * 44.0 / 28.0).abs() < 1e-9);
        let indirect = flow_by_source(&calc, "Indirect N2O");
        assert!((indirect - n * 0.15 * 0.005 * 44.0 / 28.0).abs() < 1e-9);
        assert_eq!(sum_substance(&calc, "Nitrate (NO3-)"), 0.0);
    }

    fn assessment(foods: Vec<FoodItem>, fert: FertilizationPractices, water: WaterManagement,
                  lime: Vec<LimeApplication>) -> Assessment {
        Assessment {
            id: uuid::Uuid::new_v4(), company_name: "t".into(), country: Country::Ghana,
            currency: Currency::GHS, region: None, foods, assessment_date: chrono::Utc::now(),
            methodology: LCAMethodology {
                functional_unit: "1 kg".into(), system_boundary: SystemBoundary::CradleToGate,
                allocation_method: AllocationMethod::Mass,
                characterization_method: CharacterizationMethod::IpccAr6,
                normalization_method: None, weighting_method: None },
            results: None, farm_profile: None,
            management_practices: Some(ManagementPractices {
                soil_management: SoilManagement { soil_type: None, uses_compost: false,
                    compost_source: None, conservation_practices: vec![],
                    soil_testing_frequency: None, compost_application_rate: None,
                    compost_crop_ids: vec![], lime_applications: lime },
                fertilization: fert,
                water_management: water,
                pest_management: PestManagement { management_approach: "x".into(), uses_ipm: false,
                    pesticides_used: vec![], monitoring_frequency: None },
            }),
            equipment_energy: None, field_parameters: None,
        }
    }

    fn water(system: &str, practices: &[&str]) -> WaterManagement {
        WaterManagement { water_source: vec![], irrigation_system: Some(system.to_string()),
            water_conservation_practices: practices.iter().map(|s| s.to_string()).collect() }
    }

    fn no_fert() -> FertilizationPractices {
        FertilizationPractices { uses_fertilizers: false, fertilizer_applications: vec![],
            soil_test_based: false, follows_nutrient_plan: false }
    }

    fn by_cat(calc: &LCICalculator, substance: &str, cat: FlowCategory) -> f64 {
        calc.get_inventory().values().filter(|i| i.substance == substance && i.category == cat)
            .map(|i| i.quantity).sum()
    }

    // NH3 = N x FracGASF(urea 0.15) x 17/14; NOx = 0.21 x soil N2O; urea CO2 = M x 0.2 x 44/12.
    #[test]
    fn urea_nh3_nox_and_hydrolysis_co2() {
        let mut calc = LCICalculator::new();
        let mut food = maize(1.0);
        food.quantity_kg = 0.0; // no residues, to isolate the fertiliser N2O
        calc.calculate_inventory(&assessment(vec![food], urea_100kg(), water("None (Rainfed)", &[]), vec![]))
            .unwrap();
        let nh3 = sum_substance(&calc, "Ammonia (NH3)");
        assert!((nh3 - 46.0 * 0.15 * 17.0 / 14.0).abs() < 1e-9, "{nh3}");
        let n2o: f64 = SOIL_N2O_SUBSTANCES.iter().map(|s| sum_substance(&calc, s)).sum();
        assert!((sum_substance(&calc, "Nitrogen oxides (NOx)") - 0.21 * n2o).abs() < 1e-12);
        let co2 = by_cat(&calc, "Carbon dioxide (CO2) - urea hydrolysis", FlowCategory::Field);
        assert!((co2 - 100.0 * 0.20 * 44.0 / 12.0).abs() < 1e-9);
        // production CO2 is a separate (upstream) item and never merges with the field CO2
        assert!(by_cat(&calc, "Carbon dioxide (CO2)", FlowCategory::Upstream) > 0.0);
        assert_eq!(by_cat(&calc, "Carbon dioxide (CO2)", FlowCategory::Field), 0.0);
    }

    // A free-text product with the straight urea grade is treated as urea (FracGASF 0.15 and
    // Eq 11.13 CO2), as engine/inputs.py identifies it from the grade.
    #[test]
    fn free_text_urea_grade_is_urea() {
        let mut calc = LCICalculator::new();
        let mut f = urea_100kg();
        f.fertilizer_applications[0].fertilizer_type = "White prills".into();
        f.fertilizer_applications[0].npk_ratio = Some("46-0-0".into());
        calc.calculate_fertilizer_emissions(&f, &vec![maize(1.0)]).unwrap();
        assert!((sum_substance(&calc, "Ammonia (NH3)") - 46.0 * 0.15 * 17.0 / 14.0).abs() < 1e-9);
        assert!((sum_substance(&calc, "Carbon dioxide (CO2) - urea hydrolysis") - 100.0 * 0.2 * 44.0 / 12.0).abs() < 1e-9);
    }

    #[test]
    fn none_rows_and_zero_applications_are_skipped() {
        let mut calc = LCICalculator::new();
        let mut f = urea_100kg();
        f.fertilizer_applications[0].applications_per_season = 0;
        calc.calculate_fertilizer_emissions(&f, &vec![maize(1.0)]).unwrap();
        assert!(calc.get_inventory().is_empty());
        f.fertilizer_applications[0].applications_per_season = 1;
        f.fertilizer_applications[0].fertilizer_type = "None".into();
        calc.calculate_fertilizer_emissions(&f, &vec![maize(1.0)]).unwrap();
        assert!(calc.get_inventory().is_empty());
    }

    // crops_per_year multiplies seasonal fertiliser N; crop_ids restrict a row to its crops.
    #[test]
    fn crops_per_year_and_crop_ids() {
        let mut one = LCICalculator::new();
        one.calculate_fertilizer_emissions(&urea_100kg(), &vec![maize(1.0)]).unwrap();
        let mut two = LCICalculator::new();
        let mut m = maize(1.0);
        m.crops_per_year = Some(2);
        two.calculate_fertilizer_emissions(&urea_100kg(), &vec![m]).unwrap();
        let d1 = sum_substance(&one, "Dinitrogen monoxide (N2O)");
        assert!((sum_substance(&two, "Dinitrogen monoxide (N2O)") - 2.0 * d1).abs() < 1e-9);

        let mut cowpea = maize(1.0);
        cowpea.id = "2".into();
        cowpea.name = "Cowpea".into();
        let mut f = urea_100kg();
        f.fertilizer_applications[0].crop_ids = vec!["1".into()];
        let mut both = LCICalculator::new();
        both.calculate_fertilizer_emissions(&f, &vec![maize(1.0), cowpea]).unwrap();
        assert!((sum_substance(&both, "Dinitrogen monoxide (N2O)") - d1).abs() < 1e-9);
    }

    #[test]
    fn liming_co2() {
        let mut calc = LCICalculator::new();
        let lime = vec![LimeApplication { material: "limestone".into(), rate_t_per_ha_per_year: 1.0, crop_ids: vec![] },
                        LimeApplication { material: "dolomite".into(), rate_t_per_ha_per_year: 1.0, crop_ids: vec!["9".into()] }];
        calc.calculate_inventory(&assessment(vec![maize(2.0)], no_fert(), water("None (Rainfed)", &[]), lime)).unwrap();
        let co2 = sum_substance(&calc, "Carbon dioxide (CO2) - liming");
        assert!((co2 - 2.0 * 1000.0 * 0.12 * 44.0 / 12.0).abs() < 1e-9, "{co2}");
    }

    fn rice(area: f64) -> FoodItem {
        let mut r = maize(area);
        r.name = "Rice".into();
        r.quantity_kg = 0.0; // no straw: isolates EFc x SFw x SFp
        r.growing_period_days = Some(120.0);
        r
    }

    fn rice_ch4(food: FoodItem, w: WaterManagement) -> f64 {
        let mut calc = LCICalculator::new();
        calc.calculate_inventory(&assessment(vec![food], no_fert(), w, vec![])).unwrap();
        sum_substance(&calc, "Methane (CH4)")
    }

    #[test]
    fn rice_ch4_follows_ipcc_2019_ch5() {
        let flooded = rice_ch4(rice(1.0), water("Flood Irrigation", &[]));
        assert!((flooded - 1.19 * 120.0).abs() < 1e-9, "{flooded}");
        let awd = rice_ch4(rice(1.0), water("Flood Irrigation", &["Alternate wetting and drying"]));
        assert!((awd - 1.19 * 120.0 * 0.55).abs() < 1e-9);
        let mut up = rice(1.0);
        up.name = "Upland rice".into();
        assert_eq!(rice_ch4(up, water("Flood Irrigation", &[])), 0.0);
        let mut two = rice(1.0);
        two.crops_per_year = Some(2);
        assert!((rice_ch4(two, water("Flood Irrigation", &[])) - 2.0 * flooded).abs() < 1e-9);
        let mut declared = rice(1.0);
        declared.water_regime = Some("rainfed_drought_prone".into());
        declared.preseason_water_status = Some("flooded_gt_30d".into());
        assert!((rice_ch4(declared, water("Flood Irrigation", &[])) - 1.19 * 120.0 * 0.16 * 2.41).abs() < 1e-9);
        // retained straw: SFo = (1 + ROA x CFOA)^0.59, single crop -> CFOA 0.19 (> 30 d)
        let mut straw = rice(1.0);
        straw.quantity_kg = 4000.0;
        let roa = 4000.0 * 0.89 * 1.4 / 1000.0;
        let expect = 1.19 * 120.0 * (1.0 + roa * 0.19f64).powf(0.59);
        assert!((rice_ch4(straw, water("Flood Irrigation", &[])) - expect).abs() < 1e-9);
    }

    // The flooded-rice EF1 follows the same water regime as CH4: upland rice uses EF1.
    #[test]
    fn upland_rice_uses_upland_ef1() {
        let mut calc = LCICalculator::new();
        calc.params = FieldParameters { ef1_synthetic: 0.016, ..FieldParameters::default() };
        calc.water = Some(water("Sprinkler System", &[]));
        let mut r = maize(1.0);
        r.name = "Rice".into();
        calc.calculate_fertilizer_emissions(&urea_100kg(), &vec![r]).unwrap();
        let direct = flow_by_source(&calc, "Direct N2O");
        assert!((direct - 46.0 * 0.016 * 44.0 / 28.0).abs() < 1e-9);
    }

    // An unknown fertiliser gets zero N (no N2O) and a validation warning, never 10% N.
    #[test]
    fn unknown_fertiliser_is_zero_n_and_warns() {
        let mut calc = LCICalculator::new();
        let mut f = urea_100kg();
        f.fertilizer_applications[0].fertilizer_type = "Foliar Fertilizer".to_string();
        calc.calculate_fertilizer_emissions(&f, &vec![maize(1.0)]).unwrap();
        assert_eq!(sum_substance(&calc, "Dinitrogen monoxide (N2O)"), 0.0);
        assert!(calc.warnings().iter().any(|w| w.contains("not recognised")));
    }

    // Crop residues add N2O even without fertiliser, at EF1 for other N inputs plus leaching.
    #[test]
    fn residue_n2o_without_fertiliser() {
        let mut calc = LCICalculator::new();
        calc.params = FieldParameters { ef1_other: 0.006, ..FieldParameters::default() };
        let mut food = maize(2.0);
        food.quantity_kg = 6000.0; // 3 t/ha
        calc.calculate_crop_residue_emissions(&vec![food]).unwrap();
        let r = field::residue_n("Maize", 3000.0, 2.0, 0.0, 0.0, 1.0);
        let expect = r.f_cr() * (0.006 + 0.24 * 0.011) * 44.0 / 28.0;
        let got = sum_substance(&calc, "Dinitrogen monoxide (N2O) - crop residues");
        assert!((got - expect).abs() < 1e-9, "{got} vs {expect}");
        assert!(sum_substance(&calc, "Nitrate (NO3-)") > 0.0);
    }

    // Flooded rice uses EF1FR = 0.004 for fertiliser N (IPCC 2019 Table 11.1).
    #[test]
    fn flooded_rice_uses_ef1fr() {
        let mut calc = LCICalculator::new();
        calc.params = FieldParameters { ef1_synthetic: 0.016, ..FieldParameters::default() };
        let mut rice = maize(1.0);
        rice.name = "Rice".to_string();
        calc.calculate_fertilizer_emissions(&urea_100kg(), &vec![rice]).unwrap();
        let direct = flow_by_source(&calc, "Direct N2O");
        assert!((direct - 46.0 * EF1_FLOODED_RICE * 44.0 / 28.0).abs() < 1e-9);
    }

    // Declared residue burning emits CH4 and N2O by IPCC 2006 Vol 4 Table 2.5.
    #[test]
    fn residue_burning_emits_ch4() {
        let mut calc = LCICalculator::new();
        let mut food = maize(1.0);
        food.quantity_kg = 3000.0;
        food.residue_management = Some(ResidueManagement { fraction_removed: None,
            fraction_burnt: Some(0.5), frac_renew: None });
        calc.calculate_crop_residue_emissions(&vec![food]).unwrap();
        let dm = 3000.0 * 0.87 * 1.0 * 0.5 * 0.80;
        let ch4 = sum_substance(&calc, "Methane (CH4) - residue burning");
        assert!((ch4 - dm * 2.7 / 1000.0).abs() < 1e-9);
        assert!((sum_substance(&calc, "Carbon monoxide - residue burning") - dm * 92.0 / 1000.0).abs() < 1e-9);
        assert!((sum_substance(&calc, "NOx - residue burning") - dm * 2.5 / 1000.0).abs() < 1e-9);
        assert!((sum_substance(&calc, "Particulates, < 2.5 um - residue burning") - dm * 5.4 / 1000.0).abs() < 1e-9);
        assert!((sum_substance(&calc, "NMVOC - residue burning") - dm * 0.5 / 1000.0).abs() < 1e-9);
    }
}

// ======================================================================
// LCI TO LCIA BRIDGE - DEPRECATED. The served path characterises `lci_inventory` in Python
// (ecoinvent EF 3.1 / ReCiPe 2016 packs); this bridge only feeds the legacy Rust LCIA.
// ======================================================================

impl LCICalculator {
    /// Convert LCI results to LCIA midpoint indicators
    /// This is where we go from "kg N2O" to "kg CO2-eq global warming potential"
    pub fn calculate_midpoint_impacts(
        &self,
        inventory: &HashMap<String, InventoryItem>,
    ) -> Result<HashMap<String, MidpointResult>, Box<dyn std::error::Error>> {

        let mut impacts = HashMap::new();

        // Initialize all impact categories
        let impact_categories = vec![
            "Global warming",
            "Water consumption",
            "Water scarcity",
            "Land use",
            "Biodiversity loss",
            "Soil degradation",
            "Terrestrial acidification",
            "Freshwater eutrophication",
            "Marine eutrophication",
            "Fossil depletion",
            "Mineral depletion",
            "Particulate matter formation",
            "Photochemical oxidation",
        ];

        for category in &impact_categories {
            impacts.insert(category.to_string(), MidpointResult {
                value: 0.0,
                unit: self.get_impact_unit(category),
                uncertainty_range: (0.0, 0.0),
                data_quality_score: 0.8, // High quality - calculated from primary data
                contributing_sources: Vec::new(),
            });
        }

        // DEPRECATED legacy LCIA (served only with USE_LEGACY_RUST_LCIA). GWP100 on one
        // basis, IPCC AR6 WG1 Ch 7 Table 7.15: N2O 273; the only CH4 summed here is rice
        // paddy CH4, which is non-fossil (27.0). The field CO2 flows "- urea hydrolysis" /
        // "- liming" are deliberately not summed (the legacy urea production factor already
        // folds in hydrolysis).
        let gwp_n2o = 273.0;
        let gwp_ch4 = 27.0;

        // Calculate Global Warming Potential
        let mut gwp_total = 0.0;
        let mut gwp_sources = Vec::new();

        for (_, item) in inventory {
            match item.substance.as_str() {
                "Carbon dioxide (CO2)" | "Carbon dioxide (CO2) equivalent" => {
                    gwp_total += item.quantity; // Already in kg CO2
                    gwp_sources.push(format!("{}: {:.2} kg CO2", item.source, item.quantity));
                }
                s if s.contains("N2O") => {
                    let co2_eq = item.quantity * gwp_n2o;
                    gwp_total += co2_eq;
                    gwp_sources.push(format!("{}: {:.2} kg N2O ({:.2} kg CO2-eq)",
                                            item.source, item.quantity, co2_eq));
                }
                "Methane (CH4)" => {
                    let co2_eq = item.quantity * gwp_ch4;
                    gwp_total += co2_eq;
                    gwp_sources.push(format!("{}: {:.2} kg CH4 ({:.2} kg CO2-eq)",
                                            item.source, item.quantity, co2_eq));
                }
                _ => {}
            }
        }

        if let Some(gwp_result) = impacts.get_mut("Global warming") {
            gwp_result.value = gwp_total;
            gwp_result.contributing_sources = gwp_sources;
            gwp_result.uncertainty_range = (gwp_total * 0.8, gwp_total * 1.2); // ±20% uncertainty
        }

        // Water consumption
        for (_, item) in inventory {
            if item.substance == "Water" {
                if let Some(water_result) = impacts.get_mut("Water consumption") {
                    water_result.value += item.quantity; // m3
                    water_result.contributing_sources.push(item.source.clone());
                }
            }
        }

        // Land use
        for (_, item) in inventory {
            if item.substance.contains("Land occupation") {
                if let Some(land_result) = impacts.get_mut("Land use") {
                    land_result.value += item.quantity / 10000.0; // Convert m2*year to m2a
                    land_result.contributing_sources.push(item.source.clone());
                }
            }
        }

        // Freshwater eutrophication (from nitrate leaching)
        for (_, item) in inventory {
            if item.substance.contains("Nitrate") {
                if let Some(eutroph_result) = impacts.get_mut("Freshwater eutrophication") {
                    // Convert NO3 to P-equivalent using ReCiPe characterization
                    // Simplified: NO3 has lower eutrophication potential than P
                    let p_eq = item.quantity * 0.01; // Rough conversion factor
                    eutroph_result.value += p_eq;
                    eutroph_result.contributing_sources.push(item.source.clone());
                }
            }
        }

        info!("Calculated {} midpoint impact categories from LCI", impacts.len());

        Ok(impacts)
    }

    fn get_impact_unit(&self, category: &str) -> String {
        match category {
            "Global warming" => "kg CO2-eq".to_string(),
            "Water consumption" => "m3".to_string(),
            "Water scarcity" => "m3 H2O-eq".to_string(),
            "Land use" => "m2a crop-eq".to_string(),
            "Biodiversity loss" => "MSA*m2*yr".to_string(),
            "Soil degradation" => "kg soil-eq".to_string(),
            "Terrestrial acidification" => "kg SO2-eq".to_string(),
            "Freshwater eutrophication" => "kg P-eq".to_string(),
            "Marine eutrophication" => "kg N-eq".to_string(),
            "Fossil depletion" => "kg oil-eq".to_string(),
            "Mineral depletion" => "kg Fe-eq".to_string(),
            "Particulate matter formation" => "PM2.5-eq".to_string(),
            "Photochemical oxidation" => "kg NMVOC-eq".to_string(),
            _ => "Unknown".to_string(),
        }
    }
}
