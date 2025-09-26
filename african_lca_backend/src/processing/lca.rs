use crate::models::*;
use crate::processing::models::{
    ProcessingAssessment, ProcessingFacilityProfile, ProcessingOperations, ProcessedProduct,
    ProcessingImpactFactor, ProcessingBenchmark, ProcessingFacilityType, ProductType,
    EnergySource, WasteDisposalMethod, WastewaterTreatment, LocationType,
    EquipmentAge, MaintenanceFrequency,
    ProcessingRecommendation, ProcessingRecommendationCategory, ImplementationCost, ComplexityLevel,
    Priority as ProcessingPriority
};
use std::collections::HashMap;
use log::info;

pub struct ProcessingLCAEngine {
    impact_factors: HashMap<String, ProcessingImpactFactor>,
    benchmarks: HashMap<String, ProcessingBenchmark>,
    characterization_factors: CharacterizationFactors,
    regional_factors: HashMap<String, f64>,
    methodology: LCAMethodology,
}

impl ProcessingLCAEngine {
    pub fn new(methodology: LCAMethodology) -> Self {
        Self {
            impact_factors: HashMap::new(),
            benchmarks: HashMap::new(),
            characterization_factors: CharacterizationFactors::default(),
            regional_factors: HashMap::new(),
            methodology,
        }
    }

    pub fn load_impact_factors(&mut self, factors: Vec<ProcessingImpactFactor>) {
        for factor in factors {
            let key = self.create_factor_key(&factor);
            self.impact_factors.insert(key, factor);
        }
        info!("Loaded {} processing impact factors", self.impact_factors.len());
    }

    pub fn load_benchmarks(&mut self, benchmarks: Vec<ProcessingBenchmark>) {
        for benchmark in benchmarks {
            let key = format!("{:?}_{:?}_{:?}", benchmark.facility_type, benchmark.capacity_range, benchmark.country);
            self.benchmarks.insert(key, benchmark);
        }
        info!("Loaded {} processing benchmarks", self.benchmarks.len());
    }

    pub fn load_regional_factors(&mut self, factors: HashMap<String, f64>) {
        self.regional_factors = factors;
    }

    fn create_factor_key(&self, factor: &ProcessingImpactFactor) -> String {
        format!("{:?}_{:?}_{:?}_{}", 
            factor.facility_type, 
            factor.product_type, 
            factor.country, 
            factor.impact_category)
    }

