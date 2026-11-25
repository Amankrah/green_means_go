/**
 * processing-assessment-schema.ts: validation schema, form model, step config, and the
 * backend payload builder for the PROCESSING (facility) assessment.
 *
 * Shared by the single-page form and the multi-step wizard so both validate identically and
 * emit the same request shape. Mirrors the farm side (enhanced-assessment-schema.ts) and the
 * backend contract in app/processing/models.py.
 *
 * Only fields the validated engine actually consumes are collected: raw materials (blank ->
 * cited default conversion ratio), electricity and its supply, several fuel streams, water
 * source / treatment / wastewater, packaging, solid waste (organic share, by-products used),
 * inbound transport (blank distance -> default from the local-sourcing share), refrigerant,
 * and per-product price (economic co-product allocation). Capacity, operating hours and
 * location type are kept for the report only and are labelled so in the form.
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

export const FUEL_TYPES = [
  'Diesel', 'Diesel generator', 'Petrol', 'LPG', 'Natural gas', 'Kerosene', 'Biodiesel',
  'Firewood', 'Charcoal', 'Palm kernel shell', 'Palm fibre', 'Biogas',
] as const;
export const FUEL_UNITS = ['L', 'kg', 'm3', 'MJ'] as const;
// Natural unit per fuel, used as the default when a stream is added.
export const FUEL_DEFAULT_UNIT: Record<(typeof FUEL_TYPES)[number], (typeof FUEL_UNITS)[number]> = {
  'Diesel': 'L', 'Diesel generator': 'L', 'Petrol': 'L', 'LPG': 'kg', 'Natural gas': 'm3',
  'Kerosene': 'L', 'Biodiesel': 'L', 'Firewood': 'kg', 'Charcoal': 'kg', 'Palm kernel shell': 'kg',
  'Palm fibre': 'kg', 'Biogas': 'm3',
};

// Electricity supply (backend EnergySource values) -> which dataset the kWh are modelled with.
export const ELECTRICITY_SUPPLY = [
  'GridElectricity', 'DieselGenerator', 'SolarPower', 'HydroElectricity', 'WindPower',
] as const;
export const WATER_SOURCES = ['Municipal', 'Borehole', 'Well', 'River', 'Dam/Reservoir', 'Rainwater'] as const;
export const WATER_TREATMENTS = ['None', 'BasicFiltration', 'ChemicalTreatment', 'ReverseOsmosis', 'Comprehensive'] as const;
export const WASTEWATER_TREATMENTS = ['None', 'BasicSedimentation', 'BiologicalTreatment', 'ChemicalTreatment', 'Advanced'] as const;

export const ALLOCATION_BASES = ['mass', 'economic'] as const;

// Refrigerant designations the API accepts (engine/refrigerants.py KNOWN_REFRIGERANTS, AR6
// GWP100 table) plus "None". The backend rejects anything else, so no free text here.
export const REFRIGERANTS = [
  'HFC-134a', 'R-134a', 'HFC-125', 'R-125', 'HFC-143a', 'R-143a', 'HFC-32', 'R-32',
  'HFC-152a', 'R-152a', 'HCFC-22', 'R-22', 'R-717', 'Ammonia', 'NH3', 'R-744', 'CO2',
  'R-290', 'Propane', 'R-600a', 'Isobutane', 'R-1234yf', 'R-1234ze',
  'R-404A', 'R-410A', 'R-407C', 'R-507A', 'R-448A', 'R-449A', 'R-513A',
] as const;
export const REFRIGERANT_OPTIONS = ['None', ...REFRIGERANTS] as const;

// Product types with a cited default raw-material conversion ratio (engine/conversion_ratios.py
// DEFAULT_RATIOS); "Other" resolves through the facility type (FACILITY_DEFAULT_PRODUCT).
// Any other combination must declare a raw material, or the API refuses the request.
export const PRODUCT_TYPES_WITH_DEFAULT_RATIO = [
  'PalmOil', 'CocoaPowder', 'CocoaButter', 'FlourMaize', 'FlourWheat', 'RiceProcessed', 'FlourCassava',
] as const;
export const FACILITY_DEFAULT_PRODUCT: Partial<Record<(typeof FACILITY_TYPES)[number], (typeof PRODUCT_TYPES)[number]>> = {
  PalmOilMill: 'PalmOil',
  CocoaProcessing: 'CocoaPowder',
  RiceProcessing: 'RiceProcessed',
  CassivaProcessing: 'FlourCassava',
};

export function hasDefaultConversionRatio(productType: string | undefined, facilityType: string | undefined): boolean {
  let ptype = productType || 'Other';
  if (ptype === 'Other' && facilityType) {
    ptype = FACILITY_DEFAULT_PRODUCT[facilityType as (typeof FACILITY_TYPES)[number]] ?? ptype;
  }
  return (PRODUCT_TYPES_WITH_DEFAULT_RATIO as readonly string[]).includes(ptype);
}

/** Index and message for every product that needs a raw material but has none (mirrors the API completeness gate). */
export function missingRawMaterialIssues(
  products: ReadonlyArray<{ productType?: string; rawMaterial?: string; rawKgPerTonne?: unknown }>,
  facilityType: string | undefined,
): Array<{ index: number; message: string }> {
  const out: Array<{ index: number; message: string }> = [];
  products.forEach((p, index) => {
    const kg = toNum(p.rawKgPerTonne);
    const declared = !!p.rawMaterial?.trim() && typeof kg === 'number' && kg > 0;
    if (!declared && !hasDefaultConversionRatio(p.productType, facilityType)) {
      out.push({
        index,
        message: 'This product type has no default conversion ratio: enter its main raw material and the kg per tonne of product',
      });
    }
  });
  return out;
}

