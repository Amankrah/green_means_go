/**
 * seasonal-factor.ts - derive the engine's `seasonal_factor` (WetSeason | DrySeason |
 * YearRound) from the crop's planting months and the country's rainy season.
 *
 * The engine uses the factor to pick the irrigated share of the crop water need when no
 * measured irrigation volume is given (engine/crop_defaults.py IRRIGATION_SHARE: wet 0.5,
 * dry and year-round 1.0). It used to be hard-wired to WetSeason with no user control.
 *
 * Rainy-season months per country (calendar months, 1 = January):
 *   Ghana, Nigeria   April to October  (unimodal north May to Oct; bimodal south Apr to Jul
 *                    and Sep to Nov; the union is used)
 *   Senegal          July to October   (Sahelian single wet season)
 *   Burkina Faso     June to September (Sudano-Sahelian single wet season)
 *   South Africa     October to March  (summer-rainfall interior; the Western Cape winter
 *                    rainfall region is the exception and is not modelled separately)
 *   Canada           May to September  (frost-free growing season; no tropical dry season)
 */
export type SeasonalFactor = 'WetSeason' | 'DrySeason' | 'YearRound';

export const WET_SEASON_MONTHS: Record<string, readonly number[]> = {
  Ghana: [4, 5, 6, 7, 8, 9, 10],
  Nigeria: [4, 5, 6, 7, 8, 9, 10],
  Senegal: [7, 8, 9, 10],
  'Burkina Faso': [6, 7, 8, 9],
  'South Africa': [10, 11, 12, 1, 2, 3],
  Canada: [5, 6, 7, 8, 9],
};

const DEFAULT_WET_MONTHS: readonly number[] = [4, 5, 6, 7, 8, 9, 10];

/**
 * Rule: every planting month inside the rainy season -> WetSeason; none inside -> DrySeason;
 * a mix (or two plantings straddling both seasons) -> YearRound. With no planting months
 * selected yet the previous default (WetSeason) is returned.
 */
export function deriveSeasonalFactor(
  country: string | undefined | null,
  plantingMonths: ReadonlyArray<number | string> | undefined | null,
): SeasonalFactor {
  const wet = new Set(WET_SEASON_MONTHS[country ?? ''] ?? DEFAULT_WET_MONTHS);
  const months = (plantingMonths ?? [])
    .map((m) => Number(m))
    .filter((m) => Number.isInteger(m) && m >= 1 && m <= 12);
  if (months.length === 0) return 'WetSeason';
  const inWet = months.filter((m) => wet.has(m)).length;
  if (inWet === months.length) return 'WetSeason';
  if (inWet === 0) return 'DrySeason';
  return 'YearRound';
}

export function seasonalFactorLabel(factor: SeasonalFactor): string {
  switch (factor) {
    case 'WetSeason':
      return 'Wet season (rain-fed share of crop water need)';
    case 'DrySeason':
      return 'Dry season (crop water need fully irrigated)';
    default:
      return 'Year round (plantings in both seasons; fully irrigated)';
  }
}
