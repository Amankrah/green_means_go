/**
 * Enhanced Assessment Validation Schema & Form Configuration
 * 
 * This implements a step-by-step, farmer-friendly form structure that collects
 * all necessary LCA data while being practical and not overwhelming.
 */

import { z } from 'zod';
import type { DefaultValues } from 'react-hook-form';
import { NEW_REGIONS_BY_COUNTRY, NEW_COMMON_CROPS } from './regions';
import {
  FarmType,
  FarmingSystem,
  CertificationType,
  ProductionSystem,
  CroppingPattern,
  SeasonType,
  SoilType,
  TestingFrequency,
  SoilConservationPractice,
  CompostSource,
  FertilizerType,
  ApplicationMethod,
  TimingStrategy,
  WaterSource,
  IrrigationSystem,
  PestManagementApproach,
  PesticideType,
  IPMPractice,
  MonitoringFrequency,
  EquipmentType,
  PowerSource,
  EnergyType,
  FuelType,
  StorageFacilityType,
  RoadAccessType,
  TransportMode,
  FunctionalUnit,
  SystemBoundary,
  FormStep,
  Currency,
  type RiceWaterRegime,
  type RicePreseasonWaterStatus,
  type RemovedResidueUse,
  isKnownAnnualCrop,
} from '@/types/enhanced-assessment';
import { REFRIGERANTS } from './processing-assessment-schema';

// ======================================================================
// FORM STEP CONFIGURATION - Progressive Disclosure Approach
// ======================================================================

export const FORM_STEPS = [
  {
    id: FormStep.FARM_PROFILE,
    title: "Farm Profile",
    description: "Tell us about your farm and farming background",
    icon: "farm",
    estimatedTime: "3-5 minutes"
  },
  {
    id: FormStep.CROP_DETAILS,
    title: "Crop Production",
    description: "Details about the crops you grow and production systems",
    icon: "crops",
    estimatedTime: "5-8 minutes"
  },
  {
    id: FormStep.MANAGEMENT_PRACTICES,
    title: "Soil & Water Management",
    description: "How you manage soil health, fertilizers, and water",
    icon: "management",
    estimatedTime: "4-6 minutes"
  },
  {
    id: FormStep.PEST_MANAGEMENT,
    title: "Pest & Disease Control",
    description: "Your pest management practices and inputs used",
    icon: "pest",
    estimatedTime: "3-4 minutes"
  },
  {
    id: FormStep.EQUIPMENT_ENERGY,
    title: "Equipment & Energy",
    description: "Farm equipment, energy use, and infrastructure",
    icon: "equipment",
    estimatedTime: "2-4 minutes"
  },
  {
    id: FormStep.REVIEW_SUBMIT,
    title: "Review & Submit",
    description: "Review your inputs and submit for assessment",
    icon: "submit",
    estimatedTime: "2-3 minutes"
  }
];

// ======================================================================
// VALIDATION SCHEMAS - Step by Step
// ======================================================================

// Upper bounds shared with the API models (app/production/models.py). The server rejects
// anything above these, so the wizard must never let them through.
export const MAX_AREA_HA = 1_000_000;
export const MAX_RATE_KG_PER_HA = 5000;
export const MAX_APPLICATIONS_PER_SEASON = 12;
export const MAX_HOURS_PER_YEAR = 8760;
export const MAX_MONTHLY_CONSUMPTION = 1_000_000;

// Engine-fuel units the API accepts for farm fuel rows; natural unit per fuel type.
export const FARM_FUEL_UNITS = ['L', 'kg'] as const;
export type FarmFuelUnit = (typeof FARM_FUEL_UNITS)[number];
export const FARM_FUEL_DEFAULT_UNIT: Record<FuelType, FarmFuelUnit> = {
  [FuelType.DIESEL]: 'L',
  [FuelType.PETROL]: 'L',
  [FuelType.KEROSENE]: 'L',
  [FuelType.LPG]: 'kg',
};

export const RICE_WATER_REGIMES = [
  'upland', 'irrigated_continuously_flooded', 'irrigated_single_drainage',
  'irrigated_multiple_drainage', 'rainfed_regular', 'rainfed_drought_prone', 'deep_water',
] as const satisfies readonly RiceWaterRegime[];
export const RICE_PRESEASON_STATUSES = [
  'non_flooded_lt_180d', 'non_flooded_gt_180d', 'flooded_gt_30d',
] as const satisfies readonly RicePreseasonWaterStatus[];

export const REMOVED_RESIDUE_USES = [
  'sold', 'fed', 'fed_to_own_livestock', 'left_on_farm', 'fuel', 'other',
] as const satisfies readonly RemovedResidueUse[];

export const LIME_MATERIALS = ['limestone', 'dolomite'] as const;
export const MAX_LIME_T_PER_HA = 20;
export const MAX_STORAGE_TONNES = 1_000_000;

// Refrigerants the API accepts (shared with the processing wizard).
export { REFRIGERANTS };

/** Blank / NaN input -> undefined, otherwise a number validated by `inner`. */
function optionalNumber<T extends z.ZodTypeAny>(inner: T) {
  return z.preprocess(
    (val) => val === "" || val === null || val === undefined || Number.isNaN(Number(val)) ? undefined : Number(val),
    inner.optional()
  );
}

const cropIdList = z.array(z.string()).default([]);

