use african_lca_backend::*;
use std::env;
use std::fs;
use std::process;
use uuid::Uuid;
use chrono::Utc;

fn main() {
    env_logger::init();
    
    let args: Vec<String> = env::args().collect();
    
    if args.len() != 2 {
        eprintln!("Usage: {} <input_json_file>", args[0]);
        process::exit(1);
    }
    
    let input_file = &args[1];
    
    // Read input JSON
    let input_data = match fs::read_to_string(input_file) {
        Ok(data) => data,
        Err(e) => {
            eprintln!("Error reading input file: {}", e);
            process::exit(1);
        }
    };
    
    // Parse input to detect format
    let input: serde_json::Value = match serde_json::from_str(&input_data) {
        Ok(data) => data,
        Err(e) => {
            eprintln!("Error parsing JSON: {}", e);
            process::exit(1);
        }
    };
    
    // Detect assessment type
    let is_processing = input.get("facility_profile").is_some() || 
                       input.get("processing_operations").is_some() ||
                       input.get("processed_products").is_some();
    
    let is_comprehensive = input.get("farm_profile").is_some() || 
                          input.get("management_practices").is_some();
    
    if is_processing {
        handle_processing_assessment(&input);
    } else if is_comprehensive {
        handle_comprehensive_assessment(&input);
    } else {
        handle_simple_assessment(&input);
    }
}

fn handle_processing_assessment(input: &serde_json::Value) {
    println!("Processing facility assessment...");
    
    // Create processing assessment from input
    let mut assessment = match create_processing_assessment(input) {
        Ok(assessment) => assessment,
        Err(e) => {
            eprintln!("Error creating processing assessment: {}", e);
            process::exit(1);
        }
    };
    
    // Initialize Processing LCA engine
    let methodology = LCAMethodology {
        functional_unit: "1 tonne product".to_string(),
        system_boundary: SystemBoundary::GateToGate, // Processing facility boundary
        allocation_method: AllocationMethod::Mass,
        characterization_method: CharacterizationMethod::IpccAr6,
        normalization_method: Some(NormalizationMethod::AfricanContext),
        weighting_method: Some(WeightingMethod::AfricanPriorities),
    };
    
    let mut engine = ProcessingLCAEngine::new(methodology);
    
    // Load processing impact factors
    let mut data_loader = ProcessingDataLoader::new();
    if let Err(e) = data_loader.load_default_factors() {
        eprintln!("Warning: Error loading processing factors: {}", e);
    }
    
    engine.load_impact_factors(data_loader.get_factors().clone());
    engine.load_benchmarks(data_loader.get_benchmarks().clone());
    
    // Perform processing assessment
    if let Err(e) = engine.perform_processing_assessment(&mut assessment) {
        eprintln!("Error performing processing assessment: {}", e);
        process::exit(1);
    }
    
    // Output results as JSON
    match serde_json::to_string_pretty(&assessment) {
        Ok(json) => println!("{}", json),
        Err(e) => {
            eprintln!("Error serializing results: {}", e);
            process::exit(1);
        }
    }
}

fn handle_comprehensive_assessment(input: &serde_json::Value) {
    println!("Processing comprehensive assessment...");
    
    // Create comprehensive assessment from input
    let mut assessment = match create_comprehensive_assessment(input) {
        Ok(assessment) => assessment,
        Err(e) => {
            eprintln!("Error creating comprehensive assessment: {}", e);
            process::exit(1);
        }
    };
    
    // Initialize LCA engine
    let methodology = LCAMethodology {
        functional_unit: "1 kg product".to_string(),
        system_boundary: SystemBoundary::CradleToGate,
        allocation_method: AllocationMethod::Mass,
        characterization_method: CharacterizationMethod::IpccAr6,
        normalization_method: Some(NormalizationMethod::AfricanContext),
        weighting_method: Some(WeightingMethod::AfricanPriorities),
    };
    
    let mut engine = AfricanLCAEngine::new(methodology);
    
    // Load impact factors
    let mut data_loader = DataLoader::new();
    if let Err(e) = data_loader.load_default_factors() {
        eprintln!("Warning: Error loading default factors: {}", e);
    }
    
    engine.load_impact_factors(data_loader.get_factors().clone());
    
    // Perform assessment with enhanced analysis
    if let Err(e) = engine.perform_comprehensive_assessment(&mut assessment) {
        eprintln!("Error performing comprehensive assessment: {}", e);
        process::exit(1);
    }
    
    // Output results as JSON
    match serde_json::to_string_pretty(&assessment) {
        Ok(json) => println!("{}", json),
        Err(e) => {
            eprintln!("Error serializing results: {}", e);
            process::exit(1);
        }
    }
}