// UI countries (the page maps these to the backend country + engine region via COUNTRY_TO_REGION).
export const COUNTRIES = ['Canada', 'Ghana', 'Nigeria', 'Senegal', 'Burkina Faso', 'South Africa'] as const;

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
  hoursPerDay: z.preprocess(toNum, z.number({ message: 'Operating hours per day must be greater than zero' })
    .positive('Operating hours per day must be greater than zero')
    .max(24, 'Operating hours per day cannot exceed 24')),
  // The API stores this as an integer and scales daily solid waste by it.
  daysPerYear: z.preprocess(toNum, z.number({ message: 'Operating days per year must be greater than zero' })
    .int('Operating days per year must be a whole number')
    .min(1, 'Operating days per year must be at least 1')
    .max(366, 'Operating days per year cannot exceed 366')),
});

// Packaging is explicit: either the user states the product leaves unpackaged (bulk), or
// types the numbers (no prefilled bag). The API models a product without packaging as
// unpackaged and adds no packaging row.
export const packagingSchema = z.object({
  material: z.enum(PACKAGING_MATERIALS),
  packageSize: optNonNeg('Package size cannot be negative'),
  weightPerUnit: optNonNeg('Packaging weight cannot be negative'),
});

export const productSchema = z.object({
  name: z.string().trim().min(1, 'Product name is required').max(120),
  productType: z.enum(PRODUCT_TYPES),
  annualProduction: reqPositive('Annual output must be greater than zero'), // tonnes
  rawMaterial: z.string().trim().max(120).optional(),
  rawKgPerTonne: optNonNeg('Raw material amount cannot be negative'),       // kg per tonne output
  pricePerKg: optNonNeg('Price cannot be negative'),                        // economic_value
  packaged: z.boolean().default(true),
  packaging: packagingSchema,
}).superRefine((p, ctx) => {
  // A packaged product needs real packaging numbers; an unpackaged one sends none.
  if (p.packaged) {
    if (!(typeof p.packaging.packageSize === 'number' && p.packaging.packageSize > 0)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Package size must be greater than zero (or mark the product as unpackaged)', path: ['packaging', 'packageSize'] });
    }
    if (!(typeof p.packaging.weightPerUnit === 'number' && p.packaging.weightPerUnit > 0)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: 'Packaging weight must be greater than zero (or mark the product as unpackaged)', path: ['packaging', 'weightPerUnit'] });
    }
  }
  // A raw material needs both its name and its amount; a half-filled pair used to be
  // dropped silently by the payload builder.
  const hasName = !!p.rawMaterial?.trim();
  const hasKg = typeof p.rawKgPerTonne === 'number' && p.rawKgPerTonne > 0;
  if (hasName && !hasKg) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Enter the kg of this raw material per tonne of product (or clear the name to use the default ratio)',
      path: ['rawKgPerTonne'],
    });
  }
  if (!hasName && hasKg) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Name the raw material this amount refers to (or clear the amount to use the default ratio)',
      path: ['rawMaterial'],
    });
  }
});

