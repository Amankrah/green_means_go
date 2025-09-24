// Core Types for the African LCA Assessment System

// Basic enums and country types
export type Country = 'Ghana' | 'Nigeria' | 'Global';

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
  farm_profile?: any;
  management_practices?: any;
}

export interface AssessmentRequest {
  company_name: string;
  country: Country;
  foods: FoodItem[];
  region?: string;
  farm_profile?: any; // Enhanced farm profile data
  management_practices?: any; // Enhanced management practices data
}

// Assessment Results
export interface AssessmentResult {
  id: string;
  company_name: string;
  country: string;
  assessment_date: string;
  midpoint_impacts: Record<string, MidpointResult>;
  endpoint_impacts: Record<string, EndpointResult>;
  single_score: SingleScoreResult;
  data_quality: DataQuality;
  breakdown_by_food: Record<string, Record<string, MidpointResult>>;
  sensitivity_analysis?: SensitivityAnalysis;
  comparative_analysis?: ComparativeAnalysis;
  management_analysis?: ManagementAnalysis;
  benchmarking?: BenchmarkingResults;
  recommendations?: Recommendation[];
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
  uncertainty_range: [number, number];
  weighting_factors: Record<string, number>;
  methodology: string;
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
  most_influential_parameters: InfluentialParameter[];
  uncertainty_contributions: Record<string, number>;
  scenario_analysis: ScenarioResult[];
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