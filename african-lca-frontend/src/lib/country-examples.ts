/**
 * country-examples.ts: per-country default farm data, drawn from the validated engine
 * case studies (engine/case_studies/*.json). Selecting a country in the wizard loads that
 * country's example so the defaults reflect a real farm for that region.
 *
 * COUNTRY_TO_REGION also carries the backend contract: the API only accepts the countries
 * Ghana / Nigeria / Global, and the engine region is GH / NG / CA. Canada is therefore sent
 * as country "Global" + region "CA" (the engine has no "Canada" country, only the CA region).
 */
import {
  FarmType, FarmingSystem, CompostSource, ProductionSystem, CroppingPattern, SeasonType,
  SoilType, TestingFrequency, SoilConservationPractice, FertilizerType, WaterSource,
  IrrigationSystem, PestManagementApproach, PesticideType, IPMPractice, MonitoringFrequency,
  EquipmentType, PowerSource, EnergyType, FuelType, StorageFacilityType, RoadAccessType, TransportMode,
  Currency, ApplicationMethod, TimingStrategy,
  type RiceWaterRegime, type RicePreseasonWaterStatus, type LimeApplication,
} from '@/types/enhanced-assessment';
import { NEW_COUNTRY_TO_REGION } from './regions';

const clone = <T,>(o: T): T => JSON.parse(JSON.stringify(o));

