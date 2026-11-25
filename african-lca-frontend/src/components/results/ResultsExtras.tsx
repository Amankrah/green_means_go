'use client';

// Panels for engine outputs added after the original results page: the publication gate,
// multi-product functional units, soil carbon from management, and the packaged
// sensitivity cases. Every field is optional so older saved assessments render unchanged.

import React from 'react';
import { AlertTriangle, Layers, Sprout, SlidersHorizontal, Scale } from 'lucide-react';
import type {
  AssessmentResult,
  PerCropFunctionalUnit,
  SocManagement,
  OneAtATimeCase,
  MethodSensitivity,
} from '@/types/assessment';

const BAND_LESS = new Set(['Unavailable', 'Not banded']);

/** True when the single score has a usable Low/Moderate/High band (and cutoffs to draw a gauge). */
export function hasUsableBand(score: AssessmentResult['single_score'] | undefined): boolean {
  const band = score?.band;
  if (!band || BAND_LESS.has(band)) return false;
  const c = score?.band_cutoffs;
  if (c && (c.low == null || c.high == null)) return false;
  return true;
}

export function isMultiProductHeadline(results: AssessmentResult): boolean {
  return results.functional_units?.headline === 'per_ha';
}

function fmt(n: number | null | undefined, digits = 3): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return '—';
  if (n === 0) return '0';
  const a = Math.abs(n);
  if (a < 1e-3 || a >= 1e6) return n.toExponential(2);
  return Number(n.toPrecision(digits)).toLocaleString();
}

function pct(n: number | null | undefined): string {
  if (n === null || n === undefined || !Number.isFinite(n)) return '—';
  return `${n > 0 ? '+' : ''}${n.toFixed(1)}%`;
}

