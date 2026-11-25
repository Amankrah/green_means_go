// Core Types for the Green Means Go LCA Assessment System

// Basic enums and country types
// UI-level countries. 'Global' is the backend country used for Canada (which is sent with
// region 'CA'); the api transform maps 'Canada' -> 'Global' before the request leaves.
export type Country = 'Ghana' | 'Nigeria' | 'Global' | 'Canada' | 'Senegal' | 'Burkina Faso' | 'South Africa';

export type FoodCategory = 
  | 'Cereals' 
  | 'Legumes' 
  | 'Vegetables' 
  | 'Fruits' 
  | 'Meat' 
  | 'Poultry' 
  | 'Fish' 
  | 'Dairy' 
  | 'Eggs' 
  | 'Oils' 
  | 'Nuts' 
  | 'Roots' 
  | 'Other';

// Backend API interfaces - simplified for core functionality
export interface FoodItem {
  id: string;
  name: string;
  quantity_kg: number;
  category: FoodCategory;
  origin_country?: string;
  crop_type?: string;
  production_system?: string;
  seasonal_factor?: string;
  variety?: string;
  area_allocated?: number;
  cropping_pattern?: string;
  intercropping_partners?: string[];
  post_harvest_losses?: number;
  seed_rate_kg_per_ha?: number;
  land_use_change?: { previous_land_use: string; years_since_conversion: number };
  residue_management?: {
    fraction_removed: number;
    fraction_burnt: number;
    removed_residue_use?: 'sold' | 'fed' | 'fed_to_own_livestock' | 'left_on_farm' | 'fuel' | 'other';
  };
  establishment?: { immature_years?: number; productive_years?: number; input_share?: number };
  /** Harvests per year on area_allocated (1-4); quantity_kg is the annual total. */
  crops_per_year?: number;
  /** Days from planting to harvest of one season (30-400). */
  growing_period_days?: number;
  planting_months?: number[];
  harvest_months?: number[];
  /** Previous crops in the rotation, most recent first. */
  rotation_sequence?: string[];
  water_regime?:
    | 'upland'
    | 'irrigated_continuously_flooded'
    | 'irrigated_single_drainage'
    | 'irrigated_multiple_drainage'
    | 'rainfed_regular'
    | 'rainfed_drought_prone'
    | 'deep_water';
  preseason_water_status?: 'non_flooded_lt_180d' | 'non_flooded_gt_180d' | 'flooded_gt_30d';
}

export type FertilizerApplicationMethodPayload =
  | 'broadcast'
  | 'incorporated'
  | 'band_placement'
  | 'side_dressing'
  | 'foliar'
  | 'fertigation';

export interface SoilManagementPayload {
  soil_type?: string;
  uses_compost: boolean;
  compost_source?: string;
  compost_application_rate?: number;
  conservation_practices: string[];
  soil_testing_frequency?: string;
  soil_ph?: number;
  organic_matter_pct?: number;
  cover_crops?: boolean;
  practices_adopted_years_ago?: number;
  lime_applications?: Array<{
    material: 'limestone' | 'dolomite';
    rate_t_per_ha_per_year: number;
    crop_ids: string[];
  }>;
  compost_crop_ids?: string[];
}

export interface FertilizerApplicationPayload {
  fertilizer_type: string;
  npk_ratio?: string;
  /** kg of PRODUCT per ha per application. */
  application_rate: number;
  applications_per_season: number;
  application_method?: FertilizerApplicationMethodPayload;
  brand_name?: string;
  crop_ids: string[];
  cost?: number;
}

export interface PesticideApplicationPayload {
  pesticide_type: string;
  active_ingredient: string;
  application_rate: number;
  applications_per_season: number;
  active_ingredient_content?: number;
  target_pests: string[];
  brand_name?: string;
  crop_ids: string[];
}