// Step 1: Farm Profile Schema
export const farmProfileSchema = z.object({
  // Basic Information
  farmerName: z.string()
    .min(2, "Farmer name must be at least 2 characters")
    .max(100, "Farmer name must be less than 100 characters"),
  
  farmName: z.string()
    .min(2, "Farm name must be at least 2 characters")
    .max(100, "Farm name must be less than 100 characters"),
  
  country: z.enum(['Ghana', 'Nigeria', 'Senegal', 'Burkina Faso', 'South Africa', 'Canada'], {
    message: "Please select your country"
  }),
  
  region: z.string()
    .min(2, "Please specify your region/state")
    .max(100, "Region name must be less than 100 characters"),
  
  // Optional GPS coordinates
  coordinates: z.object({
    latitude: z.number().min(-90).max(90),
    longitude: z.number().min(-180).max(180)
  }).optional(),
  
  // Farm Infrastructure (upper bound mirrors the API: 1,000,000 ha)
  totalFarmSize: z.number({ message: "Enter the total farm size in hectares" })
    .min(0.1, "Farm size must be at least 0.1 hectares")
    .max(MAX_AREA_HA, "Please verify the farm size (maximum 1,000,000 hectares)"),
  
  farmingExperience: z.number()
    .min(0, "Experience cannot be negative")
    .max(80, "Please verify farming experience"),
  
  farmType: z.nativeEnum(FarmType, {
    message: "Please select your farm type"
  }),
  
  primaryFarmingSystem: z.nativeEnum(FarmingSystem, {
    message: "Please select your farming system"
  }),
  
  // Certifications (optional)
  certifications: z.array(z.nativeEnum(CertificationType)).default([]),
  participatesInPrograms: z.array(z.string()).default([])
});

// Step 2: Crop Production Schema
export const cropProductionSchema = z.array(z.object({
    // Basic Crop Information
    cropId: z.string().default(() => `crop_${Date.now()}`),
    cropName: z.string()
      .min(1, "Crop name is required")
      .max(100, "Crop name must be less than 100 characters"),
    
    localName: z.string().optional(),
    category: z.string().min(1, "Please select crop category"),
    variety: z.string()
      .min(1, "Please specify the crop variety")
      .max(100, "Variety name must be less than 100 characters"),
    
    // Production Details. Area and production drive every per-hectare input and the
    // functional unit, so both must be real positive numbers (0 is not "unknown").
    areaAllocated: z.number({ message: "Enter the area allocated to this crop" })
      .min(0.01, "Area must be at least 0.01 hectares")
      .max(MAX_AREA_HA, "Please verify area allocated"),

    annualProduction: z.number({ message: "Enter the annual production in kg" })
      .min(0.1, "Production must be at least 0.1 kg")
      .max(100000000, "Please verify annual production"),  // up to ~100k tonnes for large commercial farms
    
    productionSystem: z.nativeEnum(ProductionSystem, {
      message: "Please select production system"
    }),
    
    // Cropping Pattern
    croppingPattern: z.nativeEnum(CroppingPattern, {
      message: "Please select cropping pattern"
    }),
    
    // Seasonal Information
    seasonality: z.object({
      plantingMonths: z.array(z.coerce.number().int().min(1).max(12))
        .min(1, "Please select at least one planting month"),
      harvestingMonths: z.array(z.coerce.number().int().min(1).max(12))
        .min(1, "Please select at least one harvesting month"),
      // Days for ONE season (rice CH4 cultivation period). Blank -> engine default.
      growingPeriod: optionalNumber(
        z.number()
          .int("Growing period must be a whole number of days")
          .min(30, "Growing period must be at least 30 days")
          .max(365, "Growing period cannot exceed 365 days")
      ),
      cropsPerYear: z.coerce.number({ message: "Select the number of harvests per year" })
        .int("Harvests per year must be a whole number")
        .min(1, "At least 1 harvest per year")
        .max(4, "Cannot exceed 4 harvests per year")
        .default(1),
      // Display mirror of the derived season (lib/seasonal-factor.ts); never sent.
      season: z.array(z.string()).optional(),
      // Explicit override; blank -> the engine derives wet/dry from the planting months.
      seasonOverride: z.union([z.literal(''), z.nativeEnum(SeasonType)]).optional(),
    }),
    
    // Intercropping & Rotation
    isIntercropped: z.boolean().default(false),
    intercroppingPartners: z.array(z.string()).optional(),
    intercroppingRatio: z.record(z.string(), z.number()).optional(),
    // Previous crops in the rotation, most recent first.
    rotationSequence: z.array(z.string()).default([]),
    rotationDuration: z.number().min(1).max(10).default(1),
    
    // Derived from annualProduction / areaAllocated; never a blocking input.
    averageYieldPerHectare: optionalNumber(z.number().min(0)),
    
    // Blank -> not sent (it used to default to a hidden 10% that was printed in the report).
    postHarvestLosses: optionalNumber(
      z.number()
        .min(0, "Losses cannot be negative")
        .max(100, "Losses cannot exceed 100%")
    ),

    // Seed sown (kg/ha); blank -> FAO default for the crop / category.
    seedRateKgPerHa: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0, "Seed rate cannot be negative").max(500, "Please verify seed rate").optional()
    ),

    // Rice only (IPCC 2019 Vol 4 Ch 5 Tables 5.12 / 5.13); blank -> engine inference.
    waterRegime: z.union([z.literal(''), z.enum(RICE_WATER_REGIMES)]).optional(),
    preseasonWaterStatus: z.union([z.literal(''), z.enum(RICE_PRESEASON_STATUSES)]).optional(),

    // Advanced (optional): land-use change, residue management, perennial establishment.
    landUseChange: z.object({
      previousLandUse: z.enum(['', 'forest', 'grassland', 'annual_cropland', 'perennial_cropland']).optional(),
      yearsSinceConversion: optionalNumber(
        z.number().int("Enter whole years").min(0, "Years cannot be negative").max(200, "Please verify the years")
      ),
    }).superRefine((luc, ctx) => {
      // A blank years value used to be sent as 0, which books the full carbon loss this year.
      if (luc.previousLandUse && luc.yearsSinceConversion === undefined) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Enter how many years ago the land was converted",
          path: ["yearsSinceConversion"],
        });
      }
    }).optional(),
    residueManagement: z.object({
      fractionRemoved: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0).max(1).optional()
    ),
      fractionBurnt: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0).max(1).optional()
    ),
      removedResidueUse: z.union([z.literal(''), z.enum(REMOVED_RESIDUE_USES)]).optional(),
    }).optional(),
    establishment: z.object({
      immatureYears: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0).optional()
    ),
      productiveYears: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().gt(0, "Productive years must be greater than zero").optional()
    ),
      inputShare: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0).optional()
    ),
    }).optional()
  }))
  .min(1, "Please add at least one crop")
  .max(10, "Maximum 10 crops can be assessed at once");



