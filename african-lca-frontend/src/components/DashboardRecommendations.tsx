'use client';

// Compact "next steps" card for the dashboard overview. The overview only holds
// assessment summary rows, so this takes the most recent one and fetches its full
// recommendations, showing the top few. It renders nothing (not an error) when there's
// no assessment or nothing matched — a secondary widget shouldn't clutter the dashboard.

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Loader2, Lightbulb, ArrowRight } from 'lucide-react';
import { assessmentAPI, AssessmentSummary } from '@/lib/api';
import { RecommendationsResponse, RecommendationMeasure } from '@/types/recommendations';

interface Props {
  /** The user's most recent assessment; the card is for its results. */
  assessment?: AssessmentSummary;
  /** How many measures to preview. */
  limit?: number;
}

function ghs(n: number | null | undefined): string {
  if (n === null || n === undefined) return '';
  return `GH₵${Math.round(n).toLocaleString()}`;
}

function savingPill(m: RecommendationMeasure): { text: string; cls: string } | null {
  const s = m.economics.annual_saving_ghs;
  if (s === null) return null;
  if (s > 0) return { text: `Saves ~${ghs(s)}/yr`, cls: 'bg-emerald-50 text-emerald-700' };
  if (s < 0) return { text: `Costs ~${ghs(-s)}/yr`, cls: 'bg-orange-50 text-orange-700' };
  return { text: 'Cost-neutral', cls: 'bg-gray-100 text-gray-600' };
}

export default function DashboardRecommendations({ assessment, limit = 3 }: Props) {
  const [data, setData] = useState<RecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);

  const id = assessment?.id;
  const isProcessing = assessment?.type === 'processing';

  useEffect(() => {
    if (!id) {
      setLoading(false);
      return;
    }
    let active = true;
    setLoading(true);
    setFailed(false);
    assessmentAPI
      .getRecommendations(id, isProcessing)
      .then((r) => {
        if (active) setData(r);
      })
      .catch(() => {
        if (active) setFailed(true);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [id, isProcessing]);

  // Nothing to show, or a failure in a secondary widget: render nothing.
  if (!id || failed) return null;
  if (!loading && (!data || data.measures.length === 0)) return null;

  const resultsHref = `/results?id=${id}${isProcessing ? '&type=processing' : ''}`;
  const top = data?.measures.slice(0, limit) ?? [];

  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
          <Lightbulb className="h-5 w-5 text-moss" />
          Recommended next steps
        </h3>
        <Link href={resultsHref} className="text-sm font-medium text-moss hover:text-spruce">
          View plan
        </Link>
      </div>
      <p className="mt-1 text-sm text-gray-500">
        For {assessment?.title || assessment?.company_name || 'your latest assessment'}
        {data?.pending_review && ' · draft guidance'}
      </p>

      {loading ? (
        <div className="mt-4 flex items-center gap-2 text-gray-500">
          <Loader2 className="h-4 w-4 animate-spin" /> Finding steps…
        </div>
      ) : (
        <ul className="mt-4 space-y-2">
          {top.map((m) => {
            const pill = savingPill(m);
            return (
              <li key={m.id} className="flex items-start justify-between gap-3 rounded-lg bg-gray-50 px-3 py-2">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-gray-900">{m.title}</p>
                  <p className="truncate text-xs text-gray-500">
                    {m.targets_source} · {Math.round(m.targets_share * 100)}% of impact
                  </p>
                </div>
                {pill && (
                  <span className={`shrink-0 rounded-full px-2 py-1 text-xs font-medium ${pill.cls}`}>
                    {pill.text}
                  </span>
                )}
              </li>
            );
          })}
        </ul>
      )}

      {!loading && data && data.measures.length > top.length && (
        <Link
          href={resultsHref}
          className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-moss hover:text-spruce"
        >
          See all {data.measures.length} steps <ArrowRight className="h-3.5 w-3.5" />
        </Link>
      )}
    </section>
  );
}
