/**
 * Contract tests: the wizard payload builders must emit exactly the keys the API models
 * declare (app/production/models.py, app/processing/models.py; both reject unknown keys),
 * and the zod schemas must refuse the inputs the API would otherwise accept blindly.
 */
import { describe, expect, it } from 'vitest';
import { transformEnhancedAssessmentToBackend } from './api';
import {
  enhancedAssessmentSchema,
  blankFarmAssessmentForm,
  managementPracticesSchema,
  pestManagementSchema,
  equipmentEnergySchema,
} from './enhanced-assessment-schema';
import {
  buildProcessingPayload,
  processingAssessmentSchema,
  facilitySchema,
  productSchema,
  utilitiesSchema,
  fuelStreamSchema,
  defaultProcessingForm,
  missingRawMaterialIssues,
  hasDefaultConversionRatio,
  REFRIGERANT_OPTIONS,
  FUEL_UNITS,
  WATER_SOURCES,
} from './processing-assessment-schema';
import { COUNTRY_TO_REGION, GHANA_EXAMPLE, NIGERIA_EXAMPLE } from './country-examples';
import { deriveSeasonalFactor } from './seasonal-factor';
import { pickMarketMode } from './api';
import { restoreFormSnapshot } from './enhanced-assessment-schema';
import {
  EnhancedAssessmentRequest,
  FuelType,
  PestManagementApproach,
  IrrigationSystem,
  CompostSource,
  SoilType,
  TestingFrequency,
  WaterSource,
  FertilizerType,
  MonitoringFrequency,
  SeasonType,
  ApplicationMethod,
  StorageFacilityType,
  isKnownAnnualCrop,
} from '@/types/enhanced-assessment';

// The Nigeria case study has no measured irrigation volume, which the wizard requires.
function NIGERIA_EXAMPLE_WITH_WATER() {
  const ng = JSON.parse(JSON.stringify(NIGERIA_EXAMPLE));
  ng.managementPractices.waterManagement.irrigationWaterM3 = 150000;
  return ng;
}

/** Sorted list of every key path in an object tree; arrays contribute their first element. */
function keyPaths(value: unknown, prefix = ''): string[] {
  if (Array.isArray(value)) {
    if (!value.length) return [];
    const nested = keyPaths(value[0], `${prefix}[]`);
    return nested.length ? nested : [`${prefix}[]`];
  }
  if (value && typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => v !== undefined)
      .flatMap(([k, v]) => {
        const path = prefix ? `${prefix}.${k}` : k;
        const nested = keyPaths(v, path);
        return nested.length ? nested : [path];
      })
      .sort();
  }
  return [];
}

// A complete wizard form (the Ghana case study) turned into the request the wizard builds.
function farmRequestFixture(): EnhancedAssessmentRequest {
  const base = JSON.parse(JSON.stringify(GHANA_EXAMPLE));
  base.equipmentEnergy.fuelConsumption = [
    { fuelType: FuelType.LPG, monthlyConsumption: 6, unit: 'kg', primaryUse: 'Drying', cost: 120 },
    { fuelType: FuelType.DIESEL, monthlyConsumption: 40, primaryUse: 'Ploughing', cost: 500 },
  ];
  base.equipmentEnergy.energySources = [
    { energyType: 'Grid Electricity', monthlyConsumption: 85, primaryUse: 'Lighting', cost: 65, currency: 'GHS' },
  ];
  base.equipmentEnergy.infrastructure.packagingMaterial = 'Polypropylene sacks';
  base.equipmentEnergy.infrastructure.inputTransportKm = 12;
  return base as EnhancedAssessmentRequest;
}