// ---- Ghana: smallholder rainfed maize + cowpea intercrop (Northern Ghana) --------------
export const GHANA_EXAMPLE = {
  farmProfile: {
    farmerName: 'Abubakar Yakubu',
    farmName: 'Tamale Agro Ventures',
    country: 'Ghana',
    region: 'Northern',
    totalFarmSize: 4.2,
    farmingExperience: 14,
    farmType: FarmType.SMALLHOLDER,
    primaryFarmingSystem: FarmingSystem.SEMI_COMMERCIAL,
    certifications: [],
    participatesInPrograms: ['Climate Smart Agriculture', 'Farmer Field School'],
  },
  cropProductions: [
    {
      cropId: 'crop_maize_001', cropName: 'Maize', localName: 'Aburo', category: 'Cereals',
      variety: 'Obatanpa', areaAllocated: 2.5, annualProduction: 3500,
      productionSystem: ProductionSystem.RAINFED, croppingPattern: CroppingPattern.INTERCROPPING,
      seasonality: { plantingMonths: [4, 5], harvestingMonths: [8, 9], growingPeriod: 120, cropsPerYear: 1, season: [SeasonType.WET_SEASON], seasonOverride: '' as SeasonType | '' },
      isIntercropped: true, intercroppingPartners: ['Cowpea'], intercroppingRatio: {},
      // Previous crops on this field, most recent first.
      rotationSequence: ['Groundnuts', 'Cowpea'], rotationDuration: 2,
      averageYieldPerHectare: 1400, postHarvestLosses: 15,
      waterRegime: '' as RiceWaterRegime | '', preseasonWaterStatus: '' as RicePreseasonWaterStatus | '',
    },
    {
      cropId: 'crop_cowpea_001', cropName: 'Cowpea', localName: 'Songotra', category: 'Legumes',
      variety: 'Songotra', areaAllocated: 1.7, annualProduction: 850,
      productionSystem: ProductionSystem.RAINFED, croppingPattern: CroppingPattern.INTERCROPPING,
      seasonality: { plantingMonths: [4, 5], harvestingMonths: [7, 8], growingPeriod: 90, cropsPerYear: 1, season: [SeasonType.WET_SEASON], seasonOverride: '' as SeasonType | '' },
      isIntercropped: true, intercroppingPartners: ['Maize'], intercroppingRatio: {},
      rotationSequence: ['Maize'], rotationDuration: 2,
      averageYieldPerHectare: 500, postHarvestLosses: 10,
      waterRegime: '' as RiceWaterRegime | '', preseasonWaterStatus: '' as RicePreseasonWaterStatus | '',
    },
  ],
  managementPractices: {
    soilManagement: {
      soilType: SoilType.LATERITIC, soilpH: 5.9 as number | undefined, organicMatterContent: 2.4 as number | undefined,
      soilTestingFrequency: TestingFrequency.EVERY_2_3_YEARS,
      conservationPractices: [SoilConservationPractice.CONTOUR_PLOWING, SoilConservationPractice.MULCHING],
      usesCoverCrops: true,
      coverCrops: ['Mucuna', 'Cowpea'],
      // Not recorded in the case study: blank (SOC change from management not booked).
      practicesAdoptedYearsAgo: undefined as number | undefined,
      limeApplications: [] as LimeApplication[],
      compostUse: { usesCompost: true, compostsource: CompostSource.FARM_MADE, applicationRate: 6, applicationTiming: 'Before planting', cropIds: [] as string[] },
    },
    fertilization: {
      usesFertilizers: true,
      // Both fertilisers go on the maize only (the cowpea is not fertilised).
      fertilizerApplications: [
        { fertilizerType: FertilizerType.NPK_COMPOUND, brandName: 'Yara NPK 15-15-15', npkRatio: '15-15-15', applicationRate: 200, applicationsPerSeason: 1, applicationMethod: ApplicationMethod.BAND_PLACEMENT, cropIds: ['crop_maize_001'], cost: 165, currency: Currency.GHS },
        { fertilizerType: FertilizerType.UREA, brandName: 'Wienco Urea', npkRatio: '46-0-0', applicationRate: 75, applicationsPerSeason: 1, applicationMethod: ApplicationMethod.SIDE_DRESSING, cropIds: ['crop_maize_001'], cost: 95, currency: Currency.GHS },
      ],
      timingStrategy: TimingStrategy.SPLIT_APPLICATION,
      soilTestBased: true, followsNutrientPlan: true,
    },
    waterManagement: { waterSource: [WaterSource.RAINFALL], irrigationSystem: IrrigationSystem.NONE, drainageSystem: true, waterConservationPractices: [] },
  },
  pestManagement: {
    primaryPests: ['Fall armyworm', 'Stemborer'], primaryDiseases: ['Maize leaf blight'],
    managementApproach: PestManagementApproach.INTEGRATED_IPM,
    pesticides: [
      { pesticideType: PesticideType.INSECTICIDE, activeIngredient: 'Lambda-cyhalothrin', brandName: 'Karate 5EC', applicationRate: 0.25, applicationsPerSeason: 2, cropIds: ['crop_maize_001'], targetPests: ['Fall armyworm'], cost: 38, currency: Currency.GHS, safetyPrecautions: [] },
    ],
    usesIPM: true, ipmPractices: [IPMPractice.CROP_ROTATION, IPMPractice.COMPANION_PLANTING, IPMPractice.RESISTANT_VARIETIES],
    biologicalControls: ['Neem extract'], pestMonitoringFrequency: MonitoringFrequency.WEEKLY, usesEconomicThresholds: true,
  },
  equipmentEnergy: {
    equipment: [
      { equipmentType: EquipmentType.ANIMAL_TRACTION, powerSource: PowerSource.MANUAL, age: 5, hoursPerYear: 200, fuelEfficiency: 0 },
      { equipmentType: EquipmentType.SPRAYER, powerSource: PowerSource.MANUAL, age: 2, hoursPerYear: 40, fuelEfficiency: 0 },
    ],
    energySources: [] as Array<{ energyType: EnergyType; monthlyConsumption: number; primaryUse: string; cost: number; currency: Currency }>,
    fuelConsumption: [
      { fuelType: FuelType.DIESEL, monthlyConsumption: 45, unit: 'L' as const, primaryUse: 'Water pumping and threshing', cost: 120 },
    ],
    infrastructure: {
      // tonnes (granary for the season's grain); report-only.
      storageCapacity: 5 as number | undefined, storageFacilities: [StorageFacilityType.TRADITIONAL_GRANARY],
      refrigerant: undefined as string | undefined, refrigerantChargeKg: undefined as number | undefined,
      transportAccess: { roadAccess: RoadAccessType.GRAVEL_ROAD, distanceToMarket: 22, transportMode: [TransportMode.MOTORCYCLE], transportCost: 30 },
    },
  },
  assessmentParameters: { includeUncertaintyAnalysis: true },
};