fn handle_simple_assessment(input: &serde_json::Value) {
    println!("Processing simple assessment...");
    
    // Convert to Assessment (existing logic)
    let mut assessment = match create_simple_assessment(input) {
        Ok(assessment) => assessment,
        Err(e) => {
            eprintln!("Error creating assessment: {}", e);
            process::exit(1);
        }
    };
    
    // Initialize LCA engine
    let methodology = LCAMethodology {
        functional_unit: "1 kg product".to_string(),
        system_boundary: SystemBoundary::CradleToGate,
        allocation_method: AllocationMethod::Mass,
        characterization_method: CharacterizationMethod::IpccAr6,
        normalization_method: Some(NormalizationMethod::AfricanContext),
        weighting_method: Some(WeightingMethod::AfricanPriorities),
    };
    let mut engine = AfricanLCAEngine::new(methodology);
    
    // Load impact factors
    let mut data_loader = DataLoader::new();
    if let Err(e) = data_loader.load_default_factors() {
        eprintln!("Warning: Error loading default factors: {}", e);
    }
    
    engine.load_impact_factors(data_loader.get_factors().clone());
    
    // Perform assessment
    if let Err(e) = engine.perform_assessment(&mut assessment) {
        eprintln!("Error performing assessment: {}", e);
        process::exit(1);
    }
    
    // Output results as JSON
    match serde_json::to_string_pretty(&assessment) {
        Ok(json) => println!("{}", json),
        Err(e) => {
            eprintln!("Error serializing results: {}", e);
            process::exit(1);
        }
    }
}

fn create_comprehensive_assessment(input: &serde_json::Value) -> Result<Assessment, Box<dyn std::error::Error>> {
    let company_name = input["company_name"]
        .as_str()
        .ok_or("Missing company_name")?
        .to_string();
    
    let methodology = LCAMethodology {
        functional_unit: "1 kg product".to_string(),
        system_boundary: SystemBoundary::CradleToGate,
        allocation_method: AllocationMethod::Mass,
        characterization_method: CharacterizationMethod::IpccAr6,
        normalization_method: Some(NormalizationMethod::AfricanContext),
        weighting_method: Some(WeightingMethod::AfricanPriorities),
    };
    
    let country_str = input["country"]
        .as_str()
        .ok_or("Missing country")?;
    
    let country = match country_str {
        "Ghana" => Country::Ghana,
        "Nigeria" => Country::Nigeria,
        "Global" => Country::Global,
        _ => return Err(format!("Unknown country: {}", country_str).into()),
    };
    
    let region = input["region"].as_str().map(|s| s.to_string());
    
    // Parse farm profile if present
    let farm_profile = if let Some(fp) = input.get("farm_profile") {
        Some(FarmProfile {
            farmer_name: fp["farmer_name"].as_str().unwrap_or("").to_string(),
            farm_name: fp["farm_name"].as_str().unwrap_or("").to_string(),
            total_farm_size: fp["total_farm_size"].as_f64().unwrap_or(0.0),
            farming_experience: fp["farming_experience"].as_u64().unwrap_or(0) as u32,
            farm_type: parse_farm_type(fp["farm_type"].as_str().unwrap_or("Smallholder"))?,
            primary_farming_system: parse_farming_system(fp["primary_farming_system"].as_str().unwrap_or("Subsistence"))?,
            certifications: fp["certifications"].as_array()
                .map(|arr| arr.iter().filter_map(|v| v.as_str()).map(|s| s.to_string()).collect())
                .unwrap_or_default(),
            participates_in_programs: fp["participates_in_programs"].as_array()
                .map(|arr| arr.iter().filter_map(|v| v.as_str()).map(|s| s.to_string()).collect())
                .unwrap_or_default(),
        })
    } else {
        None
    };
    
    // Parse management practices if present
    let management_practices = if let Some(mp) = input.get("management_practices") {
        Some(parse_management_practices(mp)?)
    } else {
        None
    };
    
    // Parse foods
    let foods_array = input["foods"].as_array()
        .ok_or("Missing or invalid foods array")?;
    
    let mut foods = Vec::new();
    for food_value in foods_array {
        let food = parse_food_item(food_value, country_str)?;
        foods.push(food);
    }
    
    Ok(Assessment {
        id: Uuid::new_v4(),
        company_name,
        country,
        region,
        foods,
        assessment_date: Utc::now(),
        methodology,
        results: None,
        farm_profile,
        management_practices,
    })
}

