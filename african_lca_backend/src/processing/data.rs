use crate::models::*;
use crate::processing::models::*;
use std::error::Error;
use std::collections::HashMap;

pub struct ProcessingDataLoader {
    pub impact_factors: Vec<ProcessingImpactFactor>,
    pub benchmarks: Vec<ProcessingBenchmark>,
    pub regional_factors: HashMap<String, f64>,
}

impl ProcessingDataLoader {
    pub fn new() -> Self {
        Self {
            impact_factors: Vec::new(),
            benchmarks: Vec::new(),
            regional_factors: Self::initialize_processing_regional_factors(),
        }
    }

    fn initialize_processing_regional_factors() -> HashMap<String, f64> {
        let mut factors = HashMap::new();
        
        // Energy emission factors by country (kg CO2/kWh)
        factors.insert("Ghana_grid_emission_factor".to_string(), 0.45);
        factors.insert("Nigeria_grid_emission_factor".to_string(), 0.52);
        
        // Water scarcity factors for processing industries
        factors.insert("Ghana_processing_water_scarcity".to_string(), 25.0);
        factors.insert("Nigeria_north_processing_water_scarcity".to_string(), 35.0);
        factors.insert("Nigeria_south_processing_water_scarcity".to_string(), 20.0);
        
        // Waste management efficiency factors
        factors.insert("Ghana_waste_management_efficiency".to_string(), 0.3);
        factors.insert("Nigeria_waste_management_efficiency".to_string(), 0.25);
        
        // Labor productivity factors (output per worker-hour)
        factors.insert("Ghana_processing_productivity".to_string(), 2.5);
        factors.insert("Nigeria_processing_productivity".to_string(), 2.2);
        
        factors
    }

    pub fn load_default_factors(&mut self) -> Result<(), Box<dyn Error>> {
        // Load Ghana-specific processing factors
        self.add_ghana_processing_factors();
        
        // Load Nigeria-specific processing factors
        self.add_nigeria_processing_factors();
        
        // Load global processing factors as fallback
        self.add_global_processing_factors();
        
        // Load processing benchmarks
        self.add_processing_benchmarks();
        
        Ok(())
    }

