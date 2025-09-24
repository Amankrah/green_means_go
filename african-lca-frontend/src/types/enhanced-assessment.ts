/**
 * Enhanced LCA Assessment Types for African Agricultural Systems
 * 
 * This implements standardized LCA data collection following ISO 14040/14044 
 * while being practical for African farmers. Covers all necessary system 
 * boundaries for accurate sustainability assessment.
 */

import { FoodCategory, Country } from './assessment';

// ======================================================================
// ENHANCED FARM PROFILE
// ======================================================================

export interface EnhancedFarmProfile {
  // Basic Information
  farmerName: string;
  farmName: string;
  country: Country;
  region: string; // Sub-national region (e.g., "Northern Region", "Kaduna State")
  coordinates?: {
    latitude: number;
    longitude: number;
  };
  
  // Farm Infrastructure
  totalFarmSize: number; // hectares
  farmingExperience: number; // years
  farmType: FarmType;
  primaryFarmingSystem: FarmingSystem;
  
  // Certification & Standards
  certifications: CertificationType[];
  participatesInPrograms: string[]; // e.g., ["Climate Smart Agriculture", "Organic Certification"]
}

export enum FarmType {
  SMALLHOLDER = "Smallholder", // < 2 hectares
  SMALL_SCALE = "SmallScale", // 2-5 hectares  
  MEDIUM_SCALE = "MediumScale", // 5-20 hectares
  COMMERCIAL = "Commercial", // > 20 hectares
  COOPERATIVE = "Cooperative",
  MIXED_LIVESTOCK = "MixedLivestock"
}

export enum FarmingSystem {
  SUBSISTENCE = "Subsistence",
  SEMI_COMMERCIAL = "Semi-commercial", 
  COMMERCIAL = "Commercial",
  ORGANIC = "Organic",
  AGROECOLOGICAL = "Agroecological",
  CONVENTIONAL = "Conventional",
  INTEGRATED_FARMING = "Integrated Farming System"
}

export enum CertificationType {
  ORGANIC = "Organic",
  FAIRTRADE = "Fair Trade",
  RAINFOREST_ALLIANCE = "Rainforest Alliance",
  GLOBAL_GAP = "GlobalGAP",
  NONE = "None"
}

// ======================================================================
// COMPREHENSIVE CROP PRODUCTION
// ======================================================================

export interface CropProduction {
  // Basic Crop Information
  cropId: string;
  cropName: string;
  localName?: string; // Local/vernacular name
  category: FoodCategory;
  variety: string; // Specific variety/cultivar
  
  // Production Details
  areaAllocated: number; // hectares for this crop
  annualProduction: number; // kg/year
  productionSystem: ProductionSystem;
  
  // Cropping Pattern
  croppingPattern: CroppingPattern;
  seasonality: SeasonalPattern;
  
  // Intercropping & Rotation
  isIntercropped: boolean;
  intercroppingPartners?: string[]; // Names of companion crops
  intercroppingRatio?: Record<string, number>; // Crop proportion ratios
  rotationSequence?: string[]; // Crops in rotation cycle
  rotationDuration: number; // years in rotation cycle
  
  // Yield & Quality
  averageYieldPerHectare: number; // kg/ha
  qualityGrades: QualityGrade[];
  postHarvestLosses: number; // percentage lost after harvest
}

export enum ProductionSystem {
  IRRIGATED = "Irrigated",
  RAINFED = "Rainfed", 
  MIXED_IRRIGATION = "Mixed (Irrigated + Rainfed)",
  GREENHOUSE = "Greenhouse/Protected",
  WETLAND = "Wetland/Lowland",
  UPLAND = "Upland/Highland"
}

export enum CroppingPattern {
  MONOCULTURE = "Monoculture",
  INTERCROPPING = "Intercropping",
  RELAY_CROPPING = "Relay Cropping",
  STRIP_CROPPING = "Strip Cropping",
  AGROFORESTRY = "Agroforestry",
  CROP_ROTATION = "Crop Rotation"
}

export interface SeasonalPattern {
  plantingMonths: number[]; // Month numbers (1-12)
  harvestingMonths: number[]; // Month numbers (1-12)  
  growingPeriod: number; // days from planting to harvest
  cropsPerYear: number; // Number of crops per year
  season: SeasonType[];
}

export enum SeasonType {
  WET_SEASON = "WetSeason",
  DRY_SEASON = "DrySeason", 
  HARMATTAN = "Harmattan",
  YEAR_ROUND = "YearRound"
}

