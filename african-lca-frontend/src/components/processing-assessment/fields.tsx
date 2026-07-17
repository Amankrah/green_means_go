'use client';

import React from 'react';

// Shared field styling for the processing wizard, using the global design-system tokens
// (--gmg-* / Tailwind color tokens) so it matches the rest of the app without depending on
// any page-local class.
export const inputClass =
  'mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-ink outline-none transition ' +
  'focus:border-moss focus:ring-2 focus:ring-moss/20 disabled:opacity-60';

export function Field({
  label,
  required,
  error,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-sm font-medium text-ink">
        {label}
        {required && <span className="text-red-500"> *</span>}
      </span>
      {children}
      {hint && !error && <span className="mt-1 block text-xs text-muted">{hint}</span>}
      {error && <span className="mt-1 block text-xs text-red-600">{error}</span>}
    </label>
  );
}