const optPct = (msg: string) =>
  z.preprocess(toNum, z.number().min(0).max(100, msg).optional()).optional();

// A fuel line the user adds must carry an amount; empty lines are not sent.
export const fuelStreamSchema = z.object({
  fuelType: z.enum(FUEL_TYPES),
  amountMonth: z.preprocess(toNum, z.number({ message: 'Enter the monthly amount for this fuel' })
    .positive('Fuel amount must be greater than zero')
    .max(1_000_000, 'Please verify the fuel amount')),
  unit: z.enum(FUEL_UNITS),
});

export const utilitiesSchema = z.object({
  elecKwhMonth: optNonNeg('Electricity cannot be negative'),
  electricitySupply: z.enum(ELECTRICITY_SUPPLY),
  renewablePct: optPct('Renewable share is a percentage (0-100)'),
  fuelStreams: z.array(fuelStreamSchema),
  waterM3Month: optNonNeg('Water cannot be negative'),
  waterSource: z.enum(WATER_SOURCES),
  waterTreatment: z.enum(WATER_TREATMENTS),
  wastewaterTreatment: z.enum(WASTEWATER_TREATMENTS),
  transportKm: optNonNeg('Distance cannot be negative'),
  localSourcingPct: optPct('Local share is a percentage (0-100)'),
  transportMode: z.enum(TRANSPORT_MODES),
  solidWasteKgDay: optNonNeg('Solid waste cannot be negative'),
  organicWastePct: optPct('Organic share is a percentage (0-100)'),
  byproductPct: optPct('By-product share is a percentage (0-100)'),
  byproductName: z.string().trim().max(80).optional(),
  wasteDisposalMethod: z.enum(WASTE_DISPOSAL_METHODS),
  allocationBasis: z.enum(ALLOCATION_BASES),
  refrigerantType: z.enum(REFRIGERANT_OPTIONS).default('None'),
  refrigerantKg: optNonNeg('Leakage cannot be negative'),
}).superRefine((u, ctx) => {
  // A leak amount is meaningless without the gas: the GWP comes from the designation.
  if (typeof u.refrigerantKg === 'number' && u.refrigerantKg > 0 && (!u.refrigerantType || u.refrigerantType === 'None')) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Select the refrigerant gas for the leakage entered',
      path: ['refrigerantType'],
    });
  }
  // A facility with no energy input at all is not an assessable facility: require either
  // metered electricity or at least one fuel line.
  const hasElectricity = typeof u.elecKwhMonth === 'number' && u.elecKwhMonth > 0;
  const hasFuel = (u.fuelStreams ?? []).some((f) => typeof f.amountMonth === 'number' && f.amountMonth > 0);
  if (!hasElectricity && !hasFuel) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: 'Enter the monthly electricity use or add at least one fuel burned on site',
      path: ['elecKwhMonth'],
    });
  }
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
    // Mirror of the API completeness gate (also run by the wizard on the Products step).
    for (const issue of missingRawMaterialIssues(data.products, data.facility.facilityType)) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, message: issue.message, path: ['products', issue.index, 'rawMaterial'] });
    }
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
  // Packaging numbers are entered by the user, never prefilled.
  packaged: true,
  packaging: { material: 'PlasticBag', packageSize: undefined, weightPerUnit: undefined },
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
    electricitySupply: 'GridElectricity',
    renewablePct: 0,
    fuelStreams: [],
    waterM3Month: undefined,
    waterSource: 'Municipal',
    waterTreatment: 'BasicFiltration',
    wastewaterTreatment: 'BasicSedimentation',
    transportKm: undefined,
    localSourcingPct: 80,
    transportMode: 'Truck',
    solidWasteKgDay: undefined,
    organicWastePct: 70,
    byproductPct: 0,
    byproductName: '',
    wasteDisposalMethod: 'Landfill',
    allocationBasis: 'mass',
    refrigerantType: 'None',
    refrigerantKg: undefined,
  },
});

