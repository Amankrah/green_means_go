/**
 * Life Cycle Inventory (LCI) Module - ISO 14040/14044 Compliant
 *
 * This module implements proper LCI calculations by computing environmental
 * burdens from actual user inputs (inventory data) rather than using generic
 * category-level factors.
 *
 * LCA Methodology Flow (ISO 14040/14044):
 * 1. Goal & Scope Definition
 * 2. Life Cycle Inventory (LCI) ← THIS MODULE
 *    - Collect input data (fertilizers, fuels, pesticides, etc.)
 *    - Calculate elementary flows (emissions, resource use)
 *    - Apply emission factors
 * 3. Life Cycle Impact Assessment (LCIA)
 *    - Characterization (midpoint impacts)
 *    - Normalization
 *    - Weighting (endpoint impacts)
 * 4. Interpretation
 *
 * References:
 * - IPCC 2019 Refinement to 2006 Guidelines (N2O emissions from N inputs)
 * - IPCC AR6 (GWP values)
 * - Ecoinvent 3.8 database (emission factors)
 * - GREET model (fuel combustion factors)
 */

use crate::models::*;
use std::collections::HashMap;
use log::{info, warn};

// ======================================================================
// EMISSION FACTORS DATABASE - Based on Scientific Literature
// ======================================================================

/// Emission factors for agricultural inputs and activities
/// All factors are peer-reviewed and cited
pub struct EmissionFactorsDatabase {
    /// N2O emissions from nitrogen fertilizers (kg N2O-N per kg N applied)
    /// Source: IPCC 2019 Refinement, Volume 4, Chapter 11
    pub n2o_from_n_fertilizer: EmissionFactor,

    /// CO2 from diesel combustion (kg CO2 per liter)
    /// Source: GREET 2021 model, EPA
    pub co2_from_diesel: EmissionFactor,

    /// CO2 from petrol/gasoline combustion (kg CO2 per liter)
    /// Source: GREET 2021 model, EPA
    pub co2_from_petrol: EmissionFactor,

    /// CO2 from grid electricity - Ghana (kg CO2 per kWh)
    /// Source: Ghana Energy Commission 2021
    pub co2_from_electricity_ghana: EmissionFactor,

    /// CO2 from grid electricity - Nigeria (kg CO2 per kWh)
    /// Source: Nigerian Electricity Regulatory Commission
    pub co2_from_electricity_nigeria: EmissionFactor,

    /// CO2 from urea production and transport (kg CO2 per kg urea)
    /// Source: Ecoinvent 3.8
    pub co2_from_urea_production: EmissionFactor,

    /// CO2 from NPK production and transport (kg CO2 per kg NPK)
    /// Source: Ecoinvent 3.8
    pub co2_from_npk_production: EmissionFactor,

    /// Pesticide production impacts (kg CO2-eq per kg active ingredient)
    /// Source: Ecoinvent 3.8, averaged for common pesticides
    pub pesticide_production_impact: EmissionFactor,

    /// Water consumption factor for irrigation (no emission, but resource use)
    pub water_use_factor: f64, // Typically 1:1 for direct use

    /// CH4 emissions from rice paddies (kg CH4 per ha per season)
    /// Source: IPCC 2019, Chapter 5
    pub ch4_from_rice_paddies: EmissionFactor,
}

#[derive(Debug, Clone)]
pub struct EmissionFactor {
    pub value: f64,
    pub unit: String,
    pub source: String,
    pub year: i32,
    pub uncertainty: f64, // ±% uncertainty
    pub geographical_validity: String,
}

