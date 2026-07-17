'use client';

// The single "New assessment" entry point across the dashboard. Roles that can start
// only one kind of assessment get a plain link; roles that can start both (researchers)
// get a picker, so neither type is buried behind a default.

import React, { useState } from 'react';
import Link from 'next/link';
import { Plus, ChevronDown, Sprout, Factory } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { assessmentTypesForRole, type AssessmentKind } from '@/lib/assessment-types';

const KIND_ICON: Record<AssessmentKind, React.ElementType> = {
  farm: Sprout,
  processing: Factory,
};

interface NewAssessmentButtonProps {
  /** Full-width, for the sidebar. Also opens the menu upward, since it sits at the bottom. */
  block?: boolean;
  /** Lets the sidebar close itself once a choice is made. */
  onNavigate?: () => void;
  /** Overrides the label when only one type is available. */
  label?: string;
}

export default function NewAssessmentButton({
  block = false,
  onNavigate,
  label = 'New assessment',
}: NewAssessmentButtonProps) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const options = assessmentTypesForRole(user?.role);

  // A role with no assessment types (or a user still loading) gets no button.
  if (options.length === 0) return null;

  const trigger = `inline-flex items-center justify-center gap-2 rounded-lg bg-spruce px-4 py-2.5 text-sm font-medium text-white hover:bg-ink transition-colors ${
    block ? 'w-full' : ''
  }`;

  if (options.length === 1) {
    return (
      <Link href={options[0].href} onClick={onNavigate} className={trigger}>
        <Plus className="w-4 h-4" /> {label}
      </Link>
    );
  }

  const handlePick = () => {
    setOpen(false);
    onNavigate?.();
  };

  return (
    <div className={`relative ${block ? 'w-full' : ''}`}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={trigger}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Plus className="w-4 h-4" /> {label}
        <ChevronDown className={`w-4 h-4 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} />
          <div
            role="menu"
            className={`absolute z-50 rounded-xl bg-white shadow-xl border border-gray-100 py-2 ${
              block ? 'bottom-full mb-2 left-0 w-full' : 'top-full mt-2 right-0 w-72'
            }`}
          >
            {options.map((opt) => {
              const Icon = KIND_ICON[opt.kind];
              return (
                <Link
                  key={opt.kind}
                  href={opt.href}
                  role="menuitem"
                  onClick={handlePick}
                  className="flex items-start gap-3 px-4 py-2.5 text-left hover:bg-gray-50"
                >
                  <Icon className="w-5 h-5 mt-0.5 text-moss shrink-0" />
                  <span>
                    <span className="block text-sm font-medium text-gray-900">{opt.label}</span>
                    <span className="block text-xs text-gray-500">{opt.description}</span>
                  </span>
                </Link>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
