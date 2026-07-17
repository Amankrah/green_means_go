// Shape of GET /assess/{id}/recommendations — the deterministic, costed action plan.
// Mirrors engine/recommend/serialize.py::recommendation_to_dict. Every number here is
// produced by the engine; the chat only explains it.

export type Horizon = 'quick_win' | 'medium' | 'strategic';
export type EffectBasis = 'measured' | 'modelled' | 'expert_judgement';
export type CostTier = 'NoCost' | 'LowCost' | 'MediumCost' | 'HighCost';
export type Affordability = 'affordable' | 'needs_finance' | 'unknown';

export interface MeasureEffect {
  value: number;                 // signed fraction; negative = impact reduction
  unit: string;
  basis: EffectBasis;
  uncertainty: [number, number] | null;
  yield_effect: number | null;
  note: string;
}

export interface MeasureEconomics {
  capex_ghs: number | null;
  annual_saving_ghs: number | null;  // signed: +ve saving, -ve net cost, null = not estimable
  payback_months: number | null;
  cost_tier: CostTier;
  affordability: Affordability;
  currency: string;
}

export interface MeasureProvenance {
  source: string;
  citation: string;
  span: string;
  publication_date: string | null;
  licence: string;
}

export interface RecommendationMeasure {
  id: string;
  title: string;
  action: string;
  targets_source: string;        // the assessment source this measure acts on
  targets_share: number;         // that source's share of climate impact [0..1]
  impact_category: string;
  horizon: Horizon;
  effect: MeasureEffect;
  economics: MeasureEconomics;
  provenance: MeasureProvenance;
  reviewed: boolean;             // false until an agronomist signs the measure off
  data_gaps: string[];
}

export interface RevenueLine {
  crop: string;
  quantity_kg: number;
  price_ghs_per_kg: number | null;
  revenue_ghs: number | null;
  price_source: string;
  priced: boolean;
}

export interface RevenueEstimate {
  total_ghs: number | null;
  currency: string;
  basis: string;                 // "derived from prices" | "user-provided" | "unknown"
  unit_assumption: string;
  priced_fraction: number;
  stale_prices: boolean;
  lines: RevenueLine[];
  gaps: string[];
}

export interface ActionPhase {
  key: 'start_now' | 'this_year' | 'plan_ahead';
  label: string;
  measures: RecommendationMeasure[];
}

export interface RecommendationsResponse {
  assessment_id: string | null;
  generated_at: string | null;
  pending_review: boolean;
  disclaimer: string;
  revenue: RevenueEstimate;
  plan: { phases: ActionPhase[] };
  measures: RecommendationMeasure[];
}