    pub fn perform_processing_assessment(&self, assessment: &mut ProcessingAssessment) -> Result<(), Box<dyn std::error::Error>> {
        info!("Starting processing LCA assessment for {} using {:?}", 
              assessment.facility_profile.company_name, self.methodology.characterization_method);

        let mut midpoint_impacts = HashMap::new();
        let mut breakdown_by_product = HashMap::new();

        let impact_categories = self.get_processing_impact_categories();

        // Initialize all impact categories
        for category in &impact_categories {
            midpoint_impacts.insert(category.clone(), MidpointResult {
                value: 0.0,
                unit: self.get_processing_impact_unit(category),
                uncertainty_range: (0.0, 0.0),
                data_quality_score: 0.0,
                contributing_sources: Vec::new(),
            });
        }

        // Calculate impacts for each processed product
        for product in &assessment.processed_products {
            let product_results = self.calculate_product_impacts(
                product, 
                &assessment.facility_profile,
                &assessment.processing_operations,
                &assessment.country
            )?;
            
            // Add to breakdown
            breakdown_by_product.insert(
                format!("{} ({} tonnes/year)", product.name, product.annual_production),
                product_results.clone()
            );

            // Aggregate impacts
            for (category, result) in product_results {
                if let Some(total_result) = midpoint_impacts.get_mut(&category) {
                    self.aggregate_midpoint_results(total_result, &result);
                }
            }
        }

        // Apply processing-specific adjustments
        self.apply_processing_adjustments(&mut midpoint_impacts, &assessment.processing_operations, &assessment.country);

        // Calculate endpoint impacts
        let endpoint_impacts = self.calculate_processing_endpoint_impacts(&midpoint_impacts)?;

        // Calculate single score
        let single_score = self.calculate_processing_single_score(&endpoint_impacts)?;

        // Assess data quality
        let data_quality = self.assess_processing_data_quality(&assessment.processed_products, &assessment.country)?;

        // Generate recommendations
        let recommendations = self.generate_processing_recommendations(
            &midpoint_impacts, 
            &assessment.facility_profile,
            &assessment.processing_operations
        )?;

        // Store results
        assessment.results = Some(LCAResults {
            midpoint_impacts,
            endpoint_impacts,
            single_score,
            data_quality,
            breakdown_by_food: breakdown_by_product,
            sensitivity_analysis: None,
            comparative_analysis: None,
            management_analysis: None,
            benchmarking: None,
            recommendations: Some(recommendations.into_iter().map(|rec| Recommendation {
                category: match rec.category {
                    ProcessingRecommendationCategory::EnergyEfficiency => RecommendationCategory::EnergyEfficiency,
                    ProcessingRecommendationCategory::WaterConservation => RecommendationCategory::WaterManagement,
                    ProcessingRecommendationCategory::WasteReduction => RecommendationCategory::PostHarvest,
                    ProcessingRecommendationCategory::EquipmentUpgrade => RecommendationCategory::SystemDesign,
                    _ => RecommendationCategory::EnergyEfficiency,
                },
                title: rec.title,
                description: rec.description,
                potential_impact_reduction: rec.potential_savings,
                implementation_difficulty: match rec.complexity {
                    ComplexityLevel::Simple => DifficultyLevel::Low,
                    ComplexityLevel::Moderate => DifficultyLevel::Medium,
                    ComplexityLevel::Complex => DifficultyLevel::High,
                    ComplexityLevel::VeryComplex => DifficultyLevel::High,
                },
                cost_category: match rec.implementation_cost {
                    ImplementationCost::Low => CostCategory::LowCost,
                    ImplementationCost::Medium => CostCategory::MediumCost,
                    ImplementationCost::High => CostCategory::HighCost,
                    ImplementationCost::VeryHigh => CostCategory::HighCost,
                },
                priority: Priority::Medium,
            }).collect()),
        });

        info!("Processing assessment completed for {}", assessment.facility_profile.company_name);
        Ok(())
    }

    fn get_processing_impact_categories(&self) -> Vec<String> {
        vec![
            "Global warming".to_string(),
            "Energy consumption".to_string(),
            "Water consumption".to_string(),
            "Water scarcity".to_string(),
            "Wastewater generation".to_string(),
            "Solid waste generation".to_string(),
            "Air pollution".to_string(),
            "Land use".to_string(),
            "Terrestrial acidification".to_string(),
            "Freshwater eutrophication".to_string(),
            "Marine eutrophication".to_string(),
            "Fossil depletion".to_string(),
            "Particulate matter formation".to_string(),
            "Raw material depletion".to_string(),
        ]
    }

    fn get_processing_impact_unit(&self, category: &str) -> String {
        match category {
            "Global warming" => "kg CO2-eq".to_string(),
            "Energy consumption" => "kWh".to_string(),
            "Water consumption" => "m3".to_string(),
            "Water scarcity" => "m3 H2O-eq".to_string(),
            "Wastewater generation" => "m3".to_string(),
            "Solid waste generation" => "kg".to_string(),
            "Air pollution" => "kg PM2.5-eq".to_string(),
            "Land use" => "m2a".to_string(),
            "Terrestrial acidification" => "kg SO2-eq".to_string(),
            "Freshwater eutrophication" => "kg P-eq".to_string(),
            "Marine eutrophication" => "kg N-eq".to_string(),
            "Fossil depletion" => "kg oil-eq".to_string(),
            "Particulate matter formation" => "PM2.5-eq".to_string(),
            "Raw material depletion" => "kg".to_string(),
            _ => "Unknown".to_string(),
        }
    }