fn create_simple_assessment(input: &serde_json::Value) -> Result<Assessment, Box<dyn std::error::Error>> {
    let company_name = input["company_name"]
        .as_str()
        .ok_or("Missing company_name")?
        .to_string();
    
    let methodology = LCAMethodology {
        functional_unit: "1 kg product".to_string(),
        system_boundary: SystemBoundary::CradleToGate,
        allocation_method: AllocationMethod::Mass,
        characterization_method: CharacterizationMethod::IpccAr6,
        normalization_method: Some(NormalizationMethod::AfricanContext),
        weighting_method: Some(WeightingMethod::AfricanPriorities),
    };
    
    let country_str = input["country"]
        .as_str()
        .ok_or("Missing country")?;
    
    let country = match country_str {
        "Ghana" => Country::Ghana,
        "Nigeria" => Country::Nigeria,
        "Global" => Country::Global,
        _ => return Err(format!("Unknown country: {}", country_str).into()),
    };
    
    let foods_array = input["foods"]
        .as_array()
        .ok_or("Missing or invalid foods array")?;
    
    let mut foods = Vec::new();
    for food_value in foods_array {
        let food = FoodItem {
            id: food_value["id"]
                .as_str()
                .ok_or("Missing food id")?
                .to_string(),
            name: food_value["name"]
                .as_str()
                .ok_or("Missing food name")?
                .to_string(),
            quantity_kg: food_value["quantity_kg"]
                .as_f64()
                .ok_or("Missing or invalid quantity_kg")?,
            category: parse_food_category(
                food_value["category"]
                    .as_str()
                    .ok_or("Missing food category")?
            )?,
            crop_type: food_value["crop_type"].as_str().map(|s| s.to_string()),
            origin_country: food_value["origin_country"]
                .as_str()
                .map(|s| s.to_string()),
            production_system: None,
            seasonal_factor: None,
            variety: None,
            area_allocated: None,
            cropping_pattern: None,
            intercropping_partners: None,
            post_harvest_losses: None,
        };
        foods.push(food);
    }
    
    Ok(Assessment {
        id: Uuid::new_v4(),
        company_name,
        country,
        region: None,
        foods,
        assessment_date: Utc::now(),
        methodology,
        results: None,
        farm_profile: None,
        management_practices: None,
    })
}

// Helper parsing functions
fn parse_food_category(s: &str) -> Result<FoodCategory, Box<dyn std::error::Error>> {
    match s {
        "Cereals" => Ok(FoodCategory::Cereals),
        "Legumes" => Ok(FoodCategory::Legumes),
        "Vegetables" => Ok(FoodCategory::Vegetables),
        "Fruits" => Ok(FoodCategory::Fruits),
        "Meat" => Ok(FoodCategory::Meat),
        "Poultry" => Ok(FoodCategory::Poultry),
        "Fish" => Ok(FoodCategory::Fish),
        "Dairy" => Ok(FoodCategory::Dairy),
        "Eggs" => Ok(FoodCategory::Eggs),
        "Oils" => Ok(FoodCategory::Oils),
        "Nuts" => Ok(FoodCategory::Nuts),
        "Roots" => Ok(FoodCategory::Roots),
        "Other" => Ok(FoodCategory::Other),
        _ => Err(format!("Unknown food category: {}", s).into()),
    }
}

fn parse_farm_type(s: &str) -> Result<FarmType, Box<dyn std::error::Error>> {
    match s {
        "Smallholder" => Ok(FarmType::Smallholder),
        "SmallScale" => Ok(FarmType::SmallScale),
        "MediumScale" => Ok(FarmType::MediumScale),
        "Commercial" => Ok(FarmType::Commercial),
        "Cooperative" => Ok(FarmType::Cooperative),
        "MixedLivestock" => Ok(FarmType::MixedLivestock),
        _ => Err(format!("Unknown farm type: {}", s).into()),
    }
}

