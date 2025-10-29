/**
 * Extended LCI Characterization Module
 *
 * This module implements comprehensive LCIA characterization factors for:
 * - Water scarcity (AWARE methodology)
 * - Biodiversity impacts (MSA - Mean Species Abundance)
 * - Soil degradation
 * - Marine eutrophication
 * - Terrestrial acidification
 * - Particulate matter formation
 * - Photochemical oxidation
 * - Mineral and fossil depletion
 *
 * All calculations follow ISO 14044 LCIA methodology
 */

use crate::models::*;
use crate::production::lci::{LCICalculator, InventoryItem, EnvironmentalCompartment};
use std::collections::HashMap;
use log::info;

/// Extended characterization factors for comprehensive LCIA
pub trait LCIExtendedCharacterization {
    fn calculate_extended_midpoint_impacts(
        &self,
        inventory: &HashMap<String, InventoryItem>,
        assessment: &Assessment,
    ) -> Result<HashMap<String, MidpointResult>, Box<dyn std::error::Error>>;
}

impl LCIExtendedCharacterization for LCICalculator {
    fn calculate_extended_midpoint_impacts(
        &self,
        inventory: &HashMap<String, InventoryItem>,
        assessment: &Assessment,
    ) -> Result<HashMap<String, MidpointResult>, Box<dyn std::error::Error>> {

        // Start with basic midpoint impacts
        let mut impacts = self.calculate_midpoint_impacts(inventory)?;

        // Calculate total production and area for per-kg basis
        let total_production_kg: f64 = assessment.foods.iter()
            .map(|f| f.quantity_kg)
            .sum();

        let total_area_ha: f64 = assessment.foods.iter()
            .filter_map(|f| f.area_allocated)
            .sum();

        if total_production_kg == 0.0 {
            return Ok(impacts);
        }

        // 1. Water Scarcity (AWARE methodology)
        if let Some(water_consumption) = impacts.get("Water consumption") {
            let aware_factor = get_aware_factor(&assessment.country, &assessment.region);
            let water_scarcity = water_consumption.value * aware_factor;

            impacts.insert("Water scarcity".to_string(), MidpointResult {
                value: water_scarcity / total_production_kg,
                unit: "m3 H2O-eq per kg".to_string(),
                uncertainty_range: (water_scarcity * 0.7 / total_production_kg,
                                   water_scarcity * 1.3 / total_production_kg),
                data_quality_score: 0.75,
                contributing_sources: vec![
                    format!("Water consumption: {:.1} m³ × AWARE factor {:.1} = {:.1} m³ H2O-eq",
                           water_consumption.value, aware_factor, water_scarcity)
                ],
            });
        }

        // 2. Biodiversity Loss (MSA - Mean Species Abundance)
        if total_area_ha > 0.0 {
            let biodiversity_impact = calculate_biodiversity_impact(
                &assessment.foods,
                &assessment.management_practices,
                total_area_ha,
                total_production_kg
            );

            impacts.insert("Biodiversity loss".to_string(), biodiversity_impact);
        }

        // 3. Soil Degradation
        if let Some(mgmt) = &assessment.management_practices {
            let soil_degradation = calculate_soil_degradation(
                &mgmt.soil_management,
                &mgmt.fertilization,
                &assessment.foods,
                total_area_ha,
                total_production_kg
            );

            impacts.insert("Soil degradation".to_string(), soil_degradation);
        }

        // 4. Marine Eutrophication (from N runoff)
        let marine_eutro = calculate_marine_eutrophication(
            inventory,
            total_production_kg
        );
        impacts.insert("Marine eutrophication".to_string(), marine_eutro);

        // 5. Terrestrial Acidification (from NH3 and NOx)
        let terrestrial_acid = calculate_terrestrial_acidification(
            inventory,
            &assessment.management_practices,
            total_production_kg
        );
        impacts.insert("Terrestrial acidification".to_string(), terrestrial_acid);

        // 6. Particulate Matter Formation
        let pm_formation = calculate_particulate_matter(
            inventory,
            total_production_kg
        );
        impacts.insert("Particulate matter formation".to_string(), pm_formation);

        // 7. Photochemical Oxidation
        let photo_ox = calculate_photochemical_oxidation(
            inventory,
            total_production_kg
        );
        impacts.insert("Photochemical oxidation".to_string(), photo_ox);

        // 8. Fossil Depletion (from fuel consumption)
        let fossil_dep = calculate_fossil_depletion(
            inventory,
            total_production_kg
        );
        impacts.insert("Fossil depletion".to_string(), fossil_dep);

        // 9. Mineral Depletion (from fertilizer extraction)
        let mineral_dep = calculate_mineral_depletion(
            inventory,
            &assessment.management_practices,
            total_production_kg
        );
        impacts.insert("Mineral depletion".to_string(), mineral_dep);

        // Scale all impacts to per-kg basis
        for (category, result) in impacts.iter_mut() {
            if !result.unit.contains("per kg") && category != "Land use" {
                result.value /= total_production_kg;
                result.unit = format!("{} per kg", result.unit);
                result.uncertainty_range = (
                    result.uncertainty_range.0 / total_production_kg,
                    result.uncertainty_range.1 / total_production_kg
                );
            }
        }

        info!("Extended LCIA calculation completed for {} categories", impacts.len());

        Ok(impacts)
    }
}