    fn calculate_product_impacts(
        &self,
        product: &ProcessedProduct,
        facility: &ProcessingFacilityProfile,
        operations: &ProcessingOperations,
        country: &Country
    ) -> Result<HashMap<String, MidpointResult>, Box<dyn std::error::Error>> {
        
        let mut impacts = HashMap::new();
        let impact_categories = self.get_processing_impact_categories();

        for category in &impact_categories {
            let impact_value = match category.as_str() {
                "Global warming" => self.calculate_gwp_impact(product, facility, operations),
                "Energy consumption" => self.calculate_energy_impact(product, facility, operations),
                "Water consumption" => self.calculate_water_impact(product, facility, operations),
                "Wastewater generation" => self.calculate_wastewater_impact(product, facility, operations),
                "Solid waste generation" => self.calculate_waste_impact(product, facility, operations),
                _ => self.calculate_generic_processing_impact(product, facility, country, category),
            };

            // Apply facility-specific adjustments
            let adjusted_impact = self.apply_facility_adjustments(impact_value, facility, operations, category);

            // Calculate uncertainty
            let uncertainty_range = (adjusted_impact * 0.7, adjusted_impact * 1.3); // Simplified uncertainty

            impacts.insert(category.clone(), MidpointResult {
                value: adjusted_impact,
                unit: self.get_processing_impact_unit(category),
                uncertainty_range,
                data_quality_score: 0.7, // Medium quality for processing data
                contributing_sources: vec!["Processing calculations".to_string()],
            });
        }

        Ok(impacts)
    }

    fn calculate_gwp_impact(
        &self,
        product: &ProcessedProduct,
        facility: &ProcessingFacilityProfile,
        operations: &ProcessingOperations
    ) -> f64 {
        let mut total_gwp = 0.0;

        // Energy-related emissions
        let energy_gwp = match operations.energy_management.primary_energy_source {
            EnergySource::GridElectricity => {
                // Emission factor for West African grid (kg CO2/kWh)
                let grid_factor = 0.45; // Average for Ghana/Nigeria
                let energy_per_tonne = self.estimate_energy_consumption_per_tonne(product, facility);
                energy_per_tonne * grid_factor * product.annual_production
            },
            EnergySource::DieselGenerator => {
                let diesel_factor = 2.68; // kg CO2/liter
                let fuel_consumption = operations.energy_management.monthly_fuel_consumption.unwrap_or(1000.0) * 12.0;
                fuel_consumption * diesel_factor
            },
            EnergySource::SolarPower => {
                // Very low emissions for solar
                let solar_factor = 0.05; // kg CO2/kWh
                let energy_per_tonne = self.estimate_energy_consumption_per_tonne(product, facility);
                energy_per_tonne * solar_factor * product.annual_production
            },
            _ => {
                // Default mixed energy factor
                let mixed_factor = 0.35;
                let energy_per_tonne = self.estimate_energy_consumption_per_tonne(product, facility);
                energy_per_tonne * mixed_factor * product.annual_production
            },
        };

        total_gwp += energy_gwp;

        // Process-specific emissions
        for step in &product.processing_steps {
            if let Some(step_emissions) = step.emissions_factor {
                total_gwp += step_emissions * product.annual_production;
            }
        }

        // Waste-related emissions
        let waste_gwp = match operations.waste_management.waste_disposal_method {
            WasteDisposalMethod::Landfill => {
                // Methane emissions from organic waste in landfill
                let organic_waste = operations.waste_management.solid_waste_generation.unwrap_or(100.0) * 365.0;
                let organic_fraction = operations.waste_management.organic_waste_percentage / 100.0;
                organic_waste * organic_fraction * 0.5 // kg CO2-eq/kg organic waste
            },
            WasteDisposalMethod::Composting => {
                // Lower emissions from composting
                let organic_waste = operations.waste_management.solid_waste_generation.unwrap_or(100.0) * 365.0;
                let organic_fraction = operations.waste_management.organic_waste_percentage / 100.0;
                organic_waste * organic_fraction * 0.1
            },
            WasteDisposalMethod::AnaerobicDigestion => {
                // Negative emissions due to biogas capture
                let organic_waste = operations.waste_management.solid_waste_generation.unwrap_or(100.0) * 365.0;
                let organic_fraction = operations.waste_management.organic_waste_percentage / 100.0;
                -(organic_waste * organic_fraction * 0.2) // Carbon credit
            },
            _ => 0.0,
        };

        total_gwp += waste_gwp;

        total_gwp
    }

