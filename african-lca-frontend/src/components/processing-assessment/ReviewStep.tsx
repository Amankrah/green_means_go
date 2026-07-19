'use client';

import React from 'react';
import { useFormContext } from 'react-hook-form';
import { ChevronLeft, Loader2, AlertTriangle } from 'lucide-react';
import { ProcessingFormData } from '@/lib/processing-assessment-schema';
import type { AssessmentProgressEvent } from '@/lib/api';
import AssessmentProgress from '@/components/AssessmentProgress';

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4 py-1.5 border-b border-line/60 last:border-0">
      <span className="text-sm text-muted">{label}</span>
      <span className="text-sm font-medium text-ink text-right">{value}</span>
    </div>
  );
}

export default function ReviewStep({
  onSubmit,
  isSubmitting,
  onPrevious,
  progress,
}: {
  onSubmit: () => void;
  isSubmitting: boolean;
  onPrevious: () => void;
  progress?: AssessmentProgressEvent | null;
}) {
  const { getValues, formState: { errors } } = useFormContext<ProcessingFormData>();
  const v = getValues();
  const hasErrors = Object.keys(errors).length > 0;

  // While the (long) solve runs, show the staged progress view instead of the review.
  if (isSubmitting) {
    return <AssessmentProgress variant="processing" live={progress} />;
  }
  const num = (n: number | undefined, unit = '') => (n || n === 0 ? `${n}${unit}` : '—');

  return (
    <div className="space-y-6">
      <div className="grid gap-6 md:grid-cols-2">
        <section className="rounded-xl border border-line bg-surface p-5">
          <h3 className="font-semibold text-ink mb-2">Facility</h3>
          <Row label="Name" value={v.facility.facilityName || '—'} />
          <Row label="Type" value={v.facility.facilityType} />
          <Row label="Country / region" value={`${v.facility.country}${v.facility.region ? ` · ${v.facility.region}` : ''}`} />
          <Row label="Capacity" value={num(v.facility.capacity, ' t/day')} />
          <Row label="Operating" value={`${num(v.facility.hoursPerDay)} h/day · ${num(v.facility.daysPerYear)} days/yr`} />
        </section>

        <section className="rounded-xl border border-line bg-surface p-5">
          <h3 className="font-semibold text-ink mb-2">Utilities</h3>
          <Row label="Electricity" value={num(v.utilities.elecKwhMonth, ' kWh/mo')} />
          <Row label="Renewable share" value={num(v.utilities.renewablePct, '%')} />
          <Row label="Fuel" value={v.utilities.fuelLMonth ? `${v.utilities.fuelLMonth} L/mo (${v.utilities.fuelType})` : '—'} />
          <Row label="Water" value={num(v.utilities.waterM3Month, ' m³/mo')} />
          <Row label="Solid waste" value={v.utilities.solidWasteKgDay ? `${v.utilities.solidWasteKgDay} kg/day (${v.utilities.wasteDisposalMethod})` : '—'} />
          <Row label="Inbound transport" value={v.utilities.transportKm ? `${v.utilities.transportKm} km (${v.utilities.transportMode})` : '—'} />
          {v.products.length > 1 && <Row label="Allocation" value={v.utilities.allocationBasis === 'economic' ? 'Economic value' : 'Output mass'} />}
        </section>
      </div>

      <section className="rounded-xl border border-line bg-surface p-5">
        <h3 className="font-semibold text-ink mb-2">Products ({v.products.length})</h3>
        <div className="space-y-1">
          {v.products.map((p, i) => (
            <Row
              key={i}
              label={p.name || `Product ${i + 1}`}
              value={`${num(p.annualProduction, ' t/yr')}${p.rawMaterial ? ` · ${p.rawMaterial}` : ''}${v.utilities.allocationBasis === 'economic' && p.pricePerKg ? ` · ${p.pricePerKg}/kg` : ''}`}
            />
          ))}
        </div>
      </section>

      {hasErrors && (
        <div className="flex items-start gap-2 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          <AlertTriangle className="w-4 h-4 mt-0.5 shrink-0" />
          <span>Some inputs still need attention. Go back through the steps to fix the highlighted fields.</span>
        </div>
      )}

      <div className="flex flex-col sm:flex-row justify-between items-center gap-4">
        <button
          type="button"
          onClick={onPrevious}
          className="flex items-center gap-2 px-6 py-3 border border-line rounded-full text-ink font-semibold hover:bg-paper transition-colors"
        >
          <ChevronLeft className="w-5 h-5" />
          <span>Previous</span>
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={isSubmitting}
          className="inline-flex items-center gap-2 rounded-full bg-spruce px-8 py-3 font-semibold text-white hover:bg-ink disabled:opacity-60 transition-colors"
        >
          {isSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
          {isSubmitting ? 'Running assessment…' : 'Run assessment'}
        </button>
      </div>
    </div>
  );
}