export interface QualityGrade {
  grade: string; // e.g., "Grade A", "Export Quality"
  percentage: number; // Percentage of harvest in this grade
  priceMultiplier: number; // Price relative to base grade
}

// ======================================================================
// FARM MANAGEMENT PRACTICES
// ======================================================================

export interface FarmManagementPractices {
  // Soil Management
  soilManagement: SoilManagement;
  
  // Nutrient Management  
  fertilization: FertilizationPractices;
  
  // Water Management
  waterManagement: WaterManagement;
  
  // Pest & Disease Management
  pestManagement: PestManagement;
  
  // Tillage & Field Preparation
  tillageSystem: TillageSystem;
  
  // Harvesting & Post-harvest
  harvestingMethods: HarvestingMethods;
}

export interface SoilManagement {
  soilType: SoilType;
  soilpH: number;
  organicMatterContent: number; // percentage
  soilTestingFrequency: TestingFrequency;
  
  // Soil Conservation
  conservationPractices: SoilConservationPractice[];
  coverCrops: string[]; // Names of cover crops used
  compostUse: CompostUsage;
}

export enum SoilType {
  SANDY = "Sandy",
  CLAY = "Clay",
  LOAM = "Loam", 
  SANDY_LOAM = "Sandy Loam",
  CLAY_LOAM = "Clay Loam",
  SILT_LOAM = "Silt Loam",
  LATERITIC = "Lateritic",
  VOLCANIC = "Volcanic"
}

export enum TestingFrequency {
  NEVER = "Never",
  EVERY_5_YEARS = "Every 5+ years",
  EVERY_2_3_YEARS = "Every 2-3 years", 
  ANNUALLY = "Annually",
  TWICE_YEARLY = "Twice per year"
}

export enum SoilConservationPractice {
  CONTOUR_PLOWING = "Contour Plowing",
  TERRACING = "Terracing", 
  BUNDS = "Bunds/Ridges",
  TREE_PLANTING = "Tree Planting/Windbreaks",
  MULCHING = "Mulching",
  NO_TILL = "No-till",
  MINIMUM_TILL = "Minimum Tillage",
  NONE = "None"
}

export interface CompostUsage {
  usesCompost: boolean;
  compostsource: CompostSource;
  applicationRate?: number; // tons/hectare/year
  applicationTiming: string; // e.g., "Before planting", "Mid-season"
}

export enum CompostSource {
  FARM_MADE = "Farm-made compost",
  PURCHASED = "Purchased compost",
  ANIMAL_MANURE = "Animal manure",
  GREEN_WASTE = "Green waste/crop residues",
  MIXED = "Mixed sources",
  NONE = "Not used"
}

export interface FertilizationPractices {
  // Fertilizer Use
  usesFertilizers: boolean;
  fertilizerApplications: FertilizerApplication[];
  
  // Application Methods
  applicationMethod: ApplicationMethod;
  timingStrategy: TimingStrategy;
  
  // Nutrient Management
  soilTestBased: boolean;
  followsNutrientPlan: boolean;
}

export interface FertilizerApplication {
  fertilizerType: FertilizerType;
  brandName?: string;
  npkRatio?: string; // e.g., "15-15-15"
  applicationRate: number; // kg/hectare/season
  applicationsPerSeason: number;
  cost: number; // local currency per unit
}

export enum FertilizerType {
  NPK_COMPOUND = "NPK Compound",
  UREA = "Urea",
  DAP = "Diammonium Phosphate (DAP)",
  SINGLE_SUPER_PHOSPHATE = "Single Super Phosphate",
  MURIATE_OF_POTASH = "Muriate of Potash",
  ORGANIC_FERTILIZER = "Organic Fertilizer",
  BIO_FERTILIZER = "Bio-fertilizer",
  FOLIAR_FERTILIZER = "Foliar Fertilizer",
  NONE = "None"
}

export enum ApplicationMethod {
  BROADCAST = "Broadcasting",
  BAND_PLACEMENT = "Band Placement",
  SIDE_DRESSING = "Side Dressing", 
  FOLIAR_SPRAY = "Foliar Spray",
  FERTIGATION = "Fertigation",
  PRECISION_APPLICATION = "Precision Application"
}

export enum TimingStrategy {
  BEFORE_PLANTING = "Before Planting",
  AT_PLANTING = "At Planting",
  SPLIT_APPLICATION = "Split Application",
  BASED_ON_GROWTH_STAGE = "Based on Growth Stage",
  SOIL_TEST_BASED = "Soil Test Based",
  TRADITIONAL_TIMING = "Traditional Timing"
}

