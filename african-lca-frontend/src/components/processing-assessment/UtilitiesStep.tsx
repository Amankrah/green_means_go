'use client';

import React from 'react';
import { useFormContext } from 'react-hook-form';
import { AlertTriangle } from 'lucide-react';
import {
  ProcessingFormData,
  FUEL_TYPES,
  TRANSPORT_MODES,
  WASTE_DISPOSAL_METHODS,
} from '@/lib/processing-assessment-schema';
import { Field, inputClass } from './fields';

export default function UtilitiesStep() {
  const { register, watch, formState: { errors } } = useFormContext<ProcessingFormData>();
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
        <Field label="Renewable share of electricity (%)" error={e?.renewablePct?.message}>
          <input type="number" min="0" max="100" step="any" {...register('utilities.renewablePct')} className={inputClass} />
        </Field>
        <Field label="Fuel (litres / month)" error={e?.fuelLMonth?.message}>
          <input type="number" min="0" step="any" {...register('utilities.fuelLMonth')} className={inputClass} />
        </Field>
        <Field label="Fuel type">
          <select {...register('utilities.fuelType')} className={inputClass}>
            {FUEL_TYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
        </Field>
        <Field label="Water (m³ / month)" error={e?.waterM3Month?.message}>
          <input type="number" min="0" step="any" {...register('utilities.waterM3Month')} className={inputClass} />
        </Field>
        <Field label="Solid waste (kg / day)" error={e?.solidWasteKgDay?.message}>
          <input type="number" min="0" step="any" {...register('utilities.solidWasteKgDay')} className={inputClass} />
        </Field>
        <Field label="Waste disposal method">
          <select {...register('utilities.wasteDisposalMethod')} className={inputClass}>
            {WASTE_DISPOSAL_METHODS.map((m) => <option key={m}>{m}</option>)}
          </select>
        </Field>
        <Field label="Inbound transport distance (km)" error={e?.transportKm?.message}>
          <input type="number" min="0" step="any" {...register('utilities.transportKm')} className={inputClass} />
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