// Step 3: Farm Management Practices Schema
export const managementPracticesSchema = z.object({
  // Soil Management
  soilManagement: z.object({
    soilType: z.nativeEnum(SoilType, {
      message: "Please select your predominant soil type"
    }),
    soilpH: z.preprocess(
      (val) => val === "" || val === null || val === undefined || val === "Not known" ? undefined : Number(val),
      z.number().min(3, "Soil pH must be at least 3").max(10, "Soil pH cannot exceed 10").optional()
    ),
    organicMatterContent: z.preprocess(
      (val) => val === "" || val === null || val === undefined || val === "Not known" ? undefined : Number(val),
      z.number().min(0, "Organic matter cannot be negative").max(100, "Organic matter cannot exceed 100%").optional()
    ),
    soilTestingFrequency: z.nativeEnum(TestingFrequency),
    conservationPractices: z.array(z.nativeEnum(SoilConservationPractice)).default([]),
    usesCoverCrops: z.boolean().default(false),
    coverCrops: z.array(z.string()).default([]),
    // Blank -> SOC change from management is not booked (the engine discloses it).
    practicesAdoptedYearsAgo: optionalNumber(
      z.number().int("Enter whole years").min(0, "Years cannot be negative").max(100, "Maximum 100 years")
    ),
    limeApplications: z.array(z.object({
      material: z.enum(LIME_MATERIALS, { message: "Select limestone or dolomite" }),
      rateTPerHaPerYear: z.number({ message: "Enter the lime rate in tonnes per hectare per year" })
        .gt(0, "Lime rate must be greater than zero")
        .max(MAX_LIME_T_PER_HA, `Please verify the lime rate (maximum ${MAX_LIME_T_PER_HA} t/ha/year)`),
      cropIds: cropIdList,
    })).default([]),
    compostUse: z.object({
      usesCompost: z.boolean(),
      compostsource: z.nativeEnum(CompostSource).default(CompostSource.NONE),
      applicationRate: z.preprocess(
        (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
        z.number().min(0).max(100).optional()
      ),
      applicationTiming: z.string().default("Before planting"),
      cropIds: cropIdList,
    }).superRefine((data, ctx) => {
      // If user doesn't use compost, validation passes
      if (!data.usesCompost) return;
      // If user uses compost, they must select a valid source (not "Not used") ...
      if (data.compostsource === CompostSource.NONE) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Please select a compost source when using compost",
          path: ["compostsource"],
        });
      }
      // ... and give the rate, because the engine scales the compost burden and field N2O by it.
      if (!(typeof data.applicationRate === "number" && data.applicationRate > 0)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          message: "Enter the compost application rate (tonnes per hectare) when using compost",
          path: ["applicationRate"],
        });
      }
    })
  }),
  
  // Fertilization Practices
  fertilization: z.object({
    usesFertilizers: z.boolean(),
    fertilizerApplications: z.array(z.object({
      // "None" is not a fertiliser: untick "uses fertilizers" instead (the API skips such rows).
      fertilizerType: z.nativeEnum(FertilizerType).refine(
        (t): boolean => t !== FertilizerType.NONE,
        "Remove this row (or untick 'uses fertilizers') instead of choosing None",
      ),
      brandName: z.string().max(120, "Brand name must be under 120 characters").optional(),
      npkRatio: z.string().optional(),
      // kg of PRODUCT per ha for ONE application (seasonal = rate x applications). A row the
      // user adds must describe a real application: zero rows used to be silently skipped.
      applicationRate: z.number({ message: "Enter kg of product per hectare per application" })
        .gt(0, "Application rate must be greater than zero")
        .max(MAX_RATE_KG_PER_HA, "Please verify application rate (maximum 5000 kg/ha)"),
      applicationsPerSeason: z.number({ message: "Enter the number of applications per season" })
        .int("Applications per season must be a whole number")
        .min(1, "At least one application per season")
        .max(MAX_APPLICATIONS_PER_SEASON, "Maximum 12 applications per season"),
      applicationMethod: z.preprocess(
        (val) => (val === "" || val === null ? undefined : val),
        z.nativeEnum(ApplicationMethod).optional()
      ),
      cropIds: cropIdList,
      cost: z.preprocess(
        (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
        z.number().min(0, "Cost cannot be negative").optional()
      ),
      currency: z.nativeEnum(Currency).optional()
    })).default([]),
    // Legacy farm-level method (archived snapshots); copied onto rows that have none.
    applicationMethod: z.preprocess(
      (val) => (val === "" || val === null ? undefined : val),
      z.nativeEnum(ApplicationMethod).optional()
    ),
    timingStrategy: z.preprocess(
      (val) => (val === "" || val === null ? undefined : val),
      z.nativeEnum(TimingStrategy).optional()
    ),
    soilTestBased: z.boolean().default(false),
    followsNutrientPlan: z.boolean().default(false)
  }).superRefine((data, ctx) => {
    // The flag and the rows must agree: the engine reads the rows, the kernel reads the flag.
    const rows = data.fertilizerApplications ?? [];
    if (data.usesFertilizers && rows.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Add at least one fertilizer application, or untick 'uses fertilizers'",
        path: ["fertilizerApplications"],
      });
    }
    if (!data.usesFertilizers && rows.length > 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Tick 'uses fertilizers' or remove the fertilizer applications listed",
        path: ["usesFertilizers"],
      });
    }
  }),
  
  // Water Management
  waterManagement: z.object({
    waterSource: z.array(z.nativeEnum(WaterSource))
      .min(1, "Please select at least one water source"),
    // "" is what an unselected <select> submits; treat it as "no irrigation system".
    irrigationSystem: z.preprocess(
      (val) => (val === "" || val === null ? undefined : val),
      z.nativeEnum(IrrigationSystem).optional()
    ),
    irrigationWaterM3: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0, "Water volume cannot be negative").max(1e9, "Please verify the irrigation volume").optional()
    ),
    drainageSystem: z.boolean().default(false),
    waterConservationPractices: z.array(z.string()).default([])
  }).superRefine((data, ctx) => {
    // An irrigated farm must report its water: without it the engine invents a volume (and
    // pumping energy) from the crop water need, which is not the farmer's data.
    const irrigated = !!data.irrigationSystem && data.irrigationSystem !== IrrigationSystem.NONE;
    if (irrigated && !(typeof data.irrigationWaterM3 === "number" && data.irrigationWaterM3 > 0)) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Enter the irrigation water applied per year (m3) for the selected irrigation system",
        path: ["irrigationWaterM3"],
      });
    }
  })
});