export interface WaterManagement {
  waterSource: WaterSource[];
  irrigationSystem?: IrrigationSystem;
  waterUseEfficiency: WaterEfficiencyPractice[];
  drainageSystem: boolean;
  waterConservationPractices: WaterConservationPractice[];
}

export enum WaterSource {
  RAINFALL = "Rainfall only",
  BOREHOLE = "Borehole",
  RIVER_STREAM = "River/Stream", 
  DAM_RESERVOIR = "Dam/Reservoir",
  WELL = "Well",
  MUNICIPAL_SUPPLY = "Municipal Water Supply"
}

export enum IrrigationSystem {
  NONE = "None (Rainfed)",
  FLOOD_IRRIGATION = "Flood Irrigation",
  FURROW_IRRIGATION = "Furrow Irrigation",
  SPRINKLER = "Sprinkler System",
  DRIP_IRRIGATION = "Drip Irrigation", 
  BUCKET_IRRIGATION = "Bucket/Manual Irrigation"
}

export enum WaterEfficiencyPractice {
  MULCHING = "Mulching",
  DRIP_IRRIGATION = "Drip Irrigation",
  SCHEDULING_OPTIMIZATION = "Irrigation Scheduling",
  DEFICIT_IRRIGATION = "Deficit Irrigation",
  RAINWATER_HARVESTING = "Rainwater Harvesting",
  NONE = "None"
}

export enum WaterConservationPractice {
  RAINWATER_HARVESTING = "Rainwater Harvesting",
  CONTOUR_BUNDS = "Contour Bunds",
  CHECK_DAMS = "Check Dams",
  WATER_RECYCLING = "Water Recycling",
  DROUGHT_RESISTANT_VARIETIES = "Drought Resistant Varieties",
  NONE = "None"
}

// ======================================================================
// PEST & DISEASE MANAGEMENT
// ======================================================================

export interface PestManagement {
  primaryPests: string[]; // Names of major pests encountered
  primaryDiseases: string[]; // Names of major diseases
  
  // Management Approach
  managementApproach: PestManagementApproach;
  pesticides: PesticideApplication[];
  
  // Integrated Pest Management
  usesIPM: boolean;
  ipmPractices: IPMPractice[];
  biologicalControls: string[]; // Natural enemies used
  
  // Monitoring & Scouting
  pestMonitoringFrequency: MonitoringFrequency;
  usesEconomicThresholds: boolean;
}

export enum PestManagementApproach {
  CHEMICAL_ONLY = "Chemical pesticides only",
  BIOLOGICAL_ONLY = "Biological control only",
  INTEGRATED_IPM = "Integrated Pest Management (IPM)",
  ORGANIC_METHODS = "Organic methods only",
  TRADITIONAL_METHODS = "Traditional/cultural methods",
  MINIMAL_INTERVENTION = "Minimal intervention"
}

export interface PesticideApplication {
  pesticideType: PesticideType;
  activeIngredient: string;
  brandName: string;
  applicationRate: number; // liters or kg per hectare
  applicationsPerSeason: number;
  targetPests: string[];
  cost: number; // local currency per application
  safetyPrecautions: SafetyPrecaution[];
}

export enum PesticideType {
  INSECTICIDE = "Insecticide",
  HERBICIDE = "Herbicide", 
  FUNGICIDE = "Fungicide",
  NEMATICIDE = "Nematicide",
  RODENTICIDE = "Rodenticide",
  BIO_PESTICIDE = "Bio-pesticide",
  ORGANIC_APPROVED = "Organic-approved pesticide"
}

export enum SafetyPrecaution {
  PPE_USED = "Personal Protective Equipment used",
  BUFFER_ZONES = "Buffer zones maintained",
  PRE_HARVEST_INTERVAL = "Pre-harvest interval observed", 
  TRAINED_APPLICATION = "Trained applicator used",
  PROPER_DISPOSAL = "Proper container disposal",
  NONE = "No specific precautions"
}

export enum IPMPractice {
  CROP_ROTATION = "Crop Rotation",
  COMPANION_PLANTING = "Companion Planting",
  BENEFICIAL_INSECTS = "Beneficial Insect Conservation",
  PHEROMONE_TRAPS = "Pheromone Traps",
  RESISTANT_VARIETIES = "Resistant Varieties",
  CULTURAL_CONTROLS = "Cultural Controls",
  MECHANICAL_CONTROLS = "Mechanical Controls"
}