fn parse_farming_system(s: &str) -> Result<FarmingSystem, Box<dyn std::error::Error>> {
    match s {
        "Subsistence" => Ok(FarmingSystem::Subsistence),
        "SemiCommercial" => Ok(FarmingSystem::SemiCommercial),
        "Commercial" => Ok(FarmingSystem::Commercial),
        "Organic" => Ok(FarmingSystem::Organic),
        "Agroecological" => Ok(FarmingSystem::Agroecological),
        "Conventional" => Ok(FarmingSystem::Conventional),
        "IntegratedFarming" => Ok(FarmingSystem::IntegratedFarming),
        _ => Err(format!("Unknown farming system: {}", s).into()),
    }
}

fn parse_food_item(food_value: &serde_json::Value, country: &str) -> Result<FoodItem, Box<dyn std::error::Error>> {
    Ok(FoodItem {
        id: food_value.get("crop_id")
            .or_else(|| food_value.get("id"))
            .and_then(|v| v.as_str())
            .ok_or("Missing food id")?
            .to_string(),
        name: food_value.get("crop_name")
            .or_else(|| food_value.get("name"))
            .and_then(|v| v.as_str())
            .ok_or("Missing food name")?
            .to_string(),
        quantity_kg: food_value.get("annual_production")
            .or_else(|| food_value.get("quantity_kg"))
            .and_then(|v| v.as_f64())
            .ok_or("Missing or invalid quantity")?,
        category: parse_food_category(
            food_value["category"]
                .as_str()
                .ok_or("Missing food category")?
        )?,
        crop_type: food_value.get("variety")
            .or_else(|| food_value.get("crop_type"))
            .and_then(|v| v.as_str())
            .map(|s| s.to_string()),
        origin_country: Some(country.to_string()),
        production_system: food_value.get("production_system")
            .and_then(|v| v.as_str())
            .and_then(|s| parse_production_system(s).ok()),
        seasonal_factor: None,
        variety: food_value.get("variety")
            .and_then(|v| v.as_str())
            .map(|s| s.to_string()),
        area_allocated: food_value.get("area_allocated")
            .and_then(|v| v.as_f64()),
        cropping_pattern: food_value.get("cropping_pattern")
            .and_then(|v| v.as_str())
            .and_then(|s| parse_cropping_pattern(s).ok()),
        intercropping_partners: food_value.get("intercropping_partners")
            .and_then(|v| v.as_array())
            .map(|arr| arr.iter().filter_map(|v| v.as_str()).map(|s| s.to_string()).collect()),
        post_harvest_losses: food_value.get("post_harvest_losses")
            .and_then(|v| v.as_f64()),
    })
}

fn parse_production_system(s: &str) -> Result<ProductionSystem, Box<dyn std::error::Error>> {
    match s {
        "Rainfed" => Ok(ProductionSystem::Rainfed),
        "Irrigated" => Ok(ProductionSystem::Irrigated),
        "Smallholder" => Ok(ProductionSystem::Smallholder),
        "Intensive" => Ok(ProductionSystem::Intensive),
        "Extensive" => Ok(ProductionSystem::Extensive),
        "Agroforestry" => Ok(ProductionSystem::Agroforestry),
        "Organic" => Ok(ProductionSystem::Organic),
        "Conventional" => Ok(ProductionSystem::Conventional),
        _ => Err(format!("Unknown production system: {}", s).into()),
    }
}

fn parse_cropping_pattern(s: &str) -> Result<CroppingPattern, Box<dyn std::error::Error>> {
    match s {
        "Monoculture" => Ok(CroppingPattern::Monoculture),
        "Intercropping" => Ok(CroppingPattern::Intercropping),
        "RelayCropping" => Ok(CroppingPattern::RelayCropping),
        "Agroforestry" => Ok(CroppingPattern::Agroforestry),
        "CropRotation" => Ok(CroppingPattern::CropRotation),
        _ => Err(format!("Unknown cropping pattern: {}", s).into()),
    }
}