describe('farm payload contract (transformEnhancedAssessmentToBackend)', () => {
  const payload = transformEnhancedAssessmentToBackend(farmRequestFixture());

  it('emits exactly the AssessmentRequest keys the API declares', () => {
    expect(keyPaths(payload)).toEqual([
      'company_name',
      'country',
      'equipment_energy.energy_sources[].cost',
      'equipment_energy.energy_sources[].currency',
      'equipment_energy.energy_sources[].energy_type',
      'equipment_energy.energy_sources[].monthly_consumption',
      'equipment_energy.energy_sources[].primary_use',
      'equipment_energy.equipment[].age',
      'equipment_energy.equipment[].equipment_type',
      'equipment_energy.equipment[].fuel_efficiency',
      'equipment_energy.equipment[].hours_per_year',
      'equipment_energy.equipment[].power_source',
      'equipment_energy.fuel_consumption[].cost',
      'equipment_energy.fuel_consumption[].fuel_type',
      'equipment_energy.fuel_consumption[].monthly_consumption',
      'equipment_energy.fuel_consumption[].primary_use',
      'equipment_energy.fuel_consumption[].unit',
      'equipment_energy.storage.capacity_tonnes',
      'equipment_energy.storage.facilities[]',
      'farm_profile.certifications',
      'farm_profile.farm_name',
      'farm_profile.farm_type',
      'farm_profile.farmer_name',
      'farm_profile.farming_experience',
      'farm_profile.participates_in_programs[]',
      'farm_profile.primary_farming_system',
      'farm_profile.total_farm_size',
      'foods[].area_allocated',
      'foods[].category',
      'foods[].crop_type',
      'foods[].cropping_pattern',
      'foods[].crops_per_year',
      'foods[].growing_period_days',
      'foods[].harvest_months[]',
      'foods[].id',
      'foods[].intercropping_partners[]',
      'foods[].name',
      'foods[].origin_country',
      'foods[].planting_months[]',
      'foods[].post_harvest_losses',
      'foods[].production_system',
      'foods[].quantity_kg',
      'foods[].rotation_sequence[]',
      'foods[].variety',
      'logistics.distance_to_market_km',
      'logistics.input_transport_km',
      'logistics.market_transport_mode',
      'logistics.packaging_material',
      'management_practices.fertilization.fertilizer_applications[].application_method',
      'management_practices.fertilization.fertilizer_applications[].application_rate',
      'management_practices.fertilization.fertilizer_applications[].applications_per_season',
      'management_practices.fertilization.fertilizer_applications[].brand_name',
      'management_practices.fertilization.fertilizer_applications[].cost',
      'management_practices.fertilization.fertilizer_applications[].crop_ids[]',
      'management_practices.fertilization.fertilizer_applications[].fertilizer_type',
      'management_practices.fertilization.fertilizer_applications[].npk_ratio',
      'management_practices.fertilization.follows_nutrient_plan',
      'management_practices.fertilization.soil_test_based',
      'management_practices.fertilization.timing_strategy',
      'management_practices.fertilization.uses_fertilizers',
      'management_practices.pest_management.biological_controls[]',
      'management_practices.pest_management.ipm_practices[]',
      'management_practices.pest_management.management_approach',
      'management_practices.pest_management.pest_monitoring_frequency',
      'management_practices.pest_management.pesticides[].active_ingredient',
      'management_practices.pest_management.pesticides[].application_rate',
      'management_practices.pest_management.pesticides[].applications_per_season',
      'management_practices.pest_management.pesticides[].brand_name',
      'management_practices.pest_management.pesticides[].crop_ids[]',
      'management_practices.pest_management.pesticides[].pesticide_type',
      'management_practices.pest_management.pesticides[].target_pests[]',
      'management_practices.pest_management.primary_diseases[]',
      'management_practices.pest_management.primary_pests[]',
      'management_practices.pest_management.uses_economic_thresholds',
      'management_practices.pest_management.uses_ipm',
      'management_practices.soil_management.compost_application_rate',
      'management_practices.soil_management.compost_crop_ids',
      'management_practices.soil_management.compost_source',
      'management_practices.soil_management.conservation_practices[]',
      'management_practices.soil_management.cover_crops',
      'management_practices.soil_management.lime_applications',
      'management_practices.soil_management.organic_matter_pct',
      'management_practices.soil_management.soil_ph',
      'management_practices.soil_management.soil_testing_frequency',
      'management_practices.soil_management.soil_type',
      'management_practices.soil_management.uses_compost',
      'management_practices.water_management.drainage_system',
      'management_practices.water_management.irrigation_system',
      'management_practices.water_management.water_conservation_practices',
      'management_practices.water_management.water_source[]',
      'region',
      'run_uncertainty',
      'study_meta.admin_region',
    ]);
  });

  it('sends the fuel unit for every fuel row (kg for LPG, L otherwise) and forwards logistics', () => {
    const fuels = payload.equipment_energy!.fuel_consumption;
    expect(fuels.map((f) => [f.fuel_type, f.unit])).toEqual([
      [FuelType.LPG, 'kg'],
      [FuelType.DIESEL, 'L'],
    ]);
    expect(payload.logistics).toMatchObject({
      packaging_material: 'Polypropylene sacks',
      input_transport_km: 12,
      distance_to_market_km: GHANA_EXAMPLE.equipmentEnergy.infrastructure.transportAccess.distanceToMarket,
    });
    expect(payload.management_practices!.pest_management).toBeDefined();
  });

  it('maps the UI country to the API country and engine region', () => {
    expect(payload.country).toBe(COUNTRY_TO_REGION.Ghana.country);
    expect(payload.region).toBe('GH');
  });

  it('sends seasonal_factor only as an explicit override (engine derives it otherwise)', () => {
    const fx = farmRequestFixture();
    fx.cropProductions[0].seasonality.plantingMonths = [2, 3];
    const auto = transformEnhancedAssessmentToBackend(fx);
    expect(auto.foods[0].seasonal_factor).toBeUndefined();
    expect(auto.foods[0].planting_months).toEqual([2, 3]);
    fx.cropProductions[0].seasonality.seasonOverride = SeasonType.DRY_SEASON;
    expect(transformEnhancedAssessmentToBackend(fx).foods[0].seasonal_factor).toBe('DrySeason');
    expect(Object.values(SeasonType)).toEqual(['WetSeason', 'DrySeason', 'YearRound']);
  });

  it('sends admin region, uncertainty flag and stable crop ids', () => {
    expect(payload.study_meta).toEqual({ admin_region: 'Northern' });
    expect(payload.run_uncertainty).toBe(true);
    expect(payload.foods.map((f) => f.id)).toEqual(['crop_maize_001', 'crop_cowpea_001']);
    const fx = farmRequestFixture();
    fx.assessmentParameters.includeUncertaintyAnalysis = false;
    expect(transformEnhancedAssessmentToBackend(fx).run_uncertainty).toBe(false);
  });

  it('targets fertiliser and pesticide rows at crops by foods[].id and maps the method', () => {
    const fert = payload.management_practices!.fertilization.fertilizer_applications;
    expect(fert.map((f) => [f.crop_ids, f.application_method, f.brand_name])).toEqual([
      [['crop_maize_001'], 'band_placement', 'Yara NPK 15-15-15'],
      [['crop_maize_001'], 'side_dressing', 'Wienco Urea'],
    ]);
    expect(payload.management_practices!.pest_management.pesticides[0].crop_ids).toEqual(['crop_maize_001']);
    expect(payload.management_practices!.soil_management.compost_crop_ids).toEqual([]);
  });

  it('copies a legacy farm-level application method onto rows and maps Precision to band placement', () => {
    const fx = farmRequestFixture();
    fx.managementPractices.fertilization.fertilizerApplications.forEach((a) => { delete a.applicationMethod; });
    fx.managementPractices.fertilization.applicationMethod = ApplicationMethod.PRECISION_APPLICATION;
    const rows = transformEnhancedAssessmentToBackend(fx).management_practices!.fertilization.fertilizer_applications;
    expect(rows.map((r) => r.application_method)).toEqual(['band_placement', 'band_placement']);
  });

  it('never sends fertiliser rows of type None or with no rate', () => {
    const fx = farmRequestFixture();
    fx.managementPractices.fertilization.fertilizerApplications.push(
      { fertilizerType: FertilizerType.NONE, applicationRate: 50, applicationsPerSeason: 1, cost: 0 },
      { fertilizerType: FertilizerType.UREA, applicationRate: 0, applicationsPerSeason: 1, cost: 0 },
    );
    const fert = transformEnhancedAssessmentToBackend(fx).management_practices!.fertilization;
    expect(fert.fertilizer_applications).toHaveLength(2);
    expect(fert.uses_fertilizers).toBe(true);
  });

  it('sends soil pH / organic matter only when known (no injected defaults)', () => {
    expect(payload.management_practices!.soil_management).toMatchObject({ soil_ph: 5.9, organic_matter_pct: 2.4, cover_crops: true });
    const fx = farmRequestFixture();
    fx.managementPractices.soilManagement.soilpH = undefined;
    fx.managementPractices.soilManagement.organicMatterContent = undefined;
    const soil = transformEnhancedAssessmentToBackend(fx).management_practices!.soil_management;
    expect(soil.soil_ph).toBeUndefined();
    expect(soil.organic_matter_pct).toBeUndefined();
  });

  it('sends lime rows with crop ids', () => {
    const fx = farmRequestFixture();
    fx.managementPractices.soilManagement.limeApplications = [
      { material: 'dolomite', rateTPerHaPerYear: 0.5, cropIds: ['crop_cowpea_001'] },
    ];
    expect(transformEnhancedAssessmentToBackend(fx).management_practices!.soil_management.lime_applications)
      .toEqual([{ material: 'dolomite', rate_t_per_ha_per_year: 0.5, crop_ids: ['crop_cowpea_001'] }]);
  });

  it('sends land-use change only with explicit years and never null establishment keys', () => {
    const fx = farmRequestFixture();
    fx.cropProductions[0].landUseChange = { previousLandUse: 'forest', yearsSinceConversion: 7 };
    // Establishment is perennial-only: use a tree crop (maize would drop it).
    Object.assign(fx.cropProductions[0], { cropName: 'Cocoa', variety: 'Amazonia', category: 'Other' });
    fx.cropProductions[0].establishment = { productiveYears: 25 };
    const food = transformEnhancedAssessmentToBackend(fx).foods[0];
    expect(food.land_use_change).toEqual({ previous_land_use: 'forest', years_since_conversion: 7 });
    expect(food.establishment).toEqual({ productive_years: 25 });
    fx.cropProductions[0].landUseChange = { previousLandUse: 'forest' };
    fx.cropProductions[0].establishment = {};
    const blank = transformEnhancedAssessmentToBackend(fx).foods[0];
    expect(blank.land_use_change).toBeUndefined();
    expect(blank.establishment).toBeUndefined();
  });

  it('sends the cold-store refrigerant only when Cold Storage is ticked', () => {
    const fx = farmRequestFixture();
    fx.equipmentEnergy.infrastructure.refrigerant = 'R-134a';
    fx.equipmentEnergy.infrastructure.refrigerantChargeKg = 4;
    expect(transformEnhancedAssessmentToBackend(fx).equipment_energy!.storage).toEqual({
      facilities: ['Traditional Granary'], capacity_tonnes: 5, refrigerant: undefined, refrigerant_charge_kg: undefined,
    });
    fx.equipmentEnergy.infrastructure.storageFacilities = [StorageFacilityType.COLD_STORAGE];
    expect(transformEnhancedAssessmentToBackend(fx).equipment_energy!.storage).toMatchObject({
      facilities: ['Cold Storage'], refrigerant: 'R-134a', refrigerant_charge_kg: 4,
    });
  });

  it('maps market transport modes to the engine keywords (pickup is not a lorry)', () => {
    expect(pickMarketMode(['Pickup truck', 'Motorcycle'])).toBe('Pickup');
    expect(pickMarketMode(['Large truck', 'Pickup truck'])).toBe('Large truck');
    expect(pickMarketMode(['On foot/Head carrying'])).toBe('On foot');
    expect(pickMarketMode([])).toBeUndefined();
  });

  it('sends the Nigeria rice example with two seasons and a flooded water regime', () => {
    const food = transformEnhancedAssessmentToBackend(NIGERIA_EXAMPLE as unknown as EnhancedAssessmentRequest).foods[0];
    expect(food).toMatchObject({
      crops_per_year: 2,
      growing_period_days: 120,
      water_regime: 'irrigated_continuously_flooded',
      preseason_water_status: 'non_flooded_lt_180d',
      planting_months: [1, 2, 6, 7],
      harvest_months: [4, 5, 10, 11],
    });
  });

  it('sends removed_residue_use only when some residue is removed', () => {
    const fx = farmRequestFixture();
    fx.cropProductions[0].residueManagement = { fractionRemoved: 0.5, fractionBurnt: 0, removedResidueUse: 'fed_to_own_livestock' };
    expect(transformEnhancedAssessmentToBackend(fx).foods[0].residue_management).toEqual({
      fraction_removed: 0.5, fraction_burnt: 0, removed_residue_use: 'fed_to_own_livestock',
    });
    fx.cropProductions[0].residueManagement = { fractionRemoved: 0, fractionBurnt: 0.2, removedResidueUse: 'sold' };
    expect(transformEnhancedAssessmentToBackend(fx).foods[0].residue_management?.removed_residue_use).toBeUndefined();
  });

  it('never sends establishment for annual crops (mirror of engine known_annual)', () => {
    const fx = farmRequestFixture();
    fx.cropProductions[0].establishment = { immatureYears: 1, productiveYears: 3 };
    expect(transformEnhancedAssessmentToBackend(fx).foods[0].establishment).toBeUndefined();
    expect(isKnownAnnualCrop({ cropName: 'Maize', category: 'Cereals' })).toBe(true);
    expect(isKnownAnnualCrop({ cropName: 'Cassava', category: 'Roots' })).toBe(true);
    expect(isKnownAnnualCrop({ cropName: 'Mystery crop', category: 'Vegetables' })).toBe(true);
    expect(isKnownAnnualCrop({ cropName: 'Cocoa', category: 'Other' })).toBe(false);
    expect(isKnownAnnualCrop({ cropName: 'Palm', category: 'Oils' })).toBe(false);
    expect(isKnownAnnualCrop({ cropName: 'African locust bean', category: 'Legumes' })).toBe(false);
    expect(isKnownAnnualCrop({ cropName: 'Shea', category: 'Nuts' })).toBe(false);
    expect(isKnownAnnualCrop({ cropName: 'Orange-fleshed sweet potato', category: 'Roots' })).toBe(true);
  });

  it('never sends a rice water regime for a non-rice crop', () => {
    const fx = farmRequestFixture();
    fx.cropProductions[0].waterRegime = 'upland';
    expect(transformEnhancedAssessmentToBackend(fx).foods[0].water_regime).toBeUndefined();
  });
});