// Helper functions for specific impact categories

fn get_aware_factor(country: &Country, region: &Option<String>) -> f64 {
    // AWARE factors for water scarcity (m3 H2O-eq per m3 consumed)
    // Source: AWARE 1.0 database
    match (country, region.as_deref()) {
        (Country::Ghana, Some(r)) if r.contains("Northern") || r.contains("Upper") => 30.0, // Drier regions
        (Country::Ghana, _) => 15.0, // Southern regions
        (Country::Nigeria, Some(r)) if r.contains("Northern") || r.contains("Sokoto") || r.contains("Kano") => 35.0,
        (Country::Nigeria, _) => 18.0, // Southern regions
        _ => 20.0, // Global average
    }
}

fn calculate_biodiversity_impact(
    foods: &[FoodItem],
    management_practices: &Option<ManagementPractices>,
    _total_area_ha: f64,
    total_production_kg: f64,
) -> MidpointResult {

    let mut biodiversity_loss = 0.0;
    let mut sources = Vec::new();

    for food in foods {
        if let Some(area_ha) = food.area_allocated {
            // Base MSA loss depends on production system
            let base_msa_loss = match &food.production_system {
                Some(ProductionSystem::Intensive) => 0.30, // 30% biodiversity loss
                Some(ProductionSystem::Organic) => 0.10, // 10% loss
                Some(ProductionSystem::Agroforestry) => 0.05, // 5% loss
                Some(ProductionSystem::Extensive) => 0.20,
                _ => 0.25, // Default conventional
            };

            // Adjustments for conservation practices
            let conservation_factor = if let Some(mgmt) = management_practices {
                if mgmt.soil_management.conservation_practices.len() > 2 {
                    0.8 // 20% reduction in biodiversity loss
                } else if !mgmt.soil_management.conservation_practices.is_empty() {
                    0.9 // 10% reduction
                } else {
                    1.0
                }
            } else {
                1.0
            };

            let crop_biodiversity_loss = base_msa_loss * conservation_factor * area_ha * 10000.0; // Convert to m²

            biodiversity_loss += crop_biodiversity_loss;
            sources.push(format!("{}: {:.0} m²·yr (production system: {:?})",
                                food.name, crop_biodiversity_loss,
                                food.production_system.as_ref().unwrap_or(&ProductionSystem::Conventional)));
        }
    }

    MidpointResult {
        value: biodiversity_loss / total_production_kg,
        unit: "PDF·m²·yr per kg".to_string(), // PDF = Potentially Disappeared Fraction
        uncertainty_range: (biodiversity_loss * 0.5 / total_production_kg,
                           biodiversity_loss * 1.5 / total_production_kg),
        data_quality_score: 0.6, // Moderate quality - based on production system proxy
        contributing_sources: sources,
    }
}