fn parse_management_practices(mp: &serde_json::Value) -> Result<ManagementPractices, Box<dyn std::error::Error>> {
    let soil_mgmt = mp.get("soil_management").unwrap_or(&serde_json::Value::Null);
    let fertilization = mp.get("fertilization").unwrap_or(&serde_json::Value::Null);
    let water_mgmt = mp.get("water_management").unwrap_or(&serde_json::Value::Null);
    let pest_mgmt = mp.get("pest_management").unwrap_or(&serde_json::Value::Null);
    
    Ok(ManagementPractices {
        soil_management: SoilManagement {
            soil_type: soil_mgmt.get("soil_type")
                .and_then(|v| v.as_str())
                .and_then(|s| parse_soil_type(s).ok()),
            uses_compost: soil_mgmt.get("compost_use")
                .and_then(|cu| cu.get("uses_compost"))
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            compost_source: soil_mgmt.get("compost_use")
                .and_then(|cu| cu.get("compost_source"))
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            conservation_practices: soil_mgmt.get("conservation_practices")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|v| v.as_str()).map(|s| s.to_string()).collect())
                .unwrap_or_default(),
            soil_testing_frequency: soil_mgmt.get("soil_testing_frequency")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
        },
        fertilization: FertilizationPractices {
            uses_fertilizers: fertilization.get("uses_fertilizers")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            fertilizer_applications: fertilization.get("fertilizer_applications")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|app| {
                    Some(FertilizerApplication {
                        fertilizer_type: app.get("fertilizer_type")?.as_str()?.to_string(),
                        application_rate: app.get("application_rate")?.as_f64()?,
                        applications_per_season: app.get("applications_per_season")?.as_u64()? as u32,
                        cost: app.get("cost").and_then(|v| v.as_f64()),
                    })
                }).collect())
                .unwrap_or_default(),
            soil_test_based: fertilization.get("soil_test_based")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            follows_nutrient_plan: fertilization.get("follows_nutrient_plan")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
        },
        water_management: crate::models::WaterManagement {
            water_source: water_mgmt.get("water_source")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|v| v.as_str()).map(|s| s.to_string()).collect())
                .unwrap_or_default(),
            irrigation_system: water_mgmt.get("irrigation_system")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
            water_conservation_practices: water_mgmt.get("water_conservation_practices")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|v| v.as_str()).map(|s| s.to_string()).collect())
                .unwrap_or_default(),
        },
        pest_management: PestManagement {
            management_approach: pest_mgmt.get("management_approach")
                .and_then(|v| v.as_str())
                .unwrap_or("IntegratedIPM")
                .to_string(),
            uses_ipm: pest_mgmt.get("uses_ipm")
                .and_then(|v| v.as_bool())
                .unwrap_or(false),
            pesticides_used: pest_mgmt.get("pesticides")
                .and_then(|v| v.as_array())
                .map(|arr| arr.iter().filter_map(|app| {
                    Some(PesticideApplication {
                        pesticide_type: app.get("pesticide_type")?.as_str()?.to_string(),
                        active_ingredient: app.get("active_ingredient")?.as_str()?.to_string(),
                        application_rate: app.get("application_rate")?.as_f64()?,
                        applications_per_season: app.get("applications_per_season")?.as_u64()? as u32,
                        target_pests: app.get("target_pests")
                            .and_then(|v| v.as_array())
                            .map(|arr| arr.iter().filter_map(|v| v.as_str()).map(|s| s.to_string()).collect())
                            .unwrap_or_default(),
                    })
                }).collect())
                .unwrap_or_default(),
            monitoring_frequency: pest_mgmt.get("pest_monitoring_frequency")
                .and_then(|v| v.as_str())
                .map(|s| s.to_string()),
        },
    })
}

fn parse_soil_type(s: &str) -> Result<SoilType, Box<dyn std::error::Error>> {
    match s {
        "Sandy" => Ok(SoilType::Sandy),
        "Clay" => Ok(SoilType::Clay),
        "Loam" => Ok(SoilType::Loam),
        "SandyLoam" => Ok(SoilType::SandyLoam),
        "ClayLoam" => Ok(SoilType::ClayLoam),
        "SiltLoam" => Ok(SoilType::SiltLoam),
        "Lateritic" => Ok(SoilType::Lateritic),
        "Volcanic" => Ok(SoilType::Volcanic),
        _ => Err(format!("Unknown soil type: {}", s).into()),
    }
}

