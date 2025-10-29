use crate::models::*;
use crate::production::lci::LCICalculator;
use crate::production::lci_extended::LCIExtendedCharacterization;
use std::collections::HashMap;
use log::{info, warn};


pub struct AfricanLCAEngine {
    impact_factors: HashMap<String, ImpactFactor>,
    characterization_factors: CharacterizationFactors,
    regional_factors: HashMap<String, f64>,
    climate_adjustments: HashMap<String, f64>,
    methodology: LCAMethodology,
    lci_calculator: LCICalculator, // NEW: ISO-compliant inventory calculator
}

impl AfricanLCAEngine {
    pub fn new(methodology: LCAMethodology) -> Self {
        Self {
            impact_factors: HashMap::new(),
            characterization_factors: CharacterizationFactors::default(),
            regional_factors: HashMap::new(),
            climate_adjustments: HashMap::new(),
            methodology,
            lci_calculator: LCICalculator::new(), // Initialize LCI calculator
        }
    }

    pub fn load_impact_factors(&mut self, factors: Vec<ImpactFactor>) {
        for factor in factors {
            // Create hierarchical key for factor lookup
            let key = self.create_factor_key(&factor);
            self.impact_factors.insert(key, factor);
        }
        info!("Loaded {} impact factors", self.impact_factors.len());
    }

    pub fn load_regional_factors(&mut self, factors: HashMap<String, f64>) {
        self.regional_factors = factors;
    }

    pub fn load_climate_adjustments(&mut self, adjustments: HashMap<String, f64>) {
        self.climate_adjustments = adjustments;
    }

    fn create_factor_key(&self, factor: &ImpactFactor) -> String {
        match &factor.crop_type {
            Some(crop) => format!("{:?}_{:?}_{}_{}", 
                factor.food_category, factor.country, crop, factor.impact_category),
            None => format!("{:?}_{:?}_{}", 
                factor.food_category, factor.country, factor.impact_category),
        }
    }

    pub fn perform_comprehensive_assessment(&mut self, assessment: &mut Assessment) -> Result<(), Box<dyn std::error::Error>> {
        info!("Starting comprehensive LCA assessment for {} using {:?}",
              assessment.company_name, self.methodology.characterization_method);

        // DEBUG: Log equipment_energy data
        if let Some(ref eq_energy) = assessment.equipment_energy {
            info!("🔧 Equipment/Energy data received:");
            info!("  - Equipment items: {}", eq_energy.equipment.len());
            info!("  - Energy sources: {}", eq_energy.energy_sources.len());
            info!("  - Fuel consumption items: {}", eq_energy.fuel_consumption.len());
            for fuel in &eq_energy.fuel_consumption {
                info!("    * Fuel: {} - {} liters/month - {}",
                      fuel.fuel_type, fuel.monthly_consumption, fuel.primary_use);
            }
        } else {
            warn!("⚠️ No equipment_energy data found in assessment!");
        }

        // NEW ISO 14040/14044 METHODOLOGY:
        // Step 1: Calculate Life Cycle Inventory (LCI) from user inputs
        info!("Step 1: Calculating Life Cycle Inventory (LCI) from user inputs");
        let inventory = self.lci_calculator.calculate_inventory(assessment)?;

        info!("LCI generated {} inventory items:", inventory.len());
        for (key, item) in &inventory {
            info!("  - {}: {:.2} {} ({})", key, item.quantity, item.unit, item.source);
        }

        // Step 2: Calculate midpoint impacts from LCI (characterization)
        info!("Step 2: Calculating midpoint impacts from LCI with extended characterization");
        let mut midpoint_impacts = self.lci_calculator.calculate_extended_midpoint_impacts(&inventory, assessment)?;

        // Step 3: Apply additional regional adjustments and factors
        info!("Step 3: Applying regional adjustments");
        self.apply_regional_adjustments(&mut midpoint_impacts, &assessment.country, &assessment.region);

        // Step 4: Calculate per-crop breakdown (if needed for detailed analysis)
        let mut breakdown_by_food = HashMap::new();
        for food in &assessment.foods {
            // For breakdown, we still use the enhanced calculation but now it's supplementary
            let mut food_results = self.calculate_enhanced_food_impacts(food, &assessment.country, &assessment.region)?;

            // Apply management practice adjustments if available
            if let Some(ref management_practices) = assessment.management_practices {
                self.apply_management_practice_adjustments(&mut food_results, management_practices, food)?;
            }

            breakdown_by_food.insert(
                format!("{} ({}kg)", food.name, food.quantity_kg),
                food_results
            );
        }

        // Calculate endpoint impacts with enhanced methodology
        let endpoint_impacts = self.calculate_enhanced_endpoint_impacts(&midpoint_impacts)?;

        // Calculate single score with African-adapted normalization and weighting
        let single_score = self.calculate_enhanced_single_score(&endpoint_impacts)?;

        // Perform comprehensive data quality assessment
        let data_quality = self.assess_data_quality(&assessment.foods, &assessment.country)?;

        // Perform sensitivity analysis
        let sensitivity_analysis = self.perform_sensitivity_analysis(&assessment.foods, &assessment.country)?;

        // Generate comparative analysis with management practice recommendations
        let comparative_analysis = self.generate_comprehensive_comparative_analysis(&midpoint_impacts, &assessment.country, &assessment.foods)?;

        // Store enhanced results
        assessment.results = Some(LCAResults {
            midpoint_impacts,
            endpoint_impacts,
            single_score,
            data_quality,
            breakdown_by_food,
            sensitivity_analysis: Some(sensitivity_analysis),
            comparative_analysis: Some(comparative_analysis),
            management_analysis: None, // TODO: Implement management analysis
            benchmarking: None, // TODO: Implement benchmarking
            recommendations: None, // TODO: Implement recommendations
        });

        info!("Comprehensive assessment completed for {}", assessment.company_name);
        Ok(())
    }