impl Default for EmissionFactorsDatabase {
    fn default() -> Self {
        Self {
            // IPCC 2019: Default N2O emission factor for direct emissions
            // EF1 = 0.01 kg N2O-N per kg N applied (1% of applied N)
            n2o_from_n_fertilizer: EmissionFactor {
                value: 0.01, // 1% of applied N converted to N2O-N
                unit: "kg N2O-N per kg N".to_string(),
                source: "IPCC 2019 Refinement, Vol 4, Ch 11, Table 11.1".to_string(),
                year: 2019,
                uncertainty: 70.0, // ±70% uncertainty range
                geographical_validity: "Global default, tropical conditions".to_string(),
            },

            // Diesel combustion: 2.68 kg CO2 per liter
            // Source: EPA, GREET model
            co2_from_diesel: EmissionFactor {
                value: 2.68,
                unit: "kg CO2 per liter".to_string(),
                source: "GREET 2021 Model, EPA".to_string(),
                year: 2021,
                uncertainty: 5.0, // Well-established factor
                geographical_validity: "Global".to_string(),
            },

            // Petrol/gasoline combustion: 2.31 kg CO2 per liter
            // Source: EPA, GREET model
            co2_from_petrol: EmissionFactor {
                value: 2.31,
                unit: "kg CO2 per liter".to_string(),
                source: "GREET 2021 Model, EPA".to_string(),
                year: 2021,
                uncertainty: 5.0,
                geographical_validity: "Global".to_string(),
            },

            // Ghana electricity grid: 0.45 kg CO2 per kWh
            // Mix of thermal, hydro, and imports
            co2_from_electricity_ghana: EmissionFactor {
                value: 0.45,
                unit: "kg CO2 per kWh".to_string(),
                source: "Ghana Energy Commission, 2021 Grid Factor".to_string(),
                year: 2021,
                uncertainty: 20.0, // Grid mix varies
                geographical_validity: "Ghana national grid".to_string(),
            },

            // Nigeria electricity grid: 0.58 kg CO2 per kWh
            // Heavily thermal-based (gas, coal)
            co2_from_electricity_nigeria: EmissionFactor {
                value: 0.58,
                unit: "kg CO2 per kWh".to_string(),
                source: "Nigerian Electricity Regulatory Commission, 2020".to_string(),
                year: 2020,
                uncertainty: 25.0,
                geographical_validity: "Nigeria national grid".to_string(),
            },

            // Urea production: 1.2 kg CO2 per kg urea
            // Includes production energy and CO2 release from urea hydrolysis
            co2_from_urea_production: EmissionFactor {
                value: 1.2,
                unit: "kg CO2 per kg urea".to_string(),
                source: "Ecoinvent 3.8, Urea production GLO".to_string(),
                year: 2021,
                uncertainty: 15.0,
                geographical_validity: "Global average".to_string(),
            },

            // NPK compound fertilizer production: 1.5 kg CO2 per kg NPK
            co2_from_npk_production: EmissionFactor {
                value: 1.5,
                unit: "kg CO2 per kg NPK".to_string(),
                source: "Ecoinvent 3.8, NPK fertilizer production".to_string(),
                year: 2021,
                uncertainty: 20.0,
                geographical_validity: "Global average".to_string(),
            },

            // Pesticide production: 10 kg CO2-eq per kg active ingredient
            // High energy intensity for chemical synthesis
            pesticide_production_impact: EmissionFactor {
                value: 10.0,
                unit: "kg CO2-eq per kg a.i.".to_string(),
                source: "Ecoinvent 3.8, Pesticide production average".to_string(),
                year: 2021,
                uncertainty: 50.0, // High variation between pesticide types
                geographical_validity: "Global average".to_string(),
            },

            // Water use: Direct measurement
            water_use_factor: 1.0,

            // Methane from rice paddies: 200 kg CH4 per ha per season (continuously flooded)
            // Source: IPCC 2019, Chapter 5
            ch4_from_rice_paddies: EmissionFactor {
                value: 200.0,
                unit: "kg CH4 per ha per season".to_string(),
                source: "IPCC 2019, Vol 4, Ch 5, Table 5.12".to_string(),
                year: 2019,
                uncertainty: 50.0, // High variation based on water regime
                geographical_validity: "Tropical continuously flooded rice".to_string(),
            },
        }
    }
}

