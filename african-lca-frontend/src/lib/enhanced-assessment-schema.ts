/**
 * Enhanced Assessment Validation Schema & Form Configuration
 * 
 * This implements a step-by-step, farmer-friendly form structure that collects
 * all necessary LCA data while being practical and not overwhelming.
 */

import { z } from 'zod';
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
  StorageFacilityType,
  RoadAccessType,
  TransportMode,
  FunctionalUnit,
  SystemBoundary,
  FormStep,
  Currency
} from '@/types/enhanced-assessment';

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

// Step 1: Farm Profile Schema
export const farmProfileSchema = z.object({
  // Basic Information
  farmerName: z.string()
    .min(2, "Farmer name must be at least 2 characters")
    .max(100, "Farmer name must be less than 100 characters"),
  
  farmName: z.string()
    .min(2, "Farm name must be at least 2 characters")
    .max(100, "Farm name must be less than 100 characters"),
  
  country: z.enum(['Ghana', 'Nigeria'], {
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
  
  // Farm Infrastructure
  totalFarmSize: z.number()
    .min(0.1, "Farm size must be at least 0.1 hectares")
    .max(10000, "Please contact us for farms larger than 10,000 hectares"),
  
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
    
    // Production Details
    areaAllocated: z.number()
      .min(0.01, "Area must be at least 0.01 hectares")
      .max(10000, "Please verify area allocated"),
    
    annualProduction: z.number()
      .min(0.1, "Production must be at least 0.1 kg")
      .max(1000000, "Please verify annual production"),
    
    productionSystem: z.nativeEnum(ProductionSystem, {
      message: "Please select production system"
    }),
    
    // Cropping Pattern
    croppingPattern: z.nativeEnum(CroppingPattern, {
      message: "Please select cropping pattern"
    }),
    
    // Seasonal Information
    seasonality: z.object({
      plantingMonths: z.array(z.coerce.number().min(1).max(12))
        .min(1, "Please select at least one planting month"),
      harvestingMonths: z.array(z.coerce.number().min(1).max(12))
        .min(1, "Please select at least one harvesting month"),
      growingPeriod: z.number()
        .min(30, "Growing period must be at least 30 days")
        .max(365, "Growing period cannot exceed 365 days"),
      cropsPerYear: z.number()
        .min(0.5, "Must be at least 0.5 crops per year")
        .max(4, "Cannot exceed 4 crops per year"),
      season: z.array(z.nativeEnum(SeasonType))
        .min(1, "Please select at least one season")
    }),
    
    // Intercropping & Rotation
    isIntercropped: z.boolean().default(false),
    intercroppingPartners: z.array(z.string()).optional(),
    intercroppingRatio: z.record(z.string(), z.number()).optional(),
    rotationSequence: z.array(z.string()).default([]),
    rotationDuration: z.number().min(1).max(10).default(1),
    
    // Yield & Quality
    averageYieldPerHectare: z.number()
      .min(1, "Yield per hectare must be at least 1 kg")
      .max(50000, "Please verify yield per hectare"),
    
    postHarvestLosses: z.number()
      .min(0, "Losses cannot be negative")
      .max(100, "Losses cannot exceed 100%")
      .default(10)
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
    coverCrops: z.array(z.string()).default([]),
    compostUse: z.object({
      usesCompost: z.boolean(),
      compostsource: z.nativeEnum(CompostSource).default(CompostSource.NONE),
      applicationRate: z.preprocess(
        (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
        z.number().min(0).max(100).optional()
      ),
      applicationTiming: z.string().default("Before planting")
    }).refine(
      (data) => {
        // If user doesn't use compost, validation passes
        if (!data.usesCompost) {
          return true;
        }
        // If user uses compost, they must select a valid source (not "Not used")
        return data.compostsource !== CompostSource.NONE;
      },
      {
        message: "Please select a compost source when using compost",
        path: ["compostsource"]
      }
    )
  }),
  
  // Fertilization Practices
  fertilization: z.object({
    usesFertilizers: z.boolean(),
    fertilizerApplications: z.array(z.object({
      fertilizerType: z.nativeEnum(FertilizerType),
      brandName: z.string().optional(),
      npkRatio: z.string().optional(),
      applicationRate: z.number()
        .min(0, "Application rate cannot be negative")
        .max(1000, "Please verify application rate"),
      applicationsPerSeason: z.number()
        .min(0, "Applications cannot be negative")
        .max(10, "Maximum 10 applications per season"),
      cost: z.preprocess(
        (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
        z.number().min(0, "Cost cannot be negative").optional()
      ),
      currency: z.nativeEnum(Currency).optional()
    })).default([]),
    applicationMethod: z.nativeEnum(ApplicationMethod).optional(),
    timingStrategy: z.nativeEnum(TimingStrategy).optional(),
    soilTestBased: z.boolean().default(false),
    followsNutrientPlan: z.boolean().default(false)
  }),
  
  // Water Management
  waterManagement: z.object({
    waterSource: z.array(z.nativeEnum(WaterSource))
      .min(1, "Please select at least one water source"),
    irrigationSystem: z.nativeEnum(IrrigationSystem).optional(),
    drainageSystem: z.boolean().default(false),
    waterConservationPractices: z.array(z.string()).default([])
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
    brandName: z.string().min(1, "Brand name is required"),
    applicationRate: z.number()
      .min(0, "Application rate cannot be negative")
      .max(100, "Please verify application rate"),
    applicationsPerSeason: z.number()
      .min(0, "Applications cannot be negative")
      .max(20, "Maximum 20 applications per season"),
    targetPests: z.array(z.string()),
    cost: z.number().min(0).optional(),
    currency: z.nativeEnum(Currency).optional(),
    safetyPrecautions: z.array(z.string()).optional().default([])
  })).default([]),
  
  usesIPM: z.boolean().default(false),
  ipmPractices: z.array(z.nativeEnum(IPMPractice)).default([]),
  biologicalControls: z.array(z.string()).default([]),
  
  pestMonitoringFrequency: z.nativeEnum(MonitoringFrequency),
  usesEconomicThresholds: z.boolean().default(false)
});

// Step 5: Equipment & Energy Schema
export const equipmentEnergySchema = z.object({
  equipment: z.array(z.object({
    equipmentType: z.nativeEnum(EquipmentType),
    powerSource: z.nativeEnum(PowerSource),
    age: z.number()
      .min(0, "Age cannot be negative")
      .max(50, "Please verify equipment age"),
    hoursPerYear: z.number()
      .min(0, "Hours cannot be negative")
      .max(4000, "Maximum 4000 hours per year"),
    fuelEfficiency: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0, "Fuel efficiency cannot be negative").optional()
    )
  })).default([]),
  
  energySources: z.array(z.object({
    energyType: z.nativeEnum(EnergyType),
    monthlyConsumption: z.number()
      .min(0, "Consumption cannot be negative"),
    primaryUse: z.string().min(1, "Primary use is required"),
    cost: z.preprocess(
      (val) => val === "" || val === null || val === undefined || isNaN(Number(val)) ? undefined : Number(val),
      z.number().min(0, "Cost cannot be negative").optional()
    ),
    currency: z.nativeEnum(Currency).optional()
  })).default([]),
  
  infrastructure: z.object({
    storageCapacity: z.number()
      .min(0, "Storage capacity cannot be negative")
      .max(50000, "Please verify storage capacity (max 50 tonnes)"),
    storageFacilities: z.array(z.nativeEnum(StorageFacilityType)).default([]),
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
  })
});