export function ReviewBanner({ results }: { results: AssessmentResult }) {
  const items = results.review_items ?? [];
  if (!results.review_required && !results.needs_review) return null;
  return (
    <div className="mb-8 rounded-2xl border-2 border-amber-300 bg-amber-50 p-5">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-6 h-6 text-amber-600 flex-shrink-0 mt-0.5" />
        <div className="min-w-0">
          <p className="font-bold text-amber-900">
            Needs review before it is published
          </p>
          <p className="text-sm text-amber-800 mt-1">
            {items.length > 0
              ? `${items.length} input(s) were matched to background datasets that an LCA practitioner should confirm.`
              : 'Some background dataset choices are flagged for review.'}{' '}
            The numbers are a draft until those choices are checked.
          </p>
          {items.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm text-amber-900">
              {items.slice(0, 8).map((it, i) => (
                <li key={i} className="break-words">
                  <span className="font-medium">{it.input || 'Input'}</span>
                  {it.matched ? <> matched to <span className="italic">{it.matched}</span></> : null}
                  {it.reason ? <span className="text-amber-700"> ({it.reason})</span> : null}
                  {it.excluded ? <span className="text-amber-700"> · excluded: {String(it.excluded)}</span> : null}
                </li>
              ))}
              {items.length > 8 && <li className="text-amber-700">… and {items.length - 8} more</li>}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

const PER_CROP_CATEGORIES = ['Global warming', 'Land use', 'Water consumption'];

export function PerCropTable({ results }: { results: AssessmentResult }) {
  const perCrop = results.functional_units?.per_crop;
  const rows = perCrop ? Object.entries(perCrop) : [];
  if (rows.length === 0) return null;
  const multi = isMultiProductHeadline(results);
  const unitOf = (r: PerCropFunctionalUnit, cat: string) =>
    (r.midpoint_impacts_per_kg?.[cat]?.unit || '').replace(/\s*per kg$/, '');
  const firstWithUnits = rows.find(([, r]) => r.midpoint_impacts_per_kg)?.[1];
  return (
    <div className="mb-12 bg-white rounded-2xl p-8 shadow-lg">
      <h3 className="text-2xl font-bold text-gray-900 mb-2 flex items-center">
        <Layers className="w-6 h-6 text-green-600 mr-3" />
        Results per crop
      </h3>
      <p className="text-sm text-gray-600 mb-4 max-w-3xl">
        {multi
          ? 'This farm grows several different products, so the footprint per kilogram is given for each crop on its own. Each crop carries only the inputs you linked to it. The whole farm is compared per hectare.'
          : 'Footprint of each crop per kilogram of that crop.'}
      </p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
          <thead className="bg-gray-50">
            <tr>
              <th className="text-left font-semibold text-gray-600 px-3 py-2 border-b">Crop</th>
              <th className="text-right font-semibold text-gray-600 px-3 py-2 border-b">Harvest (kg)</th>
              <th className="text-right font-semibold text-gray-600 px-3 py-2 border-b">Area (ha)</th>
              {PER_CROP_CATEGORIES.map((c) => (
                <th key={c} className="text-right font-semibold text-gray-600 px-3 py-2 border-b">
                  {c}
                  <span className="block font-normal text-xs text-gray-400">
                    {(firstWithUnits && unitOf(firstWithUnits, c)) || ''} per kg
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map(([label, r]) => (
              <tr key={label} className="odd:bg-white even:bg-gray-50/50">
                <td className="px-3 py-2 border-b border-gray-100 font-medium text-gray-900">{r.name || label}</td>
                <td className="px-3 py-2 border-b border-gray-100 text-right">{fmt(r.quantity_kg, 6)}</td>
                <td className="px-3 py-2 border-b border-gray-100 text-right">{fmt(r.area_ha, 4)}</td>
                {PER_CROP_CATEGORIES.map((c) => (
                  <td key={c} className="px-3 py-2 border-b border-gray-100 text-right font-mono">
                    {fmt(r.midpoint_impacts_per_kg?.[c]?.value)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** [low, high] when it is a real (non-degenerate) numeric range, else null. */
export function socRange(r: unknown): [number, number] | null {
  if (!Array.isArray(r) || r.length !== 2) return null;
  const [lo, hi] = r.map(Number);
  if (!Number.isFinite(lo) || !Number.isFinite(hi) || Math.abs(hi - lo) < 1e-9) return null;
  return [Math.min(lo, hi), Math.max(lo, hi)];
}

const signed = (n: number, digits = 4) => `${n > 0 ? '+' : ''}${fmt(n, digits)}`;

export function SocManagementCard({ soc }: { soc?: SocManagement | null }) {
  if (!soc || typeof soc !== 'object') return null;
  const booked = soc.booked === true && typeof soc.value === 'number';
  const value = soc.value ?? 0;
  const range = socRange(soc.value_range);
  return (
    <div className="mb-12 rounded-2xl border border-emerald-200 bg-emerald-50/50 p-6">
      <h3 className="text-xl font-bold text-gray-900 mb-1 flex items-center">
        <Sprout className="w-5 h-5 text-emerald-600 mr-2" />
        Soil carbon from management
      </h3>
      <p className="text-sm text-gray-600 mb-4">
        Reported separately (ISO 14067), not included in the headline.
      </p>
      {booked ? (
        <div className="flex flex-col sm:flex-row sm:items-end gap-4">
          <div>
            <div className={`text-3xl font-bold ${value < 0 ? 'text-emerald-700' : value > 0 ? 'text-red-700' : 'text-gray-800'}`}>
              {value > 0 ? '+' : ''}{fmt(value, 4)} <span className="text-base font-semibold">{soc.unit || 'kg CO2/yr'}</span>
            </div>
            {range && (
              <div className="text-sm text-gray-700 mt-1">
                Range {signed(range[0])} to {signed(range[1])} {soc.unit || 'kg CO2/yr'}
                <span className="text-xs text-gray-500"> (where your inputs fit more than one IPCC input class; not averaged)</span>
              </div>
            )}
            <div className="text-xs text-gray-600 mt-1">
              {soc.sign_convention || '+ = emission, - = removal'}
              {value < 0 ? ' · the soil is gaining carbon' : value > 0 ? ' · the soil is losing carbon' : ''}
            </div>
          </div>
          <div className="text-sm text-gray-700 sm:ml-auto space-y-0.5">
            {typeof soc.years_remaining_in_transition === 'number' && (
              <div>{soc.years_remaining_in_transition.toFixed(0)} years left in the 20-year transition</div>
            )}
            {soc.method && <div className="text-xs text-gray-500">{soc.method}</div>}
          </div>
        </div>
      ) : (
        <p className="text-sm text-gray-800">
          Not calculated for this farm: {soc.assumptions?.[0] || 'inputs for the stock-change method were incomplete'}.
        </p>
      )}
      {booked && (soc.per_crop?.length ?? 0) > 0 && (
        <ul className="mt-4 text-xs text-gray-700 space-y-2">
          {soc.per_crop!.map((c, i) => {
            const cr = socRange(c.value_range);
            const alts = (c.input_alternatives ?? []).filter((a) => a && (a.input || a.why));
            return (
              <li key={i}>
                <span className="font-medium">{c.crop || `Crop ${i + 1}`}</span>:{' '}
                {c.value == null ? (c.note || 'not calculated') : `${signed(c.value)} ${soc.unit || 'kg CO2/yr'}`}
                {cr && ` (range ${signed(cr[0])} to ${signed(cr[1])})`}
                {c.tillage ? ` · tillage: ${c.tillage}` : ''}
                {c.input ? ` · input class: ${c.input}` : ''}
                {(c.input_definition || c.input_reason) && (
                  <div className="text-gray-500 mt-0.5">
                    {c.input_definition}{c.input_definition && c.input_reason ? ' ' : ''}{c.input_reason ? `(${c.input_reason})` : ''}
                  </div>
                )}
                {alts.map((a, j) => (
                  <div key={j} className="text-gray-500 mt-0.5">
                    Alternative class {a.input || ''}{typeof a.value === 'number' ? `: ${signed(a.value)} ${soc.unit || 'kg CO2/yr'}` : ''}
                    {a.why ? ` (${a.why})` : ''}
                  </div>
                ))}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export function SensitivityCases({
  cases,
  methodSensitivity,
  note,
}: {
  cases?: OneAtATimeCase[];
  methodSensitivity?: MethodSensitivity | null;
  note?: string;
}) {
  const rows = Array.isArray(cases) ? cases : [];
  if (rows.length === 0 && !methodSensitivity) return null;
  const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.global_warming_change_pct ?? 0)));
  return (
    <div className="mb-12 bg-white rounded-2xl p-8 shadow-lg border border-gray-200">
      <h3 className="text-2xl font-bold text-gray-900 mb-2 flex items-center">
        <SlidersHorizontal className="w-6 h-6 text-green-600 mr-3" />
        How sensitive is the climate result?
      </h3>
      <p className="text-sm text-gray-600 mb-6 max-w-3xl">
        Change in climate impact per kg when one assumption is moved to its published low or high
        value (IPCC 2019 ranges) or when the yield is 20% higher or lower.
      </p>
      {rows.length > 0 && (
        <div className="space-y-2">
          {rows.map((r, i) => {
            const v = r.global_warming_change_pct ?? 0;
            const half = (Math.abs(v) / maxAbs) * 50;
            return (
              <div key={i} className="flex items-center gap-3 text-sm">
                <span className="w-36 shrink-0 text-gray-800" title={r.source}>{r.case}</span>
                <div className="relative flex-1 h-4 rounded bg-gray-50">
                  <div className="absolute left-1/2 top-0 bottom-0 w-px bg-gray-300" />
                  <div
                    className={`absolute top-0 bottom-0 rounded-sm ${v > 0 ? 'bg-red-400' : 'bg-green-500'}`}
                    style={v > 0 ? { left: '50%', width: `${half}%` } : { right: '50%', width: `${half}%` }}
                  />
                </div>
                <span className={`w-16 shrink-0 text-right font-mono ${v > 0 ? 'text-red-600' : 'text-green-700'}`}>
                  {pct(r.global_warming_change_pct)}
                </span>
              </div>
            );
          })}
        </div>
      )}
      {methodSensitivity && (
        <div className="mt-6 rounded-xl bg-gray-50 border border-gray-200 p-4 text-sm">
          <div className="font-semibold text-gray-900 mb-1 flex items-center">
            <Scale className="w-4 h-4 mr-1.5 text-gray-600" /> Choice of impact method
          </div>
          <p className="text-gray-700">
            Climate per kg: {fmt(methodSensitivity.global_warming_current)} ({methodSensitivity.current_method || 'current method'})
            {' '}vs {fmt(methodSensitivity.global_warming_alternative)} ({methodSensitivity.alternative_method || 'alternative'})
            {methodSensitivity.change_pct != null && <> · {pct(methodSensitivity.change_pct)}</>}
          </p>
          {methodSensitivity.note && <p className="text-xs text-gray-500 mt-1">{methodSensitivity.note}</p>}
        </div>
      )}
      {note && <p className="text-xs text-gray-400 mt-4">{note}</p>}
    </div>
  );
}

type PerCropResultRow = {
  crop?: string;
  quantity_kg?: number | null;
  area_ha?: number | null;
  global_warming_total_kg_co2e?: number | null;
  global_warming_per_kg?: number | null;
};

/** Per-crop climate rows from the service (shown only when functional_units.per_crop is absent). */
export function PerCropResults({ data }: { data: unknown }) {
  let rows: PerCropResultRow[] = [];
  if (Array.isArray(data)) rows = data as PerCropResultRow[];
  else if (data && typeof data === 'object') {
    rows = Object.entries(data as Record<string, PerCropResultRow>).map(([k, v]) => ({ crop: k, ...(v || {}) }));
  }
  rows = rows.filter((r) => r && typeof r === 'object');
  if (rows.length === 0) return null;
  return (
    <div className="mb-12 bg-white rounded-2xl p-8 shadow-lg">
      <h3 className="text-xl font-bold text-gray-900 mb-4 flex items-center">
        <Layers className="w-5 h-5 text-green-600 mr-2" /> Climate impact per crop
      </h3>
      <table className="w-full text-sm border border-gray-200 rounded-lg overflow-hidden">
        <thead className="bg-gray-50">
          <tr>
            <th className="text-left font-semibold text-gray-600 px-3 py-2 border-b">Crop</th>
            <th className="text-right font-semibold text-gray-600 px-3 py-2 border-b">kg CO₂-eq per kg</th>
            <th className="text-right font-semibold text-gray-600 px-3 py-2 border-b">kg CO₂-eq total</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="odd:bg-white even:bg-gray-50/50">
              <td className="px-3 py-2 border-b border-gray-100">{r.crop || `Crop ${i + 1}`}</td>
              <td className="px-3 py-2 border-b border-gray-100 text-right font-mono">{fmt(r.global_warming_per_kg)}</td>
              <td className="px-3 py-2 border-b border-gray-100 text-right font-mono">{fmt(r.global_warming_total_kg_co2e, 4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