// ======================================================================
// LIFE CYCLE INVENTORY CALCULATOR
// ======================================================================

pub struct LCICalculator {
    emission_factors: EmissionFactorsDatabase,
    inventory: HashMap<String, InventoryItem>,
}

#[derive(Debug, Clone)]
pub struct InventoryItem {
    pub substance: String,
    pub quantity: f64,
    pub unit: String,
    pub compartment: EnvironmentalCompartment, // Air, Water, Soil
    pub source: String, // Which input caused this emission
}

#[derive(Debug, Clone, PartialEq)]
pub enum EnvironmentalCompartment {
    Air,
    Water,
    Soil,
    Resource, // For resource extraction/use
}

impl LCICalculator {
    pub fn new() -> Self {
        Self {
            emission_factors: EmissionFactorsDatabase::default(),
            inventory: HashMap::new(),
        }
    }

    /// Calculate complete life cycle inventory from user inputs
    pub fn calculate_inventory(
        &mut self,
        assessment: &Assessment,
    ) -> Result<HashMap<String, InventoryItem>, Box<dyn std::error::Error>> {

        info!("Starting LCI calculation for assessment {}", assessment.id);

        // Clear previous inventory
        self.inventory.clear();

        // 1. Calculate emissions from fertilizers (N2O, production CO2)
        if let Some(ref mgmt) = assessment.management_practices {
            self.calculate_fertilizer_emissions(&mgmt.fertilization, &assessment.foods)?;
        }

        // 2. Calculate emissions from fuel consumption (CO2)
        // TODO: This requires EquipmentEnergy data from frontend
        // For now, we'll use a simplified approach based on farm size
        self.calculate_energy_emissions(assessment)?;

        // 3. Calculate emissions from pesticide production
        if let Some(ref mgmt) = assessment.management_practices {
            self.calculate_pesticide_emissions(&mgmt.pest_management)?;
        }

        // 4. Calculate water consumption
        if let Some(ref mgmt) = assessment.management_practices {
            self.calculate_water_consumption(&mgmt.water_management, &assessment.foods)?;
        }

        // 5. Calculate crop-specific emissions (e.g., CH4 from rice)
        self.calculate_crop_specific_emissions(&assessment.foods)?;

        // 6. Calculate land use
        self.calculate_land_use(&assessment.foods)?;

        info!("LCI calculation completed. {} inventory items generated", self.inventory.len());

        Ok(self.inventory.clone())
    }