fn calculate_soil_degradation(
    soil_mgmt: &SoilManagement,
    _fertilization: &FertilizationPractices,
    _foods: &[FoodItem],
    total_area_ha: f64,
    total_production_kg: f64,
) -> MidpointResult {

    let mut soil_degradation = 0.0;
    let mut sources = Vec::new();

    // Base soil erosion: 10 tons per hectare per year for conventional tillage
    let base_erosion_t_per_ha = 10.0;

    // Conservation practice adjustments
    let conservation_factor = if soil_mgmt.conservation_practices.iter().any(|p| p.contains("No-till") || p.contains("Minimum")) {
        0.3 // 70% reduction with no-till
    } else if soil_mgmt.conservation_practices.iter().any(|p| p.contains("Contour") || p.contains("Terrac")) {
        0.5 // 50% reduction with contour plowing
    } else if !soil_mgmt.conservation_practices.is_empty() {
        0.7 // 30% reduction with some practices
    } else {
        1.0 // No conservation
    };

    let erosion_total = base_erosion_t_per_ha * total_area_ha * conservation_factor;
    soil_degradation += erosion_total * 1000.0; // Convert to kg

    sources.push(format!("Soil erosion: {:.1} t/ha × {:.1} ha × {:.2} conservation factor = {:.0} kg",
                        base_erosion_t_per_ha, total_area_ha, conservation_factor, erosion_total * 1000.0));

    // Soil organic carbon loss
    if soil_mgmt.uses_compost {
        sources.push("Compost use: reduces soil degradation".to_string());
    } else {
        let soc_loss = total_area_ha * 500.0; // 500 kg C/ha/year loss without organic inputs
        soil_degradation += soc_loss;
        sources.push(format!("Soil organic carbon loss: {:.0} kg", soc_loss));
    }

    // Compaction from tillage
    let compaction_impact = total_area_ha * 100.0; // 100 kg soil-eq per ha
    soil_degradation += compaction_impact;

    MidpointResult {
        value: soil_degradation / total_production_kg,
        unit: "kg soil-eq per kg".to_string(),
        uncertainty_range: (soil_degradation * 0.6 / total_production_kg,
                           soil_degradation * 1.4 / total_production_kg),
        data_quality_score: 0.7,
        contributing_sources: sources,
    }
}

fn calculate_marine_eutrophication(
    inventory: &HashMap<String, InventoryItem>,
    total_production_kg: f64,
) -> MidpointResult {

    let mut n_runoff = 0.0;
    let mut sources = Vec::new();

    // Get nitrate leaching from inventory
    for (_, item) in inventory {
        if item.substance.contains("Nitrate") {
            // Nitrate leaching to water → runoff to marine environment
            // Assume 50% reaches marine systems (simplified)
            let marine_n = item.quantity * 0.5 * (14.0 / 62.0); // Convert NO3 to N
            n_runoff += marine_n;
            sources.push(format!("N runoff from nitrate leaching: {:.1} kg N", marine_n));
        }
    }

    // Characterization: 1 kg N = 1 kg N-eq (marine eutrophication potential)
    let marine_eutro = n_runoff;

    MidpointResult {
        value: marine_eutro / total_production_kg,
        unit: "kg N-eq per kg".to_string(),
        uncertainty_range: (marine_eutro * 0.5 / total_production_kg,
                           marine_eutro * 1.5 / total_production_kg),
        data_quality_score: 0.65,
        contributing_sources: sources,
    }
}