describe('farm wizard snapshot restore', () => {
  it('fills fields added since a snapshot was saved and moves the legacy method onto rows', () => {
    const legacy = JSON.parse(JSON.stringify(GHANA_EXAMPLE));
    legacy.managementPractices.fertilization.fertilizerApplications.forEach((a: Record<string, unknown>) => {
      delete a.applicationMethod; delete a.cropIds;
    });
    legacy.managementPractices.fertilization.applicationMethod = ApplicationMethod.BROADCAST;
    delete legacy.managementPractices.soilManagement.limeApplications;
    delete legacy.pestManagement.pesticides[0].cropIds;
    legacy.assessmentParameters = { functionalUnit: 'Per kg of product', systemBoundary: 'Cradle-to-gate (production only)', assessmentPeriod: 1, includeUncertaintyAnalysis: true, includeSensitivityAnalysis: true, benchmarkComparison: true };
    const restored = restoreFormSnapshot(legacy);
    const fert = restored.managementPractices!.fertilization!.fertilizerApplications!;
    expect(fert.map((a) => [a!.applicationMethod, a!.cropIds])).toEqual([
      [ApplicationMethod.BROADCAST, []], [ApplicationMethod.BROADCAST, []],
    ]);
    expect(restored.managementPractices!.soilManagement!.limeApplications).toEqual([]);
    const parsed = enhancedAssessmentSchema.safeParse(restored);
    expect(parsed.success, JSON.stringify(parsed.success ? null : parsed.error.issues)).toBe(true);
  });

  it('round-trips the new fields through the parsed form (form_snapshot)', () => {
    const parsed = enhancedAssessmentSchema.parse(NIGERIA_EXAMPLE_WITH_WATER());
    const again = enhancedAssessmentSchema.parse(restoreFormSnapshot(JSON.parse(JSON.stringify(parsed))));
    expect(again.cropProductions[0]).toMatchObject({
      waterRegime: 'irrigated_continuously_flooded',
      seasonality: { cropsPerYear: 2, growingPeriod: 120 },
      rotationSequence: ['Rice'],
    });
    expect(again.managementPractices.fertilization.fertilizerApplications[0].applicationMethod).toBe(ApplicationMethod.BROADCAST);
  });
});