// Step 4: Pest Management Schema
export const pestManagementSchema = z.object({
  primaryPests: z.array(z.string()).default([]),
  primaryDiseases: z.array(z.string()).default([]),
  
  managementApproach: z.nativeEnum(PestManagementApproach, {
    message: "Please select your pest management approach"
  }),
  
  pesticides: z.array(z.object({
    pesticideType: z.nativeEnum(PesticideType),
    activeIngredient: z.string().min(1, "Active ingredient is required"),
    activeIngredientContent: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().gt(0, "Must be above 0").max(1, "Enter a fraction, e.g. 0.36 for 360 g/L").optional()
    ),
    // Optional: the engine uses it as a second key for active-ingredient synonym lookup.
    brandName: z.string().max(120, "Brand name must be under 120 characters").optional(),
    applicationRate: z.number({ message: "Enter the application rate (product per hectare)" })
      .gt(0, "Application rate must be greater than zero")
      .max(100, "Please verify application rate"),
    // 0 is allowed and means "not applied this season" (no burden), never "once".
    applicationsPerSeason: z.number({ message: "Enter the number of applications per season" })
      .int("Applications per season must be a whole number")
      .min(0, "Applications cannot be negative")
      .max(MAX_APPLICATIONS_PER_SEASON, "Maximum 12 applications per season"),
    cropIds: cropIdList,
    targetPests: z.array(z.string()).default([]),
    cost: z.number().min(0).optional(),
    currency: z.nativeEnum(Currency).optional(),
    safetyPrecautions: z.array(z.string()).optional().default([])
  })).default([]),

  usesIPM: z.boolean().default(false),
  ipmPractices: z.array(z.nativeEnum(IPMPractice)).default([]),
  biologicalControls: z.array(z.string()).default([]),

  pestMonitoringFrequency: z.nativeEnum(MonitoringFrequency),
  usesEconomicThresholds: z.boolean().default(false)
}).superRefine((data, ctx) => {
  // "Chemical pesticides only" without a single pesticide row is a contradiction the engine
  // would score as a pesticide-free farm.
  if (data.managementApproach === PestManagementApproach.CHEMICAL_ONLY && (data.pesticides ?? []).length === 0) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "List the pesticides used, or choose a different pest management approach",
      path: ["pesticides"],
    });
  }
});