fn calculate_terrestrial_acidification(
    inventory: &HashMap<String, InventoryItem>,
    management_practices: &Option<ManagementPractices>,
    total_production_kg: f64,
) -> MidpointResult {

    let mut so2_eq = 0.0;
    let mut sources = Vec::new();

    // NH3 volatilization from fertilizers (20% of applied N volatilizes)
    if let Some(mgmt) = management_practices {
        if mgmt.fertilization.uses_fertilizers {
            let total_n_applied: f64 = mgmt.fertilization.fertilizer_applications.iter()
                .map(|app| {
                    let n_content = get_n_content(&app.fertilizer_type, &app.npk_ratio);
                    app.application_rate * n_content * app.applications_per_season as f64
                })
                .sum();

            let nh3_volatilized = total_n_applied * 0.20; // 20% volatilizes as NH3
            let nh3_to_so2_eq = nh3_volatilized * (17.0 / 14.0) * 1.88; // NH3 → SO2-eq (characterization factor 1.88)

            so2_eq += nh3_to_so2_eq;
            sources.push(format!("NH3 volatilization: {:.1} kg NH3 ({:.1} kg SO2-eq)",
                                nh3_volatilized * (17.0 / 14.0), nh3_to_so2_eq));
        }
    }

    // NOx from fuel combustion
    for (_, item) in inventory {
        if item.source.contains("Diesel") || item.source.contains("Petrol") {
            // Estimate NOx emissions: 0.02 kg NOx per L fuel
            // Extract fuel consumption from source string (simplified)
            if let Some(fuel_l) = extract_fuel_consumption(&item.source) {
                let nox = fuel_l * 0.02;
                let nox_to_so2_eq = nox * 0.70; // NOx characterization factor
                so2_eq += nox_to_so2_eq;
                sources.push(format!("NOx from fuel: {:.1} kg NOx ({:.1} kg SO2-eq)", nox, nox_to_so2_eq));
            }
        }
    }

    MidpointResult {
        value: so2_eq / total_production_kg,
        unit: "kg SO2-eq per kg".to_string(),
        uncertainty_range: (so2_eq * 0.6 / total_production_kg,
                           so2_eq * 1.4 / total_production_kg),
        data_quality_score: 0.7,
        contributing_sources: sources,
    }
}

fn calculate_particulate_matter(
    inventory: &HashMap<String, InventoryItem>,
    total_production_kg: f64,
) -> MidpointResult {

    let mut pm25_eq = 0.0;
    let mut sources = Vec::new();

    // PM2.5 from diesel combustion: 0.1 g per L
    for (_, item) in inventory {
        if item.source.contains("Diesel") {
            if let Some(fuel_l) = extract_fuel_consumption(&item.source) {
                let pm25 = fuel_l * 0.0001; // 0.1 g/L = 0.0001 kg/L
                pm25_eq += pm25;
                sources.push(format!("PM2.5 from diesel: {:.3} kg", pm25));
            }
        }
    }

    // PM from NH3 (secondary PM formation)
    // Simplified: 10% of NH3 forms secondary PM
    // NH3 already calculated in acidification, estimate here
    pm25_eq *= 1.2; // Account for secondary PM

    MidpointResult {
        value: pm25_eq / total_production_kg,
        unit: "kg PM2.5-eq per kg".to_string(),
        uncertainty_range: (pm25_eq * 0.5 / total_production_kg,
                           pm25_eq * 1.5 / total_production_kg),
        data_quality_score: 0.6,
        contributing_sources: sources,
    }
}

fn calculate_photochemical_oxidation(
    inventory: &HashMap<String, InventoryItem>,
    total_production_kg: f64,
) -> MidpointResult {

    let mut nmvoc_eq = 0.0;
    let mut sources = Vec::new();

    // NMVOC from fuel combustion: 0.5 g per L diesel, 2 g per L petrol
    for (_, item) in inventory {
        if let Some(fuel_l) = extract_fuel_consumption(&item.source) {
            let nmvoc = if item.source.contains("Diesel") {
                fuel_l * 0.0005 // 0.5 g/L
            } else if item.source.contains("Petrol") {
                fuel_l * 0.002 // 2 g/L
            } else {
                0.0
            };

            nmvoc_eq += nmvoc;
            sources.push(format!("NMVOC from fuel: {:.3} kg", nmvoc));
        }
    }

    MidpointResult {
        value: nmvoc_eq / total_production_kg,
        unit: "kg NMVOC-eq per kg".to_string(),
        uncertainty_range: (nmvoc_eq * 0.5 / total_production_kg,
                           nmvoc_eq * 1.5 / total_production_kg),
        data_quality_score: 0.65,
        contributing_sources: sources,
    }
}

