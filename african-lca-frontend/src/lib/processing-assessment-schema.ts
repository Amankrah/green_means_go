/**
 * processing-assessment-schema.ts — validation schema, form model, step config, and the
 * backend payload builder for the PROCESSING (facility) assessment.
 *
 * Shared by the single-page form and the multi-step wizard so both validate identically and
 * emit the same request shape. Mirrors the farm side (enhanced-assessment-schema.ts) and the
 * backend contract in app/processing/models.py.
 *
 * Only fields the validated engine actually consumes are collected: raw materials, energy,
 * water, packaging, solid waste, inbound transport, refrigerant, and per-product price (for
 * economic co-product allocation). Fields the engine ignores are deliberately left out so the
 * form does not promise rigor the result cannot deliver.
 */
import { z } from 'zod';

// ---- backend enums (exact string values; see app/processing/models.py) -----------------
export const FACILITY_TYPES = [
  'Mill', 'Bakery', 'CassivaProcessing', 'RiceProcessing', 'PalmOilMill', 'CocoaProcessing',
  'FishProcessing', 'MeatProcessing', 'DairyProcessing', 'FruitProcessing',
  'VegetableProcessing', 'General',
] as const;

export const LOCATION_TYPES = ['Urban', 'PeriUrban', 'Rural', 'Industrial'] as const;

export const PRODUCT_TYPES = [
  'FlourMaize', 'FlourWheat', 'FlourCassava', 'FlourPlantain', 'RiceProcessed', 'PalmOil',
  'CocoaPowder', 'CocoaButter', 'BakedGoods', 'ProcessedFish', 'ProcessedMeat', 'Dairy',
  'FruitJuice', 'DriedFruits', 'Other',
] as const;

export const PACKAGING_MATERIALS = [
  'PlasticBag', 'PaperBag', 'Jute', 'Polypropylene', 'Cardboard', 'Metal', 'Glass', 'Composite',
] as const;

export const WASTE_DISPOSAL_METHODS = [
  'Landfill', 'Incineration', 'Composting', 'AnaerobicDigestion', 'Recycling', 'Mixed',
] as const;

export const TRANSPORT_MODES = ['Truck', 'Rail', 'Ship', 'Mixed'] as const;

export const FUEL_TYPES = ['Diesel', 'LPG', 'Natural gas', 'Kerosene', 'Biodiesel'] as const;

export const ALLOCATION_BASES = ['mass', 'economic'] as const;

// UI countries (the page maps these to the backend country + engine region via COUNTRY_TO_REGION).
export const COUNTRIES = ['Canada', 'Ghana', 'Nigeria'] as const;

// ---- numeric coercion: form inputs arrive as strings; "" -> undefined -------------------
const toNum = (v: unknown): number | undefined => {
  if (v === '' || v === null || v === undefined) return undefined;
  const n = Number(v);
  return Number.isNaN(n) ? undefined : n;
};
const reqPositive = (msg: string) =>
  z.preprocess(toNum, z.number({ message: msg }).positive(msg));
// Two .optional()s on purpose: the INNER one lets an emptied input ("" -> undefined via
// toNum) pass at runtime; the OUTER one makes the object KEY optional in BOTH the schema's
// input and output types, so react-hook-form's resolver input type (which would otherwise
// mark the key required) matches the inferred output type.
const optNonNeg = (msg: string) =>
  z.preprocess(toNum, z.number().min(0, msg).optional()).optional();

// ---- section schemas -------------------------------------------------------------------
export const facilitySchema = z.object({
  facilityName: z.string().trim().min(2, 'Facility name must be at least 2 characters').max(120),
  companyName: z.string().trim().max(120).optional(),
  facilityType: z.enum(FACILITY_TYPES),
  country: z.enum(COUNTRIES),
  region: z.string().trim().max(100).optional(),
  locationType: z.enum(LOCATION_TYPES),
  capacity: reqPositive('Processing capacity must be greater than zero'),
  hoursPerDay: reqPositive('Operating hours per day must be greater than zero'),
  daysPerYear: reqPositive('Operating days per year must be greater than zero'),
});

export const packagingSchema = z.object({
  material: z.enum(PACKAGING_MATERIALS),
  packageSize: reqPositive('Package size must be greater than zero'),
  weightPerUnit: reqPositive('Packaging weight must be greater than zero'),
});