fn create_processing_assessment(input: &serde_json::Value) -> Result<ProcessingAssessment, Box<dyn std::error::Error>> {
    let country_str = input["country"]
        .as_str()
        .ok_or("Missing country")?;
    
    let country = match country_str {
        "Ghana" => Country::Ghana,
        "Nigeria" => Country::Nigeria,
        "Global" => Country::Global,
        _ => return Err(format!("Unknown country: {}", country_str).into()),
    };
    
    let region = input["region"].as_str().map(|s| s.to_string());
    
    // Parse facility profile
    let facility_profile = parse_facility_profile(input.get("facility_profile")
        .ok_or("Missing facility_profile")?)?;
    
    // Parse processing operations
    let processing_operations = parse_processing_operations(input.get("processing_operations")
        .ok_or("Missing processing_operations")?)?;
    
    // Parse processed products
    let products_array = input["processed_products"].as_array()
        .ok_or("Missing or invalid processed_products array")?;
    
    let mut processed_products = Vec::new();
    for product_value in products_array {
        let product = parse_processed_product(product_value)?;
        processed_products.push(product);
    }
    
    let methodology = LCAMethodology {
        functional_unit: "1 tonne product".to_string(),
        system_boundary: SystemBoundary::GateToGate,
        allocation_method: AllocationMethod::Mass,
        characterization_method: CharacterizationMethod::IpccAr6,
        normalization_method: Some(NormalizationMethod::AfricanContext),
        weighting_method: Some(WeightingMethod::AfricanPriorities),
    };
    
    Ok(ProcessingAssessment {
        id: Uuid::new_v4(),
        facility_profile,
        processing_operations,
        processed_products,
        country,
        region,
        assessment_date: Utc::now(),
        methodology,
        results: None,
    })
}

fn parse_facility_profile(fp: &serde_json::Value) -> Result<ProcessingFacilityProfile, Box<dyn std::error::Error>> {
    Ok(ProcessingFacilityProfile {
        facility_name: fp["facility_name"].as_str().unwrap_or("").to_string(),
        company_name: fp["company_name"].as_str().unwrap_or("").to_string(),
        facility_type: parse_facility_type(fp["facility_type"].as_str().unwrap_or("General"))?,
        processing_capacity: fp["processing_capacity"].as_f64().unwrap_or(0.0),
        operational_hours_per_day: fp["operational_hours_per_day"].as_f64().unwrap_or(8.0),
        operational_days_per_year: fp["operational_days_per_year"].as_u64().unwrap_or(250) as u32,
        established_year: fp["established_year"].as_u64().map(|y| y as u32),
        certifications: fp["certifications"].as_array()
            .map(|arr| arr.iter().filter_map(|v| v.as_str()).map(|s| s.to_string()).collect())
            .unwrap_or_default(),
        employee_count: fp["employee_count"].as_u64().map(|c| c as u32),
        facility_size: fp["facility_size"].as_f64(),
        location_type: parse_location_type(fp["location_type"].as_str().unwrap_or("Rural"))?,
    })
}

fn parse_processing_operations(po: &serde_json::Value) -> Result<ProcessingOperations, Box<dyn std::error::Error>> {
    Ok(ProcessingOperations {
        energy_management: parse_energy_management(po.get("energy_management").unwrap_or(&serde_json::Value::Null))?,
        water_management: parse_water_management_processing(po.get("water_management").unwrap_or(&serde_json::Value::Null))?,
        waste_management: parse_waste_management(po.get("waste_management").unwrap_or(&serde_json::Value::Null))?,
        raw_material_sourcing: parse_raw_material_sourcing(po.get("raw_material_sourcing").unwrap_or(&serde_json::Value::Null))?,
        equipment_efficiency: parse_equipment_efficiency(po.get("equipment_efficiency").unwrap_or(&serde_json::Value::Null))?,
    })
}