describe('deriveSeasonalFactor', () => {
  it('follows each country rainy season', () => {
    expect(deriveSeasonalFactor('Ghana', [5])).toBe('WetSeason');
    expect(deriveSeasonalFactor('Ghana', [12, 1])).toBe('DrySeason');
    expect(deriveSeasonalFactor('South Africa', [11])).toBe('WetSeason');
    expect(deriveSeasonalFactor('South Africa', [6])).toBe('DrySeason');
    expect(deriveSeasonalFactor('Burkina Faso', ['7', '12'])).toBe('YearRound');
    expect(deriveSeasonalFactor('Canada', [])).toBe('WetSeason');
  });
});

describe('farm wizard validation', () => {
  it('rejects the blank starting form (no demo prefill can be submitted)', () => {
    expect(enhancedAssessmentSchema.safeParse(blankFarmAssessmentForm()).success).toBe(false);
  });

  it('accepts the Ghana example farm', () => {
    const r = enhancedAssessmentSchema.safeParse(GHANA_EXAMPLE);
    expect(r.success, JSON.stringify(r.success ? null : r.error.issues)).toBe(true);
  });

  const mgmt = () => ({
    soilManagement: {
      soilType: SoilType.LOAM,
      soilTestingFrequency: TestingFrequency.NEVER ?? Object.values(TestingFrequency)[0],
      conservationPractices: [],
      coverCrops: [],
      compostUse: { usesCompost: false, compostsource: CompostSource.NONE, applicationTiming: 'Before planting' },
    },
    fertilization: {
      usesFertilizers: true,
      fertilizerApplications: [{ fertilizerType: FertilizerType.UREA, applicationRate: 100, applicationsPerSeason: 1 }],
      soilTestBased: false,
      followsNutrientPlan: false,
    },
    waterManagement: { waterSource: [WaterSource.RAINFALL], irrigationSystem: '', drainageSystem: false, waterConservationPractices: [] },
  });

  it('refuses zero-rate and zero-application fertiliser rows', () => {
    const m = mgmt();
    m.fertilization.fertilizerApplications[0].applicationRate = 0;
    expect(managementPracticesSchema.safeParse(m).success).toBe(false);
    const m2 = mgmt();
    m2.fertilization.fertilizerApplications[0].applicationsPerSeason = 0;
    expect(managementPracticesSchema.safeParse(m2).success).toBe(false);
    expect(managementPracticesSchema.safeParse(mgmt()).success).toBe(true);
  });

  it('requires the fertiliser flag and the rows to agree', () => {
    const noRows = mgmt();
    noRows.fertilization.fertilizerApplications = [];
    expect(managementPracticesSchema.safeParse(noRows).success).toBe(false);
    const flagOff = mgmt();
    flagOff.fertilization.usesFertilizers = false;
    expect(managementPracticesSchema.safeParse(flagOff).success).toBe(false);
  });

  it('requires a compost rate and source when compost is used', () => {
    const m = mgmt();
    m.soilManagement.compostUse = { usesCompost: true, compostsource: CompostSource.FARM_MADE, applicationTiming: 'Before planting' };
    expect(managementPracticesSchema.safeParse(m).success).toBe(false);
  });

  it('requires the irrigation volume when an irrigation system is selected', () => {
    const m = mgmt();
    m.waterManagement.irrigationSystem = IrrigationSystem.DRIP_IRRIGATION;
    expect(managementPracticesSchema.safeParse(m).success).toBe(false);
    const withWater = { ...m, waterManagement: { ...m.waterManagement, irrigationWaterM3: 1200 } };
    expect(managementPracticesSchema.safeParse(withWater).success).toBe(true);
  });

  it('refuses "chemical pesticides only" with no pesticide rows', () => {
    const pest = {
      managementApproach: PestManagementApproach.CHEMICAL_ONLY,
      pesticides: [],
      pestMonitoringFrequency: Object.values(MonitoringFrequency)[0],
    };
    expect(pestManagementSchema.safeParse(pest).success).toBe(false);
    expect(pestManagementSchema.safeParse({ ...pest, managementApproach: PestManagementApproach.INTEGRATED_IPM }).success).toBe(true);
  });

  it('requires whole years since conversion once a previous land use is chosen', () => {
    const g = () => JSON.parse(JSON.stringify(GHANA_EXAMPLE));
    const blankYears = g();
    blankYears.cropProductions[0].landUseChange = { previousLandUse: 'forest', yearsSinceConversion: '' };
    expect(enhancedAssessmentSchema.safeParse(blankYears).success).toBe(false);
    const fractional = g();
    fractional.cropProductions[0].landUseChange = { previousLandUse: 'forest', yearsSinceConversion: 2.5 };
    expect(enhancedAssessmentSchema.safeParse(fractional).success).toBe(false);
    const ok = g();
    ok.cropProductions[0].landUseChange = { previousLandUse: 'forest', yearsSinceConversion: '6' };
    expect(enhancedAssessmentSchema.safeParse(ok).success).toBe(true);
    const none = g();
    none.cropProductions[0].landUseChange = { previousLandUse: '', yearsSinceConversion: '' };
    expect(enhancedAssessmentSchema.safeParse(none).success).toBe(true);
  });

  it('refuses zero productive years for a perennial and needs no yield per hectare', () => {
    const g = JSON.parse(JSON.stringify(GHANA_EXAMPLE));
    g.cropProductions[0].establishment = { productiveYears: 0 };
    expect(enhancedAssessmentSchema.safeParse(g).success).toBe(false);
    const noYield = JSON.parse(JSON.stringify(GHANA_EXAMPLE));
    delete noYield.cropProductions[0].averageYieldPerHectare;
    delete noYield.cropProductions[0].postHarvestLosses;
    const r = enhancedAssessmentSchema.safeParse(noYield);
    expect(r.success).toBe(true);
    expect(r.success && r.data.cropProductions[0].postHarvestLosses).toBeUndefined();
  });

  it('refuses a fertiliser row of type None', () => {
    const m = mgmt();
    m.fertilization.fertilizerApplications[0].fertilizerType = FertilizerType.NONE;
    expect(managementPracticesSchema.safeParse(m).success).toBe(false);
  });

  it('allows a pesticide row with 0 applications (not applied) but not a missing count', () => {
    const pest = (n: unknown) => ({
      managementApproach: PestManagementApproach.INTEGRATED_IPM,
      pestMonitoringFrequency: Object.values(MonitoringFrequency)[0],
      pesticides: [{ pesticideType: 'Herbicide', activeIngredient: 'Glyphosate', applicationRate: 2, applicationsPerSeason: n, targetPests: [] }],
    });
    expect(pestManagementSchema.safeParse(pest(0)).success).toBe(true);
    expect(pestManagementSchema.safeParse(pest(undefined)).success).toBe(false);
  });

  it('refuses rows linked to a crop that is not in the crop list', () => {
    const g = JSON.parse(JSON.stringify(GHANA_EXAMPLE));
    g.managementPractices.fertilization.fertilizerApplications[0].cropIds = ['crop_gone'];
    expect(enhancedAssessmentSchema.safeParse(g).success).toBe(false);
  });

  it('makes storage capacity optional and needs a gas for a cold-store charge', () => {
    const infra = { ...GHANA_EXAMPLE.equipmentEnergy.infrastructure, storageCapacity: '' };
    const base = { equipment: [], energySources: [], fuelConsumption: [], infrastructure: infra };
    expect(equipmentEnergySchema.safeParse(base).success).toBe(true);
    const cold = { ...base, infrastructure: { ...infra, storageFacilities: [StorageFacilityType.COLD_STORAGE], refrigerantChargeKg: 3 } };
    expect(equipmentEnergySchema.safeParse(cold).success).toBe(false);
    expect(equipmentEnergySchema.safeParse({ ...cold, infrastructure: { ...cold.infrastructure, refrigerant: 'R-404A' } }).success).toBe(true);
  });

  it('refuses zero-hour equipment and zero-consumption energy or fuel rows', () => {
    const infra = GHANA_EXAMPLE.equipmentEnergy.infrastructure;
    const base = { equipment: [], energySources: [], fuelConsumption: [], infrastructure: infra };
    expect(equipmentEnergySchema.safeParse(base).success).toBe(true);
    expect(equipmentEnergySchema.safeParse({
      ...base, equipment: [{ equipmentType: 'Sprayer', powerSource: 'Petrol engine', age: 1, hoursPerYear: 0 }],
    }).success).toBe(false);
    expect(equipmentEnergySchema.safeParse({
      ...base, energySources: [{ energyType: 'Grid Electricity', monthlyConsumption: 0, primaryUse: 'Lighting' }],
    }).success).toBe(false);
    expect(equipmentEnergySchema.safeParse({
      ...base, fuelConsumption: [{ fuelType: FuelType.DIESEL, monthlyConsumption: 0, unit: 'L', primaryUse: 'Pump' }],
    }).success).toBe(false);
    const ok = equipmentEnergySchema.safeParse({
      ...base, fuelConsumption: [{ fuelType: FuelType.LPG, monthlyConsumption: 6, unit: 'kg', primaryUse: 'Drying' }],
    });
    expect(ok.success).toBe(true);
  });
});

