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
    
    // Detect if this is a comprehensive assessment request
    let is_comprehensive = input.get("farm_profile").is_some() || 
                          input.get("management_practices").is_some();
    
    if is_comprehensive {
        handle_comprehensive_assessment(&input);
    } else {
        handle_simple_assessment(&input);
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
        water_management: WaterManagement {
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