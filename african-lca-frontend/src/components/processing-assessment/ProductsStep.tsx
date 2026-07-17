'use client';

import React from 'react';
import { useFormContext, useFieldArray } from 'react-hook-form';
import { Plus, Trash2 } from 'lucide-react';
import {
  ProcessingFormData,
  PRODUCT_TYPES,
  PACKAGING_MATERIALS,
  newProduct,
} from '@/lib/processing-assessment-schema';
import { Field, inputClass } from './fields';

export default function ProductsStep() {
  const { control, register, watch, formState: { errors } } = useFormContext<ProcessingFormData>();
  const { fields, append, remove } = useFieldArray({ control, name: 'products' });
  const economic = watch('utilities.allocationBasis') === 'economic';
  const arrayError = errors.products?.root?.message || (typeof errors.products?.message === 'string' ? errors.products?.message : undefined);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">
          Add each product the facility makes. The raw material is usually the biggest part of the footprint,
          so include it where you can.
        </p>
        <button
          type="button"
          onClick={() => append(newProduct())}
          className="inline-flex items-center gap-1 whitespace-nowrap text-sm font-medium text-moss hover:text-spruce"
        >
          <Plus className="w-4 h-4" /> Add product
        </button>
      </div>
      {arrayError && <p className="text-sm text-red-600">{arrayError}</p>}

      {fields.map((field, i) => {
        const pe = errors.products?.[i];
        return (
          <div key={field.id} className="rounded-xl border border-line bg-surface p-4">
            <div className="grid gap-3 sm:grid-cols-[1fr_1fr_1fr_auto] items-start">
              <Field label="Product name" required error={pe?.name?.message}>
                <input {...register(`products.${i}.name`)} className={inputClass} />
              </Field>
              <Field label="Type">
                <select {...register(`products.${i}.productType`)} className={inputClass}>
                  {PRODUCT_TYPES.map((t) => <option key={t}>{t}</option>)}
                </select>
              </Field>
              <Field label="Annual output (tonnes)" required error={pe?.annualProduction?.message}>
                <input type="number" min="0" step="any" {...register(`products.${i}.annualProduction`)} className={inputClass} />
              </Field>
              <button
                type="button"
                onClick={() => remove(i)}
                disabled={fields.length === 1}
                className="mt-6 p-2 rounded-lg text-muted hover:text-red-600 hover:bg-red-50 disabled:opacity-40 disabled:hover:bg-transparent"
                aria-label="Remove product"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field label="Main raw material (the crop or ingredient)">
                <input {...register(`products.${i}.rawMaterial`)} className={inputClass} placeholder="e.g. maize grain, wheat grain" />
              </Field>
              <Field label="Raw material per tonne of product (kg)" error={pe?.rawKgPerTonne?.message}>
                <input type="number" min="0" step="any" {...register(`products.${i}.rawKgPerTonne`)} className={inputClass} placeholder="e.g. 1050" />
              </Field>
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-3">
              <Field label="Packaging material">
                <select {...register(`products.${i}.packaging.material`)} className={inputClass}>
                  {PACKAGING_MATERIALS.map((m) => <option key={m}>{m}</option>)}
                </select>
              </Field>
              <Field label="Package size (kg)" required error={pe?.packaging?.packageSize?.message}>
                <input type="number" min="0" step="any" {...register(`products.${i}.packaging.packageSize`)} className={inputClass} />
              </Field>
              <Field label="Packaging weight / unit (kg)" required error={pe?.packaging?.weightPerUnit?.message}>
                <input type="number" min="0" step="any" {...register(`products.${i}.packaging.weightPerUnit`)} className={inputClass} />
              </Field>
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Field
                label={economic ? 'Price per kg (required for economic split)' : 'Price per kg (optional)'}
                required={economic}
                error={pe?.pricePerKg?.message}
                hint={economic ? undefined : 'Only needed if you split impact between products by economic value'}
              >
                <input type="number" min="0" step="any" {...register(`products.${i}.pricePerKg`)} className={inputClass} placeholder="e.g. 1.20" />
              </Field>
            </div>
          </div>
        );
      })}
    </div>
  );
}