describe('processing payload contract (buildProcessingPayload)', () => {
  const form = defaultProcessingForm();
  form.facility.facilityName = 'Kumasi Palm Mill';
  form.facility.facilityType = 'PalmOilMill';
  form.facility.country = 'Ghana';
  form.products[0].name = 'Crude palm oil';
  form.products[0].productType = 'PalmOil';
  form.products[0].annualProduction = 900;
  form.products[0].packaging = { material: 'Metal', packageSize: 25, weightPerUnit: 1.2 };
  form.utilities.elecKwhMonth = 4000;
  form.utilities.fuelStreams = [{ fuelType: 'Palm kernel shell', amountMonth: 30000, unit: 'kg' }];
  form.utilities.transportKm = 0;
  const payload = buildProcessingPayload(form, COUNTRY_TO_REGION, { facilityId: null, formSnapshot: form });

  it('emits exactly the ProcessingAssessmentRequest keys the API declares', () => {
    const paths = keyPaths(payload).filter((p) => !p.startsWith('form_snapshot'));
    expect(paths).toEqual([
      'allocation_basis',
      'country',
      'facility_profile.company_name',
      'facility_profile.facility_name',
      'facility_profile.facility_type',
      'facility_profile.location_type',
      'facility_profile.operational_days_per_year',
      'facility_profile.operational_hours_per_day',
      'facility_profile.processing_capacity',
      'processed_products[].annual_production',
      'processed_products[].id',
      'processed_products[].name',
      'processed_products[].packaging.package_size',
      'processed_products[].packaging.packaging_material',
      'processed_products[].packaging.packaging_weight_per_unit',
      'processed_products[].product_type',
      'processed_products[].raw_material_inputs',
      'processing_operations.energy_management.fuel_streams[].fuel_type',
      'processing_operations.energy_management.fuel_streams[].monthly_consumption',
      'processing_operations.energy_management.fuel_streams[].unit',
      'processing_operations.energy_management.monthly_electricity_consumption',
      'processing_operations.energy_management.primary_energy_source',
      'processing_operations.energy_management.renewable_energy_percentage',
      'processing_operations.raw_material_sourcing.local_sourcing_percentage',
      'processing_operations.raw_material_sourcing.transport_mode',
      'processing_operations.refrigerant_management',
      'processing_operations.waste_management.byproduct_utilization',
      'processing_operations.waste_management.organic_waste_percentage',
      'processing_operations.waste_management.waste_disposal_method',
      'processing_operations.water_management.wastewater_treatment',
      'processing_operations.water_management.water_source[]',
      'processing_operations.water_management.water_treatment',
      'region',
      'title',
    ]);
  });

  it('sends measured effluent only for untreated wastewater', () => {
    const f = defaultProcessingForm();
    f.facility.facilityName = 'Plant';
    f.utilities.effluentCodMgPerL = 1200;
    f.utilities.effluentTotalPMgPerL = 8;
    const wm = (form: typeof f) =>
      (buildProcessingPayload(form, COUNTRY_TO_REGION).processing_operations as { water_management: Record<string, unknown> }).water_management;
    expect(wm(f).effluent_cod_mg_per_l).toBeUndefined();
    f.utilities.wastewaterTreatment = 'None';
    expect(wm(f)).toMatchObject({ effluent_cod_mg_per_l: 1200, effluent_total_p_mg_per_l: 8 });
    expect(wm(f).effluent_bod5_mg_per_l).toBeUndefined();
    expect(utilitiesSchema.safeParse({ ...f.utilities, elecKwhMonth: 1, effluentCodMgPerL: -1 }).success).toBe(false);
  });

  it('treats a 0 km transport distance as "use the default" and carries the form snapshot', () => {
    const ops = payload.processing_operations as { raw_material_sourcing: Record<string, unknown> };
    expect(ops.raw_material_sourcing.average_transport_distance).toBeUndefined();
    expect(payload.form_snapshot).toBe(form);
  });
});