// ---- Nigeria: commercial irrigated rice (Kano) -----------------------------------------
export const NIGERIA_EXAMPLE = clone(GHANA_EXAMPLE);
NIGERIA_EXAMPLE.farmProfile = {
  farmerName: 'Fatima Bello', farmName: 'Kano Rice Estates', country: 'Nigeria', region: 'Kano',
  totalFarmSize: 12, farmingExperience: 16, farmType: FarmType.COMMERCIAL,
  primaryFarmingSystem: FarmingSystem.COMMERCIAL, certifications: [], participatesInPrograms: [],
};
NIGERIA_EXAMPLE.cropProductions = [
  {
    cropId: 'crop_rice_001', cropName: 'Rice', localName: 'Shinkafa', category: 'Cereals',
    variety: 'FARO 44', areaAllocated: 12, annualProduction: 50400,
    productionSystem: ProductionSystem.IRRIGATED, croppingPattern: CroppingPattern.MONOCULTURE,
    // Two irrigated seasons a year (dry season Jan-May, wet season Jun-Nov); 50.4 t is the annual total.
    seasonality: { plantingMonths: [1, 2, 6, 7], harvestingMonths: [4, 5, 10, 11], growingPeriod: 120, cropsPerYear: 2, season: [SeasonType.YEAR_ROUND], seasonOverride: '' as SeasonType | '' },
    isIntercropped: false, intercroppingPartners: [], intercroppingRatio: {},
    rotationSequence: ['Rice'], rotationDuration: 1, averageYieldPerHectare: 4200, postHarvestLosses: 10,
    waterRegime: 'irrigated_continuously_flooded' as RiceWaterRegime | '',
    preseasonWaterStatus: 'non_flooded_lt_180d' as RicePreseasonWaterStatus | '',
  },
];
NIGERIA_EXAMPLE.managementPractices.soilManagement.soilType = SoilType.CLAY;
NIGERIA_EXAMPLE.managementPractices.soilManagement.usesCoverCrops = false;
NIGERIA_EXAMPLE.managementPractices.soilManagement.coverCrops = [];
NIGERIA_EXAMPLE.managementPractices.soilManagement.compostUse = { usesCompost: false, compostsource: CompostSource.NONE, applicationRate: 0, applicationTiming: '', cropIds: [] };
NIGERIA_EXAMPLE.managementPractices.fertilization.fertilizerApplications = [
  { fertilizerType: FertilizerType.NPK_COMPOUND, brandName: 'Notore NPK 15-15-15', npkRatio: '15-15-15', applicationRate: 200, applicationsPerSeason: 1, applicationMethod: ApplicationMethod.BROADCAST, cropIds: [], cost: 60000, currency: Currency.NGN },
  { fertilizerType: FertilizerType.UREA, brandName: 'Indorama Urea', npkRatio: '46-0-0', applicationRate: 50, applicationsPerSeason: 2, applicationMethod: ApplicationMethod.BROADCAST, cropIds: [], cost: 40000, currency: Currency.NGN },
];
NIGERIA_EXAMPLE.managementPractices.waterManagement = { waterSource: [WaterSource.BOREHOLE, WaterSource.DAM_RESERVOIR], irrigationSystem: IrrigationSystem.SPRINKLER, drainageSystem: true, waterConservationPractices: [] };
NIGERIA_EXAMPLE.pestManagement.primaryPests = ['Stem borer', 'African rice gall midge'];
NIGERIA_EXAMPLE.pestManagement.primaryDiseases = ['Rice blast'];
NIGERIA_EXAMPLE.pestManagement.pesticides = [
  { pesticideType: PesticideType.HERBICIDE, activeIngredient: 'Glyphosate', brandName: 'Roundup', applicationRate: 3.0, applicationsPerSeason: 1, cropIds: [], targetPests: ['Weeds'], cost: 25000, currency: Currency.NGN, safetyPrecautions: [] },
  { pesticideType: PesticideType.INSECTICIDE, activeIngredient: 'Chlorantraniliprole', brandName: 'Coragen', applicationRate: 0.4, applicationsPerSeason: 2, cropIds: [], targetPests: ['Stem borer'], cost: 30000, currency: Currency.NGN, safetyPrecautions: [] },
];
NIGERIA_EXAMPLE.equipmentEnergy.equipment = [
  { equipmentType: EquipmentType.LARGE_TRACTOR, powerSource: PowerSource.DIESEL, age: 6, hoursPerYear: 600, fuelEfficiency: 18 },
  { equipmentType: EquipmentType.SPRAYER, powerSource: PowerSource.PETROL, age: 3, hoursPerYear: 120, fuelEfficiency: 2.5 },
];
NIGERIA_EXAMPLE.equipmentEnergy.energySources = [];
NIGERIA_EXAMPLE.equipmentEnergy.fuelConsumption = [
  { fuelType: FuelType.DIESEL, monthlyConsumption: 220, unit: 'L' as const, primaryUse: 'Irrigation pumping and tractor', cost: 300000 },
];
NIGERIA_EXAMPLE.equipmentEnergy.infrastructure = {
  storageCapacity: 40, storageFacilities: [StorageFacilityType.HERMETIC_STORAGE],
  refrigerant: undefined, refrigerantChargeKg: undefined,
  transportAccess: { roadAccess: RoadAccessType.PAVED_ROAD, distanceToMarket: 12, transportMode: [TransportMode.LARGE_TRUCK], transportCost: 150000 },
};