    pub fn perform_assessment(&mut self, assessment: &mut Assessment) -> Result<(), Box<dyn std::error::Error>> {
        info!("Starting enhanced LCA assessment for {} using {:?}",
              assessment.company_name, self.methodology.characterization_method);

        // NEW ISO 14040/14044 METHODOLOGY:
        // If we have management practices data, use the ISO-compliant LCI approach
        if assessment.management_practices.is_some() {
            info!("Management practices data available - using ISO-compliant LCI methodology");
            return self.perform_comprehensive_assessment(assessment);
        }

        // Otherwise, fall back to hybrid approach (LCI + category factors)
        info!("Limited data available - using hybrid LCI + category factors methodology");

        // Step 1: Calculate what we can from LCI with extended characterization
        let inventory = self.lci_calculator.calculate_inventory(assessment)?;
        let mut midpoint_impacts = self.lci_calculator.calculate_extended_midpoint_impacts(&inventory, assessment)?;

        // Step 2: For missing data, supplement with category-level factors
        let mut breakdown_by_food = HashMap::new();
        for food in &assessment.foods {
            let food_results = self.calculate_enhanced_food_impacts(food, &assessment.country, &assessment.region)?;

            breakdown_by_food.insert(
                format!("{} ({}kg)", food.name, food.quantity_kg),
                food_results.clone()
            );

            // Only aggregate categories that weren't calculated from LCI
            for (category, result) in food_results {
                if let Some(total_result) = midpoint_impacts.get_mut(&category) {
                    // If LCI didn't calculate this impact, use the category factor
                    if total_result.value == 0.0 {
                        self.aggregate_midpoint_results(total_result, &result);
                    }
                }
            }
        }

        // Apply regional adjustments
        self.apply_regional_adjustments(&mut midpoint_impacts, &assessment.country, &assessment.region);

        // Calculate endpoint impacts with enhanced methodology
        let endpoint_impacts = self.calculate_enhanced_endpoint_impacts(&midpoint_impacts)?;

        // Calculate single score with African-adapted normalization and weighting
        let single_score = self.calculate_enhanced_single_score(&endpoint_impacts)?;

        // Perform comprehensive data quality assessment
        let data_quality = self.assess_data_quality(&assessment.foods, &assessment.country)?;

        // Perform sensitivity analysis
        let sensitivity_analysis = self.perform_sensitivity_analysis(&assessment.foods, &assessment.country)?;

        // Generate comparative analysis
        let comparative_analysis = self.generate_comparative_analysis(&midpoint_impacts, &assessment.country)?;

        // Store enhanced results
        assessment.results = Some(LCAResults {
            midpoint_impacts,
            endpoint_impacts,
            single_score,
            data_quality,
            breakdown_by_food,
            sensitivity_analysis: Some(sensitivity_analysis),
            comparative_analysis: Some(comparative_analysis),
            management_analysis: None, // TODO: Implement management analysis
            benchmarking: None, // TODO: Implement benchmarking
            recommendations: None, // TODO: Implement recommendations
        });

        info!("Enhanced assessment completed for {}", assessment.company_name);
        Ok(())
    }

