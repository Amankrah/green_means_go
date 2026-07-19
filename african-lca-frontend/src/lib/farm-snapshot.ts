import type { AssessmentRequestArchive } from '@/lib/api';

export interface FarmSnapshotCrop {
  name: string;
  areaHa: number | null;
  productionKg: number | null;
  productionSystem: string | null;
  croppingPattern: string | null;
  partners?: string[];
}

export interface FarmSnapshot {
  assessedSizeHa: number | null;
  farmType: string | null;
  primaryFarmingSystem: string | null;
  crops: FarmSnapshotCrop[];
  allocatedHa: number;
  unallocatedHa: number;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value;
  if (typeof value === 'string' && value.trim() !== '') {
    const n = Number(value);
    return Number.isFinite(n) ? n : null;
  }
  return null;
}

function asString(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function asStringArray(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) return undefined;
  const items = value
    .map((v) => (typeof v === 'string' ? v.trim() : ''))
    .filter(Boolean);
  return items.length ? items : undefined;
}

function cropsFromForm(form: Record<string, unknown> | null): FarmSnapshotCrop[] {
  if (!form) return [];
  const list = form.cropProductions;
  if (!Array.isArray(list)) return [];

  return list
    .map((raw): FarmSnapshotCrop | null => {
      const row = asRecord(raw);
      if (!row) return null;
      const name = asString(row.cropName) || asString(row.name);
      if (!name) return null;
      return {
        name,
        areaHa: asNumber(row.areaAllocated),
        productionKg: asNumber(row.annualProduction),
        productionSystem: asString(row.productionSystem),
        croppingPattern: asString(row.croppingPattern),
        partners: asStringArray(row.intercroppingPartners),
      };
    })
    .filter((c): c is FarmSnapshotCrop => c != null);
}

function cropsFromApi(api: Record<string, unknown> | null): FarmSnapshotCrop[] {
  if (!api) return [];
  const list = api.foods;
  if (!Array.isArray(list)) return [];

  return list
    .map((raw): FarmSnapshotCrop | null => {
      const row = asRecord(raw);
      if (!row) return null;
      const name = asString(row.name);
      if (!name) return null;
      return {
        name,
        areaHa: asNumber(row.area_allocated),
        productionKg: asNumber(row.quantity_kg),
        productionSystem: asString(row.production_system),
        croppingPattern: asString(row.cropping_pattern),
        partners: asStringArray(row.intercropping_partners),
      };
    })
    .filter((c): c is FarmSnapshotCrop => c != null);
}

/**
 * Normalize size/crop details from a stored assessment request archive.
 * Prefers the wizard form snapshot; falls back to the API payload.
 */
export function normalizeFarmSnapshot(
  archive: AssessmentRequestArchive
): FarmSnapshot {
  const form = asRecord(archive.form);
  const api = asRecord(archive.api);

  const formProfile = asRecord(form?.farmProfile);
  const apiProfile = asRecord(api?.farm_profile);

  const assessedSizeHa =
    asNumber(formProfile?.totalFarmSize) ??
    asNumber(apiProfile?.total_farm_size);

  const farmType =
    asString(formProfile?.farmType) ?? asString(apiProfile?.farm_type);
  const primaryFarmingSystem =
    asString(formProfile?.primaryFarmingSystem) ??
    asString(apiProfile?.primary_farming_system);

  const formCrops = cropsFromForm(form);
  const crops = formCrops.length > 0 ? formCrops : cropsFromApi(api);

  const allocatedHa = crops.reduce((sum, c) => sum + (c.areaHa ?? 0), 0);
  const unallocatedHa =
    assessedSizeHa != null ? Math.max(0, assessedSizeHa - allocatedHa) : 0;

  return {
    assessedSizeHa,
    farmType,
    primaryFarmingSystem,
    crops,
    allocatedHa,
    unallocatedHa,
  };
}