export interface ManagementPracticesPayload {
  soil_management: SoilManagementPayload;
  fertilization: {
    uses_fertilizers: boolean;
    fertilizer_applications: FertilizerApplicationPayload[];
    soil_test_based: boolean;
    follows_nutrient_plan: boolean;
    timing_strategy?: string;
  };
  water_management: {
    water_source: string[];
    irrigation_system?: string;
    irrigation_water_m3?: number;
    water_conservation_practices: string[];
    drainage_system?: string;
  };
  pest_management: {
    management_approach?: string;
    uses_ipm: boolean;
    pesticides: PesticideApplicationPayload[];
    pest_monitoring_frequency?: string;
    primary_pests?: string[];
    primary_diseases?: string[];
    ipm_practices?: string[];
    biological_controls?: string[];
    uses_economic_thresholds?: boolean;
  };
}

export interface AssessmentRequest {
  company_name: string;
  country: Country;
  foods: FoodItem[];
  region?: string;
  farm_id?: string; // attach the saved assessment to a Farm the user owns
  title?: string;   // human label for the saved assessment
  /** Opaque wizard snapshot so edit/re-run can restore the form exactly. */
  form_snapshot?: unknown;
  /** Optional LCIA method override (region default when omitted). */
  lcia_method?: string;
  /** Pedigree Monte Carlo uncertainty (API default true). */
  run_uncertainty?: boolean;
  study_meta?: { crop_year?: number; season?: string; admin_region?: string };
  farm_profile?: Record<string, unknown>; // Enhanced farm profile data
  management_practices?: ManagementPracticesPayload;
  equipment_energy?: {
    equipment: Array<{
      equipment_type: string;
      power_source: string;
      age: number;
      hours_per_year: number;
      fuel_efficiency?: number;
    }>;
    energy_sources: Array<{
      energy_type: string;
      monthly_consumption: number;
      primary_use: string;
      cost: number;
      currency?: string;
    }>;
    fuel_consumption: Array<{
      fuel_type: string;
      monthly_consumption: number;
      unit?: string;
      primary_use: string;
      cost: number;
    }>;
    storage?: {
      facilities: string[];
      capacity_tonnes?: number;
      refrigerant?: string;
      refrigerant_charge_kg?: number;
    };
  };
  logistics?: {
    packaging_material?: string;
    packaging_kg_per_tonne?: number;
    distance_to_market_km?: number;
    market_transport_mode?: string;
    input_transport_km?: number;
  };
}

// Assessment Results
export interface AssessmentResult {
  id: string;
  // Farm results carry company_name; processing results carry facility_profile instead.
  company_name?: string;
  farm_profile?: {
    farmer_name?: string;
    farm_name?: string;
    [k: string]: unknown;
  };
  facility_profile?: { facility_name?: string; [k: string]: unknown };
  country: string;
  assessment_date: string;
  midpoint_impacts: Record<string, MidpointResult>;
  endpoint_impacts: Record<string, EndpointResult>;
  single_score: SingleScoreResult;
  data_quality: DataQuality;
  // Present on farm results only — a processing result keys its breakdown by product.
  breakdown_by_food?: Record<string, Record<string, MidpointResult>>;
  breakdown_by_product?: Record<string, Record<string, MidpointResult>>;
  sensitivity_analysis?: SensitivityAnalysis;
  comparative_analysis?: ComparativeAnalysis;
  management_analysis?: ManagementAnalysis;
  benchmarking?: BenchmarkingResults;
  recommendations?: Recommendation[];
  /** Matched background processes (research / LCI transparency). */
  input_matches?: InputMatchRow[];
  contribution_by_source?: Record<string, Record<string, { value: number; unit?: string }>>;
  /** Dual FU block from the engine (per kg + per ha). */
  functional_units?: {
    per_kg?: { midpoint_impacts?: Record<string, MidpointResult>; total_kg?: number; note?: string; mixed_products?: boolean };
    per_ha?: { midpoint_impacts?: Record<string, MidpointResult> | null; total_ha?: number; kg_per_ha?: number | null; note?: string };
    land_intensity_note?: string;
    /** "per_ha" for farms with several different products (the farm per-kg is not a product footprint). */
    headline?: 'per_ha' | 'per_kg';
    per_crop?: Record<string, PerCropFunctionalUnit>;
  };
  /** Publication gate: background matches that need review before the result is published. */
  review_required?: boolean;
  review_items?: ReviewItem[];
  needs_review?: boolean;
  climate_zone_used?: string;
  /** Soil carbon change from management: reported separately, never in the headline. */
  soc_management?: SocManagement;
  per_crop_results?: unknown;
  baseline_assessment_id?: string;
  lcia_method?: string;
  provenance?: {
    engine?: string;
    engine_version?: string;
    schema_version?: string;
    lcia_method?: string;
    field_emission_model?: string;
    background_databases?: Array<{ name?: string; version?: string; license?: string }>;
    region?: string;
    generated_at?: string;
  };
  method_variants?: Record<
    string,
    {
      midpoint_impacts?: Record<string, MidpointResult>;
      single_score?: SingleScoreResult;
      methodology?: string;
    }
  >;
  uncertainty?: {
    n?: number;
    method?: string;
    gsd?: number;
    gsd_by_source?: Record<string, number>;
    basis?: string;
    percentiles?: Record<string, { p5: number; p50: number; p95: number; base?: number }>;
    single_score?: { p5: number; p50: number; p95: number };
  };
  study_meta?: {
    crop_year?: number;
    season?: string;
    admin_region?: string;
  };
  contribution_sankey?: {
    top_n?: number;
    categories?: Record<
      string,
      {
        unit?: string;
        sources?: Array<{ rank: number; source: string; value: number; share: number }>;
      }
    >;
  };
  review_status?: string;
}