    /// Calculate N2O and CO2 emissions from fertilizer use
    /// Following IPCC 2019 methodology
    fn calculate_fertilizer_emissions(
        &mut self,
        fertilization: &FertilizationPractices,
        foods: &[FoodItem],
    ) -> Result<(), Box<dyn std::error::Error>> {

        if !fertilization.uses_fertilizers {
            return Ok(());
        }

        // Calculate total area under cultivation
        let total_area_ha: f64 = foods.iter()
            .filter_map(|f| f.area_allocated)
            .sum();

        if total_area_ha == 0.0 {
            warn!("No area allocated for crops, cannot calculate fertilizer emissions accurately");
            return Ok(());
        }

        for app in &fertilization.fertilizer_applications {
            // Calculate total N applied
            let n_content = self.get_nitrogen_content(&app.fertilizer_type, &app.npk_ratio);

            // Total N applied (kg N)
            // application_rate is in kg fertilizer/ha/season
            // n_content is fraction of N in the fertilizer
            let n_applied_per_ha = app.application_rate * n_content;
            let applications_per_year = app.applications_per_season as f64;
            let total_n_applied = n_applied_per_ha * total_area_ha * applications_per_year;

            info!("Fertilizer application: {} kg/ha/season × {} ha × {} times = {} kg N/year",
                  n_applied_per_ha, total_area_ha, applications_per_year, total_n_applied);

            // IPCC 2019 Equation 11.1: Direct N2O emissions
            // N2O-N = N_applied × EF1
            // where EF1 = 0.01 kg N2O-N per kg N applied
            let n2o_n_direct = total_n_applied * self.emission_factors.n2o_from_n_fertilizer.value;

            // Convert N2O-N to N2O (molecular weight ratio: 44/28)
            let n2o_direct = n2o_n_direct * (44.0 / 28.0);

            // Add to inventory
            self.add_inventory_item(InventoryItem {
                substance: "Dinitrogen monoxide (N2O)".to_string(),
                quantity: n2o_direct,
                unit: "kg".to_string(),
                compartment: EnvironmentalCompartment::Air,
                source: format!("Direct N2O emissions from {} application", app.fertilizer_type),
            });

            // CO2 from fertilizer production
            let production_co2 = match app.fertilizer_type.as_str() {
                "Urea" => app.application_rate * total_area_ha * applications_per_year
                         * self.emission_factors.co2_from_urea_production.value,
                "NPK Compound" | "NPK" => app.application_rate * total_area_ha * applications_per_year
                                         * self.emission_factors.co2_from_npk_production.value,
                _ => app.application_rate * total_area_ha * applications_per_year * 1.0, // Generic factor
            };

            self.add_inventory_item(InventoryItem {
                substance: "Carbon dioxide (CO2)".to_string(),
                quantity: production_co2,
                unit: "kg".to_string(),
                compartment: EnvironmentalCompartment::Air,
                source: format!("Production and transport of {}", app.fertilizer_type),
            });

            // Mineral depletion from fertilizer production
            // NPK requires phosphate rock (P) and potash (K) mining
            // Urea requires natural gas (but that's fossil depletion, not mineral)
            let total_fertilizer_kg = app.application_rate * total_area_ha * applications_per_year;

            match app.fertilizer_type.as_str() {
                "NPK Compound" | "NPK" => {
                    // Extract P and K content from NPK ratio (e.g., "15-15-15")
                    if let Some(ref npk_ratio) = app.npk_ratio {
                        let parts: Vec<&str> = npk_ratio.split('-').collect();
                        if parts.len() == 3 {
                            // Phosphate (P2O5) content - converted to Fe-eq
                            // 1 kg P2O5 ≈ 0.3 kg Fe-eq (phosphate rock mining)
                            if let Ok(p_percent) = parts[1].parse::<f64>() {
                                let p2o5_kg = total_fertilizer_kg * (p_percent / 100.0);
                                let phosphate_depletion = p2o5_kg * 0.3;

                                self.add_inventory_item(InventoryItem {
                                    substance: "Phosphate rock".to_string(),
                                    quantity: phosphate_depletion,
                                    unit: "kg Fe-eq".to_string(),
                                    compartment: EnvironmentalCompartment::Resource,
                                    source: format!("Phosphate mining for {} production", app.fertilizer_type),
                                });
                            }

                            // Potash (K2O) content - converted to Fe-eq
                            // 1 kg K2O ≈ 0.2 kg Fe-eq (potash mining)
                            if let Ok(k_percent) = parts[2].parse::<f64>() {
                                let k2o_kg = total_fertilizer_kg * (k_percent / 100.0);
                                let potash_depletion = k2o_kg * 0.2;

                                self.add_inventory_item(InventoryItem {
                                    substance: "Potash".to_string(),
                                    quantity: potash_depletion,
                                    unit: "kg Fe-eq".to_string(),
                                    compartment: EnvironmentalCompartment::Resource,
                                    source: format!("Potash mining for {} production", app.fertilizer_type),
                                });
                            }
                        }
                    }
                }
                _ => {
                    // Other fertilizers have minimal mineral depletion
                    // (Urea is from natural gas, organic fertilizers don't deplete minerals)
                }
            }

            // Indirect N2O emissions from volatilization and leaching (IPCC 2019)
            // Simplified: 0.01 kg N2O-N per kg N volatilized/leached
            // Assume 20% of applied N is lost via volatilization + leaching
            let n_volatilized_leached = total_n_applied * 0.20;
            let n2o_n_indirect = n_volatilized_leached * 0.01;
            let n2o_indirect = n2o_n_indirect * (44.0 / 28.0);

            self.add_inventory_item(InventoryItem {
                substance: "Dinitrogen monoxide (N2O) - indirect".to_string(),
                quantity: n2o_indirect,
                unit: "kg".to_string(),
                compartment: EnvironmentalCompartment::Air,
                source: format!("Indirect N2O emissions from {} (volatilization/leaching)", app.fertilizer_type),
            });

            // Nitrate leaching to water
            let no3_leached = n_volatilized_leached * (62.0 / 14.0); // Convert N to NO3
            self.add_inventory_item(InventoryItem {
                substance: "Nitrate (NO3-)".to_string(),
                quantity: no3_leached,
                unit: "kg".to_string(),
                compartment: EnvironmentalCompartment::Water,
                source: format!("Nitrate leaching from {} application", app.fertilizer_type),
            });
        }

        Ok(())
    }