fn parse_processed_product(pp: &serde_json::Value) -> Result<ProcessedProduct, Box<dyn std::error::Error>> {
    let raw_materials = pp.get("raw_material_inputs")
        .and_then(|v| v.as_array())
        .map(|arr| arr.iter().filter_map(|rm| {
            Some(RawMaterialInput {
                material_name: rm.get("material_name")?.as_str()?.to_string(),
                quantity_per_tonne_output: rm.get("quantity_per_tonne_output")?.as_f64()?,
                source_location: rm.get("source_location").and_then(|v| v.as_str()).map(|s| s.to_string()),
                quality_requirements: rm.get("quality_requirements")
                    .and_then(|v| v.as_array())
                    .map(|arr| arr.iter().filter_map(|v| v.as_str()).map(|s| s.to_string()).collect())
                    .unwrap_or_default(),
                seasonal_availability: rm.get("seasonal_availability").and_then(|v| v.as_bool()).unwrap_or(true),
            })
        }).collect())
        .unwrap_or_default();
    
    let processing_steps = pp.get("processing_steps")
        .and_then(|v| v.as_array())
        .map(|arr| arr.iter().filter_map(|ps| {
            Some(ProcessingStep {
                step_name: ps.get("step_name")?.as_str()?.to_string(),
                energy_intensity: ps.get("energy_intensity")?.as_f64()?,
                water_usage: ps.get("water_usage")?.as_f64()?,
                duration: ps.get("duration")?.as_f64()?,
                yield_efficiency: ps.get("yield_efficiency").and_then(|v| v.as_f64()).unwrap_or(95.0),
                emissions_factor: ps.get("emissions_factor").and_then(|v| v.as_f64()),
            })
        }).collect())
        .unwrap_or_default();
    
    Ok(ProcessedProduct {
        id: pp.get("id").or_else(|| pp.get("product_id"))
            .and_then(|v| v.as_str())
            .ok_or("Missing product id")?
            .to_string(),
        name: pp.get("name").or_else(|| pp.get("product_name"))
            .and_then(|v| v.as_str())
            .ok_or("Missing product name")?
            .to_string(),
        product_type: parse_product_type(pp["product_type"].as_str().ok_or("Missing product_type")?)?,
        annual_production: pp["annual_production"].as_f64().ok_or("Missing annual_production")?,
        raw_material_inputs: raw_materials,
        processing_steps,
        packaging: parse_packaging_info(pp.get("packaging").unwrap_or(&serde_json::Value::Null))?,
        quality_grade: parse_quality_grade(pp.get("quality_grade").and_then(|v| v.as_str()).unwrap_or("Standard"))?,
        market_destination: parse_market_destination(pp.get("market_destination").and_then(|v| v.as_str()).unwrap_or("Local"))?,
    })
}

// Helper parsing functions for processing-specific enums
fn parse_facility_type(s: &str) -> Result<ProcessingFacilityType, Box<dyn std::error::Error>> {
    match s {
        "Mill" => Ok(ProcessingFacilityType::Mill),
        "Bakery" => Ok(ProcessingFacilityType::Bakery),
        "CassivaProcessing" => Ok(ProcessingFacilityType::CassivaProcessing),
        "RiceProcessing" => Ok(ProcessingFacilityType::RiceProcessing),
        "PalmOilMill" => Ok(ProcessingFacilityType::PalmOilMill),
        "CocoaProcessing" => Ok(ProcessingFacilityType::CocoaProcessing),
        "FishProcessing" => Ok(ProcessingFacilityType::FishProcessing),
        "MeatProcessing" => Ok(ProcessingFacilityType::MeatProcessing),
        "DairyProcessing" => Ok(ProcessingFacilityType::DairyProcessing),
        "FruitProcessing" => Ok(ProcessingFacilityType::FruitProcessing),
        "VegetableProcessing" => Ok(ProcessingFacilityType::VegetableProcessing),
        "General" => Ok(ProcessingFacilityType::General),
        _ => Err(format!("Unknown facility type: {}", s).into()),
    }
}

fn parse_location_type(s: &str) -> Result<LocationType, Box<dyn std::error::Error>> {
    match s {
        "Urban" => Ok(LocationType::Urban),
        "PeriUrban" => Ok(LocationType::PeriUrban),
        "Rural" => Ok(LocationType::Rural),
        "Industrial" => Ok(LocationType::Industrial),
        _ => Err(format!("Unknown location type: {}", s).into()),
    }
}

fn parse_product_type(s: &str) -> Result<ProductType, Box<dyn std::error::Error>> {
    match s {
        "FlourMaize" => Ok(ProductType::FlourMaize),
        "FlourWheat" => Ok(ProductType::FlourWheat),
        "FlourCassava" => Ok(ProductType::FlourCassava),
        "FlourPlantain" => Ok(ProductType::FlourPlantain),
        "RiceProcessed" => Ok(ProductType::RiceProcessed),
        "PalmOil" => Ok(ProductType::PalmOil),
        "CocoaPowder" => Ok(ProductType::CocoaPowder),
        "CocoaButter" => Ok(ProductType::CocoaButter),
        "BakedGoods" => Ok(ProductType::BakedGoods),
        "ProcessedFish" => Ok(ProductType::ProcessedFish),
        "ProcessedMeat" => Ok(ProductType::ProcessedMeat),
        "Dairy" => Ok(ProductType::Dairy),
        "FruitJuice" => Ok(ProductType::FruitJuice),
        "DriedFruits" => Ok(ProductType::DriedFruits),
        _ => Ok(ProductType::Other(s.to_string())),
    }
}