// ---- Canada: conventional prairie wheat (Saskatchewan) ---------------------------------
export const CANADA_EXAMPLE = clone(GHANA_EXAMPLE);
CANADA_EXAMPLE.farmProfile = {
  farmerName: 'James Mitchell', farmName: 'Prairie Horizon Farms Ltd', country: 'Canada', region: 'Saskatchewan',
  totalFarmSize: 320, farmingExperience: 25, farmType: FarmType.COMMERCIAL,
  primaryFarmingSystem: FarmingSystem.CONVENTIONAL, certifications: [], participatesInPrograms: [],
};
CANADA_EXAMPLE.cropProductions = [
  {
    cropId: 'crop_wheat_001', cropName: 'Wheat', localName: 'Spring wheat', category: 'Cereals',
    variety: 'AAC Brandon', areaAllocated: 320, annualProduction: 1107840,
    productionSystem: ProductionSystem.CONVENTIONAL, croppingPattern: CroppingPattern.MONOCULTURE,
    seasonality: { plantingMonths: [4, 5], harvestingMonths: [8, 9], growingPeriod: 110, cropsPerYear: 1, season: [SeasonType.WET_SEASON], seasonOverride: '' as SeasonType | '' },
    isIntercropped: false, intercroppingPartners: [], intercroppingRatio: {},
    rotationSequence: ['Canola', 'Lentils'], rotationDuration: 3, averageYieldPerHectare: 3462, postHarvestLosses: 3,
    waterRegime: '' as RiceWaterRegime | '', preseasonWaterStatus: '' as RicePreseasonWaterStatus | '',
  },
];
CANADA_EXAMPLE.managementPractices.soilManagement = {
  soilType: SoilType.CLAY_LOAM, soilpH: 6.8, organicMatterContent: 4.0,
  soilTestingFrequency: TestingFrequency.EVERY_2_3_YEARS,
  conservationPractices: [SoilConservationPractice.MINIMUM_TILL],
  usesCoverCrops: false, coverCrops: [], practicesAdoptedYearsAgo: undefined, limeApplications: [],
  compostUse: { usesCompost: false, compostsource: CompostSource.NONE, applicationRate: 0, applicationTiming: '', cropIds: [] },
};
CANADA_EXAMPLE.managementPractices.fertilization.fertilizerApplications = [
  { fertilizerType: FertilizerType.UREA, brandName: 'Nutrien Urea', npkRatio: '46-0-0', applicationRate: 180, applicationsPerSeason: 1, applicationMethod: ApplicationMethod.BAND_PLACEMENT, cropIds: [], cost: 900, currency: Currency.USD },
  { fertilizerType: FertilizerType.DAP, brandName: 'Nutrien DAP', npkRatio: '18-46-0', applicationRate: 80, applicationsPerSeason: 1, applicationMethod: ApplicationMethod.BAND_PLACEMENT, cropIds: [], cost: 750, currency: Currency.USD },
];
CANADA_EXAMPLE.managementPractices.waterManagement = { waterSource: [WaterSource.RAINFALL], irrigationSystem: IrrigationSystem.NONE, drainageSystem: false, waterConservationPractices: [] };
CANADA_EXAMPLE.pestManagement.primaryPests = ['Wheat midge', 'Grasshopper'];
CANADA_EXAMPLE.pestManagement.primaryDiseases = ['Fusarium head blight'];
CANADA_EXAMPLE.pestManagement.pesticides = [
  { pesticideType: PesticideType.HERBICIDE, activeIngredient: 'Glyphosate', brandName: 'Roundup WeatherMax', applicationRate: 1.5, applicationsPerSeason: 1, cropIds: [], targetPests: ['Weeds'], cost: 1200, currency: Currency.USD, safetyPrecautions: [] },
  { pesticideType: PesticideType.FUNGICIDE, activeIngredient: 'Tebuconazole', brandName: 'Folicur', applicationRate: 0.6, applicationsPerSeason: 1, cropIds: [], targetPests: ['Fusarium head blight'], cost: 900, currency: Currency.USD, safetyPrecautions: [] },
];
CANADA_EXAMPLE.pestManagement.managementApproach = PestManagementApproach.CHEMICAL_ONLY;
CANADA_EXAMPLE.pestManagement.usesIPM = false;
CANADA_EXAMPLE.equipmentEnergy.equipment = [
  { equipmentType: EquipmentType.LARGE_TRACTOR, powerSource: PowerSource.DIESEL, age: 5, hoursPerYear: 900, fuelEfficiency: 28 },
  { equipmentType: EquipmentType.COMBINE_HARVESTER, powerSource: PowerSource.DIESEL, age: 7, hoursPerYear: 400, fuelEfficiency: 45 },
];
CANADA_EXAMPLE.equipmentEnergy.fuelConsumption = [
  { fuelType: FuelType.DIESEL, monthlyConsumption: 2200, unit: 'L' as const, primaryUse: 'Tractor and combine operations', cost: 3200 },
];
CANADA_EXAMPLE.equipmentEnergy.energySources = [
  { energyType: EnergyType.GRID_ELECTRICITY, monthlyConsumption: 1200, primaryUse: 'Grain drying and storage', cost: 480, currency: Currency.USD },
];
CANADA_EXAMPLE.equipmentEnergy.infrastructure = {
  storageCapacity: 50, storageFacilities: [StorageFacilityType.HERMETIC_STORAGE],
  refrigerant: undefined, refrigerantChargeKg: undefined,
  transportAccess: { roadAccess: RoadAccessType.PAVED_ROAD, distanceToMarket: 35, transportMode: [TransportMode.LARGE_TRUCK], transportCost: 5000 },
};