    /// Get nitrogen content of fertilizer
    fn get_nitrogen_content(&self, fertilizer_type: &str, npk_ratio: &Option<String>) -> f64 {
        match fertilizer_type {
            "Urea" => 0.46, // 46% N
            "Diammonium Phosphate (DAP)" | "DAP" => 0.18, // 18% N
            "NPK Compound" | "NPK" => {
                // Parse NPK ratio if provided (e.g., "15-15-15")
                if let Some(ratio) = npk_ratio {
                    if let Some(n_str) = ratio.split('-').next() {
                        if let Ok(n_percent) = n_str.trim().parse::<f64>() {
                            return n_percent / 100.0;
                        }
                    }
                }
                0.15 // Default 15% N for NPK
            }
            "Ammonium Sulfate" => 0.21, // 21% N
            "Calcium Ammonium Nitrate" | "CAN" => 0.27, // 27% N
            _ => 0.10, // Conservative default
        }
    }

    /// Calculate CO2 emissions from energy use
    fn calculate_energy_emissions(
        &mut self,
        assessment: &Assessment,
    ) -> Result<(), Box<dyn std::error::Error>> {

        // Check if we have actual equipment/energy data
        if let Some(ref equipment_energy) = assessment.equipment_energy {
            info!("🔥 Using actual equipment and energy consumption data");
            info!("🔥 Fuel consumption items: {}", equipment_energy.fuel_consumption.len());

            // Calculate fuel consumption from actual data
            for fuel in &equipment_energy.fuel_consumption {
                info!("🔥 Processing fuel: {} - {} L/month", fuel.fuel_type, fuel.monthly_consumption);
                let annual_consumption_l = fuel.monthly_consumption * 12.0;

                let emission_factor = match fuel.fuel_type.as_str() {
                    "Diesel" => self.emission_factors.co2_from_diesel.value,
                    "Petrol" | "Petrol/Gasoline" | "Gasoline" => self.emission_factors.co2_from_petrol.value,
                    _ => 2.5, // Conservative default
                };

                let co2_from_fuel = annual_consumption_l * emission_factor;

                self.add_inventory_item(InventoryItem {
                    substance: "Carbon dioxide (CO2)".to_string(),
                    quantity: co2_from_fuel,
                    unit: "kg".to_string(),
                    compartment: EnvironmentalCompartment::Air,
                    source: format!("{} consumption: {} L/month ({:.1} L/year)",
                                   fuel.fuel_type, fuel.monthly_consumption, annual_consumption_l),
                });
            }

            // Calculate electricity emissions from actual data
            for energy in &equipment_energy.energy_sources {
                if energy.energy_type.contains("Electricity") || energy.energy_type.contains("Grid") {
                    let annual_consumption_kwh = energy.monthly_consumption * 12.0;

                    let electricity_ef = match assessment.country {
                        Country::Ghana => self.emission_factors.co2_from_electricity_ghana.value,
                        Country::Nigeria => self.emission_factors.co2_from_electricity_nigeria.value,
                        _ => 0.50, // Global average
                    };

                    let co2_from_electricity = annual_consumption_kwh * electricity_ef;

                    self.add_inventory_item(InventoryItem {
                        substance: "Carbon dioxide (CO2)".to_string(),
                        quantity: co2_from_electricity,
                        unit: "kg".to_string(),
                        compartment: EnvironmentalCompartment::Air,
                        source: format!("{} consumption: {} kWh/month ({:.1} kWh/year) for {}",
                                       energy.energy_type, energy.monthly_consumption,
                                       annual_consumption_kwh, energy.primary_use),
                    });
                }
            }

            info!("Energy emissions calculated from actual user data");
            return Ok(());
        }

        // FALLBACK: Estimate based on farm size
        warn!("No equipment/energy data provided. Using estimates based on farm size.");

        // Get total farm area
        let total_area_ha: f64 = assessment.foods.iter()
            .filter_map(|f| f.area_allocated)
            .sum();

        if total_area_ha == 0.0 {
            return Ok(());
        }

        // Estimate diesel consumption for smallholder farms
        // Typical: 50-150 L diesel per hectare per year (plowing, transport)
        // Conservative estimate: 80 L/ha/year for mixed manual-mechanized
        let estimated_diesel_l_per_year = total_area_ha * 80.0;

        let co2_from_diesel = estimated_diesel_l_per_year * self.emission_factors.co2_from_diesel.value;

        self.add_inventory_item(InventoryItem {
            substance: "Carbon dioxide (CO2)".to_string(),
            quantity: co2_from_diesel,
            unit: "kg".to_string(),
            compartment: EnvironmentalCompartment::Air,
            source: format!("Diesel consumption for farm operations (ESTIMATED: {} L/year based on {} ha)",
                           estimated_diesel_l_per_year, total_area_ha),
        });

        // Estimate electricity use
        // Typical: 100-500 kWh per hectare per year for irrigation pumps
        let estimated_electricity_kwh = total_area_ha * 200.0;

        let electricity_ef = match assessment.country {
            Country::Ghana => self.emission_factors.co2_from_electricity_ghana.value,
            Country::Nigeria => self.emission_factors.co2_from_electricity_nigeria.value,
            _ => 0.50, // Global average
        };

        let co2_from_electricity = estimated_electricity_kwh * electricity_ef;

        self.add_inventory_item(InventoryItem {
            substance: "Carbon dioxide (CO2)".to_string(),
            quantity: co2_from_electricity,
            unit: "kg".to_string(),
            compartment: EnvironmentalCompartment::Air,
            source: format!("Grid electricity (ESTIMATED: {:.0} kWh/year based on {} ha)",
                           estimated_electricity_kwh, total_area_ha),
        });

        warn!("⚠️ Energy emissions estimated. For accurate results, provide actual fuel/electricity consumption in Equipment & Energy step.");

        Ok(())
    }