// Step 5: Equipment & Energy Schema
export const equipmentEnergySchema = z.object({
  equipment: z.array(z.object({
    equipmentType: z.nativeEnum(EquipmentType),
    powerSource: z.nativeEnum(PowerSource),
    age: z.number()
      .min(0, "Age cannot be negative")
      .max(50, "Please verify equipment age"),
    hoursPerYear: z.number({ message: "Enter the operating hours per year" })
      .gt(0, "Operating hours must be greater than zero")
      .max(MAX_HOURS_PER_YEAR, "Maximum 8760 hours per year"),
    fuelEfficiency: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0, "Fuel efficiency cannot be negative").optional()
    )
  })).default([]),

  // Engine fuels (machinery, pumps, dryers). The unit is sent to the API so LPG in kg is
  // never read as litres.
  fuelConsumption: z.array(z.object({
    fuelType: z.nativeEnum(FuelType),
    monthlyConsumption: z.number({ message: "Enter the monthly consumption" })
      .gt(0, "Monthly consumption must be greater than zero")
      .max(MAX_MONTHLY_CONSUMPTION, "Please verify the monthly consumption"),
    unit: z.enum(FARM_FUEL_UNITS).default('L'),
    primaryUse: z.string().min(1, "Primary use is required"),
    cost: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0, "Cost cannot be negative").optional()
    )
  })).optional(),

  energySources: z.array(z.object({
    energyType: z.nativeEnum(EnergyType),
    monthlyConsumption: z.number({ message: "Enter the monthly consumption" })
      .gt(0, "Monthly consumption must be greater than zero")
      .max(MAX_MONTHLY_CONSUMPTION, "Please verify the monthly consumption"),
    primaryUse: z.string().min(1, "Primary use is required"),
    cost: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0, "Cost cannot be negative").optional()
    ),
    currency: z.nativeEnum(Currency).optional()
  })).default([]),
  
  infrastructure: z.object({
    packagingMaterial: z.string().max(60).optional(),
    packagingKgPerTonne: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0, "Packaging cannot be negative").optional()
    ),
    inputTransportKm: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0, "Distance cannot be negative").optional()
    ),
    // Optional, in tonnes (report-only).
    storageCapacity: optionalNumber(
      z.number()
        .min(0, "Storage capacity cannot be negative")
        .max(MAX_STORAGE_TONNES, "Please verify storage capacity")
    ),
    storageFacilities: z.array(z.nativeEnum(StorageFacilityType)).default([]),
    // Cold storage only: leakage = charge x default annual leak rate (engine/refrigerants.py).
    refrigerant: z.preprocess(
      (val) => (val === "" || val === null || val === "None" ? undefined : val),
      z.enum(REFRIGERANTS, { message: "Select a refrigerant from the list" }).optional()
    ),
    refrigerantChargeKg: optionalNumber(
      z.number().gt(0, "Charge must be greater than zero").max(10000, "Please verify the refrigerant charge")
    ),
    transportAccess: z.object({
      roadAccess: z.nativeEnum(RoadAccessType),
      distanceToMarket: z.number()
        .min(0, "Distance cannot be negative")
        .max(1000, "Please verify distance to market"),
      transportMode: z.array(z.nativeEnum(TransportMode))
        .min(1, "Please select at least one transport mode"),
      transportCost: z.preprocess(
        (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
        z.number().min(0, "Transport cost cannot be negative").optional()
      )
    })
  }).superRefine((infra, ctx) => {
    const cold = (infra.storageFacilities ?? []).includes(StorageFacilityType.COLD_STORAGE);
    if (cold && infra.refrigerantChargeKg !== undefined && !infra.refrigerant) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Select the refrigerant gas for the charge entered",
        path: ["refrigerant"],
      });
    }
  })
});

// Step 6: Assessment Parameters Schema. Only the uncertainty toggle reaches the engine
// (run_uncertainty). The other keys are optional so archived snapshots still validate.
export const assessmentParametersSchema = z.object({
  includeUncertaintyAnalysis: z.boolean().default(true),
  functionalUnit: z.nativeEnum(FunctionalUnit).optional(),
  systemBoundary: z.nativeEnum(SystemBoundary).optional(),
  assessmentPeriod: z.number().optional(),
  includeSensitivityAnalysis: z.boolean().optional(),
  benchmarkComparison: z.boolean().optional(),
});

// ======================================================================
// COMPLETE ENHANCED ASSESSMENT SCHEMA
// ======================================================================

export const enhancedAssessmentSchema = z.object({
  farmProfile: farmProfileSchema,
  cropProductions: cropProductionSchema,
  managementPractices: managementPracticesSchema,
  pestManagement: pestManagementSchema,
  equipmentEnergy: equipmentEnergySchema,
  assessmentParameters: assessmentParametersSchema
}).superRefine((data, ctx) => {
  const totalFarmSize = data.farmProfile?.totalFarmSize || 0;
  if (totalFarmSize <= 0) return;
  const totalAllocated = sumAllocatedArea(data.cropProductions || []);
  if (totalAllocated > totalFarmSize + 1e-9) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      path: ['cropProductions'],
      message: `Total allocated area (${totalAllocated.toFixed(2)} ha) exceeds farm size (${totalFarmSize} ha). ${Math.max(0, totalFarmSize - totalAllocated).toFixed(2)} ha would need to be freed.`,
    });
  }
}).superRefine((data, ctx) => {
  // A crop target pointing at a removed crop would silently fall back to "all crops".
  const known = new Set((data.cropProductions ?? []).map((c) => c.cropId));
  const check = (ids: string[] | undefined, path: (string | number)[]) => {
    if ((ids ?? []).some((id) => !known.has(id))) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "This row is linked to a crop that was removed; reselect the crops it applies to",
        path,
      });
    }
  };
  const mp = data.managementPractices;
  mp?.fertilization?.fertilizerApplications?.forEach((a, i) =>
    check(a.cropIds, ['managementPractices', 'fertilization', 'fertilizerApplications', i, 'cropIds']));
  mp?.soilManagement?.limeApplications?.forEach((l, i) =>
    check(l.cropIds, ['managementPractices', 'soilManagement', 'limeApplications', i, 'cropIds']));
  check(mp?.soilManagement?.compostUse?.cropIds, ['managementPractices', 'soilManagement', 'compostUse', 'cropIds']);
  data.pestManagement?.pesticides?.forEach((p, i) =>
    check(p.cropIds, ['pestManagement', 'pesticides', i, 'cropIds']));
});

export type EnhancedAssessmentFormData = z.infer<typeof enhancedAssessmentSchema>;
/** What the form holds before zod applies defaults and coercions (react-hook-form's value type). */
export type EnhancedAssessmentFormInput = z.input<typeof enhancedAssessmentSchema>;

