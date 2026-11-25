use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;
use chrono::{DateTime, Utc};

// ======================================================================
// CORE DATA MODELS - Unified for both simple and comprehensive assessments
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FoodItem {
    pub id: String,
    pub name: String,
    pub quantity_kg: f64,
    pub category: FoodCategory,
    pub crop_type: Option<String>,
    pub origin_country: Option<String>,
    pub production_system: Option<ProductionSystem>,
    pub seasonal_factor: Option<SeasonalFactor>,
    
    // Enhanced fields for comprehensive assessments
    pub variety: Option<String>,
    pub area_allocated: Option<f64>, // hectares
    pub cropping_pattern: Option<CroppingPattern>,
    pub intercropping_partners: Option<Vec<String>>,
    pub post_harvest_losses: Option<f64>, // percentage

    // Crop-residue management for IPCC 2019 Eq 11.6 (F_CR). None = IPCC Tier 1 defaults
    // (no removal, no burning, annual renewal).
    #[serde(default)]
    pub residue_management: Option<ResidueManagement>,

    // Seasonality (fix-team CONTRACT §1). quantity_kg is the ANNUAL total over
    // crops_per_year harvests on area_allocated; per-season inputs and rice CH4 scale by it.
    #[serde(default)]
    pub crops_per_year: Option<u32>,
    /// One season, planting to harvest (rice CH4 cultivation period t, IPCC 2019 Eq 5.1).
    #[serde(default)]
    pub growing_period_days: Option<f64>,
    /// Rice only: IPCC 2019 Vol 4 Ch 5 Table 5.12 water regime (contract vocabulary).
    #[serde(default)]
    pub water_regime: Option<String>,
    /// Rice only: IPCC 2019 Vol 4 Ch 5 Table 5.13 pre-season water status.
    #[serde(default)]
    pub preseason_water_status: Option<String>,
}

impl FoodItem {
    /// Harvests per year on area_allocated (>= 1; blank -> 1).
    pub fn crops_per_year(&self) -> f64 {
        self.crops_per_year.unwrap_or(1).max(1) as f64
    }
}