fn calculate_fossil_depletion(
    inventory: &HashMap<String, InventoryItem>,
    total_production_kg: f64,
) -> MidpointResult {

    let mut oil_eq = 0.0;
    let mut sources = Vec::new();

    // Convert fuel consumption to oil equivalents
    // Diesel: 1 L = 0.85 kg oil-eq
    // Petrol: 1 L = 0.83 kg oil-eq
    for (_, item) in inventory {
        if let Some(fuel_l) = extract_fuel_consumption(&item.source) {
            let oil_equiv = if item.source.contains("Diesel") {
                fuel_l * 0.85
            } else if item.source.contains("Petrol") {
                fuel_l * 0.83
            } else {
                0.0
            };

            oil_eq += oil_equiv;
            sources.push(format!("Fossil fuel depletion: {:.1} L fuel = {:.1} kg oil-eq", fuel_l, oil_equiv));
        }
    }

    MidpointResult {
        value: oil_eq / total_production_kg,
        unit: "kg oil-eq per kg".to_string(),
        uncertainty_range: (oil_eq * 0.9 / total_production_kg,
                           oil_eq * 1.1 / total_production_kg),
        data_quality_score: 0.85, // High quality - direct measurement
        contributing_sources: sources,
    }
}

fn calculate_mineral_depletion(
    inventory: &HashMap<String, InventoryItem>,
    _management_practices: &Option<ManagementPractices>,
    total_production_kg: f64,
) -> MidpointResult {

    let mut fe_eq = 0.0;
    let mut sources = Vec::new();

    // Read mineral depletion from inventory (phosphate rock, potash)
    for (_key, item) in inventory {
        if item.compartment == EnvironmentalCompartment::Resource {
            // Items already in Fe-eq from LCI
            if item.substance.contains("Phosphate") || item.substance.contains("Potash") {
                fe_eq += item.quantity;
                sources.push(format!("{}: {:.1} {}",
                    item.source,
                    item.quantity,
                    item.unit
                ));
            }
        }
    }

    MidpointResult {
        value: fe_eq / total_production_kg,
        unit: "kg Fe-eq per kg".to_string(),
        uncertainty_range: (fe_eq * 0.7 / total_production_kg,
                           fe_eq * 1.3 / total_production_kg),
        data_quality_score: if fe_eq > 0.0 { 0.75 } else { 0.7 },
        contributing_sources: sources,
    }
}

// Helper functions

fn get_n_content(fertilizer_type: &str, npk_ratio: &Option<String>) -> f64 {
    match fertilizer_type {
        "Urea" => 0.46,
        "DAP" | "Diammonium Phosphate (DAP)" => 0.18,
        "NPK Compound" | "NPK" => {
            if let Some(ratio) = npk_ratio {
                if let Some(n_str) = ratio.split('-').next() {
                    if let Ok(n_percent) = n_str.trim().parse::<f64>() {
                        return n_percent / 100.0;
                    }
                }
            }
            0.15
        }
        _ => 0.10,
    }
}

fn extract_fuel_consumption(source: &str) -> Option<f64> {
    // Extract fuel consumption from source string like "Diesel: 145 L/month (1740.0 L/year)"
    if let Some(start) = source.find('(') {
        if let Some(end) = source.find(" L/year") {
            let fuel_str = &source[start + 1..end];
            if let Ok(fuel) = fuel_str.parse::<f64>() {
                return Some(fuel);
            }
        }
    }

    // Alternative format: "145 L/month"
    if let Some(pos) = source.find(" L/month") {
        let parts: Vec<&str> = source[..pos].split_whitespace().collect();
        if let Some(last) = parts.last() {
            if let Ok(monthly) = last.parse::<f64>() {
                return Some(monthly * 12.0); // Convert to annual
            }
        }
    }

    None
}