/**
 * The wizard's starting state: nothing filled in. Every result-driving field is empty so an
 * untouched form cannot pass validation (the old default was a complete synthetic farm).
 * Only fixed study parameters and empty collections are preset.
 */
export function blankFarmAssessmentForm(): DefaultValues<EnhancedAssessmentFormInput> {
  return {
    farmProfile: {
      farmerName: '',
      farmName: '',
      country: undefined,
      region: '',
      totalFarmSize: undefined,
      farmingExperience: undefined,
      farmType: undefined,
      primaryFarmingSystem: undefined,
      certifications: [],
      participatesInPrograms: [],
    },
    cropProductions: [],
    managementPractices: {
      soilManagement: {
        soilType: undefined,
        soilpH: undefined,
        organicMatterContent: undefined,
        soilTestingFrequency: undefined,
        conservationPractices: [],
        usesCoverCrops: false,
        coverCrops: [],
        practicesAdoptedYearsAgo: undefined,
        limeApplications: [],
        compostUse: {
          usesCompost: false,
          compostsource: CompostSource.NONE,
          applicationRate: undefined,
          applicationTiming: 'Before planting',
          cropIds: [],
        },
      },
      fertilization: {
        usesFertilizers: false,
        fertilizerApplications: [],
        applicationMethod: undefined,
        timingStrategy: undefined,
        soilTestBased: false,
        followsNutrientPlan: false,
      },
      waterManagement: {
        waterSource: [],
        irrigationSystem: undefined,
        irrigationWaterM3: undefined,
        drainageSystem: false,
        waterConservationPractices: [],
      },
    },
    pestManagement: {
      primaryPests: [],
      primaryDiseases: [],
      managementApproach: undefined,
      pesticides: [],
      usesIPM: false,
      ipmPractices: [],
      biologicalControls: [],
      pestMonitoringFrequency: undefined,
      usesEconomicThresholds: false,
    },
    equipmentEnergy: {
      equipment: [],
      fuelConsumption: [],
      energySources: [],
      infrastructure: {
        packagingMaterial: undefined,
        packagingKgPerTonne: undefined,
        inputTransportKm: undefined,
        storageCapacity: undefined,
        storageFacilities: [],
        refrigerant: undefined,
        refrigerantChargeKg: undefined,
        transportAccess: {
          roadAccess: undefined,
          distanceToMarket: undefined,
          transportMode: [],
          transportCost: undefined,
        },
      },
    },
    assessmentParameters: {
      includeUncertaintyAnalysis: true,
    },
  };
}

type Loose = Record<string, unknown>;
const isObj = (v: unknown): v is Loose => !!v && typeof v === 'object' && !Array.isArray(v);

/** Recursively fill keys missing from `target` with values from `defaults` (objects only). */
function fillDefaults(target: Loose, defaults: Loose): Loose {
  const out: Loose = { ...target };
  for (const [k, dv] of Object.entries(defaults)) {
    const tv = out[k];
    if (tv === undefined) out[k] = dv;
    else if (isObj(tv) && isObj(dv)) out[k] = fillDefaults(tv, dv);
  }
  return out;
}

/**
 * Prepare an archived wizard snapshot for `reset()` on edit / re-run. Snapshots saved before
 * a field existed lack it; fill those gaps with the blank-form defaults, give every row the
 * list fields it now needs, and move the legacy farm-level fertiliser method onto the rows.
 */
export function restoreFormSnapshot(snapshot: unknown): EnhancedAssessmentFormInput {
  const base = fillDefaults(isObj(snapshot) ? snapshot : {}, blankFarmAssessmentForm() as Loose);
  const form = JSON.parse(JSON.stringify(base)) as Loose;
  const crops = Array.isArray(form.cropProductions) ? (form.cropProductions as Loose[]) : [];
  crops.forEach((c, i) => {
    if (!c.cropId) c.cropId = `crop_${i + 1}`;
    if (!Array.isArray(c.rotationSequence)) c.rotationSequence = [];
    const s = isObj(c.seasonality) ? c.seasonality : (c.seasonality = {} as Loose);
    if (s.cropsPerYear === undefined || s.cropsPerYear === null) s.cropsPerYear = 1;
    // Establishment is hidden (and refused by the API) for annual crops.
    if (c.establishment && isKnownAnnualCrop(c as { cropName?: string; variety?: string; category?: string })) {
      delete c.establishment;
    }
  });
  const mp = form.managementPractices as Loose;
  const fert = mp.fertilization as Loose;
  const legacyMethod = fert.applicationMethod;
  ((fert.fertilizerApplications as Loose[]) ?? []).forEach((a) => {
    if (!Array.isArray(a.cropIds)) a.cropIds = [];
    if (!a.applicationMethod && legacyMethod) a.applicationMethod = legacyMethod;
  });
  const soil = mp.soilManagement as Loose;
  ((soil.limeApplications as Loose[]) ?? []).forEach((l) => {
    if (!Array.isArray(l.cropIds)) l.cropIds = [];
  });
  const pest = form.pestManagement as Loose;
  ((pest.pesticides as Loose[]) ?? []).forEach((p) => {
    if (!Array.isArray(p.cropIds)) p.cropIds = [];
    if (!Array.isArray(p.targetPests)) p.targetPests = [];
  });
  return form as EnhancedAssessmentFormInput;
}

// ======================================================================
// FIELD CONFIGURATIONS FOR DYNAMIC FORMS
// ======================================================================