    fn calculate_energy_impact(
        &self,
        product: &ProcessedProduct,
        facility: &ProcessingFacilityProfile,
        _operations: &ProcessingOperations
    ) -> f64 {
        // Calculate total energy consumption
        let energy_per_tonne = self.estimate_energy_consumption_per_tonne(product, facility);
        energy_per_tonne * product.annual_production
    }

    fn calculate_water_impact(
        &self,
        product: &ProcessedProduct,
        _facility: &ProcessingFacilityProfile,
        operations: &ProcessingOperations
    ) -> f64 {
        // Calculate water consumption per tonne of product
        let base_water_per_tonne = product.processing_steps.iter()
            .map(|step| step.water_usage)
            .sum::<f64>();

        // Add cooling and cleaning water (estimate)
        let additional_water = base_water_per_tonne * 0.3; // 30% additional for cooling/cleaning
        
        let total_water_per_tonne = base_water_per_tonne + additional_water;
        
        // Apply water efficiency factor
        let efficiency_factor = match operations.water_management.water_conservation_measures.len() {
            0 => 1.0,
            1..=2 => 0.9,
            3..=4 => 0.8,
            _ => 0.7,
        };

        total_water_per_tonne * efficiency_factor * product.annual_production / 1000.0 // Convert to m3
    }

    fn calculate_wastewater_impact(
        &self,
        product: &ProcessedProduct,
        _facility: &ProcessingFacilityProfile,
        operations: &ProcessingOperations
    ) -> f64 {
        // Estimate wastewater as 80% of water consumption
        let water_impact = self.calculate_water_impact(product, _facility, operations);
        
        // Apply treatment factor
        let treatment_factor = match operations.water_management.wastewater_treatment {
            WastewaterTreatment::None => 1.0,
            WastewaterTreatment::BasicSedimentation => 0.8,
            WastewaterTreatment::BiologicalTreatment => 0.6,
            WastewaterTreatment::ChemicalTreatment => 0.5,
            WastewaterTreatment::Advanced => 0.3,
        };

        water_impact * 0.8 * treatment_factor
    }

    fn calculate_waste_impact(
        &self,
        product: &ProcessedProduct,
        _facility: &ProcessingFacilityProfile,
        operations: &ProcessingOperations
    ) -> f64 {
        // Calculate waste per tonne of production
        let daily_waste = operations.waste_management.solid_waste_generation.unwrap_or(100.0);
        let annual_waste = daily_waste * _facility.operational_days_per_year as f64;
        
        // Allocate to this product based on production volume
        let facility_total_production = _facility.processing_capacity * _facility.operational_days_per_year as f64;
        let allocation_factor = product.annual_production / facility_total_production;
        
        annual_waste * allocation_factor
    }

    fn calculate_generic_processing_impact(
        &self,
        product: &ProcessedProduct,
        facility: &ProcessingFacilityProfile,
        country: &Country,
        category: &str
    ) -> f64 {
        // Try to find specific impact factor
        let key = format!("{:?}_{:?}_{:?}_{}", 
            facility.facility_type, 
            product.product_type, 
            country, 
            category);
        
        if let Some(factor) = self.impact_factors.get(&key) {
            return factor.value_per_tonne * product.annual_production;
        }

        // Fallback to default estimates
        self.get_default_processing_impact(&facility.facility_type, &product.product_type, category) * product.annual_production
    }

    fn estimate_energy_consumption_per_tonne(
        &self,
        product: &ProcessedProduct,
        facility: &ProcessingFacilityProfile
    ) -> f64 {
        // Sum energy intensity from all processing steps
        let step_energy: f64 = product.processing_steps.iter()
            .map(|step| step.energy_intensity)
            .sum();

        // Add overhead energy (lighting, administration, etc.)
        let overhead_factor = match facility.facility_type {
            ProcessingFacilityType::Mill => 1.2,
            ProcessingFacilityType::Bakery => 1.5,
            ProcessingFacilityType::FishProcessing => 1.8, // Refrigeration
            ProcessingFacilityType::MeatProcessing => 1.8,
            ProcessingFacilityType::DairyProcessing => 1.6,
            _ => 1.3,
        };

        step_energy * overhead_factor
    }