export const productSchema = z.object({
  name: z.string().trim().min(1, 'Product name is required').max(120),
  productType: z.enum(PRODUCT_TYPES),
  annualProduction: reqPositive('Annual output must be greater than zero'), // tonnes
  rawMaterial: z.string().trim().max(120).optional(),
  rawKgPerTonne: optNonNeg('Raw material amount cannot be negative'),       // kg per tonne output
  pricePerKg: optNonNeg('Price cannot be negative'),                        // economic_value
  packaging: packagingSchema,
});

export const utilitiesSchema = z.object({
  elecKwhMonth: optNonNeg('Electricity cannot be negative'),
  renewablePct: z.preprocess(toNum, z.number().min(0).max(100, 'Renewable share is a percentage (0-100)').optional()).optional(),
  fuelLMonth: optNonNeg('Fuel cannot be negative'),
  fuelType: z.enum(FUEL_TYPES),
  waterM3Month: optNonNeg('Water cannot be negative'),
  transportKm: optNonNeg('Distance cannot be negative'),
  transportMode: z.enum(TRANSPORT_MODES),
  solidWasteKgDay: optNonNeg('Solid waste cannot be negative'),
  wasteDisposalMethod: z.enum(WASTE_DISPOSAL_METHODS),
  allocationBasis: z.enum(ALLOCATION_BASES),
  refrigerantType: z.string().trim().max(60).optional(),
  refrigerantKg: optNonNeg('Leakage cannot be negative'),
});

// ---- full schema -----------------------------------------------------------------------
// Economic allocation needs a per-product price; enforce it here so the option can never
// silently degrade to mass allocation (the backend falls back quietly when a price is missing).
export const processingAssessmentSchema = z
  .object({
    facility: facilitySchema,
    products: z.array(productSchema).min(1, 'Add at least one product'),
    utilities: utilitiesSchema,
  })
  .superRefine((data, ctx) => {
    if (data.utilities.allocationBasis === 'economic') {
      data.products.forEach((p, i) => {
        if (!p.pricePerKg || p.pricePerKg <= 0) {
          ctx.addIssue({
            code: z.ZodIssueCode.custom,
            message: 'A price per kg is required for every product when splitting impact by economic value',
            path: ['products', i, 'pricePerKg'],
          });
        }
      });
    }
  });

export type ProcessingFormData = z.infer<typeof processingAssessmentSchema>;

// ---- step configuration (used by the wizard) -------------------------------------------
export enum ProcessingStep {
  FACILITY = 'facility',
  PRODUCTS = 'products',
  UTILITIES = 'utilities',
  REVIEW = 'review',
}

export const PROCESSING_FORM_STEPS = [
  { id: ProcessingStep.FACILITY, title: 'Facility', description: 'The site being assessed', estimatedTime: '2-3 minutes' },
  { id: ProcessingStep.PRODUCTS, title: 'Products', description: 'What the facility makes, its raw materials and packaging', estimatedTime: '4-6 minutes' },
  { id: ProcessingStep.UTILITIES, title: 'Utilities & operations', description: 'Energy, water, waste, transport and cooling', estimatedTime: '3-5 minutes' },
  { id: ProcessingStep.REVIEW, title: 'Review & submit', description: 'Check your inputs and run the assessment', estimatedTime: '1-2 minutes' },
] as const;

export function getProcessingStepProgress(step: ProcessingStep): number {
  const steps = PROCESSING_FORM_STEPS.map((s) => s.id);
  return ((steps.indexOf(step) + 1) / steps.length) * 100;
}
export function getNextProcessingStep(step: ProcessingStep): ProcessingStep | null {
  const steps = PROCESSING_FORM_STEPS.map((s) => s.id);
  const i = steps.indexOf(step);
  return i < steps.length - 1 ? steps[i + 1] : null;
}
export function getPreviousProcessingStep(step: ProcessingStep): ProcessingStep | null {
  const steps = PROCESSING_FORM_STEPS.map((s) => s.id);
  const i = steps.indexOf(step);
  return i > 0 ? steps[i - 1] : null;
}

// Which form section each step validates (for per-step react-hook-form trigger()).
export const STEP_FIELDS: Record<ProcessingStep, Array<'facility' | 'products' | 'utilities'>> = {
  [ProcessingStep.FACILITY]: ['facility'],
  [ProcessingStep.PRODUCTS]: ['products'],
  [ProcessingStep.UTILITIES]: ['utilities'],
  [ProcessingStep.REVIEW]: ['facility', 'products', 'utilities'],
};