describe('processing wizard validation', () => {
  it('needs whole operating days within a year and at most 24 hours a day', () => {
    const f = { ...defaultProcessingForm().facility, facilityName: 'Mill A', country: 'Ghana' as const };
    expect(facilitySchema.safeParse({ ...f, daysPerYear: 250.5 }).success).toBe(false);
    expect(facilitySchema.safeParse({ ...f, daysPerYear: 400 }).success).toBe(false);
    expect(facilitySchema.safeParse({ ...f, hoursPerDay: 25 }).success).toBe(false);
    expect(facilitySchema.safeParse({ ...f, daysPerYear: '250' }).success).toBe(true);
  });

  it('refuses a fuel line without an amount', () => {
    expect(fuelStreamSchema.safeParse({ fuelType: 'Diesel', amountMonth: '', unit: 'L' }).success).toBe(false);
    expect(fuelStreamSchema.safeParse({ fuelType: 'Diesel', amountMonth: 0, unit: 'L' }).success).toBe(false);
    expect(fuelStreamSchema.safeParse({ fuelType: 'Diesel', amountMonth: '12', unit: 'L' }).success).toBe(true);
  });

  it('requires at least one energy input', () => {
    const u = defaultProcessingForm().utilities;
    expect(utilitiesSchema.safeParse(u).success).toBe(false);
    expect(utilitiesSchema.safeParse({ ...u, elecKwhMonth: 100 }).success).toBe(true);
    expect(utilitiesSchema.safeParse({ ...u, fuelStreams: [{ fuelType: 'Firewood', amountMonth: 500, unit: 'kg' }] }).success).toBe(true);
  });

  it('requires a raw material name and amount together, and explicit packaging', () => {
    const p = { name: 'Flour', productType: 'FlourMaize', annualProduction: 10, packaging: { material: 'PaperBag', packageSize: 25, weightPerUnit: 0.2 } };
    expect(productSchema.safeParse(p).success).toBe(true);
    expect(productSchema.safeParse({ ...p, rawMaterial: 'Maize grain' }).success).toBe(false);
    expect(productSchema.safeParse({ ...p, rawKgPerTonne: 1050 }).success).toBe(false);
    expect(productSchema.safeParse({ ...p, rawMaterial: 'Maize grain', rawKgPerTonne: 1050 }).success).toBe(true);
    expect(productSchema.safeParse({ ...p, packaging: { material: 'PaperBag' } }).success).toBe(false);
  });

  it('rejects the untouched default form', () => {
    expect(processingAssessmentSchema.safeParse(defaultProcessingForm()).success).toBe(false);
  });

  it('requires a named refrigerant gas when a leak amount is entered', () => {
    const u = { ...defaultProcessingForm().utilities, elecKwhMonth: 100 };
    expect(utilitiesSchema.safeParse({ ...u, refrigerantKg: 5 }).success).toBe(false);
    expect(utilitiesSchema.safeParse({ ...u, refrigerantKg: 5, refrigerantType: 'R-134a' }).success).toBe(true);
    expect(utilitiesSchema.safeParse({ ...u, refrigerantType: 'Freon' }).success).toBe(false);
    expect(REFRIGERANT_OPTIONS).toHaveLength(31);
  });

  it('mirrors the API completeness gate: no default ratio means a raw material is required', () => {
    const complete = () => {
      const f = defaultProcessingForm();
      f.facility.facilityName = 'Plant';
      f.facility.facilityType = 'General';
      f.utilities.elecKwhMonth = 100;
      f.products[0].name = 'Juice';
      f.products[0].productType = 'Other';
      f.products[0].annualProduction = 10;
      f.products[0].packaging = { material: 'Glass', packageSize: 1, weightPerUnit: 0.3 };
      return f;
    };
    expect(processingAssessmentSchema.safeParse(complete()).success).toBe(false);
    expect(missingRawMaterialIssues(complete().products, 'General')).toHaveLength(1);
    const withRaw = complete();
    withRaw.products[0].rawMaterial = 'Oranges';
    withRaw.products[0].rawKgPerTonne = 2000;
    expect(processingAssessmentSchema.safeParse(withRaw).success).toBe(true);
    const palm = complete();
    palm.products[0].productType = 'PalmOil';
    expect(processingAssessmentSchema.safeParse(palm).success).toBe(true);
    const otherAtPalmMill = complete();
    otherAtPalmMill.facility.facilityType = 'PalmOilMill';
    expect(processingAssessmentSchema.safeParse(otherAtPalmMill).success).toBe(true);
    expect(hasDefaultConversionRatio('FlourMaize', 'General')).toBe(true);
    expect(hasDefaultConversionRatio('BakedGoods', 'Bakery')).toBe(false);
  });

  it('sends packaging only for packaged products and omits it for bulk', () => {
    const f = defaultProcessingForm();
    f.facility.facilityName = 'Plant';
    f.products[0] = { ...f.products[0], name: 'Meal', productType: 'FlourMaize', annualProduction: 10, packaged: false };
    expect(productSchema.safeParse(f.products[0]).success).toBe(true);
    const payload = buildProcessingPayload(f, COUNTRY_TO_REGION);
    const product = (payload.processed_products as Array<Record<string, unknown>>)[0];
    expect('packaging' in product).toBe(false);
    f.products[0] = { ...f.products[0], packaged: true, packaging: { material: 'Jute', packageSize: 50, weightPerUnit: 0.2 } };
    const packed = (buildProcessingPayload(f, COUNTRY_TO_REGION).processed_products as Array<Record<string, unknown>>)[0];
    expect(packed.packaging).toEqual({ packaging_material: 'Jute', package_size: 50, packaging_weight_per_unit: 0.2 });
  });

  it('emits only fuel units, water sources and refrigerants the API enumerates', () => {
    expect([...FUEL_UNITS].every((u) => ['L', 'kg', 'm3', 'MJ'].includes(u))).toBe(true);
    expect([...WATER_SOURCES]).toEqual(['Municipal', 'Borehole', 'Well', 'River', 'Dam/Reservoir', 'Rainwater']);
    const f = defaultProcessingForm();
    f.facility.facilityName = 'Plant';
    f.utilities.fuelStreams = [{ fuelType: 'Biogas', amountMonth: 10, unit: 'm3' }];
    f.utilities.waterSource = 'Dam/Reservoir';
    f.utilities.refrigerantType = 'R-404A';
    f.utilities.refrigerantKg = 2;
    const ops = buildProcessingPayload(f, COUNTRY_TO_REGION).processing_operations as {
      energy_management: { fuel_streams: Array<{ unit: string }> };
      water_management: { water_source: string[] };
      refrigerant_management: { refrigerant_type?: string };
    };
    expect(ops.energy_management.fuel_streams[0].unit).toBe('m3');
    expect(ops.water_management.water_source).toEqual(['Dam/Reservoir']);
    expect(ops.refrigerant_management.refrigerant_type).toBe('R-404A');
    f.utilities.refrigerantType = 'None';
    const none = buildProcessingPayload(f, COUNTRY_TO_REGION).processing_operations as { refrigerant_management: { refrigerant_type?: string } };
    expect(none.refrigerant_management.refrigerant_type).toBeUndefined();
  });
});