    fn apply_facility_adjustments(
        &self,
        base_impact: f64,
        facility: &ProcessingFacilityProfile,
        operations: &ProcessingOperations,
        category: &str
    ) -> f64 {
        let mut adjusted_impact = base_impact;

        // Facility scale efficiency (economies of scale)
        let scale_factor = match facility.processing_capacity {
            cap if cap < 10.0 => 1.2,    // Small facilities less efficient
            cap if cap < 100.0 => 1.0,   // Medium facilities baseline
            cap if cap < 1000.0 => 0.9,  // Large facilities more efficient
            _ => 0.8,                     // Very large facilities most efficient
        };
        adjusted_impact *= scale_factor;

        // Facility age efficiency
        let age_factor = if let Some(year) = facility.established_year {
            let age = 2024 - year;
            match age {
                0..=5 => 0.9,      // New facilities more efficient
                6..=15 => 1.0,     // Modern facilities baseline
                16..=30 => 1.1,    // Aging facilities less efficient
                _ => 1.2,          // Old facilities least efficient
            }
        } else { 1.0 };
        adjusted_impact *= age_factor;

        // Location type adjustments
        let location_factor = match facility.location_type {
            LocationType::Industrial => 0.95, // Better infrastructure
            LocationType::Urban => 1.0,       // Standard
            LocationType::PeriUrban => 1.05,  // Slightly less efficient
            LocationType::Rural => 1.1,       // Less efficient infrastructure
        };
        adjusted_impact *= location_factor;

        // Equipment efficiency adjustments
        let efficiency_factor = match operations.equipment_efficiency.equipment_age {
            EquipmentAge::New => 0.9,
            EquipmentAge::Recent => 0.95,
            EquipmentAge::Mature => 1.0,
            EquipmentAge::Old => 1.15,
            EquipmentAge::VeryOld => 1.3,
        };
        adjusted_impact *= efficiency_factor;

        // Maintenance frequency adjustments
        let maintenance_factor = match operations.equipment_efficiency.maintenance_frequency {
            MaintenanceFrequency::Daily | MaintenanceFrequency::Weekly => 0.95,
            MaintenanceFrequency::Monthly => 1.0,
            MaintenanceFrequency::Quarterly => 1.05,
            _ => 1.1,
        };

        adjusted_impact *= maintenance_factor;

        // Category-specific adjustments
        match category {
            "Energy consumption" | "Global warming" => {
                // Renewable energy reduces these impacts
                let renewable_factor = 1.0 - (operations.energy_management.renewable_energy_percentage / 100.0 * 0.8);
                adjusted_impact *= renewable_factor;
            },
            "Water consumption" | "Water scarcity" => {
                // Water conservation measures
                let conservation_factor = 1.0 - (operations.water_management.water_conservation_measures.len() as f64 * 0.05);
                adjusted_impact *= conservation_factor.max(0.7);
            },
            _ => {}
        }

        adjusted_impact
    }