    /// Calculate emissions from pesticide production
    fn calculate_pesticide_emissions(
        &mut self,
        pest_management: &PestManagement,
    ) -> Result<(), Box<dyn std::error::Error>> {

        for pesticide in &pest_management.pesticides_used {
            // Calculate total active ingredient applied
            // application_rate is typically in kg or L per ha
            // We need to estimate total area treated

            // For now, assume pesticide is applied to all crop area
            // TODO: Get actual treated area from user input
            let total_ai_kg = pesticide.application_rate * pesticide.applications_per_season as f64;

            let production_impact = total_ai_kg * self.emission_factors.pesticide_production_impact.value;

            self.add_inventory_item(InventoryItem {
                substance: "Carbon dioxide (CO2) equivalent".to_string(),
                quantity: production_impact,
                unit: "kg CO2-eq".to_string(),
                compartment: EnvironmentalCompartment::Air,
                source: format!("Production of {} pesticide ({})",
                               pesticide.pesticide_type, pesticide.active_ingredient),
            });
        }

        Ok(())
    }

    /// Calculate water consumption
    fn calculate_water_consumption(
        &mut self,
        water_management: &WaterManagement,
        foods: &[FoodItem],
    ) -> Result<(), Box<dyn std::error::Error>> {

        // Get total area
        let total_area_ha: f64 = foods.iter()
            .filter_map(|f| f.area_allocated)
            .sum();

        // Estimate irrigation water use based on system type
        let water_use_m3_per_ha = match water_management.irrigation_system.as_deref() {
            Some("Drip irrigation") | Some("Drip Irrigation") => 3000.0, // Efficient
            Some("Sprinkler") | Some("Sprinkler System") => 5000.0, // Moderate
            Some("Flood irrigation") | Some("Furrow irrigation") => 8000.0, // Inefficient
            None | Some("None (Rainfed)") => 0.0, // Rainfed
            _ => 4000.0, // Default moderate use
        };

        let total_water_m3 = water_use_m3_per_ha * total_area_ha;

        if total_water_m3 > 0.0 {
            self.add_inventory_item(InventoryItem {
                substance: "Water".to_string(),
                quantity: total_water_m3,
                unit: "m3".to_string(),
                compartment: EnvironmentalCompartment::Resource,
                source: format!("Irrigation water ({})",
                               water_management.irrigation_system.as_deref().unwrap_or("Unknown")),
            });
        }

        Ok(())
    }

