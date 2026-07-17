'use client';

// Renders the deterministic, costed action plan from GET /assess/{id}/recommendations.
// Every figure shown is produced by the engine; this component only formats it. Draft
// (unreviewed) guidance is badged as such rather than presented as signed-off advice.

import React, { useEffect, useState } from 'react';
import { Loader2, TrendingDown, Clock, Info } from 'lucide-react';
import { assessmentAPI } from '@/lib/api';
import {
  RecommendationsResponse,
  RecommendationMeasure,
  ActionPhase,
} from '@/types/recommendations';

interface Props {
  assessmentId: string;
  isProcessing?: boolean;
}

const COST_TIER_LABEL: Record<string, string> = {
  NoCost: 'No upfront cost',
  LowCost: 'Low cost',
  MediumCost: 'Medium cost',
  HighCost: 'High cost',
};

const PHASE_ICON: Record<string, React.ElementType> = {
  start_now: TrendingDown,
  this_year: Clock,
  plan_ahead: Clock,
};

function ghs(n: number | null | undefined): string {
  if (n === null || n === undefined) return '-';
  return `GH₵${Math.round(n).toLocaleString()}`;
}

/** One measure card: what to do, what it targets, what it costs/saves, and its source. */
function MeasureCard({ m }: { m: RecommendationMeasure }) {
  const saving = m.economics.annual_saving_ghs;
  const savingLabel =
    saving === null
      ? null
      : saving > 0
        ? `Saves ~${ghs(saving)}/yr`
        : saving < 0
          ? `Costs ~${ghs(-saving)}/yr`
          : 'Cost-neutral';
  const effectPct = Math.round(Math.abs(m.effect.value) * 100);

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h5 className="font-semibold text-gray-900">{m.title}</h5>
          <p className="mt-1 text-sm text-gray-600">{m.action}</p>
        </div>
        {!m.reviewed && (
          <span className="shrink-0 rounded-full bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700 border border-amber-200">
            Draft
          </span>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        <span className="text-gray-700">
          Targets <span className="font-medium">{m.targets_source}</span>{' '}
          <span className="text-gray-400">({Math.round(m.targets_share * 100)}% of climate impact)</span>
        </span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2 text-xs">
        {m.effect.value < 0 && (
          <span className="rounded-full bg-green-50 px-2 py-1 font-medium text-green-700">
            ~{effectPct}% lower {m.effect.basis === 'measured' ? '(measured)' : '(estimate)'}
          </span>
        )}
        {savingLabel && (
          <span
            className={`rounded-full px-2 py-1 font-medium ${
              (saving ?? 0) >= 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-orange-50 text-orange-700'
            }`}
          >
            {savingLabel}
          </span>
        )}
        <span className="rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-700">
          {COST_TIER_LABEL[m.economics.cost_tier] ?? m.economics.cost_tier}
        </span>
        {m.economics.payback_months !== null && (
          <span className="rounded-full bg-gray-100 px-2 py-1 font-medium text-gray-700">
            Pays back in ~{Math.round(m.economics.payback_months)} mo
          </span>
        )}
        {m.economics.affordability === 'needs_finance' && (
          <span className="rounded-full bg-blue-50 px-2 py-1 font-medium text-blue-700">
            May need finance
          </span>
        )}
      </div>

      {m.provenance.citation && (
        <p className="mt-3 text-xs text-gray-400">Source: {m.provenance.citation}</p>
      )}
    </div>
  );
}

function Phase({ phase }: { phase: ActionPhase }) {
  const Icon = PHASE_ICON[phase.key] ?? Clock;
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <Icon className="h-5 w-5 text-spruce" />
        <h4 className="text-lg font-semibold text-gray-900">{phase.label}</h4>
      </div>
      <div className="space-y-3">
        {phase.measures.map((m) => (
          <MeasureCard key={m.id} m={m} />
        ))}
      </div>
    </div>
  );
}

export default function RecommendationsPanel({ assessmentId, isProcessing = false }: Props) {
  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    assessmentAPI
      .getRecommendations(assessmentId, isProcessing)
      .then((r) => {
        if (active) setData(r);
      })
      .catch((e) => {
        if (active) setError(e instanceof Error ? e.message : 'Could not load recommendations.');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [assessmentId, isProcessing]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-gray-500">
        <Loader2 className="h-4 w-4 animate-spin" /> Finding practical steps…
      </div>
    );
  }
  if (error) {
    return (
      <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
        {error}
      </div>
    );
  }
  if (!data || data.measures.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-gray-300 bg-white px-4 py-6 text-center text-sm text-gray-500">
        No specific measures matched this assessment yet.
      </div>
    );
  }

  const rev = data.revenue;

  return (
    <div className="space-y-6">
      {/* header: revenue context + draft banner */}
      <div className="rounded-2xl border border-gray-200 bg-gradient-to-br from-green-50/60 to-white p-5">
        <h3 className="text-xl font-bold text-gray-900">
          {isProcessing ? 'Practical steps for your facility' : 'Practical steps for your farm'}
        </h3>
        <p className="mt-1 text-sm text-gray-600">
          Actions matched to what drives your footprint, ordered by when to act, with a
          rough sense of cost and payback.
        </p>
        {rev.total_ghs !== null && (
          <p className="mt-2 text-sm text-gray-500">
            Estimated annual revenue used for affordability:{' '}
            <span className="font-medium text-gray-700">{ghs(rev.total_ghs)}</span>
            {rev.stale_prices && ' (from the latest available market prices)'}
          </p>
        )}
      </div>

      {data.pending_review && (
        <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <Info className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{data.disclaimer}</span>
        </div>
      )}

      {data.plan.phases.map((phase) => (
        <Phase key={phase.key} phase={phase} />
      ))}
    </div>
  );
}