export interface InputMatchRow {
  input?: string;
  name?: string;
  amount?: number;
  amount_unit?: string;
  unit?: string;
  matched?: string | { name?: string };
  ref_unit?: string;
  score?: number;
  estimated?: boolean;
  kind?: string;
}

export interface MidpointResult {
  value: number;
  unit: string;
  uncertainty_range: [number, number];
  data_quality_score: number;
  contributing_sources: string[];
}

export interface EndpointResult {
  value: number;
  unit: string;
  uncertainty_range: [number, number];
  normalization_factor?: number;
  regional_adaptation_factor?: number;
}

export interface SingleScoreResult {
  value: number;
  unit: string;
  /** Method-specific name of the score (EF 3.1 weighted / ReCiPe equal-weighted sum). */
  label?: string;
  /** "Low" | "Moderate" | "High", or "Unavailable" / "Not banded" (cutoffs null). */
  band?: string;
  band_basis?: string;
  band_cutoffs?: {
    low: number | null;
    high: number | null;
    calibrated?: boolean;
    benchmark_min?: number | null;
    benchmark_max?: number | null;
  };
  uncertainty_range: [number, number];
  weighting_factors: Record<string, number>;
  weighting_basis?: string;
  contributions?: Record<string, number>;
  normalised_midpoints?: Record<string, number>;
  methodology: string;
  iso_14044_disclosure?: string;
}

export interface PerCropFunctionalUnit {
  crop_id?: string;
  name?: string;
  quantity_kg?: number;
  area_ha?: number;
  midpoint_impacts_per_kg?: Record<string, { value: number; unit?: string }> | null;
  midpoint_impacts_per_ha?: Record<string, { value: number; unit?: string }> | null;
}

export interface ReviewItem {
  input?: string;
  matched?: string;
  uid?: string;
  reason?: string;
  excluded?: string | boolean | null;
}

export interface SocManagement {
  value?: number | null;
  unit?: string;
  booked?: boolean;
  reported_separately?: boolean;
  included_in_headline?: boolean;
  method?: string;
  sign_convention?: string;
  years_remaining_in_transition?: number | null;
  /** [low, high] kg CO2/yr when the IPCC input class is ambiguous (alternative class, not interpolated). */
  value_range?: [number, number] | number[] | null;
  climate?: string;
  soil_class?: string;
  per_crop?: Array<{
    crop?: string;
    area_ha?: number;
    value?: number | null;
    value_range?: [number, number] | number[] | null;
    delta_soc_t_c_per_ha_yr?: number | null;
    tillage?: string;
    input?: string;
    input_reason?: string;
    input_definition?: string;
    input_alternatives?: Array<{ input?: string; f_i?: number; value?: number; why?: string }>;
    note?: string;
  }>;
  assumptions?: string[];
}