export enum MonitoringFrequency {
  DAILY = "Daily",
  WEEKLY = "Weekly",
  BIWEEKLY = "Bi-weekly",
  MONTHLY = "Monthly", 
  WHEN_PROBLEMS_OCCUR = "Only when problems occur",
  NEVER = "Never"
}

// ======================================================================
// EQUIPMENT & ENERGY
// ======================================================================

export interface EquipmentEnergy {
  // Farm Equipment
  equipment: FarmEquipment[];
  
  // Energy Sources
  energySources: EnergyUsage[];
  
  // Fuel Consumption
  fuelConsumption: FuelUsage[];
  
  // Infrastructure
  infrastructure: FarmInfrastructure;
}

export interface FarmEquipment {
  equipmentType: EquipmentType;
  powerSource: PowerSource;
  age: number; // years
  hoursPerYear: number; // operating hours per year
  fuelEfficiency?: number; // liters per hour or km
  maintenanceFrequency: MaintenanceFrequency;
}

export enum EquipmentType {
  HAND_TOOLS = "Hand Tools",
  ANIMAL_TRACTION = "Animal-drawn implements", 
  SMALL_TRACTOR = "Small Tractor (<40HP)",
  MEDIUM_TRACTOR = "Medium Tractor (40-100HP)",
  LARGE_TRACTOR = "Large Tractor (>100HP)",
  COMBINE_HARVESTER = "Combine Harvester",
  THRESHER = "Thresher",
  PLANTER_SEEDER = "Planter/Seeder",
  SPRAYER = "Sprayer",
  WATER_PUMP = "Water Pump"
}

export enum PowerSource {
  MANUAL = "Manual/Human power",
  ANIMAL_POWER = "Animal power",
  DIESEL = "Diesel engine",
  PETROL = "Petrol engine",
  ELECTRIC = "Electric",
  SOLAR = "Solar powered"
}

export enum MaintenanceFrequency {
  DAILY = "Daily",
  WEEKLY = "Weekly", 
  MONTHLY = "Monthly",
  SEASONALLY = "Seasonally",
  ANNUALLY = "Annually",
  AS_NEEDED = "As needed"
}

export interface EnergyUsage {
  energyType: EnergyType;
  monthlyConsumption: number; // kWh or liters
  primaryUse: string; // e.g., "Irrigation", "Processing", "Storage"
  cost: number; // monthly cost in local currency
}

export enum EnergyType {
  GRID_ELECTRICITY = "Grid Electricity",
  DIESEL_GENERATOR = "Diesel Generator",
  SOLAR_PANELS = "Solar Panels", 
  BIOGAS = "Biogas",
  FIREWOOD = "Firewood",
  CHARCOAL = "Charcoal"
}

export interface FuelUsage {
  fuelType: FuelType;
  monthlyConsumption: number; // liters
  primaryUse: string;
  cost: number; // cost per liter
}

export enum FuelType {
  DIESEL = "Diesel",
  PETROL = "Petrol/Gasoline", 
  KEROSENE = "Kerosene",
  LPG = "Liquefied Petroleum Gas (LPG)"
}

export interface FarmInfrastructure {
  storageCapacity: number; // cubic meters or tons
  storageFacilities: StorageFacilityType[];
  processingFacilities: ProcessingFacilityType[];
  transportAccess: TransportAccess;
}

export enum StorageFacilityType {
  TRADITIONAL_GRANARY = "Traditional Granary",
  MODERN_WAREHOUSE = "Modern Warehouse",
  COLD_STORAGE = "Cold Storage",
  HERMETIC_STORAGE = "Hermetic Storage Bags",
  METAL_SILOS = "Metal Silos",
  NONE = "No dedicated storage"
}

export enum ProcessingFacilityType {
  DRYING_FACILITY = "Crop Drying Facility",
  MILLING_UNIT = "Milling Unit",
  PACKAGING_UNIT = "Packaging Unit", 
  CLEANING_UNIT = "Cleaning/Sorting Unit",
  NONE = "No processing facilities"
}

export interface TransportAccess {
  roadAccess: RoadAccessType;
  distanceToMarket: number; // kilometers
  transportMode: TransportMode[];
  transportCost: number; // cost per ton-km
}

