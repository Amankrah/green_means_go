'use client';

import React from 'react';
import { useFormContext } from 'react-hook-form';
import {
  ProcessingFormData,
  COUNTRIES,
  FACILITY_TYPES,
  LOCATION_TYPES,
} from '@/lib/processing-assessment-schema';
import { Field, inputClass } from './fields';

export default function FacilityStep() {
  const { register, formState: { errors } } = useFormContext<ProcessingFormData>();
  const e = errors.facility;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Field label="Facility name" required error={e?.facilityName?.message}>
        <input {...register('facility.facilityName')} className={inputClass} placeholder="e.g. Tema Grain Mill" />
      </Field>
      <Field label="Company name" hint="Defaults to the facility name if left blank">
        <input {...register('facility.companyName')} className={inputClass} />
      </Field>
      <Field label="Facility type">
        <select {...register('facility.facilityType')} className={inputClass}>
          {FACILITY_TYPES.map((t) => <option key={t}>{t}</option>)}
        </select>
      </Field>
      <Field label="Location type">
        <select {...register('facility.locationType')} className={inputClass}>
          {LOCATION_TYPES.map((t) => <option key={t}>{t}</option>)}
        </select>
      </Field>
      <Field label="Country">
        <select {...register('facility.country')} className={inputClass}>
          {COUNTRIES.map((c) => <option key={c}>{c}</option>)}
        </select>
      </Field>
      <Field label="Region / province" hint="Sharpens the regional grid and water data where available">
        <input {...register('facility.region')} className={inputClass} placeholder="e.g. Greater Accra" />
      </Field>
      <Field label="Processing capacity (tonnes/day)" required error={e?.capacity?.message}>
        <input type="number" min="0" step="any" {...register('facility.capacity')} className={inputClass} />
      </Field>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Hours / day" required error={e?.hoursPerDay?.message}>
          <input type="number" min="0" step="any" {...register('facility.hoursPerDay')} className={inputClass} />
        </Field>
        <Field label="Days / year" required error={e?.daysPerYear?.message}>
          <input type="number" min="0" step="1" {...register('facility.daysPerYear')} className={inputClass} />
        </Field>
      </div>
    </div>
  );
}