/// Per-crop residue management (IPCC 2019 Vol 4 Ch 11 Eq 11.6). All fractions 0..1.
#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct ResidueManagement {
    /// Frac_Remove: fraction of above-ground residues removed (feed, bedding, fuel).
    /// IPCC 2019 Eq 11.6 note: "If data for FracRemove are not available, assume no removal".
    #[serde(default)]
    pub fraction_removed: Option<f64>,
    /// Frac_Burnt: fraction of the harvested area whose residues are burnt in the field.
    #[serde(default)]
    pub fraction_burnt: Option<f64>,
    /// Frac_Renew: fraction of the below-ground biomass renewed per year. 1 for annual
    /// crops (IPCC 2019 Eq 11.6); 1/lifetime for perennial stands (set by the Python
    /// engine from engine/perennials.py so the lifetime has a single source).
    #[serde(default)]
    pub frac_renew: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum FoodCategory {
    Cereals,
    Legumes,
    Vegetables,
    Fruits,
    Meat,
    Poultry,
    Fish,
    Dairy,
    Eggs,
    Oils,
    Nuts,
    Roots,
    Other,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProductionSystem {
    Intensive,
    Extensive,
    Smallholder,
    Agroforestry,
    Irrigated,
    Rainfed,
    Organic,
    Conventional,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SeasonalFactor {
    WetSeason,
    DrySeason,
    YearRound,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CroppingPattern {
    Monoculture,
    Intercropping,
    RelayCropping,
    Agroforestry,
    CropRotation,
}

// ======================================================================
// ASSESSMENT STRUCTURE
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Assessment {
    pub id: Uuid,
    pub company_name: String,
    pub country: Country,
    pub currency: Currency, // Primary currency for this assessment
    pub region: Option<String>,
    pub foods: Vec<FoodItem>,
    pub assessment_date: DateTime<Utc>,
    pub methodology: LCAMethodology,
    pub results: Option<LCAResults>,

    // Enhanced fields for comprehensive assessments
    pub farm_profile: Option<FarmProfile>,
    pub management_practices: Option<ManagementPractices>,
    pub equipment_energy: Option<EquipmentEnergy>, // NEW: Equipment and energy data

    // Region/climate IPCC 2019 soil-N parameters, injected by the Python engine from the
    // region registry (engine/field_params.py). None = IPCC 2019 aggregated defaults.
    #[serde(default)]
    pub field_parameters: Option<FieldParameters>,
}

/// IPCC 2019 Refinement Vol 4 Ch 11 soil-N2O parameters used by the LCI kernel.
/// Defaults are the AGGREGATED Tier 1 values (Table 11.1 and Table 11.3, 2019 Refinement);
/// the Python engine overrides them with the region's disaggregated (wet/dry) values.
/// Missing keys take the default (serde(default)), so a partial object still parses.
#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(default)]
pub struct FieldParameters {
    /// EF1 for synthetic fertiliser N (Table 11.1: aggregated 0.010, wet 0.016, dry 0.005).
    pub ef1_synthetic: f64,
    /// EF1 for other N inputs: organic N, crop residues, F_SOM (Table 11.1: aggregated 0.010,
    /// wet 0.006, dry 0.005).
    pub ef1_other: f64,
    /// FracGASF (Table 11.3 aggregated 0.11).
    pub frac_gasf: f64,
    /// FracGASM for organic N (Table 11.3: 0.21).
    pub frac_gasm: f64,
    /// FracLEACH-(H) (Table 11.3: 0.24 wet / irrigated; 0 in dry climates).
    pub frac_leach: f64,
    /// EF4 (Table 11.3: aggregated 0.010, wet 0.014, dry 0.005).
    pub ef4: f64,
    /// EF5 (Table 11.3: 0.011).
    pub ef5: f64,
    /// FracGASF disaggregated by fertiliser type (Table 11.3 updated; categories per
    /// Annex 11A.7): urea 0.15, ammonium-based 0.08, nitrate-based 0.01,
    /// ammonium-nitrate-based 0.05. Unclassified types (NPK of unknown N form) use frac_gasf.
    pub frac_gasf_urea: f64,
    pub frac_gasf_ammonium: f64,
    pub frac_gasf_nitrate: f64,
    pub frac_gasf_ammonium_nitrate: f64,
    /// Rice CH4 baseline daily EF, continuously flooded, no organic amendment, non-flooded
    /// pre-season < 180 d: IPCC 2019 Vol 4 Ch 5 Table 5.11 (updated) 1.19 kg CH4/ha/day
    /// (0.80-1.76); Africa uses the global value "due to lack of data".
    pub rice_ch4_efc: f64,
    /// Default rice cultivation period when growing_period_days is blank: IPCC 2019 Vol 4
    /// Ch 5 Table 5.11a (new) 113 days (74-152), the global value also given for Africa.
    pub rice_cultivation_days: f64,
}

impl Default for FieldParameters {
    fn default() -> Self {
        Self {
            ef1_synthetic: 0.010,
            ef1_other: 0.010,
            frac_gasf: 0.11,
            frac_gasm: 0.21,
            frac_leach: 0.24,
            ef4: 0.010,
            ef5: 0.011,
            frac_gasf_urea: 0.15,
            frac_gasf_ammonium: 0.08,
            frac_gasf_nitrate: 0.01,
            frac_gasf_ammonium_nitrate: 0.05,
            rice_ch4_efc: 1.19,
            rice_cultivation_days: 113.0,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FarmProfile {
    pub farmer_name: String,
    pub farm_name: String,
    pub total_farm_size: f64, // hectares
    pub farming_experience: u32, // years
    pub farm_type: FarmType,
    pub primary_farming_system: FarmingSystem,
    pub certifications: Vec<String>,
    pub participates_in_programs: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum FarmType {
    Smallholder,
    SmallScale,
    MediumScale,
    Commercial,
    Cooperative,
    MixedLivestock,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum FarmingSystem {
    Subsistence,
    SemiCommercial,
    Commercial,
    Organic,
    Agroecological,
    Conventional,
    IntegratedFarming,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManagementPractices {
    pub soil_management: SoilManagement,
    pub fertilization: FertilizationPractices,
    pub water_management: WaterManagement,
    pub pest_management: PestManagement,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SoilManagement {
    pub soil_type: Option<SoilType>,
    pub uses_compost: bool,
    pub compost_source: Option<String>,
    pub conservation_practices: Vec<String>,
    pub soil_testing_frequency: Option<String>,
    /// t fresh compost/manure per ha per year (compost N2O is modelled in Python; the
    /// kernel reads it only for the rice CH4 organic-amendment factor SFo).
    #[serde(default)]
    pub compost_application_rate: Option<f64>,
    /// foods[].id receiving compost; empty = all crops.
    #[serde(default)]
    pub compost_crop_ids: Vec<String>,
    #[serde(default)]
    pub lime_applications: Vec<LimeApplication>,
}

/// Agricultural liming (IPCC 2006 Vol 4 Ch 11 Eq 11.12).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LimeApplication {
    /// "limestone" (CaCO3) or "dolomite" (CaMg(CO3)2).
    pub material: String,
    pub rate_t_per_ha_per_year: f64,
    /// foods[].id receiving the lime; empty = all crops.
    #[serde(default)]
    pub crop_ids: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SoilType {
    Sandy,
    Clay,
    Loam,
    SandyLoam,
    ClayLoam,
    SiltLoam,
    Lateritic,
    Volcanic,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FertilizationPractices {
    pub uses_fertilizers: bool,
    pub fertilizer_applications: Vec<FertilizerApplication>,
    pub soil_test_based: bool,
    pub follows_nutrient_plan: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct FertilizerApplication {
    pub fertilizer_type: String,
    pub npk_ratio: Option<String>, // e.g., "15-15-15"
    pub application_rate: f64, // kg product per hectare PER APPLICATION
    pub applications_per_season: u32,
    pub cost: Option<f64>,
    pub currency: Option<Currency>,
    /// "broadcast" | "incorporated" | "band_placement" | "side_dressing" | "foliar" |
    /// "fertigation" (disclosure only: no cited Tier 1 NH3 reduction is applied).
    #[serde(default)]
    pub application_method: Option<String>,
    #[serde(default)]
    pub brand_name: Option<String>,
    /// foods[].id this row applies to; empty = all crops.
    #[serde(default)]
    pub crop_ids: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WaterManagement {
    pub water_source: Vec<String>,
    pub irrigation_system: Option<String>,
    pub water_conservation_practices: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PestManagement {
    pub management_approach: String,
    pub uses_ipm: bool,
    pub pesticides_used: Vec<PesticideApplication>,
    pub monitoring_frequency: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PesticideApplication {
    pub pesticide_type: String,
    pub active_ingredient: String,
    pub application_rate: f64,
    pub applications_per_season: u32,
    pub target_pests: Vec<String>,
}

// ======================================================================
// EQUIPMENT & ENERGY DATA
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EquipmentEnergy {
    pub equipment: Vec<FarmEquipment>,
    pub energy_sources: Vec<EnergyUsage>,
    pub fuel_consumption: Vec<FuelUsage>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FarmEquipment {
    pub equipment_type: String,
    pub power_source: String,
    pub age: u32, // years
    pub hours_per_year: f64,
    pub fuel_efficiency: Option<f64>, // liters per hour
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct EnergyUsage {
    pub energy_type: String,
    pub monthly_consumption: f64, // kWh or equivalent
    pub primary_use: String,
    pub cost: Option<f64>,
    pub currency: Option<Currency>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
pub struct FuelUsage {
    pub fuel_type: String,
    pub monthly_consumption: f64, // liters
    pub primary_use: String,
    pub cost: Option<f64>,
}

// ======================================================================
// LCA METHODOLOGY & RESULTS
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LCAMethodology {
    pub functional_unit: String,
    pub system_boundary: SystemBoundary,
    pub allocation_method: AllocationMethod,
    pub characterization_method: CharacterizationMethod,
    pub normalization_method: Option<NormalizationMethod>,
    pub weighting_method: Option<WeightingMethod>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum SystemBoundary {
    CradleToGate,
    CradleToGrave,
    GateToGate,
    FarmToFork,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AllocationMethod {
    Mass,
    Economic,
    SystemExpansion,
    Causal,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CharacterizationMethod {
    IpccAr6,
    IpccAr5,
    ReCiPe2016,
    ReCiPe2008,
    TRACI,
    CML,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum NormalizationMethod {
    AfricanContext,
    GlobalContext,
    EuropeanContext,
    None,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum WeightingMethod {
    AfricanPriorities,
    EqualWeights,
    ExpertJudgment,
    SocialPreferences,
    None,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Country {
    Ghana,
    Nigeria,
    Global,
}

impl std::fmt::Display for Country {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        match self {
            Country::Ghana => write!(f, "Ghana"),
            Country::Nigeria => write!(f, "Nigeria"),
            Country::Global => write!(f, "Global"),
        }
    }
}

impl Country {
    /// Get the currency code for this country
    pub fn currency_code(&self) -> &str {
        match self {
            Country::Ghana => "GHS",
            Country::Nigeria => "NGN",
            Country::Global => "USD",
        }
    }

    /// Get the currency symbol for this country
    pub fn currency_symbol(&self) -> &str {
        match self {
            Country::Ghana => "GH₵",
            Country::Nigeria => "₦",
            Country::Global => "$",
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum Currency {
    GHS, // Ghana Cedi
    NGN, // Nigerian Naira
    USD, // US Dollar (for global/comparison)
}

impl Currency {
    pub fn code(&self) -> &str {
        match self {
            Currency::GHS => "GHS",
            Currency::NGN => "NGN",
            Currency::USD => "USD",
        }
    }

    pub fn symbol(&self) -> &str {
        match self {
            Currency::GHS => "GH₵",
            Currency::NGN => "₦",
            Currency::USD => "$",
        }
    }

    pub fn from_country(country: &Country) -> Self {
        match country {
            Country::Ghana => Currency::GHS,
            Country::Nigeria => Currency::NGN,
            Country::Global => Currency::USD,
        }
    }
}

// ======================================================================
// LCA RESULTS STRUCTURE
// ======================================================================

/// One on-farm elementary flow, exposed so the Python engine can characterize it via
/// the validated canonical CFs (Option A: Rust = LCI kernel, Python = characterization).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LciFlow {
    pub substance: String,     // e.g. "N2O", "CH4", "CO2"
    pub quantity: f64,
    pub unit: String,
    pub compartment: String,   // "air" | "water" | "soil" | "resource"
    pub source: String,        // which input caused this emission
    /// "field" (direct on-farm emission or resource use), "upstream" (production of
    /// purchased inputs), "energy" (on-farm fuel/electricity combustion) or "aggregated"
    /// (pre-characterised CO2-eq). Python keeps "field" only; never parse `source`.
    #[serde(default)]
    pub category: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LCAResults {
    pub midpoint_impacts: HashMap<String, MidpointResult>,
    pub endpoint_impacts: HashMap<String, EndpointResult>,
    pub single_score: SingleScoreResult,
    pub data_quality: DataQuality,
    pub breakdown_by_food: HashMap<String, HashMap<String, MidpointResult>>,
    pub sensitivity_analysis: Option<SensitivityAnalysis>,
    pub comparative_analysis: Option<ComparativeAnalysis>,

    // Enhanced results for comprehensive assessments
    pub management_analysis: Option<ManagementAnalysis>,
    pub benchmarking: Option<BenchmarkingResults>,
    pub recommendations: Option<Vec<Recommendation>>,

    // On-farm LCI (elementary flows) for the Python characterization path.
    #[serde(default)]
    pub lci_inventory: Option<Vec<LciFlow>>,

    // Validation warnings raised while building the LCI (e.g. an unrecognised fertiliser
    // type that was given zero N). Surfaced by the Python engine in the assessment output.
    #[serde(default)]
    pub lci_warnings: Vec<String>,

    // Modelling disclosures (inferred rice water regime, default cultivation period,
    // methods declared but not modelled, ...). Reported as notes, not warnings.
    #[serde(default)]
    pub lci_notes: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MidpointResult {
    pub value: f64,
    pub unit: String,
    pub uncertainty_range: (f64, f64),
    pub data_quality_score: f64,
    pub contributing_sources: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EndpointResult {
    pub value: f64,
    pub unit: String,
    pub uncertainty_range: (f64, f64),
    pub normalization_factor: Option<f64>,
    pub regional_adaptation_factor: Option<f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SingleScoreResult {
    pub value: f64,
    pub unit: String,
    pub uncertainty_range: (f64, f64),
    pub weighting_factors: HashMap<String, f64>,
    pub methodology: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DataQuality {
    pub overall_confidence: ConfidenceLevel,
    pub data_source_mix: Vec<DataSourceContribution>,
    pub regional_adaptation: bool,
    pub completeness_score: f64,
    pub temporal_representativeness: f64,
    pub geographical_representativeness: f64,
    pub technological_representativeness: f64,
    pub warnings: Vec<String>,
    pub recommendations: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DataSourceContribution {
    pub source_type: DataSource,
    pub percentage: f64,
    pub quality_score: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum ConfidenceLevel {
    High,
    Medium,
    Low,
    VeryLow,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DataSource {
    CountrySpecific(Country),
    Regional(String),
    Global,
    Hybrid,
    Estimated,
}

// ======================================================================
// ENHANCED ANALYSIS RESULTS
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ManagementAnalysis {
    pub soil_health_score: f64, // 0-100
    pub fertilizer_efficiency: f64,
    pub water_use_efficiency: f64,
    pub pest_management_score: f64,
    pub sustainability_indicators: HashMap<String, f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BenchmarkingResults {
    pub farm_type_comparison: HashMap<String, f64>,
    pub regional_comparison: HashMap<String, f64>,
    pub performance_percentile: f64, // 0-100
    pub best_practices_identified: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Recommendation {
    pub category: RecommendationCategory,
    pub title: String,
    pub description: String,
    pub potential_impact_reduction: HashMap<String, f64>,
    pub implementation_difficulty: DifficultyLevel,
    pub cost_category: CostCategory,
    pub priority: Priority,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum RecommendationCategory {
    SoilManagement,
    WaterManagement,
    FertilizerOptimization,
    PestManagement,
    EnergyEfficiency,
    PostHarvest,
    CropSelection,
    SystemDesign,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum DifficultyLevel {
    Low,
    Medium,
    High,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum CostCategory {
    NoCost,
    LowCost,
    MediumCost,
    HighCost,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum Priority {
    High,
    Medium,
    Low,
}

// ======================================================================
// ANALYSIS SUPPORT STRUCTURES
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SensitivityAnalysis {
    pub most_influential_parameters: Vec<InfluentialParameter>,
    pub uncertainty_contributions: HashMap<String, f64>,
    pub scenario_analysis: Vec<ScenarioResult>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InfluentialParameter {
    pub parameter_name: String,
    pub influence_percentage: f64,
    pub current_uncertainty: f64,
    pub improvement_potential: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ScenarioResult {
    pub scenario_name: String,
    pub description: String,
    pub impact_changes: HashMap<String, f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComparativeAnalysis {
    pub benchmark_comparisons: Vec<BenchmarkComparison>,
    pub regional_comparisons: Vec<RegionalComparison>,
    pub best_practices: Vec<BestPractice>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BenchmarkComparison {
    pub benchmark_name: String,
    pub your_performance: f64,
    pub benchmark_value: f64,
    pub percentage_difference: f64,
    pub performance_category: PerformanceCategory,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegionalComparison {
    pub region_name: String,
    pub impact_ratios: HashMap<String, f64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BestPractice {
    pub practice_name: String,
    pub description: String,
    pub potential_impact_reduction: HashMap<String, f64>,
    pub implementation_difficulty: DifficultyLevel,
    pub cost_category: CostCategory,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PerformanceCategory {
    Excellent,
    Good,
    Average,
    BelowAverage,
    Poor,
}

// ======================================================================
// IMPACT FACTORS
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ImpactFactor {
    pub food_category: FoodCategory,
    pub country: Country,
    pub crop_type: Option<String>,
    pub impact_category: String,
    pub value_per_kg: f64,
    pub unit: String,
    pub confidence: ConfidenceLevel,
    pub source: String,
    pub year: i32,
    pub uncertainty_range: (f64, f64),
    pub pedigree_score: PedigreeScore,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PedigreeScore {
    pub reliability: u8,
    pub completeness: u8,
    pub temporal_correlation: u8,
    pub geographical_correlation: u8,
    pub technological_correlation: u8,
}

impl PedigreeScore {
    pub fn calculate_uncertainty_factor(&self) -> f64 {
        let indicators = [
            self.reliability,
            self.completeness,
            self.temporal_correlation,
            self.geographical_correlation,
            self.technological_correlation,
        ];
        
        let uncertainty_factors: [[f64; 5]; 5] = [
            [1.00, 1.05, 1.10, 1.20, 1.50],
            [1.00, 1.02, 1.05, 1.10, 1.20],
            [1.00, 1.03, 1.10, 1.20, 1.50],
            [1.00, 1.01, 1.02, 1.10, 1.50],
            [1.00, 1.05, 1.20, 1.50, 2.00],
        ];
        
        let mut total_variance = 0.0;
        for (i, &indicator) in indicators.iter().enumerate() {
            let factor = uncertainty_factors[i][(indicator - 1) as usize];
            total_variance += (factor.ln()).powi(2);
        }
        
        total_variance.sqrt().exp()
    }

    pub fn calculate_overall_quality_score(&self) -> f64 {
        let sum = self.reliability + self.completeness + self.temporal_correlation +
                  self.geographical_correlation + self.technological_correlation;
        1.0 - ((sum as f64 - 5.0) / 20.0)
    }
}

// ======================================================================
// CHARACTERIZATION FACTORS
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CharacterizationFactors {
    pub global_warming: GlobalWarmingFactors,
    pub water_scarcity: WaterScarcityFactors,
    pub biodiversity: BiodiversityFactors,
    pub soil_quality: SoilQualityFactors,
    pub human_health: HumanHealthFactors,
    pub resource_scarcity: ResourceScarcityFactors,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GlobalWarmingFactors {
    pub co2: f64,
    pub ch4_fossil: f64,
    pub ch4_biogenic: f64,
    pub n2o: f64,
    pub ch4_rice: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WaterScarcityFactors {
    pub ghana_aware: f64,
    pub nigeria_north_aware: f64,
    pub nigeria_south_aware: f64,
    pub global_average_aware: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BiodiversityFactors {
    pub intensive_msa: f64,
    pub extensive_msa: f64,
    pub agroforestry_msa: f64,
    pub natural_msa: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SoilQualityFactors {
    pub erosion_factor: f64,
    pub carbon_content_factor: f64,
    pub fertility_factor: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HumanHealthFactors {
    pub climate_health_africa: f64,
    pub water_stress_health_africa: f64,
    pub air_quality_health_africa: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceScarcityFactors {
    pub water_scarcity_africa: f64,
    pub land_scarcity_africa: f64,
    pub nutrient_scarcity_africa: f64,
}

/// DEPRECATED legacy Rust LCIA (USE_LEGACY_RUST_LCIA). The served path characterises the
/// kernel's `lci_inventory` in Python with the ecoinvent EF 3.1 / ReCiPe 2016 method packs.
/// The GWP100 values are kept on ONE basis, IPCC AR6 WG1 Ch 7 Table 7.15 (CH4 fossil 29.8,
/// CH4 non-fossil 27.0, N2O 273); rice CH4 is non-fossil. The other factors below are
/// unreviewed legacy screening values.
impl Default for CharacterizationFactors {
    fn default() -> Self {
        Self {
            global_warming: GlobalWarmingFactors {
                co2: 1.0,
                ch4_fossil: 29.8,
                ch4_biogenic: 27.0,
                n2o: 273.0,
                ch4_rice: 27.0,
            },
            water_scarcity: WaterScarcityFactors {
                ghana_aware: 20.0,
                nigeria_north_aware: 30.0,
                nigeria_south_aware: 15.0,
                global_average_aware: 1.0,
            },
            biodiversity: BiodiversityFactors {
                intensive_msa: 0.2,
                extensive_msa: 0.6,
                agroforestry_msa: 0.7,
                natural_msa: 1.0,
            },
            soil_quality: SoilQualityFactors {
                erosion_factor: 1.0,
                carbon_content_factor: 1.0,
                fertility_factor: 1.0,
            },
            human_health: HumanHealthFactors {
                climate_health_africa: 2.5e-7,
                water_stress_health_africa: 1.2e-7,
                air_quality_health_africa: 1.0e-6,
            },
            resource_scarcity: ResourceScarcityFactors {
                water_scarcity_africa: 0.18,
                land_scarcity_africa: 0.1,
                nutrient_scarcity_africa: 2.0,
            },
        }
    }
}