export interface OneAtATimeCase {
  case: string;
  parameter?: string;
  value?: number;
  source?: string;
  global_warming_change_pct?: number | null;
  changes_pct?: Record<string, number>;
}

export interface MethodSensitivity {
  current_method?: string;
  alternative_method?: string;
  global_warming_current?: number | null;
  global_warming_alternative?: number | null;
  change_pct?: number | null;
  note?: string;
}

export interface DataQuality {
  overall_confidence: 'High' | 'Medium' | 'Low' | 'VeryLow';
  data_source_mix: DataSourceContribution[];
  regional_adaptation: boolean;
  completeness_score: number;
  temporal_representativeness: number;
  geographical_representativeness: number;
  technological_representativeness: number;
  warnings: string[];
  recommendations: string[];
}

export interface DataSourceContribution {
  source_type: DataSource;
  percentage: number;
  quality_score: number;
}

export type DataSource = 
  | { CountrySpecific: Country }
  | { Regional: string }
  | 'Global'
  | 'Estimated';

// Additional analysis types
export interface SensitivityAnalysis {
  most_influential_parameters?: InfluentialParameter[];
  uncertainty_contributions?: Record<string, number>;
  scenario_analysis?: ScenarioResult[];
  /** EF1 / FracLEACH at IPCC bounds and yield ±20 % (linear rescaling, no re-solve). */
  one_at_a_time?: OneAtATimeCase[];
  method_sensitivity?: MethodSensitivity | null;
  note?: string;
}

export interface InfluentialParameter {
  parameter_name: string;
  influence_percentage: number;
  current_uncertainty: number;
  improvement_potential: number;
}

export interface ScenarioResult {
  scenario_name: string;
  description: string;
  impact_changes: Record<string, number>;
}

export interface ComparativeAnalysis {
  benchmark_comparisons: BenchmarkComparison[];
  regional_comparisons: RegionalComparison[];
  best_practices: BestPractice[];
}

export interface BenchmarkComparison {
  benchmark_name: string;
  your_performance: number;
  benchmark_value: number;
  percentage_difference: number;
  performance_category: PerformanceCategory;
}

export enum PerformanceCategory {
  Excellent = 'Excellent',
  Good = 'Good',
  Average = 'Average',
  BelowAverage = 'BelowAverage'
}

export interface RegionalComparison {
  region_name: string;
  impact_ratios: Record<string, number>;
}

export interface BestPractice {
  practice_name: string;
  description: string;
  potential_impact_reduction: Record<string, number>;
  implementation_difficulty: DifficultyLevel;
  cost_category: CostCategory;
}

export enum DifficultyLevel {
  Low = 'Low',
  Medium = 'Medium',
  High = 'High'
}

export enum CostCategory {
  NoCost = 'NoCost',
  LowCost = 'LowCost', 
  MediumCost = 'MediumCost',
  HighCost = 'HighCost'
}

// Placeholder for additional analysis types (will be implemented later)
export interface ManagementAnalysis {
  [key: string]: unknown;
}

export interface BenchmarkingResults {
  [key: string]: unknown;
}

export interface Recommendation {
  id: string;
  title: string;
  description: string;
  priority: 'high' | 'medium' | 'low';
}

// Score interpretation for farmers
export type ScoreCategory = 
  | 'excellent' 
  | 'good' 
  | 'typical' 
  | 'above-average' 
  | 'high-impact';

export interface ScoreInterpretation {
  category: ScoreCategory;
  title: string;
  description: string;
  color: string;
  recommendations: string[];
}