// ---- backend payload builder -----------------------------------------------------------
// Maps the (camelCase, form-friendly) ProcessingFormData to the snake_case request the
// /processing/assess endpoint expects. UI country -> backend country + engine region.
export function buildProcessingPayload(
  data: ProcessingFormData,
  countryMap: Record<string, { country: string; region: string }>,
  opts?: { facilityId?: string | null; formSnapshot?: unknown },
): Record<string, unknown> {
  const f = data.facility;
  const u = data.utilities;
  // Engine region must be the mapped code (GH/NG/CA). Free-text province/state in
  // facility.region must NOT override it: that used to send "Ontario" and cause the
  // engine to fall through to the Ghana default for Canada (country is sent as "Global").
  const mapped = countryMap[f.country] ?? { country: f.country, region: undefined };

  return {
    country: mapped.country,
    region: mapped.region,
    facility_id: opts?.facilityId ?? undefined,
    title: f.facilityName || f.companyName || undefined,
    // Opaque wizard snapshot so the saved assessment can be reopened for editing (the API
    // accepts form_snapshot on processing requests just as on farm requests).
    ...(opts?.formSnapshot !== undefined ? { form_snapshot: opts.formSnapshot } : {}),
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
        primary_energy_source: u.electricitySupply,
        monthly_electricity_consumption: u.elecKwhMonth || undefined,
        renewable_energy_percentage: u.renewablePct || 0,
        fuel_streams: (u.fuelStreams ?? [])
          .filter((f) => (f.amountMonth ?? 0) > 0)
          .map((f) => ({ fuel_type: f.fuelType, monthly_consumption: f.amountMonth, unit: f.unit })),
      },
      water_management: {
        monthly_water_consumption: u.waterM3Month || undefined,
        water_source: [u.waterSource],
        water_treatment: u.waterTreatment,
        wastewater_treatment: u.wastewaterTreatment,
      },
      waste_management: {
        solid_waste_generation: u.solidWasteKgDay || undefined,
        organic_waste_percentage: u.organicWastePct ?? 70,
        waste_disposal_method: u.wasteDisposalMethod,
        byproduct_utilization: (u.byproductPct ?? 0) > 0
          ? [{ byproduct_name: u.byproductName?.trim() || 'By-product', utilization_method: 'reused or sold',
               percentage_utilized: u.byproductPct }]
          : [],
      },
      raw_material_sourcing: {
        // Blank or 0 distance -> the engine's cited default from the local-sourcing share
        // (same rule as every other quantity here, and what the review step says).
        average_transport_distance: u.transportKm || undefined,
        local_sourcing_percentage: u.localSourcingPct ?? 80,
        transport_mode: u.transportMode,
      },
      refrigerant_management: {
        // Only a named gas is sent; "None" (the default) means no refrigerant on site.
        refrigerant_type: u.refrigerantType && u.refrigerantType !== 'None' ? u.refrigerantType : undefined,
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
      // Sent only for a packaged product with its numbers filled; omitted means unpackaged
      // (the API adds no packaging row and says so in its notes).
      ...(p.packaged && (p.packaging.packageSize ?? 0) > 0 && (p.packaging.weightPerUnit ?? 0) > 0
        ? {
            packaging: {
              packaging_material: p.packaging.material,
              package_size: p.packaging.packageSize,
              packaging_weight_per_unit: p.packaging.weightPerUnit,
            },
          }
        : {}),
    })),
  };
}
