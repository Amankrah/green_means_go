'use client';

import React from 'react';
import { useFieldArray, useFormContext } from 'react-hook-form';
import { AlertTriangle, Plus, Trash2 } from 'lucide-react';
import {
  ProcessingFormData,
  ELECTRICITY_SUPPLY,
  FUEL_DEFAULT_UNIT,
  FUEL_TYPES,
  FUEL_UNITS,
  TRANSPORT_MODES,
  WASTE_DISPOSAL_METHODS,
  WASTEWATER_TREATMENTS,
  WATER_SOURCES,
  WATER_TREATMENTS,
} from '@/lib/processing-assessment-schema';

const ELECTRICITY_LABEL: Record<(typeof ELECTRICITY_SUPPLY)[number], string> = {
  GridElectricity: 'National grid',
  DieselGenerator: 'On-site diesel generator',
  SolarPower: 'On-site solar',
  HydroElectricity: 'Hydro (dedicated supply)',
  WindPower: 'Wind (dedicated supply)',
};
import { Field, inputClass } from './fields';

export default function UtilitiesStep() {
  const { register, watch, setValue, control, formState: { errors } } = useFormContext<ProcessingFormData>();
  const { fields: fuelFields, append: appendFuel, remove: removeFuel } = useFieldArray({
    control, name: 'utilities.fuelStreams',
  });
  const e = errors.utilities;
  const products = watch('products') ?? [];
  const multiProduct = products.length > 1;
  // Warn here (where the choice is made) if economic allocation is selected but any product
  // is missing a price — otherwise the requirement only surfaces at final submit, on the
  // earlier Products step.
  const economicMissingPrices =
    watch('utilities.allocationBasis') === 'economic' &&
    products.some((p) => !(Number(p?.pricePerKg) > 0));

  return (
    <div className="space-y-6">
      <p className="text-sm text-muted">Monthly figures from your bills work best. Leave a field blank if it does not apply.</p>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Electricity (kWh / month)" error={e?.elecKwhMonth?.message}>
          <input type="number" min="0" step="any" {...register('utilities.elecKwhMonth')} className={inputClass} />
        </Field>
        <Field label="Electricity supply" hint="Selects the electricity dataset (grid, on-site generator, solar, hydro, wind)">
          <select {...register('utilities.electricitySupply')} className={inputClass}>
            {ELECTRICITY_SUPPLY.map((t) => <option key={t} value={t}>{ELECTRICITY_LABEL[t]}</option>)}
          </select>
        </Field>
        <Field label="On-site solar share of electricity (%)" error={e?.renewablePct?.message}>
          <input type="number" min="0" max="100" step="any" {...register('utilities.renewablePct')} className={inputClass} />
        </Field>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-ink">Fuels burned on site (add one line per fuel)</span>
          <button
            type="button"
            onClick={() => appendFuel({ fuelType: 'Diesel', amountMonth: undefined, unit: 'L' })}
            className="flex items-center gap-1 text-sm text-moss hover:underline"
          >
            <Plus className="w-4 h-4" /> Add fuel
          </button>
        </div>
        {fuelFields.length === 0 && <p className="text-xs text-muted">No fuel declared.</p>}
        {fuelFields.map((f, i) => (
          <div key={f.id} className="grid gap-3 sm:grid-cols-[2fr_1fr_1fr_auto] items-end">
            <Field label="Fuel">
              <select
                {...register(`utilities.fuelStreams.${i}.fuelType`, {
                  onChange: (ev) => setValue(`utilities.fuelStreams.${i}.unit`,
                    FUEL_DEFAULT_UNIT[ev.target.value as (typeof FUEL_TYPES)[number]] ?? 'L'),
                })}
                className={inputClass}
              >
                {FUEL_TYPES.map((t) => <option key={t}>{t}</option>)}
              </select>
            </Field>
            <Field label="Amount / month" error={e?.fuelStreams?.[i]?.amountMonth?.message}>
              <input type="number" min="0" step="any" {...register(`utilities.fuelStreams.${i}.amountMonth`)} className={inputClass} />
            </Field>
            <Field label="Unit">
              <select {...register(`utilities.fuelStreams.${i}.unit`)} className={inputClass}>
                {FUEL_UNITS.map((u) => <option key={u}>{u}</option>)}
              </select>
            </Field>
            <button type="button" onClick={() => removeFuel(i)} className="mb-2 text-red-600" aria-label="Remove fuel">
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Water (m³ / month)" error={e?.waterM3Month?.message}>
          <input type="number" min="0" step="any" {...register('utilities.waterM3Month')} className={inputClass} />
        </Field>
        <Field label="Water source" hint="Municipal water is a purchased product; borehole, well, river and dam water count as a withdrawal">
          <select {...register('utilities.waterSource')} className={inputClass}>
            {WATER_SOURCES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </Field>
        <Field label="On-site water treatment" hint="Chemical treatment and reverse osmosis use treated-water datasets">
          <select {...register('utilities.waterTreatment')} className={inputClass}>
            {WATER_TREATMENTS.map((t) => <option key={t}>{t}</option>)}
          </select>
        </Field>
        <Field label="Wastewater treatment" hint="None: no treatment burden, and the untreated effluent is flagged as a data gap">
          <select {...register('utilities.wastewaterTreatment')} className={inputClass}>
            {WASTEWATER_TREATMENTS.map((t) => <option key={t}>{t}</option>)}
          </select>
        </Field>
        <Field label="Solid waste (kg / day)" error={e?.solidWasteKgDay?.message}>
          <input type="number" min="0" step="any" {...register('utilities.solidWasteKgDay')} className={inputClass} />
        </Field>
        <Field label="Waste disposal method">
          <select {...register('utilities.wasteDisposalMethod')} className={inputClass}>
            {WASTE_DISPOSAL_METHODS.map((m) => <option key={m}>{m}</option>)}
          </select>
        </Field>
        <Field label="Organic share of solid waste (%)" error={e?.organicWastePct?.message} hint="Organic waste goes to the biowaste route of the disposal method">
          <input type="number" min="0" max="100" step="any" {...register('utilities.organicWastePct')} className={inputClass} />
        </Field>
        <Field label="Share of solid waste used as a by-product (%)" error={e?.byproductPct?.message} hint="Used by-products (feed, mulch, fuel) leave burden-free instead of being treated">
          <input type="number" min="0" max="100" step="any" {...register('utilities.byproductPct')} className={inputClass} />
        </Field>
        <Field label="By-product name">
          <input {...register('utilities.byproductName')} className={inputClass} placeholder="e.g. bran, empty fruit bunches" />
        </Field>
        <Field label="Inbound transport distance (km)" error={e?.transportKm?.message} hint="Leave blank to use a default from the local sourcing share">
          <input type="number" min="0" step="any" {...register('utilities.transportKm')} className={inputClass} />
        </Field>
        <Field label="Raw material sourced locally (%)" error={e?.localSourcingPct?.message} hint="Used only when the distance is blank">
          <input type="number" min="0" max="100" step="any" {...register('utilities.localSourcingPct')} className={inputClass} />
        </Field>
        <Field label="Transport mode">
          <select {...register('utilities.transportMode')} className={inputClass}>
            {TRANSPORT_MODES.map((m) => <option key={m}>{m}</option>)}
          </select>
        </Field>
      </div>

      {multiProduct && (
        <div>
          <Field label="Split impact between products by" hint="ISO 14044 requires this choice to be stated when a facility makes co-products">
            <select {...register('utilities.allocationBasis')} className={inputClass}>
              <option value="mass">Output mass (default)</option>
              <option value="economic">Economic value (needs a price per product)</option>
            </select>
          </Field>
          {economicMissingPrices && (
            <div className="mt-2 flex items-start gap-2 rounded-lg bg-amber-50 border border-amber-200 px-3 py-2 text-sm text-amber-800">
              <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
              <span>Economic allocation needs a price per kg for every product. Go back to the Products step and add the missing prices, or switch back to output mass.</span>
            </div>
          )}
        </div>
      )}

      <details className="rounded-xl border border-line bg-surface p-4">
        <summary className="cursor-pointer text-sm font-medium text-ink">On-site cooling / refrigerant (optional)</summary>
        <div className="mt-3 grid gap-4 sm:grid-cols-2">
          <Field label="Refrigerant type">
            <input {...register('utilities.refrigerantType')} className={inputClass} placeholder="e.g. R-134a, R-404A, Ammonia" />
          </Field>
          <Field label="Annual leakage (kg / year)" error={e?.refrigerantKg?.message}>
            <input type="number" min="0" step="any" {...register('utilities.refrigerantKg')} className={inputClass} />
          </Field>
        </div>
      </details>
    </div>
  );
}
