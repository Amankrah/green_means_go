'use client';

import React, { useEffect, useId, useState } from 'react';
import { AlertTriangle, X } from 'lucide-react';

export type ConfirmDialogProps = {
  open: boolean;
  title: string;
  description: React.ReactNode;
  /** Primary button label (destructive actions should say Delete / Replace). */
  confirmLabel: string;
  cancelLabel?: string;
  /** When set, user must type this exact string before Confirm is enabled. */
  requireText?: string;
  requireTextLabel?: string;
  busy?: boolean;
  tone?: 'danger' | 'warning';
  onConfirm: () => void | Promise<void>;
  onCancel: () => void;
};

/**
 * Modal confirmation for destructive or irreversible actions.
 * Optional typed confirmation (e.g. assessment title or "DELETE") adds a second safety gate.
 */
export default function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  cancelLabel = 'Cancel',
  requireText,
  requireTextLabel,
  busy = false,
  tone = 'danger',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const titleId = useId();
  const [typed, setTyped] = useState('');

  useEffect(() => {
    if (open) setTyped('');
  }, [open]);

  if (!open) return null;

  const needsMatch = Boolean(requireText && requireText.trim());
  const matched = !needsMatch || typed.trim() === requireText!.trim();
  const confirmDisabled = busy || !matched;

  const accent =
    tone === 'warning'
      ? 'bg-amber-600 hover:bg-amber-700 focus:ring-amber-500'
      : 'bg-red-600 hover:bg-red-700 focus:ring-red-500';
  const iconWrap =
    tone === 'warning' ? 'bg-amber-50 text-amber-700' : 'bg-red-50 text-red-700';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/40"
        onClick={() => {
          if (!busy) onCancel();
        }}
      />
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="relative w-full max-w-md rounded-2xl bg-white shadow-xl border border-gray-200"
      >
        <div className="flex items-start justify-between gap-3 p-5 border-b border-gray-100">
          <div className="flex items-start gap-3">
            <div className={`mt-0.5 rounded-lg p-2 ${iconWrap}`}>
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <h2 id={titleId} className="text-lg font-semibold text-gray-900">
                {title}
              </h2>
              <div className="mt-1 text-sm text-gray-600 leading-relaxed">{description}</div>
            </div>
          </div>
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="p-1 text-gray-400 hover:text-gray-700 disabled:opacity-50"
            aria-label="Close"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {needsMatch && (
          <div className="px-5 pt-4">
            <label className="block text-sm font-medium text-gray-700 mb-1.5">
              {requireTextLabel || (
                <>
                  Type <span className="font-mono text-gray-900">{requireText}</span> to confirm
                </>
              )}
            </label>
            <input
              autoFocus
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              disabled={busy}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-moss/30 focus:border-moss"
              placeholder={requireText}
              autoComplete="off"
            />
          </div>
        )}

        <div className="flex justify-end gap-2 p-5">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={() => void onConfirm()}
            disabled={confirmDisabled}
            className={`rounded-lg px-4 py-2 text-sm font-semibold text-white focus:outline-none focus:ring-2 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed ${accent}`}
          >
            {busy ? 'Working…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