// Step 6: Assessment Parameters Schema
export const assessmentParametersSchema = z.object({
  functionalUnit: z.nativeEnum(FunctionalUnit, {
    message: "Please select functional unit"
  }),
  systemBoundary: z.nativeEnum(SystemBoundary, {
    message: "Please select system boundary"
  }),
  assessmentPeriod: z.number()
    .min(1, "Assessment period must be at least 1 year")
    .max(5, "Maximum assessment period is 5 years")
    .default(1),
  includeUncertaintyAnalysis: z.boolean().default(true),
  includeSensitivityAnalysis: z.boolean().default(true),
  benchmarkComparison: z.boolean().default(true)
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
});

export type EnhancedAssessmentFormData = z.infer<typeof enhancedAssessmentSchema>;

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
  ]
};

export const COMMON_CROPS_BY_REGION = {
  "Ghana-Northern": ["Maize", "Rice", "Millet", "Sorghum", "Groundnuts", "Cowpea", "Yam"],
  "Ghana-Southern": ["Cassava", "Plantain", "Cocoyam", "Maize", "Rice", "Vegetables"],
  "Nigeria-Northern": ["Millet", "Sorghum", "Maize", "Rice", "Groundnuts", "Cowpea", "Cotton"],
  "Nigeria-Middle Belt": ["Yam", "Maize", "Rice", "Sweet Potato", "Groundnuts", "Soybeans"],
  "Nigeria-Southern": ["Cassava", "Plantain", "Cocoyam", "Vegetables", "Oil Palm", "Cocoa"]
};

export const CROP_VARIETIES = {
  "Maize": [
    "SAMMAZ 15", "SAMMAZ 16", "SAMMAZ 17", "SAMMAZ 52", "FARO 61", "FARO 62", 
    "Oba Super 1", "Oba Super 2", "Suwan 1", "DMR-ESR-Y", "Local variety"
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
    "Sampea 9", "Sampea 10", "Sampea 11", "Sampea 12", "Local variety"
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

/**
 * Validate that total allocated area doesn't exceed farm size
 */
export function validateTotalAllocation(crops: { areaAllocated?: number }[], totalFarmSize: number): string[] {
  const errors: string[] = [];
  const totalAllocated = crops.reduce((sum, crop) => sum + (crop.areaAllocated || 0), 0);
  
  if (totalAllocated > totalFarmSize) {
    errors.push(`Total allocated area (${totalAllocated.toFixed(2)} ha) exceeds farm size (${totalFarmSize} ha)`);
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
 * Helper function to estimate typical yields for West African crops
 * NOTE: This is for guidance only - actual production should be used for LCA calculations
 * @param cropName - Name of the crop
 * @param areaHa - Area in hectares
 * @returns Estimated yield in kg (for guidance only)
 */
export function calculateEstimatedYield(cropName: string, areaHa: number): number {
  // Typical yields for major crops in West Africa (kg/ha) - RESEARCH NEEDED
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