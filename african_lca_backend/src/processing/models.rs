use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use uuid::Uuid;
use chrono::{DateTime, Utc};
use crate::models::{Country, LCAMethodology, LCAResults, ConfidenceLevel, PedigreeScore};

// ======================================================================
// PROCESSING FACILITY PROFILE
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingFacilityProfile {
    pub facility_name: String,
    pub company_name: String,
    pub facility_type: ProcessingFacilityType,
    pub processing_capacity: f64, // tonnes per day
    pub operational_hours_per_day: f64,
    pub operational_days_per_year: u32,
    pub established_year: Option<u32>,
    pub certifications: Vec<String>,
    pub employee_count: Option<u32>,
    pub facility_size: Option<f64>, // m2
    pub location_type: LocationType,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProcessingFacilityType {
    Mill,
    Bakery,
    CassivaProcessing,
    RiceProcessing,
    PalmOilMill,
    CocoaProcessing,
    FishProcessing,
    MeatProcessing,
    DairyProcessing,
    FruitProcessing,
    VegetableProcessing,
    General,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum LocationType {
    Urban,
    PeriUrban,
    Rural,
    Industrial,
}

// ======================================================================
// PROCESSING OPERATIONS
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingOperations {
    pub energy_management: EnergyManagement,
    pub water_management: WaterManagement,
    pub waste_management: WasteManagement,
    pub raw_material_sourcing: RawMaterialSourcing,
    pub equipment_efficiency: EquipmentEfficiency,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnergyManagement {
    pub primary_energy_source: EnergySource,
    pub secondary_energy_sources: Vec<EnergySource>,
    pub monthly_electricity_consumption: Option<f64>, // kWh
    pub monthly_fuel_consumption: Option<f64>, // liters
    pub fuel_type: Option<String>,
    pub renewable_energy_percentage: f64,
    pub energy_efficiency_measures: Vec<String>,
    pub backup_generator: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum EnergySource {
    GridElectricity,
    DieselGenerator,
    SolarPower,
    Biomass,
    LPG,
    NaturalGas,
    HydroElectricity,
    WindPower,
    Mixed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WaterManagement {
    pub water_source: Vec<String>,
    pub monthly_water_consumption: Option<f64>, // m3
    pub water_treatment: WaterTreatment,
    pub water_conservation_measures: Vec<String>,
    pub wastewater_treatment: WastewaterTreatment,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum WaterTreatment {
    None,
    BasicFiltration,
    ChemicalTreatment,
    ReverseOsmosis,
    Comprehensive,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum WastewaterTreatment {
    None,
    BasicSedimentation,
    BiologicalTreatment,
    ChemicalTreatment,
    Advanced,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WasteManagement {
    pub solid_waste_generation: Option<f64>, // kg/day
    pub organic_waste_percentage: f64,
    pub waste_disposal_method: WasteDisposalMethod,
    pub recycling_programs: Vec<String>,
    pub byproduct_utilization: Vec<ByproductUtilization>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum WasteDisposalMethod {
    Landfill,
    Incineration,
    Composting,
    AnaerobicDigestion,
    Recycling,
    Mixed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ByproductUtilization {
    pub byproduct_name: String,
    pub utilization_method: String,
    pub percentage_utilized: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawMaterialSourcing {
    pub local_sourcing_percentage: f64,
    pub average_transport_distance: f64, // km
    pub transport_mode: TransportMode,
    pub supplier_sustainability_practices: Vec<String>,
    pub seasonal_variation: bool,
    pub storage_practices: StoragePractices,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TransportMode {
    Truck,
    Rail,
    Ship,
    Mixed,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoragePractices {
    pub storage_type: String,
    pub climate_control: bool,
    pub pest_control_methods: Vec<String>,
    pub storage_loss_percentage: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EquipmentEfficiency {
    pub equipment_age: EquipmentAge,
    pub maintenance_frequency: MaintenanceFrequency,
    pub automation_level: AutomationLevel,
    pub equipment_utilization_rate: f64, // percentage
    pub modernization_investments: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum EquipmentAge {
    New, // < 2 years
    Recent, // 2-5 years
    Mature, // 5-10 years
    Old, // 10-20 years
    VeryOld, // > 20 years
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MaintenanceFrequency {
    Daily,
    Weekly,
    Monthly,
    Quarterly,
    Biannual,
    Annual,
    Irregular,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum AutomationLevel {
    Manual,
    SemiAutomated,
    HighlyAutomated,
    FullyAutomated,
}

// ======================================================================
// PROCESSED PRODUCTS
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessedProduct {
    pub id: String,
    pub name: String,
    pub product_type: ProductType,
    pub annual_production: f64, // tonnes
    pub raw_material_inputs: Vec<RawMaterialInput>,
    pub processing_steps: Vec<ProcessingStep>,
    pub packaging: PackagingInfo,
    pub quality_grade: QualityGrade,
    pub market_destination: MarketDestination,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProductType {
    FlourMaize,
    FlourWheat,
    FlourCassava,
    FlourPlantain,
    RiceProcessed,
    PalmOil,
    CocoaPowder,
    CocoaButter,
    BakedGoods,
    ProcessedFish,
    ProcessedMeat,
    Dairy,
    FruitJuice,
    DriedFruits,
    Other(String),
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawMaterialInput {
    pub material_name: String,
    pub quantity_per_tonne_output: f64, // kg
    pub source_location: Option<String>,
    pub quality_requirements: Vec<String>,
    pub seasonal_availability: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingStep {
    pub step_name: String,
    pub energy_intensity: f64, // kWh per tonne
    pub water_usage: f64, // liters per tonne
    pub duration: f64, // hours
    pub yield_efficiency: f64, // percentage
    pub emissions_factor: Option<f64>, // kg CO2-eq per tonne
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PackagingInfo {
    pub packaging_material: PackagingMaterial,
    pub package_size: f64, // kg
    pub packaging_weight_per_unit: f64, // kg
    pub recyclable: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PackagingMaterial {
    PlasticBag,
    PaperBag,
    Jute,
    Polypropylene,
    Cardboard,
    Metal,
    Glass,
    Composite,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum QualityGrade {
    Premium,
    Standard,
    Basic,
    Industrial,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MarketDestination {
    Local,
    Regional,
    National,
    Export,
    Mixed,
}

// ======================================================================
// PROCESSING ASSESSMENT STRUCTURE
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingAssessment {
    pub id: Uuid,
    pub facility_profile: ProcessingFacilityProfile,
    pub processing_operations: ProcessingOperations,
    pub processed_products: Vec<ProcessedProduct>,
    pub country: Country,
    pub region: Option<String>,
    pub assessment_date: DateTime<Utc>,
    pub methodology: LCAMethodology,
    pub results: Option<LCAResults>,
}

// ======================================================================
// PROCESSING-SPECIFIC IMPACT FACTORS
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingImpactFactor {
    pub facility_type: ProcessingFacilityType,
    pub product_type: ProductType,
    pub country: Country,
    pub impact_category: String,
    pub value_per_tonne: f64,
    pub unit: String,
    pub confidence: ConfidenceLevel,
    pub source: String,
    pub year: i32,
    pub uncertainty_range: (f64, f64),
    pub pedigree_score: PedigreeScore,
}

// ======================================================================
// PROCESSING BENCHMARKING
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingBenchmark {
    pub facility_type: ProcessingFacilityType,
    pub capacity_range: CapacityRange,
    pub country: Country,
    pub benchmarks: HashMap<String, ProcessingBenchmarkValue>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CapacityRange {
    Small,   // < 10 tonnes/day
    Medium,  // 10-100 tonnes/day
    Large,   // 100-1000 tonnes/day
    VeryLarge, // > 1000 tonnes/day
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingBenchmarkValue {
    pub best_practice: f64,
    pub average: f64,
    pub worst_practice: f64,
    pub unit: String,
}

// ======================================================================
// PROCESSING RECOMMENDATIONS
// ======================================================================

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProcessingRecommendation {
    pub category: ProcessingRecommendationCategory,
    pub title: String,
    pub description: String,
    pub potential_savings: HashMap<String, f64>,
    pub implementation_cost: ImplementationCost,
    pub payback_period: Option<f64>, // months
    pub complexity: ComplexityLevel,
    pub priority: Priority,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ProcessingRecommendationCategory {
    EnergyEfficiency,
    WaterConservation,
    WasteReduction,
    ProcessOptimization,
    RawMaterialSourcing,
    EquipmentUpgrade,
    RenewableEnergy,
    WasteToEnergy,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum ImplementationCost {
    Low,     // < $1,000
    Medium,  // $1,000 - $10,000
    High,    // $10,000 - $100,000
    VeryHigh, // > $100,000
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum ComplexityLevel {
    Simple,
    Moderate,
    Complex,
    VeryComplex,
}

#[derive(Debug, Clone, Copy, Serialize, Deserialize)]
pub enum Priority {
    Critical,
    High,
    Medium,
    Low,
}