export const REGIONS_BY_COUNTRY = {
  Ghana: [
    "Greater Accra", "Ashanti", "Western", "Central", "Volta", 
    "Eastern", "Northern", "Upper East", "Upper West", "Brong Ahafo",
    "Western North", "Ahafo", "Bono", "Bono East", "Oti", "Savannah", "North East"
  ],
  Nigeria: [
    "Abia", "Adamawa", "Akwa Ibom", "Anambra", "Bauchi", "Bayelsa", "Benue",
    "Borno", "Cross River", "Delta", "Ebonyi", "Edo", "Ekiti", "Enugu",
    "Gombe", "Imo", "Jigawa", "Kaduna", "Kano", "Katsina", "Kebbi", "Kogi",
    "Kwara", "Lagos", "Nasarawa", "Niger", "Ogun", "Ondo", "Osun", "Oyo",
    "Plateau", "Rivers", "Sokoto", "Taraba", "Yobe", "Zamfara", "FCT"
  ],
  Canada: [
    "Alberta", "British Columbia", "Manitoba", "New Brunswick",
    "Newfoundland and Labrador", "Nova Scotia", "Ontario",
    "Prince Edward Island", "Quebec", "Saskatchewan"
  ],
  ...NEW_REGIONS_BY_COUNTRY,
};

export const COMMON_CROPS_BY_REGION = {
  "Ghana-Northern": ["Maize", "Rice", "Millet", "Sorghum", "Groundnuts", "Cowpea", "Yam"],
  "Ghana-Southern": ["Cassava", "Plantain", "Cocoyam", "Maize", "Rice", "Vegetables"],
  "Nigeria-Northern": ["Millet", "Sorghum", "Maize", "Rice", "Groundnuts", "Cowpea", "Cotton"],
  "Nigeria-Middle Belt": ["Yam", "Maize", "Rice", "Sweet Potato", "Groundnuts", "Soybeans"],
  "Nigeria-Southern": ["Cassava", "Plantain", "Cocoyam", "Vegetables", "Oil Palm", "Cocoa"],
  "Canada-Prairies": ["Wheat", "Canola", "Barley", "Oats", "Lentils", "Field Peas", "Flax"],
  "Canada-Central": ["Corn", "Soybeans", "Wheat", "Barley", "Potatoes"],
  "Canada": ["Wheat", "Canola", "Barley", "Corn", "Soybeans", "Oats", "Potatoes"],
  ...NEW_COMMON_CROPS,
};

export const CROP_VARIETIES = {
  "Maize": [
    "SAMMAZ 15", "SAMMAZ 16", "SAMMAZ 17", "SAMMAZ 52", "FARO 61", "FARO 62",
    "Oba Super 1", "Oba Super 2", "Obatanpa", "Suwan 1", "DMR-ESR-Y", "Local variety"
  ],
  "Wheat": [
    "AAC Brandon", "CDC Go", "CDC Landmark", "Katepwa", "Norwell", "Local variety"
  ],
  "Rice": [
    "FARO 44", "FARO 52", "FARO 57", "FARO 60", "FARO 66", "NERICA 1", "NERICA 2", 
    "NERICA 4", "NERICA 7", "Jasmine 85", "IR 841", "Local variety"
  ],
  "Cassava": [
    "TMS 30572", "TMS 98/0505", "TMS 98/0581", "TMS 01/1368", "TMS 01/1371", 
    "NR 8082", "NR 8083", "Bankye Hemaa", "Ampong", "Local variety"
  ],
  "Yam": [
    "Pona", "Laribako", "Obiaoturugo", "Ise-ise", "Ekpe", "Amula", "Efuru", 
    "Gbagba", "Dan Ilu", "Local variety"
  ],
  "Cowpea": [
    "IT90K-277-2", "IT07K-243-1-2", "Sampea 6", "Sampea 7", "Sampea 8", 
    "Sampea 9", "Sampea 10", "Sampea 11", "Sampea 12", "Songotra", "Local variety"
  ],
  "Groundnuts": [
    "Samnut 10", "Samnut 11", "Samnut 21", "Samnut 22", "Samnut 23", "Samnut 24", 
    "ICGV-IS 96894", "55-437", "Local variety"
  ],
  "Sorghum": [
    "SAMSORG 17", "SAMSORG 40", "SAMSORG 41", "SAMSORG 42", "SAMSORG 43", 
    "SAMSORG 44", "SAMSORG 45", "Local variety"
  ],
  "Millet": [
    "SOSAT C88", "Ex-Borno", "LCIC-9702", "ICTP 8203", "GB 8735", "Local variety"
  ],
  "Plantain": [
    "FHIA 21", "PITA 14", "PITA 17", "PITA 23", "PITA 24", "Agbagba", "Apem", 
    "Apantu", "Local variety"
  ],
  "Tomato": [
    "Roma VF", "UC82B", "Petomech", "Power", "Platinum", "Local variety"
  ],
  "Pepper": [
    "Shombo", "Tatase", "Bawa", "Yolo Wonder", "California Wonder", "Local variety"
  ],
  "Onion": [
    "Red Creole", "Violet de Galmi", "White Creole", "Local variety"
  ],
  "Other": ["Please specify variety", "Local variety", "Unknown variety"]
};

export const COMMON_PESTS_BY_CROP = {
  "Maize": ["Fall armyworm", "Stemborer", "Armyworm", "Cutworm", "Aphids"],
  "Rice": ["Rice blast", "Stem borer", "Brown planthopper", "Leaf folder"],
  "Cassava": ["Cassava green mite", "Cassava mealybug", "Cassava mosaic disease"],
  "Cowpea": ["Pod borer", "Aphids", "Thrips", "Cowpea weevil"],
  "Yam": ["Yam beetle", "Nematodes", "Anthracnose", "Dry rot"]
};