export const COUNTRY_EXAMPLES: Record<string, typeof GHANA_EXAMPLE> = {
  Ghana: GHANA_EXAMPLE,
  Nigeria: NIGERIA_EXAMPLE,
  Canada: CANADA_EXAMPLE,
};

/** Demo/default identity strings. Country switches may replace these; custom names are kept. */
export const EXAMPLE_FARMER_NAMES = new Set([
  'Sarah Thompson',       // assessment page initial default
  'Abubakar Yakubu',
  'Fatima Bello',
  'James Mitchell',
]);

export const EXAMPLE_FARM_NAMES = new Set([
  'Thompson Prairie Farm', // assessment page initial default
  'Tamale Agro Ventures',
  'Kano Rice Estates',
  'Prairie Horizon Farms Ltd',
]);

/** True when the field is empty or still a known demo placeholder. */
export function isExampleIdentity(value: string | undefined | null, known: Set<string>): boolean {
  const trimmed = (value || '').trim();
  return !trimmed || known.has(trimmed);
}

// Backend contract: UI country -> the country string the API accepts + the engine region.
export const COUNTRY_TO_REGION: Record<string, { country: string; region: string }> = {
  Ghana: { country: 'Ghana', region: 'GH' },
  Nigeria: { country: 'Nigeria', region: 'NG' },
  Canada: { country: 'Global', region: 'CA' },  // engine has a CA region but no "Canada" country
  ...NEW_COUNTRY_TO_REGION,                       // Senegal/Burkina Faso/South Africa -> Global + SN/BF/ZA
};