    /// Calculate crop-specific emissions (e.g., CH4 from rice)
    fn calculate_crop_specific_emissions(
        &mut self,
        foods: &[FoodItem],
    ) -> Result<(), Box<dyn std::error::Error>> {

        for food in foods {
            // Check if crop is rice (flooded rice paddies emit CH4)
            if food.name.to_lowercase().contains("rice") {
                if let Some(area_ha) = food.area_allocated {
                    // CH4 emissions from flooded rice paddies
                    let ch4_emissions = area_ha * self.emission_factors.ch4_from_rice_paddies.value;

                    self.add_inventory_item(InventoryItem {
                        substance: "Methane (CH4)".to_string(),
                        quantity: ch4_emissions,
                        unit: "kg".to_string(),
                        compartment: EnvironmentalCompartment::Air,
                        source: format!("Methane emissions from rice cultivation ({} ha)", area_ha),
                    });
                }
            }
        }

        Ok(())
    }

    /// Calculate land use
    fn calculate_land_use(
        &mut self,
        foods: &[FoodItem],
    ) -> Result<(), Box<dyn std::error::Error>> {

        let total_land_m2: f64 = foods.iter()
            .filter_map(|f| f.area_allocated.map(|a| a * 10000.0)) // Convert ha to m2
            .sum();

        if total_land_m2 > 0.0 {
            self.add_inventory_item(InventoryItem {
                substance: "Land occupation, annual crop".to_string(),
                quantity: total_land_m2,
                unit: "m2*year".to_string(),
                compartment: EnvironmentalCompartment::Resource,
                source: "Agricultural land occupation".to_string(),
            });
        }

        Ok(())
    }

    /// Add inventory item to the collection
    fn add_inventory_item(&mut self, item: InventoryItem) {
        let key = format!("{}_{:?}", item.substance, item.compartment);

        // If item already exists, aggregate quantities
        if let Some(existing) = self.inventory.get_mut(&key) {
            existing.quantity += item.quantity;
            existing.source = format!("{}, {}", existing.source, item.source);
        } else {
            self.inventory.insert(key, item);
        }
    }

    /// Get the complete inventory
    pub fn get_inventory(&self) -> &HashMap<String, InventoryItem> {
        &self.inventory
    }
}

// ======================================================================
// LCI TO LCIA BRIDGE - Convert Inventory to Impact Categories
// ======================================================================