// Simplified implementations for the remaining parsing functions
fn parse_energy_management(_em: &serde_json::Value) -> Result<EnergyManagement, Box<dyn std::error::Error>> {
    Ok(EnergyManagement {
        primary_energy_source: EnergySource::GridElectricity,
        secondary_energy_sources: vec![],
        monthly_electricity_consumption: Some(10000.0),
        monthly_fuel_consumption: Some(500.0),
        fuel_type: Some("Diesel".to_string()),
        renewable_energy_percentage: 0.0,
        energy_efficiency_measures: vec![],
        backup_generator: true,
    })
}

fn parse_water_management_processing(_wm: &serde_json::Value) -> Result<crate::processing::models::WaterManagement, Box<dyn std::error::Error>> {
    Ok(crate::processing::models::WaterManagement {
        water_source: vec!["Municipal".to_string()],
        monthly_water_consumption: Some(1000.0),
        water_treatment: crate::processing::models::WaterTreatment::BasicFiltration,
        water_conservation_measures: vec![],
        wastewater_treatment: crate::processing::models::WastewaterTreatment::BasicSedimentation,
    })
}

fn parse_waste_management(_wm: &serde_json::Value) -> Result<crate::processing::models::WasteManagement, Box<dyn std::error::Error>> {
    Ok(crate::processing::models::WasteManagement {
        solid_waste_generation: Some(100.0),
        organic_waste_percentage: 70.0,
        waste_disposal_method: crate::processing::models::WasteDisposalMethod::Landfill,
        recycling_programs: vec![],
        byproduct_utilization: vec![],
    })
}

fn parse_raw_material_sourcing(_rms: &serde_json::Value) -> Result<RawMaterialSourcing, Box<dyn std::error::Error>> {
    Ok(RawMaterialSourcing {
        local_sourcing_percentage: 80.0,
        average_transport_distance: 50.0,
        transport_mode: TransportMode::Truck,
        supplier_sustainability_practices: vec![],
        seasonal_variation: true,
        storage_practices: StoragePractices {
            storage_type: "Warehouse".to_string(),
            climate_control: false,
            pest_control_methods: vec![],
            storage_loss_percentage: 5.0,
        },
    })
}

fn parse_equipment_efficiency(_ee: &serde_json::Value) -> Result<EquipmentEfficiency, Box<dyn std::error::Error>> {
    Ok(EquipmentEfficiency {
        equipment_age: EquipmentAge::Mature,
        maintenance_frequency: MaintenanceFrequency::Monthly,
        automation_level: AutomationLevel::SemiAutomated,
        equipment_utilization_rate: 75.0,
        modernization_investments: vec![],
    })
}

fn parse_packaging_info(_pi: &serde_json::Value) -> Result<PackagingInfo, Box<dyn std::error::Error>> {
    Ok(PackagingInfo {
        packaging_material: PackagingMaterial::PlasticBag,
        package_size: 50.0,
        packaging_weight_per_unit: 0.1,
        recyclable: false,
    })
}

fn parse_quality_grade(s: &str) -> Result<QualityGrade, Box<dyn std::error::Error>> {
    match s {
        "Premium" => Ok(QualityGrade::Premium),
        "Standard" => Ok(QualityGrade::Standard),
        "Basic" => Ok(QualityGrade::Basic),
        "Industrial" => Ok(QualityGrade::Industrial),
        _ => Ok(QualityGrade::Standard),
    }
}

fn parse_market_destination(s: &str) -> Result<MarketDestination, Box<dyn std::error::Error>> {
    match s {
        "Local" => Ok(MarketDestination::Local),
        "Regional" => Ok(MarketDestination::Regional),
        "National" => Ok(MarketDestination::National),
        "Export" => Ok(MarketDestination::Export),
        "Mixed" => Ok(MarketDestination::Mixed),
        _ => Ok(MarketDestination::Local),
    }
}