    fn add_ghana_processing_factors(&mut self) {
        let ghana_factors = vec![
            // MAIZE MILLING - Ghana specific data
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::Mill,
                product_type: ProductType::FlourMaize,
                country: Country::Ghana,
                impact_category: "Global warming".to_string(),
                value_per_tonne: 0.12, // kg CO2-eq/tonne flour - efficient operations
                unit: "kg CO2-eq".to_string(),
                confidence: ConfidenceLevel::High,
                source: "Ghana Association of Millers 2024; Energy audit data".to_string(),
                year: 2024,
                uncertainty_range: (0.08, 0.18),
                pedigree_score: PedigreeScore {
                    reliability: 2,
                    completeness: 2,
                    temporal_correlation: 1,
                    geographical_correlation: 1,
                    technological_correlation: 2,
                },
            },
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::Mill,
                product_type: ProductType::FlourMaize,
                country: Country::Ghana,
                impact_category: "Energy consumption".to_string(),
                value_per_tonne: 65.0, // kWh/tonne - modern mills in Ghana
                unit: "kWh".to_string(),
                confidence: ConfidenceLevel::High,
                source: "Ghana Standards Authority; Mill efficiency study 2024".to_string(),
                year: 2024,
                uncertainty_range: (50.0, 85.0),
                pedigree_score: PedigreeScore {
                    reliability: 2,
                    completeness: 2,
                    temporal_correlation: 1,
                    geographical_correlation: 1,
                    technological_correlation: 2,
                },
            },
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::Mill,
                product_type: ProductType::FlourMaize,
                country: Country::Ghana,
                impact_category: "Water consumption".to_string(),
                value_per_tonne: 1.8, // m3/tonne - dry milling process
                unit: "m3".to_string(),
                confidence: ConfidenceLevel::Medium,
                source: "Ghana Water Company; Industrial water use survey 2023".to_string(),
                year: 2024,
                uncertainty_range: (1.2, 2.5),
                pedigree_score: PedigreeScore {
                    reliability: 3,
                    completeness: 3,
                    temporal_correlation: 2,
                    geographical_correlation: 1,
                    technological_correlation: 3,
                },
            },

            // CASSAVA PROCESSING - Major industry in Ghana
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::CassivaProcessing,
                product_type: ProductType::FlourCassava,
                country: Country::Ghana,
                impact_category: "Global warming".to_string(),
                value_per_tonne: 0.08, // Very low emissions for cassava flour
                unit: "kg CO2-eq".to_string(),
                confidence: ConfidenceLevel::Medium,
                source: "IITA Ghana cassava processing study 2024".to_string(),
                year: 2024,
                uncertainty_range: (0.05, 0.12),
                pedigree_score: PedigreeScore {
                    reliability: 3,
                    completeness: 3,
                    temporal_correlation: 2,
                    geographical_correlation: 1,
                    technological_correlation: 3,
                },
            },
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::CassivaProcessing,
                product_type: ProductType::FlourCassava,
                country: Country::Ghana,
                impact_category: "Energy consumption".to_string(),
                value_per_tonne: 45.0, // kWh/tonne - mainly for drying and milling
                unit: "kWh".to_string(),
                confidence: ConfidenceLevel::Medium,
                source: "Ghana cassava processing energy assessment 2024".to_string(),
                year: 2024,
                uncertainty_range: (30.0, 65.0),
                pedigree_score: PedigreeScore {
                    reliability: 3,
                    completeness: 3,
                    temporal_correlation: 2,
                    geographical_correlation: 1,
                    technological_correlation: 3,
                },
            },
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::CassivaProcessing,
                product_type: ProductType::FlourCassava,
                country: Country::Ghana,
                impact_category: "Water consumption".to_string(),
                value_per_tonne: 2.5, // m3/tonne - washing and processing
                unit: "m3".to_string(),
                confidence: ConfidenceLevel::High,
                source: "Ghana cassava value chain water assessment 2024".to_string(),
                year: 2024,
                uncertainty_range: (2.0, 3.2),
                pedigree_score: PedigreeScore {
                    reliability: 2,
                    completeness: 2,
                    temporal_correlation: 1,
                    geographical_correlation: 1,
                    technological_correlation: 2,
                },
            },

            // PALM OIL PROCESSING - Important for Ghana
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::PalmOilMill,
                product_type: ProductType::PalmOil,
                country: Country::Ghana,
                impact_category: "Global warming".to_string(),
                value_per_tonne: 0.45, // kg CO2-eq/tonne palm oil - modern mills
                unit: "kg CO2-eq".to_string(),
                confidence: ConfidenceLevel::Medium,
                source: "Ghana palm oil industry LCA 2023; RSPO data".to_string(),
                year: 2024,
                uncertainty_range: (0.3, 0.7),
                pedigree_score: PedigreeScore {
                    reliability: 3,
                    completeness: 3,
                    temporal_correlation: 2,
                    geographical_correlation: 1,
                    technological_correlation: 3,
                },
            },
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::PalmOilMill,
                product_type: ProductType::PalmOil,
                country: Country::Ghana,
                impact_category: "Water consumption".to_string(),
                value_per_tonne: 6.0, // m3/tonne - sterilization and washing
                unit: "m3".to_string(),
                confidence: ConfidenceLevel::High,
                source: "Ghana Oil Palm Development Association 2024".to_string(),
                year: 2024,
                uncertainty_range: (4.5, 8.0),
                pedigree_score: PedigreeScore {
                    reliability: 2,
                    completeness: 2,
                    temporal_correlation: 1,
                    geographical_correlation: 1,
                    technological_correlation: 2,
                },
            },

            // FISH PROCESSING - Coastal Ghana
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::FishProcessing,
                product_type: ProductType::ProcessedFish,
                country: Country::Ghana,
                impact_category: "Global warming".to_string(),
                value_per_tonne: 0.85, // kg CO2-eq/tonne - refrigeration intensive
                unit: "kg CO2-eq".to_string(),
                confidence: ConfidenceLevel::Medium,
                source: "Ghana fisheries processing industry study 2024".to_string(),
                year: 2024,
                uncertainty_range: (0.6, 1.2),
                pedigree_score: PedigreeScore {
                    reliability: 3,
                    completeness: 4,
                    temporal_correlation: 2,
                    geographical_correlation: 1,
                    technological_correlation: 4,
                },
            },
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::FishProcessing,
                product_type: ProductType::ProcessedFish,
                country: Country::Ghana,
                impact_category: "Energy consumption".to_string(),
                value_per_tonne: 320.0, // kWh/tonne - high due to cold storage
                unit: "kWh".to_string(),
                confidence: ConfidenceLevel::High,
                source: "Ghana cold chain energy audit 2024".to_string(),
                year: 2024,
                uncertainty_range: (250.0, 400.0),
                pedigree_score: PedigreeScore {
                    reliability: 2,
                    completeness: 2,
                    temporal_correlation: 1,
                    geographical_correlation: 1,
                    technological_correlation: 3,
                },
            },
        ];

        self.impact_factors.extend(ghana_factors);
    }

    fn add_nigeria_processing_factors(&mut self) {
        let nigeria_factors = vec![
            // RICE MILLING - Major industry in Nigeria
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::RiceProcessing,
                product_type: ProductType::RiceProcessed,
                country: Country::Nigeria,
                impact_category: "Global warming".to_string(),
                value_per_tonne: 0.22, // kg CO2-eq/tonne - parboiling increases emissions
                unit: "kg CO2-eq".to_string(),
                confidence: ConfidenceLevel::High,
                source: "Nigeria Rice Processors Association 2024; IRRI data".to_string(),
                year: 2024,
                uncertainty_range: (0.15, 0.35),
                pedigree_score: PedigreeScore {
                    reliability: 2,
                    completeness: 2,
                    temporal_correlation: 1,
                    geographical_correlation: 1,
                    technological_correlation: 2,
                },
            },
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::RiceProcessing,
                product_type: ProductType::RiceProcessed,
                country: Country::Nigeria,
                impact_category: "Energy consumption".to_string(),
                value_per_tonne: 110.0, // kWh/tonne - includes parboiling energy
                unit: "kWh".to_string(),
                confidence: ConfidenceLevel::High,
                source: "Nigeria rice processing energy study 2024".to_string(),
                year: 2024,
                uncertainty_range: (85.0, 140.0),
                pedigree_score: PedigreeScore {
                    reliability: 2,
                    completeness: 2,
                    temporal_correlation: 1,
                    geographical_correlation: 1,
                    technological_correlation: 2,
                },
            },
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::RiceProcessing,
                product_type: ProductType::RiceProcessed,
                country: Country::Nigeria,
                impact_category: "Water consumption".to_string(),
                value_per_tonne: 3.5, // m3/tonne - parboiling requires more water
                unit: "m3".to_string(),
                confidence: ConfidenceLevel::High,
                source: "Nigeria rice processing water assessment 2024".to_string(),
                year: 2024,
                uncertainty_range: (2.8, 4.5),
                pedigree_score: PedigreeScore {
                    reliability: 2,
                    completeness: 2,
                    temporal_correlation: 1,
                    geographical_correlation: 1,
                    technological_correlation: 2,
                },
            },

            // CASSAVA PROCESSING - Nigeria is world's largest producer
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::CassivaProcessing,
                product_type: ProductType::FlourCassava,
                country: Country::Nigeria,
                impact_category: "Global warming".to_string(),
                value_per_tonne: 0.06, // Very efficient large-scale operations
                unit: "kg CO2-eq".to_string(),
                confidence: ConfidenceLevel::High,
                source: "IITA Nigeria cassava processing assessment 2024".to_string(),
                year: 2024,
                uncertainty_range: (0.04, 0.09),
                pedigree_score: PedigreeScore {
                    reliability: 2,
                    completeness: 2,
                    temporal_correlation: 1,
                    geographical_correlation: 1,
                    technological_correlation: 2,
                },
            },
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::CassivaProcessing,
                product_type: ProductType::FlourCassava,
                country: Country::Nigeria,
                impact_category: "Energy consumption".to_string(),
                value_per_tonne: 38.0, // kWh/tonne - efficient large operations
                unit: "kWh".to_string(),
                confidence: ConfidenceLevel::High,
                source: "Nigeria cassava processing efficiency study 2024".to_string(),
                year: 2024,
                uncertainty_range: (30.0, 50.0),
                pedigree_score: PedigreeScore {
                    reliability: 2,
                    completeness: 2,
                    temporal_correlation: 1,
                    geographical_correlation: 1,
                    technological_correlation: 2,
                },
            },

            // FLOUR MILLING - Wheat and other grains
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::Mill,
                product_type: ProductType::FlourWheat,
                country: Country::Nigeria,
                impact_category: "Global warming".to_string(),
                value_per_tonne: 0.18, // kg CO2-eq/tonne - imported wheat processing
                unit: "kg CO2-eq".to_string(),
                confidence: ConfidenceLevel::Medium,
                source: "Nigeria flour millers association 2024".to_string(),
                year: 2024,
                uncertainty_range: (0.12, 0.25),
                pedigree_score: PedigreeScore {
                    reliability: 3,
                    completeness: 3,
                    temporal_correlation: 2,
                    geographical_correlation: 1,
                    technological_correlation: 3,
                },
            },
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::Mill,
                product_type: ProductType::FlourWheat,
                country: Country::Nigeria,
                impact_category: "Energy consumption".to_string(),
                value_per_tonne: 75.0, // kWh/tonne
                unit: "kWh".to_string(),
                confidence: ConfidenceLevel::High,
                source: "Nigeria milling industry energy survey 2024".to_string(),
                year: 2024,
                uncertainty_range: (60.0, 95.0),
                pedigree_score: PedigreeScore {
                    reliability: 2,
                    completeness: 2,
                    temporal_correlation: 1,
                    geographical_correlation: 1,
                    technological_correlation: 2,
                },
            },

            // PALM OIL PROCESSING - Growing industry
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::PalmOilMill,
                product_type: ProductType::PalmOil,
                country: Country::Nigeria,
                impact_category: "Global warming".to_string(),
                value_per_tonne: 0.52, // Slightly higher than Ghana due to less efficient operations
                unit: "kg CO2-eq".to_string(),
                confidence: ConfidenceLevel::Medium,
                source: "Nigeria palm oil development initiative 2024".to_string(),
                year: 2024,
                uncertainty_range: (0.35, 0.8),
                pedigree_score: PedigreeScore {
                    reliability: 3,
                    completeness: 4,
                    temporal_correlation: 2,
                    geographical_correlation: 1,
                    technological_correlation: 4,
                },
            },

            // MEAT PROCESSING - Growing urban demand
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::MeatProcessing,
                product_type: ProductType::ProcessedMeat,
                country: Country::Nigeria,
                impact_category: "Global warming".to_string(),
                value_per_tonne: 1.8, // kg CO2-eq/tonne - high due to refrigeration and processing
                unit: "kg CO2-eq".to_string(),
                confidence: ConfidenceLevel::Low,
                source: "Nigeria meat processing industry assessment 2023".to_string(),
                year: 2024,
                uncertainty_range: (1.2, 2.8),
                pedigree_score: PedigreeScore {
                    reliability: 4,
                    completeness: 4,
                    temporal_correlation: 3,
                    geographical_correlation: 2,
                    technological_correlation: 4,
                },
            },
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::MeatProcessing,
                product_type: ProductType::ProcessedMeat,
                country: Country::Nigeria,
                impact_category: "Energy consumption".to_string(),
                value_per_tonne: 450.0, // kWh/tonne - very high for cold chain
                unit: "kWh".to_string(),
                confidence: ConfidenceLevel::Medium,
                source: "Nigeria cold chain energy assessment 2024".to_string(),
                year: 2024,
                uncertainty_range: (350.0, 600.0),
                pedigree_score: PedigreeScore {
                    reliability: 3,
                    completeness: 3,
                    temporal_correlation: 2,
                    geographical_correlation: 2,
                    technological_correlation: 4,
                },
            },
        ];

        self.impact_factors.extend(nigeria_factors);
    }

    fn add_global_processing_factors(&mut self) {
        let global_factors = vec![
            // Generic mill processing - global averages
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::Mill,
                product_type: ProductType::FlourMaize,
                country: Country::Global,
                impact_category: "Global warming".to_string(),
                value_per_tonne: 0.2, // Global average
                unit: "kg CO2-eq".to_string(),
                confidence: ConfidenceLevel::Low,
                source: "Global food processing LCA database 2024".to_string(),
                year: 2024,
                uncertainty_range: (0.1, 0.4),
                pedigree_score: PedigreeScore {
                    reliability: 4,
                    completeness: 4,
                    temporal_correlation: 3,
                    geographical_correlation: 5,
                    technological_correlation: 4,
                },
            },
            ProcessingImpactFactor {
                facility_type: ProcessingFacilityType::Mill,
                product_type: ProductType::FlourMaize,
                country: Country::Global,
                impact_category: "Energy consumption".to_string(),
                value_per_tonne: 100.0, // kWh/tonne global average
                unit: "kWh".to_string(),
                confidence: ConfidenceLevel::Low,
                source: "FAO food processing energy benchmarks 2024".to_string(),
                year: 2024,
                uncertainty_range: (60.0, 150.0),
                pedigree_score: PedigreeScore {
                    reliability: 4,
                    completeness: 4,
                    temporal_correlation: 3,
                    geographical_correlation: 5,
                    technological_correlation: 4,
                },
            },
        ];

        self.impact_factors.extend(global_factors);
    }

    fn add_processing_benchmarks(&mut self) {
        let benchmarks = vec![
            // Maize milling benchmarks for Ghana
            ProcessingBenchmark {
                facility_type: ProcessingFacilityType::Mill,
                capacity_range: CapacityRange::Small,
                country: Country::Ghana,
                benchmarks: HashMap::from([
                    ("Energy consumption".to_string(), ProcessingBenchmarkValue {
                        best_practice: 50.0, // kWh/tonne
                        average: 70.0,
                        worst_practice: 100.0,
                        unit: "kWh/tonne".to_string(),
                    }),
                    ("Water consumption".to_string(), ProcessingBenchmarkValue {
                        best_practice: 1.0, // m3/tonne
                        average: 1.8,
                        worst_practice: 3.0,
                        unit: "m3/tonne".to_string(),
                    }),
                ]),
            },
            ProcessingBenchmark {
                facility_type: ProcessingFacilityType::Mill,
                capacity_range: CapacityRange::Medium,
                country: Country::Ghana,
                benchmarks: HashMap::from([
                    ("Energy consumption".to_string(), ProcessingBenchmarkValue {
                        best_practice: 45.0,
                        average: 65.0,
                        worst_practice: 90.0,
                        unit: "kWh/tonne".to_string(),
                    }),
                    ("Water consumption".to_string(), ProcessingBenchmarkValue {
                        best_practice: 0.8,
                        average: 1.5,
                        worst_practice: 2.5,
                        unit: "m3/tonne".to_string(),
                    }),
                ]),
            },
            
            // Rice processing benchmarks for Nigeria
            ProcessingBenchmark {
                facility_type: ProcessingFacilityType::RiceProcessing,
                capacity_range: CapacityRange::Medium,
                country: Country::Nigeria,
                benchmarks: HashMap::from([
                    ("Energy consumption".to_string(), ProcessingBenchmarkValue {
                        best_practice: 85.0,
                        average: 110.0,
                        worst_practice: 150.0,
                        unit: "kWh/tonne".to_string(),
                    }),
                    ("Water consumption".to_string(), ProcessingBenchmarkValue {
                        best_practice: 2.5,
                        average: 3.5,
                        worst_practice: 5.0,
                        unit: "m3/tonne".to_string(),
                    }),
                ]),
            },

            // Cassava processing benchmarks
            ProcessingBenchmark {
                facility_type: ProcessingFacilityType::CassivaProcessing,
                capacity_range: CapacityRange::Small,
                country: Country::Ghana,
                benchmarks: HashMap::from([
                    ("Energy consumption".to_string(), ProcessingBenchmarkValue {
                        best_practice: 30.0,
                        average: 45.0,
                        worst_practice: 70.0,
                        unit: "kWh/tonne".to_string(),
                    }),
                    ("Water consumption".to_string(), ProcessingBenchmarkValue {
                        best_practice: 1.8,
                        average: 2.5,
                        worst_practice: 4.0,
                        unit: "m3/tonne".to_string(),
                    }),
                ]),
            },
        ];

        self.benchmarks.extend(benchmarks);
    }

    pub fn get_factors(&self) -> &Vec<ProcessingImpactFactor> {
        &self.impact_factors
    }

    pub fn get_benchmarks(&self) -> &Vec<ProcessingBenchmark> {
        &self.benchmarks
    }

    pub fn get_regional_factor(&self, key: &str) -> Option<f64> {
        self.regional_factors.get(key).copied()
    }
}