    fn apply_processing_adjustments(
        &self,
        impacts: &mut HashMap<String, MidpointResult>,
        operations: &ProcessingOperations,
        country: &Country
    ) {
        // Apply regional water scarcity adjustments
        if let Some(water_result) = impacts.get_mut("Water consumption") {
            let aware_factor = match country {
                Country::Ghana => 20.0,
                Country::Nigeria => 25.0, // Higher scarcity in northern regions
                _ => 1.0,
            };

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

        // Apply waste management efficiency
        if let Some(waste_result) = impacts.get_mut("Solid waste generation") {
            let recycling_factor = 1.0 - (operations.waste_management.recycling_programs.len() as f64 * 0.1);
            waste_result.value *= recycling_factor.max(0.5);
        }
    }

    fn calculate_processing_endpoint_impacts(
        &self,
        midpoint: &HashMap<String, MidpointResult>
    ) -> Result<HashMap<String, EndpointResult>, Box<dyn std::error::Error>> {
        
        let mut endpoint = HashMap::new();

        // Human Health (DALY)
        let mut human_health = 0.0;

        if let Some(gwp) = midpoint.get("Global warming") {
            human_health += gwp.value * self.characterization_factors.human_health.climate_health_africa;
        }

        if let Some(air_pollution) = midpoint.get("Air pollution") {
            human_health += air_pollution.value * self.characterization_factors.human_health.air_quality_health_africa;
        }

        endpoint.insert("Human Health".to_string(), EndpointResult {
            value: human_health,
            unit: "DALY".to_string(),
            uncertainty_range: (human_health * 0.5, human_health * 2.0),
            normalization_factor: Some(5.2e-2),
            regional_adaptation_factor: Some(1.5),
        });

        // Resource Scarcity (USD)
        let mut resource_scarcity = 0.0;

        if let Some(energy) = midpoint.get("Energy consumption") {
            resource_scarcity += energy.value * 0.08; // USD per kWh
        }

        if let Some(water_scarcity) = midpoint.get("Water scarcity") {
            resource_scarcity += water_scarcity.value * self.characterization_factors.resource_scarcity.water_scarcity_africa;
        }

        endpoint.insert("Resource Scarcity".to_string(), EndpointResult {
            value: resource_scarcity,
            unit: "USD".to_string(),
            uncertainty_range: (resource_scarcity * 0.7, resource_scarcity * 1.5),
            normalization_factor: Some(8.5e3),
            regional_adaptation_factor: Some(1.3),
        });

        Ok(endpoint)
    }

    fn calculate_processing_single_score(
        &self,
        endpoint: &HashMap<String, EndpointResult>
    ) -> Result<SingleScoreResult, Box<dyn std::error::Error>> {
        
        let weighting_factors = HashMap::from([
            ("Human Health".to_string(), 0.6),      // Higher weight for health in processing
            ("Resource Scarcity".to_string(), 0.4), // Resource efficiency important
        ]);

        let mut single_score = 0.0;
        
        for (category, result) in endpoint {
            if let Some(weight) = weighting_factors.get(category) {
                single_score += result.value * weight;
            }
        }

        // Normalize to 0-1 scale using sigmoid function
        let normalized_score = 1.0 / (1.0 + (-0.1 * (single_score - 50.0)).exp());

        Ok(SingleScoreResult {
            value: normalized_score,
            unit: "Processing Environmental Impact Index (0-1, lower is better)".to_string(),
            uncertainty_range: (normalized_score * 0.8, normalized_score * 1.2),
            weighting_factors,
            methodology: "Processing-adapted African LCA methodology".to_string(),
        })
    }

    fn assess_processing_data_quality(
        &self,
        products: &[ProcessedProduct],
        _country: &Country
    ) -> Result<DataQuality, Box<dyn std::error::Error>> {
        
        let mut warnings = Vec::new();
        let mut recommendations = Vec::new();

        // Check data completeness
        for product in products {
            if product.processing_steps.is_empty() {
                warnings.push(format!("No processing steps defined for {}", product.name));
            }
            
            if product.raw_material_inputs.is_empty() {
                warnings.push(format!("No raw material inputs defined for {}", product.name));
            }
        }

        // Generate recommendations
        recommendations.push("Consider implementing energy monitoring systems for better data quality".to_string());
        recommendations.push("Regular water consumption monitoring recommended".to_string());

        let confidence_level = if warnings.len() > products.len() {
            ConfidenceLevel::Low
        } else {
            ConfidenceLevel::Medium
        };

        Ok(DataQuality {
            overall_confidence: confidence_level,
            data_source_mix: vec![
                DataSourceContribution {
                    source_type: DataSource::Estimated,
                    percentage: 60.0,
                    quality_score: 0.6,
                },
                DataSourceContribution {
                    source_type: DataSource::Global,
                    percentage: 40.0,
                    quality_score: 0.5,
                },
            ],
            regional_adaptation: true,
            completeness_score: 0.7,
            temporal_representativeness: 0.8,
            geographical_representativeness: 0.6,
            technological_representativeness: 0.7,
            warnings,
            recommendations,
        })
    }

    fn generate_processing_recommendations(
        &self,
        impacts: &HashMap<String, MidpointResult>,
        _facility: &ProcessingFacilityProfile,
        operations: &ProcessingOperations
    ) -> Result<Vec<ProcessingRecommendation>, Box<dyn std::error::Error>> {
        
        let mut recommendations = Vec::new();

        // Energy efficiency recommendations
        if let Some(energy_impact) = impacts.get("Energy consumption") {
            if energy_impact.value > 1000.0 { // High energy consumption threshold
                match operations.energy_management.primary_energy_source {
                    EnergySource::DieselGenerator => {
                        recommendations.push(ProcessingRecommendation {
                            category: ProcessingRecommendationCategory::EnergyEfficiency,
                            title: "Switch to grid electricity or solar power".to_string(),
                            description: "Reduce reliance on diesel generators by connecting to the grid or installing solar panels".to_string(),
                            potential_savings: HashMap::from([
                                ("Global warming".to_string(), 40.0),
                                ("Energy consumption".to_string(), 20.0),
                            ]),
                            complexity: ComplexityLevel::Moderate,
                            implementation_cost: ImplementationCost::High,
                            payback_period: Some(24.0),
                            priority: ProcessingPriority::High,
                        });
                    },
                    _ => {
                        recommendations.push(ProcessingRecommendation {
                            category: ProcessingRecommendationCategory::EnergyEfficiency,
                            title: "Implement energy-efficient equipment".to_string(),
                            description: "Upgrade to energy-efficient motors, LED lighting, and optimize equipment operation".to_string(),
                            potential_savings: HashMap::from([
                                ("Energy consumption".to_string(), 25.0),
                                ("Global warming".to_string(), 20.0),
                            ]),
                            complexity: ComplexityLevel::Moderate,
                            implementation_cost: ImplementationCost::Medium,
                            payback_period: Some(18.0),
                            priority: ProcessingPriority::Medium,
                        });
                    }
                }
            }
        }

        // Water conservation recommendations
        if let Some(water_impact) = impacts.get("Water consumption") {
            if water_impact.value > 500.0 { // High water consumption threshold
                recommendations.push(ProcessingRecommendation {
                            category: ProcessingRecommendationCategory::WaterConservation,
                    title: "Install water recycling system".to_string(),
                    description: "Implement water treatment and recycling for process water reuse".to_string(),
                    potential_savings: HashMap::from([
                        ("Water consumption".to_string(), 40.0),
                        ("Water scarcity".to_string(), 40.0),
                    ]),
                    complexity: ComplexityLevel::Complex,
                    implementation_cost: ImplementationCost::High,
                    payback_period: Some(36.0),
                    priority: ProcessingPriority::High,
                });
            }
        }

        // Waste management recommendations
        if let Some(waste_impact) = impacts.get("Solid waste generation") {
            if waste_impact.value > 1000.0 { // High waste generation threshold
                match operations.waste_management.waste_disposal_method {
                    WasteDisposalMethod::Landfill => {
                        recommendations.push(ProcessingRecommendation {
                            category: ProcessingRecommendationCategory::WasteReduction,
                            title: "Implement composting or anaerobic digestion".to_string(),
                            description: "Convert organic waste to compost or biogas instead of landfilling".to_string(),
                            potential_savings: HashMap::from([
                                ("Global warming".to_string(), 60.0),
                                ("Solid waste generation".to_string(), 80.0),
                            ]),
                            complexity: ComplexityLevel::Moderate,
                            implementation_cost: ImplementationCost::Medium,
                            payback_period: Some(24.0),
                            priority: ProcessingPriority::High,
                        });
                    },
                    _ => {
                        recommendations.push(ProcessingRecommendation {
                            category: ProcessingRecommendationCategory::WasteReduction,
                            title: "Increase waste reduction and recycling".to_string(),
                            description: "Implement waste minimization practices and expand recycling programs".to_string(),
                            potential_savings: HashMap::from([
                                ("Solid waste generation".to_string(), 30.0),
                            ]),
                            complexity: ComplexityLevel::Simple,
                            implementation_cost: ImplementationCost::Low,
                            payback_period: Some(12.0),
                            priority: ProcessingPriority::Medium,
                        });
                    }
                }
            }
        }

        // Equipment efficiency recommendations
        match operations.equipment_efficiency.equipment_age {
            EquipmentAge::Old | EquipmentAge::VeryOld => {
                recommendations.push(ProcessingRecommendation {
                            category: ProcessingRecommendationCategory::EquipmentUpgrade,
                    title: "Equipment modernization program".to_string(),
                    description: "Develop a phased approach to replace old equipment with energy-efficient alternatives".to_string(),
                    potential_savings: HashMap::from([
                        ("Energy consumption".to_string(), 35.0),
                        ("Global warming".to_string(), 25.0),
                    ]),
                    complexity: ComplexityLevel::Complex,
                    implementation_cost: ImplementationCost::High,
                    payback_period: Some(48.0),
                    priority: ProcessingPriority::Medium,
                });
            },
            _ => {}
        }

        Ok(recommendations)
    }

    fn aggregate_midpoint_results(&self, total: &mut MidpointResult, addition: &MidpointResult) {
        total.value += addition.value;
        
        // Simple uncertainty propagation
        let total_variance = (total.uncertainty_range.1 - total.uncertainty_range.0).powi(2) / 16.0;
        let addition_variance = (addition.uncertainty_range.1 - addition.uncertainty_range.0).powi(2) / 16.0;
        let combined_variance = total_variance + addition_variance;
        let combined_std = combined_variance.sqrt();

        total.uncertainty_range = (
            (total.value - 2.0 * combined_std).max(0.0),
            total.value + 2.0 * combined_std
        );

        total.contributing_sources.extend(addition.contributing_sources.clone());
    }

    fn get_default_processing_impact(&self, facility_type: &ProcessingFacilityType, product_type: &ProductType, impact: &str) -> f64 {
        match (facility_type, product_type, impact) {
            // Mill impacts
            (ProcessingFacilityType::Mill, ProductType::FlourMaize, "Global warming") => 0.15, // kg CO2-eq/tonne
            (ProcessingFacilityType::Mill, ProductType::FlourMaize, "Energy consumption") => 80.0, // kWh/tonne
            (ProcessingFacilityType::Mill, ProductType::FlourMaize, "Water consumption") => 2.0, // m3/tonne
            
            (ProcessingFacilityType::Mill, ProductType::RiceProcessed, "Global warming") => 0.25,
            (ProcessingFacilityType::Mill, ProductType::RiceProcessed, "Energy consumption") => 120.0,
            (ProcessingFacilityType::Mill, ProductType::RiceProcessed, "Water consumption") => 4.0,
            
            // Palm oil mill impacts
            (ProcessingFacilityType::PalmOilMill, ProductType::PalmOil, "Global warming") => 0.6,
            (ProcessingFacilityType::PalmOilMill, ProductType::PalmOil, "Energy consumption") => 200.0,
            (ProcessingFacilityType::PalmOilMill, ProductType::PalmOil, "Water consumption") => 8.0,
            
            // Cassava processing
            (ProcessingFacilityType::CassivaProcessing, ProductType::FlourCassava, "Global warming") => 0.1,
            (ProcessingFacilityType::CassivaProcessing, ProductType::FlourCassava, "Energy consumption") => 60.0,
            (ProcessingFacilityType::CassivaProcessing, ProductType::FlourCassava, "Water consumption") => 3.0,
            
            // Bakery impacts
            (ProcessingFacilityType::Bakery, ProductType::BakedGoods, "Global warming") => 0.8,
            (ProcessingFacilityType::Bakery, ProductType::BakedGoods, "Energy consumption") => 300.0,
            (ProcessingFacilityType::Bakery, ProductType::BakedGoods, "Water consumption") => 1.5,
            
            // Fish processing
            (ProcessingFacilityType::FishProcessing, ProductType::ProcessedFish, "Global warming") => 1.2,
            (ProcessingFacilityType::FishProcessing, ProductType::ProcessedFish, "Energy consumption") => 400.0, // High due to refrigeration
            (ProcessingFacilityType::FishProcessing, ProductType::ProcessedFish, "Water consumption") => 10.0,
            
            // Default fallbacks
            _ => match impact {
                "Global warming" => 0.5,
                "Energy consumption" => 150.0,
                "Water consumption" => 3.0,
                "Solid waste generation" => 50.0,
                "Wastewater generation" => 2.0,
                _ => 0.1,
            },
        }
    }
}
