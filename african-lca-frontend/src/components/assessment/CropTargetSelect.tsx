'use client';

import React from 'react';
import { useFormContext, type FieldPath } from 'react-hook-form';
import { AlertCircle } from 'lucide-react';
import { EnhancedAssessmentFormData } from '@/lib/enhanced-assessment-schema';

type Props = {
  /** Form path of a string[] of CropProduction.cropId values. */
  name: FieldPath<EnhancedAssessmentFormData>;
  label?: string;
  error?: string;
};

/**
 * Pick which of the crops entered in the Crop step a row applies to. Nothing ticked means
 * every crop (the API's [] = all crops), so a single-crop farm never has to touch it.
 */
export default function CropTargetSelect({ name, label = 'Applied to which crops?', error }: Props) {
  const { watch, setValue } = useFormContext<EnhancedAssessmentFormData>();
  const crops = (watch('cropProductions') || []).filter((c) => c?.cropId);
  const selected = ((watch(name) as string[] | undefined) ?? []);

  if (crops.length <= 1 && selected.length === 0) return null;

  const toggle = (cropId: string, checked: boolean) => {
    const next = checked ? [...new Set([...selected, cropId])] : selected.filter((id) => id !== cropId);
    setValue(name, next as never, { shouldDirty: true, shouldValidate: !!error });
  };

  return (
    <div className="md:col-span-full">
      <span className="block text-sm font-medium text-ink mb-1">{label}</span>
      <div className="flex flex-wrap gap-3">
        {crops.map((c, i) => (
          <label key={c.cropId} className="flex items-center space-x-2 text-sm text-ink">
            <input
              type="checkbox"
              checked={selected.includes(c.cropId)}
              onChange={(e) => toggle(c.cropId, e.target.checked)}
              className="text-moss focus:ring-moss rounded"
            />
            <span>{c.cropName || `Crop ${i + 1}`}</span>
          </label>
        ))}
      </div>
      <p className="text-xs text-muted mt-1">Leave all unticked if it goes on every crop.</p>
      {error && (
        <p className="mt-1 text-xs text-red-600 flex items-center">
          <AlertCircle className="w-3 h-3 mr-1" />
          {error}
        </p>
      )}
    </div>
  );
}