// ---- defaults --------------------------------------------------------------------------
export const newProduct = (): ProcessingFormData['products'][number] => ({
  name: '',
  productType: 'FlourWheat',
  annualProduction: undefined as unknown as number,
  rawMaterial: '',
  rawKgPerTonne: undefined,
  pricePerKg: undefined,
  packaging: { material: 'PlasticBag', packageSize: 50, weightPerUnit: 0.1 },
});

export const defaultProcessingForm = (): ProcessingFormData => ({
  facility: {
    facilityName: '',
    companyName: '',
    facilityType: 'General',
    country: 'Canada',
    region: '',
    locationType: 'Industrial',
    capacity: 10,
    hoursPerDay: 8,
    daysPerYear: 250,
  },
  products: [newProduct()],
  utilities: {
    elecKwhMonth: undefined,
    renewablePct: 0,
    fuelLMonth: undefined,
    fuelType: 'Diesel',
    waterM3Month: undefined,
    transportKm: 50,
    transportMode: 'Truck',
    solidWasteKgDay: undefined,
    wasteDisposalMethod: 'Landfill',
    allocationBasis: 'mass',
    refrigerantType: '',
    refrigerantKg: undefined,
  },
});

// ---- backend payload builder -----------------------------------------------------------
// Maps the (camelCase, form-friendly) ProcessingFormData to the snake_case request the
// /processing/assess endpoint expects. UI country -> backend country + engine region.
export function buildProcessingPayload(
  data: ProcessingFormData,
  countryMap: Record<string, { country: string; region: string }>,
  opts?: { facilityId?: string | null },
): Record<string, unknown> {
  const f = data.facility;
  const u = data.utilities;
  // Engine region must be the mapped code (GH/NG/CA). Free-text province/state in
  // facility.region must NOT override it — that used to send "Ontario" and cause the
  // engine to fall through to the Ghana default for Canada (country is sent as "Global").
  const mapped = countryMap[f.country] ?? { country: f.country, region: undefined };

  return {
    country: mapped.country,
    region: mapped.region,
    facility_id: opts?.facilityId ?? undefined,
    title: f.facilityName || f.companyName || undefined,
    allocation_basis: u.allocationBasis,
    facility_profile: {
      facility_name: f.facilityName.trim() || 'Facility',
      company_name: f.companyName?.trim() || f.facilityName.trim() || 'Company',
      facility_type: f.facilityType,
      processing_capacity: f.capacity,
      operational_hours_per_day: f.hoursPerDay,
      operational_days_per_year: f.daysPerYear,
      location_type: f.locationType,
      // Kept for display/rerun context only; not an engine region code.
      ...(f.region?.trim() ? { admin_region: f.region.trim() } : {}),
    },
    processing_operations: {
      energy_management: {
        monthly_electricity_consumption: u.elecKwhMonth || undefined,
        monthly_fuel_consumption: u.fuelLMonth || undefined,
        fuel_type: u.fuelType,
        renewable_energy_percentage: u.renewablePct || 0,
      },
      water_management: {
        monthly_water_consumption: u.waterM3Month || undefined,
      },
      waste_management: {
        solid_waste_generation: u.solidWasteKgDay || undefined,
        waste_disposal_method: u.wasteDisposalMethod,
      },
      raw_material_sourcing: {
        average_transport_distance: u.transportKm || 0,
        transport_mode: u.transportMode,
      },
      refrigerant_management: {
        refrigerant_type: u.refrigerantType?.trim() || undefined,
        annual_leakage_kg: u.refrigerantKg || undefined,
      },
    },
    processed_products: data.products.map((p, i) => ({
      id: `product_${i + 1}`,
      name: p.name.trim(),
      product_type: p.productType,
      annual_production: p.annualProduction,
      economic_value: p.pricePerKg || undefined,
      raw_material_inputs:
        p.rawMaterial?.trim() && (p.rawKgPerTonne ?? 0) > 0
          ? [{ material_name: p.rawMaterial.trim(), quantity_per_tonne_output: p.rawKgPerTonne }]
          : [],
      packaging: {
        packaging_material: p.packaging.material,
        package_size: p.packaging.packageSize,
        packaging_weight_per_unit: p.packaging.weightPerUnit,
      },
    })),
  };
}