export enum RoadAccessType {
  PAVED_ROAD = "Paved road to farm",
  GRAVEL_ROAD = "Gravel road to farm",
  DIRT_TRACK = "Dirt track access",
  NO_ROAD_ACCESS = "No direct road access"
}

export enum TransportMode {
  FOOT = "On foot/Head carrying",
  BICYCLE = "Bicycle",
  MOTORCYCLE = "Motorcycle",
  PICKUP_TRUCK = "Pickup truck",
  LARGE_TRUCK = "Large truck",
  PUBLIC_TRANSPORT = "Public transport"
}

// ======================================================================
// TILLAGE & HARVESTING SYSTEMS
// ======================================================================

export enum TillageSystem {
  CONVENTIONAL_TILLAGE = "Conventional Tillage",
  MINIMUM_TILLAGE = "Minimum Tillage",
  NO_TILL = "No-till/Zero Tillage",
  CONSERVATION_TILLAGE = "Conservation Tillage",
  RIDGE_TILLAGE = "Ridge Tillage",
  STRIP_TILLAGE = "Strip Tillage"
}

export interface HarvestingMethods {
  primaryMethod: HarvestingMethod;
  secondaryMethods: HarvestingMethod[];
  mechanizationLevel: MechanizationLevel;
  laborIntensity: LaborIntensity;
  postHarvestHandling: PostHarvestHandling[];
}

export enum HarvestingMethod {
  MANUAL_HARVESTING = "Manual harvesting",
  MECHANICAL_HARVESTING = "Mechanical harvesting",
  COMBINE_HARVESTER = "Combine harvester",
  SELECTIVE_HARVESTING = "Selective harvesting",
  STRIP_HARVESTING = "Strip harvesting"
}

export enum MechanizationLevel {
  FULLY_MANUAL = "Fully manual",
  PARTIALLY_MECHANIZED = "Partially mechanized",
  FULLY_MECHANIZED = "Fully mechanized"
}

export enum LaborIntensity {
  LOW = "Low labor intensity",
  MEDIUM = "Medium labor intensity",
  HIGH = "High labor intensity"
}

export enum PostHarvestHandling {
  FIELD_DRYING = "Field drying",
  MECHANICAL_DRYING = "Mechanical drying",
  CLEANING_SORTING = "Cleaning and sorting",
  GRADING = "Grading",
  PACKAGING = "Packaging",
  STORAGE = "Storage"
}

// ======================================================================
// ENHANCED ASSESSMENT REQUEST
// ======================================================================

export interface EnhancedAssessmentRequest {
  // Farm Profile
  farmProfile: EnhancedFarmProfile;
  
  // Crop Production Details
  cropProductions: CropProduction[];
  
  // Management Practices
  managementPractices: FarmManagementPractices;
  
  // Pest Management (separate from management practices in form)
  pestManagement: PestManagement;
  
  // Equipment & Energy
  equipmentEnergy: EquipmentEnergy;
  
  // Assessment Parameters
  assessmentParameters: AssessmentParameters;
}

export interface AssessmentParameters {
  functionalUnit: FunctionalUnit;
  systemBoundary: SystemBoundary;
  assessmentPeriod: number; // years
  includeUncertaintyAnalysis: boolean;
  includeSensitivityAnalysis: boolean;
  benchmarkComparison: boolean;
}

export enum FunctionalUnit {
  PER_KG_PRODUCT = "Per kg of product",
  PER_HECTARE = "Per hectare farmed",
  PER_FARM = "Per farm unit",
  PER_FARMER = "Per farmer household"
}

export enum SystemBoundary {
  CRADLE_TO_GATE = "Cradle-to-gate (production only)",
  CRADLE_TO_GRAVE = "Cradle-to-grave (including consumption)",
  FARM_TO_FORK = "Farm-to-fork",
  GATE_TO_GATE = "Gate-to-gate (farm operations only)"
}

// ======================================================================
// FORM VALIDATION & WIZARD STEPS
// ======================================================================

export enum FormStep {
  FARM_PROFILE = "farm-profile",
  CROP_DETAILS = "crop-details", 
  MANAGEMENT_PRACTICES = "management-practices",
  PEST_MANAGEMENT = "pest-management",
  EQUIPMENT_ENERGY = "equipment-energy",
  REVIEW_SUBMIT = "review-submit"
}

export interface FormValidationRules {
  [key: string]: {
    required?: boolean;
    min?: number;
    max?: number;
    pattern?: string;
    customValidation?: (value: any) => string | null;
  };
}