    fn get_impact_categories(&self) -> Vec<String> {
        vec![
            "Global warming".to_string(),
            "Water consumption".to_string(),
            "Water scarcity".to_string(), // New: AWARE-adjusted water use
            "Land use".to_string(),
            "Biodiversity loss".to_string(), // New: MSA-based assessment
            "Soil degradation".to_string(), // New: soil quality impacts
            "Terrestrial acidification".to_string(),
            "Freshwater eutrophication".to_string(),
            "Marine eutrophication".to_string(),
            "Fossil depletion".to_string(),
            "Mineral depletion".to_string(),
            "Particulate matter formation".to_string(), // New: air quality
            "Photochemical oxidation".to_string(),
        ]
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

    fn calculate_enhanced_food_impacts(
        &self, 
        food: &FoodItem, 
        country: &Country, 
        _region: &Option<String>
    ) -> Result<HashMap<String, MidpointResult>, Box<dyn std::error::Error>> {
        
        let mut impacts = HashMap::new();
        let impact_categories = self.get_impact_categories();

        // Hierarchical data lookup: specific crop -> category -> global fallback
        let lookup_hierarchy = self.build_lookup_hierarchy(food, country);

        for category in &impact_categories {
            let (factor_value, factor_source, uncertainty, pedigree) = 
                self.find_best_factor(food, country, category, &lookup_hierarchy)?;

            // Calculate per-unit impact first (factor_value is already per kg)
            let per_unit_impact = factor_value;

            // Apply climate adjustments for tropical conditions (per unit)
            let climate_adjusted_per_unit = self.apply_climate_adjustments(per_unit_impact, category, food);

            // Apply seasonal adjustments if applicable (per unit)
            let seasonally_adjusted_per_unit = self.apply_seasonal_adjustments(climate_adjusted_per_unit, food);

            // Apply production system adjustments (per unit)
            let system_adjusted_per_unit = self.apply_production_system_adjustments(seasonally_adjusted_per_unit, food);

            // Scale to total impact for display purposes
            let total_impact = system_adjusted_per_unit * food.quantity_kg;

            // Calculate uncertainty range (scaled to total)
            let uncertainty_range = self.calculate_uncertainty_range(
                total_impact, 
                uncertainty, 
                &pedigree
            );

            impacts.insert(category.clone(), MidpointResult {
                value: total_impact,
                unit: self.get_impact_unit(category),
                uncertainty_range,
                data_quality_score: pedigree.calculate_overall_quality_score(),
                contributing_sources: vec![factor_source],
            });
        }

        Ok(impacts)
    }

    #[allow(dead_code)]
    fn calculate_per_unit_food_impacts(
        &self, 
        food: &FoodItem, 
        country: &Country, 
        _region: &Option<String>
    ) -> Result<HashMap<String, MidpointResult>, Box<dyn std::error::Error>> {
        
        let mut impacts = HashMap::new();
        let impact_categories = self.get_impact_categories();

        // Hierarchical data lookup: specific crop -> category -> global fallback
        let lookup_hierarchy = self.build_lookup_hierarchy(food, country);

        for category in &impact_categories {
            let (factor_value, factor_source, uncertainty, pedigree) = 
                self.find_best_factor(food, country, category, &lookup_hierarchy)?;

            // Calculate per-unit impact (factor_value is already per kg)
            let per_unit_impact = factor_value;

            // Apply climate adjustments for tropical conditions (per unit)
            let climate_adjusted_per_unit = self.apply_climate_adjustments(per_unit_impact, category, food);

            // Apply seasonal adjustments if applicable (per unit)
            let seasonally_adjusted_per_unit = self.apply_seasonal_adjustments(climate_adjusted_per_unit, food);

            // Apply production system adjustments (per unit)
            let system_adjusted_per_unit = self.apply_production_system_adjustments(seasonally_adjusted_per_unit, food);

            // Calculate per-unit uncertainty range
            let uncertainty_value = (uncertainty.1 - uncertainty.0) / (2.0 * system_adjusted_per_unit).max(0.001);
            let per_unit_uncertainty_range = self.calculate_per_unit_uncertainty_range(
                system_adjusted_per_unit, 
                uncertainty_value, 
                &pedigree
            );

            impacts.insert(category.clone(), MidpointResult {
                value: system_adjusted_per_unit,
                unit: format!("{} per kg", self.get_impact_unit(category)),
                uncertainty_range: per_unit_uncertainty_range,
                data_quality_score: pedigree.calculate_overall_quality_score(),
                contributing_sources: vec![factor_source],
            });
        }

        Ok(impacts)
    }

    fn calculate_per_unit_uncertainty_range(
        &self,
        base_value: f64,
        uncertainty: f64,
        pedigree: &PedigreeScore
    ) -> (f64, f64) {
        // Calculate uncertainty range for per-unit values
        let combined_uncertainty = (uncertainty.powi(2) + 
            (pedigree.reliability as f64 * 0.1).powi(2) + 
            (pedigree.completeness as f64 * 0.05).powi(2) + 
            (pedigree.temporal_correlation as f64 * 0.03).powi(2) + 
            (pedigree.geographical_correlation as f64 * 0.07).powi(2) + 
            (pedigree.technological_correlation as f64 * 0.04).powi(2)).sqrt();
        
        let lower = base_value * (1.0 - combined_uncertainty);
        let upper = base_value * (1.0 + combined_uncertainty);
        
        (lower.max(0.0), upper)
    }

    fn build_lookup_hierarchy(&self, food: &FoodItem, country: &Country) -> Vec<String> {
        let mut hierarchy = Vec::new();

        // 1. Most specific: Country + Crop type + Category
        if let Some(crop_type) = &food.crop_type {
            hierarchy.push(format!("{:?}_{:?}_{}", food.category, country, crop_type));
        }

        // 2. Country + Category
        hierarchy.push(format!("{:?}_{:?}", food.category, country));

        // 3. Global + Crop type
        if let Some(crop_type) = &food.crop_type {
            hierarchy.push(format!("{:?}_Global_{}", food.category, crop_type));
        }

        // 4. Global + Category
        hierarchy.push(format!("{:?}_Global", food.category));

        hierarchy
    }

    fn find_best_factor(
        &self,
        food: &FoodItem,
        _country: &Country,
        category: &str,
        hierarchy: &[String]
    ) -> Result<(f64, String, (f64, f64), PedigreeScore), Box<dyn std::error::Error>> {
        
        // Try to find factor following the hierarchy
        for base_key in hierarchy {
            let full_key = format!("{}_{}", base_key, category);
            if let Some(factor) = self.impact_factors.get(&full_key) {
                return Ok((
                    factor.value_per_kg,
                    factor.source.clone(),
                    factor.uncertainty_range,
                    factor.pedigree_score.clone(),
                ));
            }
        }

        // Fallback to default values with high uncertainty
        let default_value = self.get_default_impact_factor(&food.category, category);
        let default_uncertainty = (default_value * 0.5, default_value * 2.0); // ±100% uncertainty
        let default_pedigree = PedigreeScore {
            reliability: 5,
            completeness: 5,
            temporal_correlation: 5,
            geographical_correlation: 5,
            technological_correlation: 5,
        };

        warn!("Using default factor for {} {:?} {}: {}", food.name, food.category, category, default_value);
        
        Ok((
            default_value,
            "Default estimate - high uncertainty".to_string(),
            default_uncertainty,
            default_pedigree,
        ))
    }

    fn apply_climate_adjustments(&self, base_impact: f64, category: &str, food: &FoodItem) -> f64 {
        let adjustment_factor = match category {
            "Global warming" => {
                // Higher methane emissions in tropical conditions
                if matches!(food.category, FoodCategory::Cereals | FoodCategory::Meat) {
                    self.climate_adjustments.get("methane_emission_factor").unwrap_or(&1.0)
                } else {
                    &1.0
                }
            },
            "Soil degradation" => {
                // Higher decomposition rates in tropical conditions
                self.climate_adjustments.get("tropical_decomposition_factor").unwrap_or(&1.0)
            },
            _ => &1.0,
        };

        base_impact * adjustment_factor
    }

    fn apply_seasonal_adjustments(&self, base_impact: f64, food: &FoodItem) -> f64 {
        match &food.seasonal_factor {
            Some(SeasonalFactor::WetSeason) => {
                let factor = self.climate_adjustments.get("wet_season_factor").unwrap_or(&1.0);
                base_impact * factor
            },
            Some(SeasonalFactor::DrySeason) => {
                let factor = self.climate_adjustments.get("dry_season_factor").unwrap_or(&1.0);
                base_impact * factor
            },
            _ => base_impact,
        }
    }

    fn apply_production_system_adjustments(&self, base_impact: f64, food: &FoodItem) -> f64 {
        match &food.production_system {
            Some(ProductionSystem::Intensive) => base_impact * 1.2, // Higher impacts per kg
            Some(ProductionSystem::Extensive) => base_impact * 1.5, // Much higher for livestock
            Some(ProductionSystem::Agroforestry) => base_impact * 0.8, // Lower impacts
            Some(ProductionSystem::Organic) => base_impact * 0.9, // Slightly lower
            _ => base_impact,
        }
    }

    fn calculate_uncertainty_range(
        &self,
        central_value: f64,
        base_uncertainty: (f64, f64),
        pedigree: &PedigreeScore
    ) -> (f64, f64) {
        let uncertainty_factor = pedigree.calculate_uncertainty_factor();
        let expanded_range = (
            base_uncertainty.0 * uncertainty_factor,
            base_uncertainty.1 * uncertainty_factor
        );
        
        // Ensure uncertainty range is centered on the central value
        let lower_bound = central_value - (central_value - expanded_range.0).abs();
        let upper_bound = central_value + (expanded_range.1 - central_value).abs();
        
        (lower_bound.max(0.0), upper_bound) // Non-negative values only
    }

    fn aggregate_midpoint_results(&self, total: &mut MidpointResult, addition: &MidpointResult) {
        // Simple addition for central values
        total.value += addition.value;

        // Uncertainty propagation (assuming independence)
        let total_variance = (total.uncertainty_range.1 - total.uncertainty_range.0).powi(2) / 16.0; // 95% CI
        let addition_variance = (addition.uncertainty_range.1 - addition.uncertainty_range.0).powi(2) / 16.0;
        let combined_variance = total_variance + addition_variance;
        let combined_std = combined_variance.sqrt();

        total.uncertainty_range = (
            (total.value - 2.0 * combined_std).max(0.0),
            total.value + 2.0 * combined_std
        );

        // Quality score weighted by contribution
        let total_contribution = total.value;
        let addition_contribution = addition.value;
        let total_weight = total_contribution + addition_contribution;
        
        if total_weight > 0.0 {
            total.data_quality_score = (total.data_quality_score * total_contribution + 
                                      addition.data_quality_score * addition_contribution) / total_weight;
        }

        // Merge sources
        total.contributing_sources.extend(addition.contributing_sources.clone());
    }

    fn apply_regional_adjustments(
        &self,
        impacts: &mut HashMap<String, MidpointResult>,
        country: &Country,
        _region: &Option<String>
    ) {
        // Apply water scarcity adjustments using AWARE methodology
        if let Some(water_result) = impacts.get_mut("Water consumption") {
            let aware_factor = match (country, _region.as_deref()) {
                (Country::Ghana, _) => self.regional_factors.get("Ghana_water_scarcity").unwrap_or(&20.0),
                (Country::Nigeria, Some("Northern")) => self.regional_factors.get("Nigeria_north_water_scarcity").unwrap_or(&30.0),
                (Country::Nigeria, _) => self.regional_factors.get("Nigeria_south_water_scarcity").unwrap_or(&15.0),
                _ => &1.0,
            };

            // Create water scarcity impact
            let water_scarcity_impact = MidpointResult {
                value: water_result.value * aware_factor,
                unit: "m3 H2O-eq".to_string(),
                uncertainty_range: (
                    water_result.uncertainty_range.0 * aware_factor,
                    water_result.uncertainty_range.1 * aware_factor
                ),
                data_quality_score: water_result.data_quality_score,
                contributing_sources: vec![format!("AWARE regional factor: {}", aware_factor)],
            };

            impacts.insert("Water scarcity".to_string(), water_scarcity_impact);
        }

        // Apply biodiversity adjustments based on production systems
        // This would require analyzing the food items' production systems
        // Implementation depends on available data
    }

    fn calculate_enhanced_endpoint_impacts(
        &self,
        midpoint: &HashMap<String, MidpointResult>
    ) -> Result<HashMap<String, EndpointResult>, Box<dyn std::error::Error>> {
        
        let mut endpoint = HashMap::new();

        // Human Health (DALY per kg)
        let mut human_health = 0.0;

        if let Some(gwp) = midpoint.get("Global warming") {
            let climate_health = gwp.value * self.characterization_factors.human_health.climate_health_africa;
            human_health += climate_health;
        }

        if let Some(water_scarcity) = midpoint.get("Water scarcity") {
            let water_health = water_scarcity.value * self.characterization_factors.human_health.water_stress_health_africa;
            human_health += water_health;
        }

        if let Some(pm) = midpoint.get("Particulate matter formation") {
            let air_health = pm.value * self.characterization_factors.human_health.air_quality_health_africa;
            human_health += air_health;
        }

        endpoint.insert("Human Health".to_string(), EndpointResult {
            value: human_health,
            unit: "DALY per kg".to_string(),
            uncertainty_range: (human_health * 0.5, human_health * 2.0), // Simplified uncertainty
            normalization_factor: Some(5.2e-2), // African-specific normalization (per kg)
            regional_adaptation_factor: Some(1.5), // Higher vulnerability in Africa
        });

        // Ecosystem Quality (species.yr per kg)
        let mut ecosystem_quality = 0.0;

        if let Some(gwp) = midpoint.get("Global warming") {
            ecosystem_quality += gwp.value * 1.2e-14;
        }

        if let Some(land_use) = midpoint.get("Land use") {
            ecosystem_quality += land_use.value * 2.1e-10;
        }

        if let Some(biodiversity) = midpoint.get("Biodiversity loss") {
            ecosystem_quality += biodiversity.value * 1.5e-12;
        }

        endpoint.insert("Ecosystem Quality".to_string(), EndpointResult {
            value: ecosystem_quality,
            unit: "species.yr per kg".to_string(),
            uncertainty_range: (ecosystem_quality * 0.3, ecosystem_quality * 3.0),
            normalization_factor: Some(4.1e-9), // African biodiversity hotspots (per kg)
            regional_adaptation_factor: Some(1.8), // Higher biodiversity sensitivity
        });

        // Resource Scarcity (USD per kg)
        let mut resource_scarcity = 0.0;

        if let Some(water_scarcity) = midpoint.get("Water scarcity") {
            resource_scarcity += water_scarcity.value * self.characterization_factors.resource_scarcity.water_scarcity_africa;
        }

        if let Some(fossil) = midpoint.get("Fossil depletion") {
            resource_scarcity += fossil.value * 0.055; // Global factor
        }

        endpoint.insert("Resource Scarcity".to_string(), EndpointResult {
            value: resource_scarcity,
            unit: "USD per kg".to_string(),
            uncertainty_range: (resource_scarcity * 0.7, resource_scarcity * 1.5),
            normalization_factor: Some(8.5e3), // Higher resource constraints in Africa (per kg)
            regional_adaptation_factor: Some(1.3),
        });

        Ok(endpoint)
    }

    fn calculate_enhanced_single_score(
        &self,
        endpoint: &HashMap<String, EndpointResult>
    ) -> Result<SingleScoreResult, Box<dyn std::error::Error>> {

        // ISO 14044-compliant weighting factors
        // Note: Weighting is value-choice dependent and should be transparent
        let weighting_factors = match self.methodology.weighting_method {
            Some(WeightingMethod::AfricanPriorities) => HashMap::from([
                ("Human Health".to_string(), 0.40),      // Higher weight for human health (African context)
                ("Ecosystem Quality".to_string(), 0.35), // Moderate weight for ecosystems
                ("Resource Scarcity".to_string(), 0.25), // Lower weight for resources
            ]),
            Some(WeightingMethod::EqualWeights) => HashMap::from([
                ("Human Health".to_string(), 0.333),     // Equal weighting (ISO default)
                ("Ecosystem Quality".to_string(), 0.333),
                ("Resource Scarcity".to_string(), 0.334),
            ]),
            _ => HashMap::from([
                ("Human Health".to_string(), 0.333),     // Default to equal weights
                ("Ecosystem Quality".to_string(), 0.333),
                ("Resource Scarcity".to_string(), 0.334),
            ]),
        };

        let mut single_score = 0.0;
        let mut score_uncertainty = 0.0;
        let mut normalization_refs = HashMap::new();

        // ISO 14044 methodology: Single Score = Σ(Endpoint / Normalization × Weight)
        for (category, result) in endpoint {
            if let Some(weight) = weighting_factors.get(category) {
                // Use normalization factor embedded in endpoint result
                // These are context-specific (African, Global, etc.) based on methodology
                let norm_factor = result.normalization_factor.unwrap_or_else(|| {
                    // Fallback normalization references (global per-capita annual basis)
                    match category.as_str() {
                        "Human Health" => 2.2e-2,      // DALY per kg global average
                        "Ecosystem Quality" => 1.8e-9, // species.yr per kg
                        "Resource Scarcity" => 4.2e3,  // USD per kg
                        _ => 1.0,
                    }
                });

                // Store for reporting
                normalization_refs.insert(category.clone(), norm_factor);

                // Normalized score = endpoint value / reference value
                // This gives dimensionless "person-equivalent" units
                let normalized_score = result.value / norm_factor;

                // Weighted score
                let weighted_score = normalized_score * weight;
                single_score += weighted_score;

                // Uncertainty propagation (ISO 14044 Section 4.4.3.3)
                let result_uncertainty = (result.uncertainty_range.1 - result.uncertainty_range.0) / 4.0;
                let normalized_uncertainty = result_uncertainty / norm_factor;
                let weighted_uncertainty = normalized_uncertainty * weight;
                score_uncertainty += weighted_uncertainty.powi(2);
            }
        }

        let score_std = score_uncertainty.sqrt();

        // Convert to percentage for user display (0-100% scale)
        // Reference: A score of 1.0 = average impact, 0.5 = half average, 2.0 = double average
        // For better UX, we map: 0-0.5 → Excellent, 0.5-1.0 → Good, 1.0-1.5 → Average, >1.5 → Poor
        // Display as percentage where 100% = 2x reference (worst reasonable case)
        let display_score = (single_score / 2.0).min(1.0).max(0.0);

        Ok(SingleScoreResult {
            value: display_score, // 0-1 scale for display (0% = best, 100% = 2x reference impact)
            unit: "Environmental Impact Score (0-1 scale, 1.0 = 2× reference impact)".to_string(),
            uncertainty_range: (
                ((single_score - 2.0 * score_std) / 2.0).max(0.0),
                ((single_score + 2.0 * score_std) / 2.0).min(1.0)
            ),
            weighting_factors,
            methodology: format!(
                "ISO 14044 compliant: {:?} normalization with {:?} weighting. Raw score: {:.3} person-equiv.",
                self.methodology.normalization_method.as_ref().unwrap_or(&NormalizationMethod::None),
                self.methodology.weighting_method.as_ref().unwrap_or(&WeightingMethod::None),
                single_score
            ),
        })
    }

    fn assess_data_quality(
        &self,
        foods: &[FoodItem],
        country: &Country
    ) -> Result<DataQuality, Box<dyn std::error::Error>> {
        
        let mut quality_scores = Vec::new();
        let mut source_contributions = HashMap::new();
        let mut warnings = Vec::new();
        let mut recommendations = Vec::new();

        // Analyze data quality for each food item
        for food in foods {
            for category in &self.get_impact_categories() {
                let hierarchy = self.build_lookup_hierarchy(food, country);
                
                if let Ok((_, source, _, pedigree)) = self.find_best_factor(food, country, category, &hierarchy) {
                    let quality_score = pedigree.calculate_overall_quality_score();
                    
                    // Only include factors that are not default fallbacks (which have all 5s)
                    if !source.contains("Default estimate") {
                        quality_scores.push(quality_score);
                        
                        // Track source contributions
                        let source_type = if source.contains("Ghana") || source.contains("Nigeria") {
                            "Country-specific"
                        } else if source.contains("Africa") {
                            "Regional"
                        } else if source.contains("Default") {
                            "Estimated"
                        } else {
                            "Global"
                        };
                        
                        *source_contributions.entry(source_type.to_string()).or_insert(0) += 1;
                        
                        // Generate warnings for low-quality data
                        if pedigree.calculate_overall_quality_score() < 0.5 {
                            warnings.push(format!("Low data quality for {} {}: {}", 
                                food.name, category, source));
                        }
                    }
                }
            }
        }

        // Calculate overall metrics
        let overall_quality = if quality_scores.is_empty() {
            0.0 // No quality data available
        } else {
            quality_scores.iter().sum::<f64>() / quality_scores.len() as f64
        };
        let total_factors = source_contributions.values().sum::<i32>() as f64;
        
        let data_source_mix = source_contributions.into_iter()
            .map(|(source_type, count)| DataSourceContribution {
                source_type: match source_type.as_str() {
                    "Country-specific" => DataSource::CountrySpecific(country.clone()),
                    "Regional" => DataSource::Regional("West Africa".to_string()),
                    "Global" => DataSource::Global,
                    _ => DataSource::Estimated,
                },
                percentage: (count as f64 / total_factors) * 100.0,
                quality_score: overall_quality, // Simplified
            })
            .collect();

        // Generate recommendations
        if overall_quality < 0.6 {
            recommendations.push("Consider collecting primary data for major food items".to_string());
        }
        if warnings.len() > foods.len() / 2 {
            recommendations.push("Prioritize data improvement for most uncertain factors".to_string());
        }

        // Sanity checks for unusual consumption patterns
        let total_meat_kg: f64 = foods.iter()
            .filter(|food| matches!(food.category, FoodCategory::Meat))
            .map(|food| food.quantity_kg)
            .sum();
        
        if total_meat_kg > 20.0 { // More than 20kg of meat is unusually high
            warnings.push(format!("High meat consumption detected: {:.1}kg. Consider reducing meat intake for environmental and health benefits.", total_meat_kg));
        }

        // Adjusted thresholds for African context - partial local data is valuable
        let confidence_level = match overall_quality {
            q if q > 0.7 => ConfidenceLevel::High,    // Lowered from 0.8 - some Ghana data available
            q if q > 0.5 => ConfidenceLevel::Medium,  // Lowered from 0.6 - mixed local + global data
            q if q > 0.3 => ConfidenceLevel::Low,     // Lowered from 0.4 - some local data better than none
            _ => ConfidenceLevel::VeryLow,            // Only for pure estimates/no data
        };



        Ok(DataQuality {
            overall_confidence: confidence_level,
            data_source_mix,
            regional_adaptation: true,
            completeness_score: overall_quality,
            temporal_representativeness: 0.8, // Most data is recent
            geographical_representativeness: if matches!(country, Country::Ghana | Country::Nigeria) { 0.7 } else { 0.4 },
            technological_representativeness: 0.6, // Mixed technology levels
            warnings,
            recommendations,
        })
    }

    fn perform_sensitivity_analysis(
        &self,
        foods: &[FoodItem],
        _country: &Country
    ) -> Result<SensitivityAnalysis, Box<dyn std::error::Error>> {
        
        // Simplified sensitivity analysis
        let mut influential_parameters = Vec::new();
        let uncertainty_contributions = HashMap::new();
        
        // Identify most influential parameters (simplified)
        for food in foods {
            if food.quantity_kg > 1.0 { // Focus on significant quantities
                influential_parameters.push(InfluentialParameter {
                    parameter_name: format!("{} carbon footprint", food.name),
                    influence_percentage: (food.quantity_kg / foods.iter().map(|f| f.quantity_kg).sum::<f64>()) * 100.0,
                    current_uncertainty: 50.0, // Simplified
                    improvement_potential: 30.0, // Simplified
                });
            }
        }

        // Sort by influence
        influential_parameters.sort_by(|a, b| b.influence_percentage.partial_cmp(&a.influence_percentage).unwrap());
        influential_parameters.truncate(5); // Top 5

        // Scenario analysis
        let scenarios = vec![
            ScenarioResult {
                scenario_name: "Best available technology".to_string(),
                description: "Using most efficient production systems".to_string(),
                impact_changes: HashMap::from([
                    ("Global warming".to_string(), -30.0),
                    ("Water consumption".to_string(), -25.0),
                ]),
            },
            ScenarioResult {
                scenario_name: "Climate adaptation".to_string(),
                description: "Drought-resistant varieties and water-efficient practices".to_string(),
                impact_changes: HashMap::from([
                    ("Water scarcity".to_string(), -40.0),
                    ("Biodiversity loss".to_string(), -20.0),
                ]),
            },
        ];

        Ok(SensitivityAnalysis {
            most_influential_parameters: influential_parameters,
            uncertainty_contributions,
            scenario_analysis: scenarios,
        })
    }

    fn generate_comparative_analysis(
        &self,
        impacts: &HashMap<String, MidpointResult>,
        _country: &Country
    ) -> Result<ComparativeAnalysis, Box<dyn std::error::Error>> {
        
        // Simplified comparative analysis
        let mut benchmark_comparisons = Vec::new();
        let mut regional_comparisons = Vec::new();
        let mut best_practices = Vec::new();

        // Compare against global averages (simplified)
        if let Some(gwp) = impacts.get("Global warming") {
            benchmark_comparisons.push(BenchmarkComparison {
                benchmark_name: "Global average diet".to_string(),
                your_performance: gwp.value,
                benchmark_value: 2000.0, // kg CO2-eq/year (example)
                percentage_difference: ((gwp.value - 2000.0) / 2000.0) * 100.0,
                performance_category: if gwp.value < 1500.0 { 
                    PerformanceCategory::Excellent 
                } else if gwp.value < 2500.0 { 
                    PerformanceCategory::Good 
                } else { 
                    PerformanceCategory::BelowAverage 
                },
            });
        }

        // Regional comparison
        regional_comparisons.push(RegionalComparison {
            region_name: "West Africa average".to_string(),
            impact_ratios: HashMap::from([
                ("Global warming".to_string(), 1.2), // 20% above regional average
                ("Water consumption".to_string(), 0.9), // 10% below regional average
            ]),
        });

        // Best practices
        best_practices.push(BestPractice {
            practice_name: "Increase legume consumption".to_string(),
            description: "Replace 25% of cereal consumption with legumes".to_string(),
            potential_impact_reduction: HashMap::from([
                ("Global warming".to_string(), 15.0),
                ("Land use".to_string(), 10.0),
            ]),
            implementation_difficulty: DifficultyLevel::Low,
            cost_category: CostCategory::NoCost,
        });

        best_practices.push(BestPractice {
            practice_name: "Improved livestock management".to_string(),
            description: "Implement rotational grazing and feed supplements".to_string(),
            potential_impact_reduction: HashMap::from([
                ("Global warming".to_string(), 25.0),
                ("Biodiversity loss".to_string(), 20.0),
            ]),
            implementation_difficulty: DifficultyLevel::Medium,
            cost_category: CostCategory::MediumCost,
        });

        Ok(ComparativeAnalysis {
            benchmark_comparisons,
            regional_comparisons,
            best_practices,
        })
    }

    fn apply_management_practice_adjustments(
        &self,
        impacts: &mut HashMap<String, MidpointResult>,
        management_practices: &ManagementPractices,
        _food: &FoodItem
    ) -> Result<(), Box<dyn std::error::Error>> {
        // Apply soil management adjustments based on conservation practices
        let soil_factor = if management_practices.soil_management.conservation_practices.len() > 2 {
            0.85  // Multiple conservation practices = 15% reduction
        } else if management_practices.soil_management.conservation_practices.len() > 0 {
            0.92  // Some conservation practices = 8% reduction
        } else {
            1.0   // No conservation practices
        };

        if let Some(soil_result) = impacts.get_mut("Soil degradation") {
            soil_result.value *= soil_factor;
            soil_result.uncertainty_range.0 *= soil_factor;
            soil_result.uncertainty_range.1 *= soil_factor;
            soil_result.contributing_sources.push(format!("Conservation practices: {}", management_practices.soil_management.conservation_practices.len()));
        }

        // Compost use affects carbon sequestration
        let carbon_factor = if management_practices.soil_management.uses_compost {
            0.92  // 8% reduction from carbon sequestration
        } else {
            1.0   // No benefit
        };

        if let Some(gwp_result) = impacts.get_mut("Global warming") {
            gwp_result.value *= carbon_factor;
            gwp_result.uncertainty_range.0 *= carbon_factor;
            gwp_result.uncertainty_range.1 *= carbon_factor;
        }

        // Apply fertilizer management adjustments
        let n2o_factor = if management_practices.fertilization.soil_test_based && management_practices.fertilization.follows_nutrient_plan {
            0.8   // Efficient management reduces N2O
        } else if management_practices.fertilization.soil_test_based || management_practices.fertilization.follows_nutrient_plan {
            0.9   // Some efficiency improvement
        } else {
            1.2   // Inefficient fertilizer use increases emissions
        };

        if let Some(gwp_result) = impacts.get_mut("Global warming") {
            gwp_result.value *= n2o_factor;
        }

        // Eutrophication impacts from nutrient runoff
        let eutrophication_factor = if management_practices.fertilization.follows_nutrient_plan {
            0.7   // Good planning reduces runoff
        } else {
            1.3   // Poor management increases runoff
        };

        if let Some(freshwater_eutroph) = impacts.get_mut("Freshwater eutrophication") {
            freshwater_eutroph.value *= eutrophication_factor;
        }
        if let Some(marine_eutroph) = impacts.get_mut("Marine eutrophication") {
            marine_eutroph.value *= eutrophication_factor;
        }

        // Apply water management adjustments based on irrigation system
        let water_efficiency_factor = match management_practices.water_management.irrigation_system.as_deref() {
            Some("Drip irrigation") | Some("Micro-sprinkler") => 0.7,  // High efficiency
            Some("Sprinkler") => 0.85,  // Medium efficiency
            Some("Flood irrigation") | Some("Furrow irrigation") => 1.0,  // Low efficiency
            None => 0.5,  // Rainfed farming
            _ => 0.9,  // Default for other systems
        };

        if let Some(water_result) = impacts.get_mut("Water consumption") {
            water_result.value *= water_efficiency_factor;
        }
        if let Some(water_scarcity_result) = impacts.get_mut("Water scarcity") {
            water_scarcity_result.value *= water_efficiency_factor;
        }

        // Conservation practices reduce runoff and erosion
        if !management_practices.water_management.water_conservation_practices.is_empty() {
            if let Some(soil_result) = impacts.get_mut("Soil degradation") {
                soil_result.value *= 0.8; // 20% reduction
            }
        }

        // Apply pest management adjustments based on IPM and pesticide use
        let pesticide_count = management_practices.pest_management.pesticides_used.len();
        let pesticide_factor = if pesticide_count == 0 {
            0.9   // No pesticides
        } else if pesticide_count <= 2 {
            0.95  // Low pesticide use
        } else if pesticide_count <= 5 {
            1.0   // Moderate use
        } else {
            1.2   // High pesticide use
        };

        // Affects biodiversity and ecosystem quality
        if let Some(biodiversity_result) = impacts.get_mut("Biodiversity loss") {
            biodiversity_result.value *= pesticide_factor;
        }

        // IPM practices reduce overall environmental impact
        if management_practices.pest_management.uses_ipm {
            // Apply 10% reduction across multiple categories
            for (category, result) in impacts.iter_mut() {
                if matches!(category.as_str(), 
                    "Biodiversity loss" | "Terrestrial acidification" | 
                    "Freshwater eutrophication" | "Marine eutrophication") {
                    result.value *= 0.9;
                }
            }
        }

        Ok(())
    }

    fn generate_comprehensive_comparative_analysis(
        &self,
        impacts: &HashMap<String, MidpointResult>,
        country: &Country,
        foods: &[FoodItem]
    ) -> Result<ComparativeAnalysis, Box<dyn std::error::Error>> {
        
        let mut benchmark_comparisons = Vec::new();
        let mut regional_comparisons = Vec::new();
        let mut best_practices = Vec::new();

        // Enhanced benchmark comparisons with farm management context
        if let Some(gwp) = impacts.get("Global warming") {
            benchmark_comparisons.push(BenchmarkComparison {
                benchmark_name: "Sustainable farming practices".to_string(),
                your_performance: gwp.value,
                benchmark_value: 1500.0, // kg CO2-eq/year for sustainable practices
                percentage_difference: ((gwp.value - 1500.0) / 1500.0) * 100.0,
                performance_category: if gwp.value < 1200.0 { 
                    PerformanceCategory::Excellent 
                } else if gwp.value < 1800.0 { 
                    PerformanceCategory::Good 
                } else { 
                    PerformanceCategory::BelowAverage 
                },
            });
        }

        // Regional comparison with management practices
        regional_comparisons.push(RegionalComparison {
            region_name: match country {
                Country::Ghana => "Ghana sustainable farming average".to_string(),
                Country::Nigeria => "Nigeria sustainable farming average".to_string(),
                _ => "West Africa sustainable farming average".to_string(),
            },
            impact_ratios: HashMap::from([
                ("Global warming".to_string(), 1.1),
                ("Water consumption".to_string(), 0.9),
                ("Soil degradation".to_string(), 1.2),
                ("Biodiversity loss".to_string(), 0.8),
            ]),
        });

        // Enhanced best practices based on current farm management
        best_practices.push(BestPractice {
            practice_name: "Implement conservation agriculture".to_string(),
            description: "Adopt no-till farming, cover crops, and crop rotation".to_string(),
            potential_impact_reduction: HashMap::from([
                ("Global warming".to_string(), 20.0),
                ("Soil degradation".to_string(), 40.0),
                ("Water consumption".to_string(), 15.0),
            ]),
            implementation_difficulty: DifficultyLevel::Medium,
            cost_category: CostCategory::LowCost,
        });

        best_practices.push(BestPractice {
            practice_name: "Optimize fertilizer application".to_string(),
            description: "Use soil testing and precision application techniques".to_string(),
            potential_impact_reduction: HashMap::from([
                ("Global warming".to_string(), 25.0),
                ("Freshwater eutrophication".to_string(), 35.0),
                ("Marine eutrophication".to_string(), 30.0),
            ]),
            implementation_difficulty: DifficultyLevel::Low,
            cost_category: CostCategory::NoCost,
        });

        best_practices.push(BestPractice {
            practice_name: "Install efficient irrigation systems".to_string(),
            description: "Upgrade to drip irrigation or micro-sprinklers".to_string(),
            potential_impact_reduction: HashMap::from([
                ("Water consumption".to_string(), 40.0),
                ("Water scarcity".to_string(), 40.0),
            ]),
            implementation_difficulty: DifficultyLevel::High,
            cost_category: CostCategory::HighCost,
        });

        // Analyze current practices and suggest specific improvements
        let has_livestock = foods.iter().any(|food| matches!(food.category, FoodCategory::Meat | FoodCategory::Dairy));
        if has_livestock {
            best_practices.push(BestPractice {
                practice_name: "Improve livestock feed efficiency".to_string(),
                description: "Use high-quality feed supplements and pasture management".to_string(),
                potential_impact_reduction: HashMap::from([
                    ("Global warming".to_string(), 30.0),
                    ("Land use".to_string(), 25.0),
                    ("Water consumption".to_string(), 20.0),
                ]),
                implementation_difficulty: DifficultyLevel::Medium,
                cost_category: CostCategory::MediumCost,
            });
        }

        let has_cereals = foods.iter().any(|food| matches!(food.category, FoodCategory::Cereals));
        if has_cereals {
            best_practices.push(BestPractice {
                practice_name: "Intercrop with legumes".to_string(),
                description: "Plant legumes between cereal rows to fix nitrogen naturally".to_string(),
                potential_impact_reduction: HashMap::from([
                    ("Global warming".to_string(), 15.0),
                    ("Soil degradation".to_string(), 20.0),
                    ("Freshwater eutrophication".to_string(), 25.0),
                ]),
                implementation_difficulty: DifficultyLevel::Low,
                cost_category: CostCategory::NoCost,
            });
        }

        Ok(ComparativeAnalysis {
            benchmark_comparisons,
            regional_comparisons,
            best_practices,
        })
    }

    // Existing helper methods updated...
    fn get_default_impact_factor(&self, category: &FoodCategory, impact: &str) -> f64 {
        // Scientifically accurate global averages based on LCA literature (Poore & Nemecek 2018, IPCC AR6)
        match (category, impact) {
            // CEREALS - Global averages from comprehensive LCA studies
            (FoodCategory::Cereals, "Global warming") => 1.4, // kg CO2-eq/kg (Poore & Nemecek 2018)
            (FoodCategory::Cereals, "Water consumption") => 1.6, // m3/kg global average
            (FoodCategory::Cereals, "Land use") => 2.8, // m2a/kg
            (FoodCategory::Cereals, "Terrestrial acidification") => 0.012, // kg SO2-eq/kg
            (FoodCategory::Cereals, "Freshwater eutrophication") => 0.003, // kg P-eq/kg
            (FoodCategory::Cereals, "Marine eutrophication") => 0.008, // kg N-eq/kg
            (FoodCategory::Cereals, "Biodiversity loss") => 0.6, // MSA*m2*yr/kg
            (FoodCategory::Cereals, "Soil degradation") => 0.15, // kg soil-eq/kg
            (FoodCategory::Cereals, "Particulate matter formation") => 0.008, // PM2.5-eq/kg
            (FoodCategory::Cereals, "Photochemical oxidation") => 0.004, // kg NMVOC-eq/kg
            (FoodCategory::Cereals, "Fossil depletion") => 0.02, // kg oil-eq/kg
            (FoodCategory::Cereals, "Mineral depletion") => 0.001, // kg Fe-eq/kg
            
            // LEGUMES - Lower impacts due to N-fixation
            (FoodCategory::Legumes, "Global warming") => 1.0, // Lower due to N-fixation
            (FoodCategory::Legumes, "Water consumption") => 4.0, // Higher water requirement
            (FoodCategory::Legumes, "Land use") => 2.5, // m2a/kg
            (FoodCategory::Legumes, "Terrestrial acidification") => 0.008, // kg SO2-eq/kg
            (FoodCategory::Legumes, "Freshwater eutrophication") => 0.002, // kg P-eq/kg
            (FoodCategory::Legumes, "Marine eutrophication") => 0.005, // kg N-eq/kg
            (FoodCategory::Legumes, "Biodiversity loss") => 0.4, // Lower impact
            (FoodCategory::Legumes, "Soil degradation") => 0.08, // Improves soil
            (FoodCategory::Legumes, "Particulate matter formation") => 0.006, // PM2.5-eq/kg
            (FoodCategory::Legumes, "Photochemical oxidation") => 0.003, // kg NMVOC-eq/kg
            (FoodCategory::Legumes, "Fossil depletion") => 0.015, // kg oil-eq/kg
            (FoodCategory::Legumes, "Mineral depletion") => 0.0008, // kg Fe-eq/kg
            
            // VEGETABLES - Generally lower impact
            (FoodCategory::Vegetables, "Global warming") => 0.5,
            (FoodCategory::Vegetables, "Water consumption") => 0.4,
            (FoodCategory::Vegetables, "Land use") => 0.3,
            (FoodCategory::Vegetables, "Terrestrial acidification") => 0.004,
            (FoodCategory::Vegetables, "Freshwater eutrophication") => 0.001,
            (FoodCategory::Vegetables, "Marine eutrophication") => 0.003,
            (FoodCategory::Vegetables, "Biodiversity loss") => 0.2,
            (FoodCategory::Vegetables, "Soil degradation") => 0.05,
            (FoodCategory::Vegetables, "Particulate matter formation") => 0.003,
            (FoodCategory::Vegetables, "Photochemical oxidation") => 0.002,
            (FoodCategory::Vegetables, "Fossil depletion") => 0.008,
            (FoodCategory::Vegetables, "Mineral depletion") => 0.0004,
            
            // FRUITS - Variable based on type
            (FoodCategory::Fruits, "Global warming") => 0.6,
            (FoodCategory::Fruits, "Water consumption") => 0.8,
            (FoodCategory::Fruits, "Land use") => 0.4,
            (FoodCategory::Fruits, "Terrestrial acidification") => 0.005,
            (FoodCategory::Fruits, "Freshwater eutrophication") => 0.001,
            (FoodCategory::Fruits, "Marine eutrophication") => 0.004,
            (FoodCategory::Fruits, "Biodiversity loss") => 0.3,
            (FoodCategory::Fruits, "Soil degradation") => 0.06,
            (FoodCategory::Fruits, "Particulate matter formation") => 0.004,
            (FoodCategory::Fruits, "Photochemical oxidation") => 0.002,
            (FoodCategory::Fruits, "Fossil depletion") => 0.01,
            (FoodCategory::Fruits, "Mineral depletion") => 0.0005,
            
            // MEAT - High impact across all categories
            (FoodCategory::Meat, "Global warming") => 25.0, // kg CO2-eq/kg (global average for beef)
            (FoodCategory::Meat, "Water consumption") => 15.0, // m3/kg
            (FoodCategory::Meat, "Land use") => 20.0, // m2a/kg
            (FoodCategory::Meat, "Terrestrial acidification") => 0.2, // kg SO2-eq/kg
            (FoodCategory::Meat, "Freshwater eutrophication") => 0.05, // kg P-eq/kg
            (FoodCategory::Meat, "Marine eutrophication") => 0.15, // kg N-eq/kg
            (FoodCategory::Meat, "Biodiversity loss") => 8.0, // MSA*m2*yr/kg
            (FoodCategory::Meat, "Soil degradation") => 2.5, // kg soil-eq/kg
            (FoodCategory::Meat, "Particulate matter formation") => 0.15, // PM2.5-eq/kg
            (FoodCategory::Meat, "Photochemical oxidation") => 0.08, // kg NMVOC-eq/kg
            (FoodCategory::Meat, "Fossil depletion") => 0.4, // kg oil-eq/kg
            (FoodCategory::Meat, "Mineral depletion") => 0.02, // kg Fe-eq/kg
            
            // POULTRY - Moderate impact
            (FoodCategory::Poultry, "Global warming") => 6.0,
            (FoodCategory::Poultry, "Water consumption") => 4.0,
            (FoodCategory::Poultry, "Land use") => 7.0,
            (FoodCategory::Poultry, "Terrestrial acidification") => 0.08,
            (FoodCategory::Poultry, "Freshwater eutrophication") => 0.02,
            (FoodCategory::Poultry, "Marine eutrophication") => 0.06,
            (FoodCategory::Poultry, "Biodiversity loss") => 2.5,
            (FoodCategory::Poultry, "Soil degradation") => 0.8,
            (FoodCategory::Poultry, "Particulate matter formation") => 0.05,
            (FoodCategory::Poultry, "Photochemical oxidation") => 0.03,
            (FoodCategory::Poultry, "Fossil depletion") => 0.15,
            (FoodCategory::Poultry, "Mineral depletion") => 0.008,
            
            // FISH - Variable based on production system
            (FoodCategory::Fish, "Global warming") => 4.0,
            (FoodCategory::Fish, "Water consumption") => 0.005, // Very low for aquaculture
            (FoodCategory::Fish, "Land use") => 3.0,
            (FoodCategory::Fish, "Terrestrial acidification") => 0.03,
            (FoodCategory::Fish, "Freshwater eutrophication") => 0.008,
            (FoodCategory::Fish, "Marine eutrophication") => 0.15, // High for marine systems
            (FoodCategory::Fish, "Biodiversity loss") => 1.5,
            (FoodCategory::Fish, "Soil degradation") => 0.2,
            (FoodCategory::Fish, "Particulate matter formation") => 0.025,
            (FoodCategory::Fish, "Photochemical oxidation") => 0.015,
            (FoodCategory::Fish, "Fossil depletion") => 0.08,
            (FoodCategory::Fish, "Mineral depletion") => 0.003,
            
            // DAIRY - Moderate to high impact
            (FoodCategory::Dairy, "Global warming") => 3.2,
            (FoodCategory::Dairy, "Water consumption") => 5.0,
            (FoodCategory::Dairy, "Land use") => 4.0,
            (FoodCategory::Dairy, "Terrestrial acidification") => 0.04,
            (FoodCategory::Dairy, "Freshwater eutrophication") => 0.01,
            (FoodCategory::Dairy, "Marine eutrophication") => 0.03,
            (FoodCategory::Dairy, "Biodiversity loss") => 1.8,
            (FoodCategory::Dairy, "Soil degradation") => 0.6,
            (FoodCategory::Dairy, "Particulate matter formation") => 0.03,
            (FoodCategory::Dairy, "Photochemical oxidation") => 0.02,
            (FoodCategory::Dairy, "Fossil depletion") => 0.08,
            (FoodCategory::Dairy, "Mineral depletion") => 0.004,
            
            // ROOTS - Efficient crops for Africa
            (FoodCategory::Roots, "Global warming") => 0.3, // Very low emissions
            (FoodCategory::Roots, "Water consumption") => 0.6, // Water efficient
            (FoodCategory::Roots, "Land use") => 1.0, // Efficient land use
            (FoodCategory::Roots, "Terrestrial acidification") => 0.002,
            (FoodCategory::Roots, "Freshwater eutrophication") => 0.0005,
            (FoodCategory::Roots, "Marine eutrophication") => 0.002,
            (FoodCategory::Roots, "Biodiversity loss") => 0.15,
            (FoodCategory::Roots, "Soil degradation") => 0.03,
            (FoodCategory::Roots, "Particulate matter formation") => 0.002,
            (FoodCategory::Roots, "Photochemical oxidation") => 0.001,
            (FoodCategory::Roots, "Fossil depletion") => 0.005,
            (FoodCategory::Roots, "Mineral depletion") => 0.0002,
            
            // Default for any missing combinations - use cereal averages as conservative estimate
            _ => match impact {
                "Global warming" => 1.4,
                "Water consumption" => 1.6,
                "Land use" => 2.8,
                "Terrestrial acidification" => 0.012,
                "Freshwater eutrophication" => 0.003,
                "Marine eutrophication" => 0.008,
                "Biodiversity loss" => 0.6,
                "Soil degradation" => 0.15,
                "Particulate matter formation" => 0.008,
                "Photochemical oxidation" => 0.004,
                "Fossil depletion" => 0.02,
                "Mineral depletion" => 0.001,
                _ => 0.1, // Conservative fallback for unknown categories
            },
        }
    }
}

impl Clone for AfricanLCAEngine {
    fn clone(&self) -> Self {
        Self {
            impact_factors: self.impact_factors.clone(),
            characterization_factors: self.characterization_factors.clone(),
            regional_factors: self.regional_factors.clone(),
            climate_adjustments: self.climate_adjustments.clone(),
            methodology: self.methodology.clone(),
            lci_calculator: LCICalculator::new(), // Create new LCI calculator instance
        }
    }
}