/**
 * Get varieties for a specific crop
 */
export function getCropVarieties(cropName: string): string[] {
  return CROP_VARIETIES[cropName as keyof typeof CROP_VARIETIES] || CROP_VARIETIES["Other"];
}

/**
 * Calculate area percentage of total farm size
 */
export function calculateAreaPercentage(areaAllocated: number, totalFarmSize: number): number {
  if (!totalFarmSize || totalFarmSize === 0) return 0;
  return Math.round((areaAllocated / totalFarmSize) * 100 * 100) / 100; // Round to 2 decimal places
}

/** Sum of areaAllocated across crops (ignores non-finite values). */
export function sumAllocatedArea(crops: { areaAllocated?: number }[]): number {
  return crops.reduce((sum, crop) => {
    const n = Number(crop.areaAllocated);
    return sum + (Number.isFinite(n) && n > 0 ? n : 0);
  }, 0);
}

/**
 * Hectares still available on the farm. When `excludeIndex` is set, that crop's
 * current allocation is treated as available again (for per-field max).
 */
export function remainingFarmArea(
  crops: { areaAllocated?: number }[],
  totalFarmSize: number,
  excludeIndex?: number,
): number {
  if (!totalFarmSize || totalFarmSize <= 0) return 0;
  const others = crops.reduce((sum, crop, i) => {
    if (excludeIndex !== undefined && i === excludeIndex) return sum;
    const n = Number(crop.areaAllocated);
    return sum + (Number.isFinite(n) && n > 0 ? n : 0);
  }, 0);
  return Math.max(0, Math.round((totalFarmSize - others) * 100) / 100);
}

/**
 * Validate that total allocated area doesn't exceed farm size
 */
export function validateTotalAllocation(crops: { areaAllocated?: number }[], totalFarmSize: number): string[] {
  const errors: string[] = [];
  const totalAllocated = sumAllocatedArea(crops);

  if (totalAllocated > totalFarmSize + 1e-9) {
    const over = totalAllocated - totalFarmSize;
    errors.push(
      `Total allocated area (${totalAllocated.toFixed(2)} ha) exceeds farm size (${totalFarmSize} ha) by ${over.toFixed(2)} ha`,
    );
  }

  return errors;
}

export const FERTILIZER_RECOMMENDATIONS_BY_CROP = {
  "Maize": [
    { type: "NPK 15-15-15", rate: "200-300 kg/ha", timing: "At planting" },
    { type: "Urea", rate: "100-150 kg/ha", timing: "4-6 weeks after planting" }
  ],
  "Rice": [
    { type: "NPK 15-15-15", rate: "150-200 kg/ha", timing: "At transplanting" },
    { type: "Urea", rate: "100 kg/ha", timing: "Tillering stage" }
  ]
};

// ======================================================================
// FORM HELPER FUNCTIONS
// ======================================================================

export function getStepProgress(currentStep: FormStep): number {
  const steps = Object.values(FormStep);
  const currentIndex = steps.indexOf(currentStep);
  return ((currentIndex + 1) / steps.length) * 100;
}

export function getNextStep(currentStep: FormStep): FormStep | null {
  const steps = Object.values(FormStep);
  const currentIndex = steps.indexOf(currentStep);
  return currentIndex < steps.length - 1 ? steps[currentIndex + 1] : null;
}

export function getPreviousStep(currentStep: FormStep): FormStep | null {
  const steps = Object.values(FormStep);
  const currentIndex = steps.indexOf(currentStep);
  return currentIndex > 0 ? steps[currentIndex - 1] : null;
}

/**
 * Helper function to estimate typical yields for common crops
 * NOTE: This is for guidance only - actual production should be used for LCA calculations
 * @param cropName - Name of the crop
 * @param areaHa - Area in hectares
 * @returns Estimated yield in kg (for guidance only)
 */
export function calculateEstimatedYield(cropName: string, areaHa: number): number {
  // Typical yields for major crops by region (kg/ha) - RESEARCH NEEDED
  // These are rough estimates and should be replaced with regional databases
  const averageYields: Record<string, number> = {
    "Maize": 1500,
    "Rice": 2000,
    "Cassava": 8000,
    "Yam": 12000,
    "Cowpea": 800,
    "Groundnuts": 1200,
    "Millet": 800,
    "Sorghum": 1000
  };
  
  const baseYield = averageYields[cropName] || 1000;
  return baseYield * areaHa;
}

/**
 * Get yield estimate disclaimer text
 */
export function getYieldEstimateDisclaimer(): string {
  return "⚠️ This is a rough estimate based on typical yields. For accurate LCA results, please enter your actual production quantities.";
}

export function validateCroppingSeason(plantingMonths: number[], harvestingMonths: number[], growingPeriod: number): string[] {
  const errors: string[] = [];
  
  // Check if growing period is realistic for the season
  const seasonLength = Math.max(...harvestingMonths) - Math.min(...plantingMonths);
  if (seasonLength < 0) {
    // Handle year overlap
    const adjustedLength = (12 - Math.min(...plantingMonths)) + Math.max(...harvestingMonths);
    if (adjustedLength < (growingPeriod / 30)) {
      errors.push("Growing period seems too long for the selected planting and harvesting months");
    }
  } else if (seasonLength < (growingPeriod / 30)) {
    errors.push("Growing period seems too long for the selected planting and harvesting months");
  }
  
  return errors;
}