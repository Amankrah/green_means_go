/**
 * Region display data for the wizard: the engine regions (engine/regions.py), how each
 * UI country maps onto the API (country bucket + engine region code), its currency and
 * units, administrative regions for the region picker, and common crops by region.
 *
 * Backend contract: the API and the Rust kernel only accept the country buckets
 * "Ghana" / "Nigeria" / "Global". Every other country is sent as "Global" plus its
 * engine region code (Canada -> CA, Senegal -> SN, Burkina Faso -> BF, South Africa -> ZA),
 * which engine/service.py resolves via the region registry.
 */

export type RegionCode = 'GH' | 'NG' | 'SN' | 'BF' | 'ZA' | 'CA';

export interface RegionInfo {
  code: RegionCode;
  /** UI country label (also the value stored in the form). */
  country: string;
  /** Country bucket the API accepts. */
  backendCountry: 'Ghana' | 'Nigeria' | 'Global';
  /** ISO 4217 code, matches engine/regions.py `currency`. */
  currency: string;
  currencySymbol: string;
  currencyName: string;
  /** Unit conventions shown next to inputs. */
  units: { area: string; yield: string; fertiliser: string; fuel: string; electricity: string };
  /** IPCC climate zone shown in the UI (engine/regions.py climate_zone). */
  climateZone: string;
}

const METRIC = { area: 'ha', yield: 'kg/ha', fertiliser: 'kg/ha', fuel: 'L', electricity: 'kWh' };

export const REGION_INFO: Record<RegionCode, RegionInfo> = {
  GH: { code: 'GH', country: 'Ghana', backendCountry: 'Ghana', currency: 'GHS', currencySymbol: 'GH₵', currencyName: 'Ghana Cedi', units: METRIC, climateZone: 'wet tropical' },
  NG: { code: 'NG', country: 'Nigeria', backendCountry: 'Nigeria', currency: 'NGN', currencySymbol: '₦', currencyName: 'Nigerian Naira', units: METRIC, climateZone: 'wet/dry tropical' },
  SN: { code: 'SN', country: 'Senegal', backendCountry: 'Global', currency: 'XOF', currencySymbol: 'FCFA', currencyName: 'West African CFA franc', units: METRIC, climateZone: 'dry tropical' },
  BF: { code: 'BF', country: 'Burkina Faso', backendCountry: 'Global', currency: 'XOF', currencySymbol: 'FCFA', currencyName: 'West African CFA franc', units: METRIC, climateZone: 'dry tropical' },
  ZA: { code: 'ZA', country: 'South Africa', backendCountry: 'Global', currency: 'ZAR', currencySymbol: 'R', currencyName: 'South African Rand', units: METRIC, climateZone: 'warm temperate dry' },
  CA: { code: 'CA', country: 'Canada', backendCountry: 'Global', currency: 'CAD', currencySymbol: 'CA$', currencyName: 'Canadian Dollar', units: METRIC, climateZone: 'cool temperate' },
};

/** The countries added in workstream 3b, in picker order. */
export const NEW_REGION_COUNTRIES = ['Senegal', 'Burkina Faso', 'South Africa'] as const;
export type NewRegionCountry = (typeof NEW_REGION_COUNTRIES)[number];

/** All UI countries in picker order. */
export const ALL_COUNTRIES = ['Ghana', 'Nigeria', 'Senegal', 'Burkina Faso', 'South Africa', 'Canada'] as const;

export function regionForCountry(country: string | undefined | null): RegionInfo | undefined {
  if (!country) return undefined;
  return Object.values(REGION_INFO).find((r) => r.country === country);
}

/** UI country -> { API country, engine region } for the new countries. */
export const NEW_COUNTRY_TO_REGION: Record<string, { country: string; region: string }> =
  Object.fromEntries(
    NEW_REGION_COUNTRIES.map((c) => {
      const r = regionForCountry(c)!;
      return [c, { country: r.backendCountry, region: r.code }];
    }),
  );

/** Administrative regions for the region/state picker. */
export const NEW_REGIONS_BY_COUNTRY: Record<NewRegionCountry, string[]> = {
  Senegal: [
    'Dakar', 'Diourbel', 'Fatick', 'Kaffrine', 'Kaolack', 'Kedougou', 'Kolda', 'Louga',
    'Matam', 'Saint-Louis', 'Sedhiou', 'Tambacounda', 'Thies', 'Ziguinchor',
  ],
  'Burkina Faso': [
    'Boucle du Mouhoun', 'Cascades', 'Centre', 'Centre-Est', 'Centre-Nord', 'Centre-Ouest',
    'Centre-Sud', 'Est', 'Hauts-Bassins', 'Nord', 'Plateau-Central', 'Sahel', 'Sud-Ouest',
  ],
  'South Africa': [
    'Eastern Cape', 'Free State', 'Gauteng', 'KwaZulu-Natal', 'Limpopo', 'Mpumalanga',
    'North West', 'Northern Cape', 'Western Cape',
  ],
};

/** Common crops by country (team brief 3b). Names match the crop picker vocabulary. */
export const NEW_COMMON_CROPS: Record<NewRegionCountry, string[]> = {
  Senegal: ['Groundnuts', 'Millet', 'Rice', 'Tomato', 'Onion'],
  'Burkina Faso': ['Cotton', 'Maize', 'Sorghum', 'Sesame', 'Tomato'],
  'South Africa': ['Maize', 'Sugarcane', 'Citrus', 'Grapes', 'Deciduous fruit (apples, pears)'],
};

export function commonCropsForCountry(country: string | undefined | null): string[] {
  return (country && (NEW_COMMON_CROPS as Record<string, string[]>)[country]) || [];
}

/** e.g. formatMoney(30000, 'Senegal') -> "30,000 FCFA"; "R 1,250" for South Africa. */
export function formatMoney(amount: number, country: string | undefined | null): string {
  const r = regionForCountry(country);
  const n = amount.toLocaleString('en-US', { maximumFractionDigits: 2 });
  if (!r) return n;
  return r.currency === 'XOF' ? `${n} ${r.currencySymbol}` : `${r.currencySymbol} ${n}`;
}