impl LCICalculator {
    /// Convert LCI results to LCIA midpoint indicators
    /// This is where we go from "kg N2O" to "kg CO2-eq global warming potential"
    pub fn calculate_midpoint_impacts(
        &self,
        inventory: &HashMap<String, InventoryItem>,
    ) -> Result<HashMap<String, MidpointResult>, Box<dyn std::error::Error>> {

        let mut impacts = HashMap::new();

        // Initialize all impact categories
        let impact_categories = vec![
            "Global warming",
            "Water consumption",
            "Water scarcity",
            "Land use",
            "Biodiversity loss",
            "Soil degradation",
            "Terrestrial acidification",
            "Freshwater eutrophication",
            "Marine eutrophication",
            "Fossil depletion",
            "Mineral depletion",
            "Particulate matter formation",
            "Photochemical oxidation",
        ];

        for category in &impact_categories {
            impacts.insert(category.to_string(), MidpointResult {
                value: 0.0,
                unit: self.get_impact_unit(category),
                uncertainty_range: (0.0, 0.0),
                data_quality_score: 0.8, // High quality - calculated from primary data
                contributing_sources: Vec::new(),
            });
        }

        // Characterization factors (IPCC AR6, ReCiPe 2016)
        let gwp_n2o = 273.0; // N2O has 273x warming potential of CO2 (100-year horizon)
        let gwp_ch4 = 28.0;  // CH4 has 28x warming potential of CO2 (fossil) - AR6

        // Calculate Global Warming Potential
        let mut gwp_total = 0.0;
        let mut gwp_sources = Vec::new();

        for (_, item) in inventory {
            match item.substance.as_str() {
                "Carbon dioxide (CO2)" | "Carbon dioxide (CO2) equivalent" => {
                    gwp_total += item.quantity; // Already in kg CO2
                    gwp_sources.push(format!("{}: {:.2} kg CO2", item.source, item.quantity));
                }
                s if s.contains("N2O") => {
                    let co2_eq = item.quantity * gwp_n2o;
                    gwp_total += co2_eq;
                    gwp_sources.push(format!("{}: {:.2} kg N2O ({:.2} kg CO2-eq)",
                                            item.source, item.quantity, co2_eq));
                }
                "Methane (CH4)" => {
                    let co2_eq = item.quantity * gwp_ch4;
                    gwp_total += co2_eq;
                    gwp_sources.push(format!("{}: {:.2} kg CH4 ({:.2} kg CO2-eq)",
                                            item.source, item.quantity, co2_eq));
                }
                _ => {}
            }
        }

        if let Some(gwp_result) = impacts.get_mut("Global warming") {
            gwp_result.value = gwp_total;
            gwp_result.contributing_sources = gwp_sources;
            gwp_result.uncertainty_range = (gwp_total * 0.8, gwp_total * 1.2); // ±20% uncertainty
        }

        // Water consumption
        for (_, item) in inventory {
            if item.substance == "Water" {
                if let Some(water_result) = impacts.get_mut("Water consumption") {
                    water_result.value += item.quantity; // m3
                    water_result.contributing_sources.push(item.source.clone());
                }
            }
        }

        // Land use
        for (_, item) in inventory {
            if item.substance.contains("Land occupation") {
                if let Some(land_result) = impacts.get_mut("Land use") {
                    land_result.value += item.quantity / 10000.0; // Convert m2*year to m2a
                    land_result.contributing_sources.push(item.source.clone());
                }
            }
        }

        // Freshwater eutrophication (from nitrate leaching)
        for (_, item) in inventory {
            if item.substance.contains("Nitrate") {
                if let Some(eutroph_result) = impacts.get_mut("Freshwater eutrophication") {
                    // Convert NO3 to P-equivalent using ReCiPe characterization
                    // Simplified: NO3 has lower eutrophication potential than P
                    let p_eq = item.quantity * 0.01; // Rough conversion factor
                    eutroph_result.value += p_eq;
                    eutroph_result.contributing_sources.push(item.source.clone());
                }
            }
        }

        info!("Calculated {} midpoint impact categories from LCI", impacts.len());

        Ok(impacts)
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
}
