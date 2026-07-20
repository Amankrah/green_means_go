'use client';

// Compact "next steps" card for the dashboard overview. The overview only holds
// assessment summary rows, so this takes the most recent one and fetches its full
// recommendations, showing the top few. It renders nothing (not an error) when there's
// no assessment or nothing matched - a secondary widget shouldn't clutter the dashboard.

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { Loader2, Lightbulb, ArrowRight } from 'lucide-react';
import { assessmentAPI, AssessmentSummary } from '@/lib/api';
import { RecommendationsResponse, RecommendationMeasure } from '@/types/recommendations';
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';

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

function savingPill(m: RecommendationMeasure): { text: string; variant: "default" | "secondary" | "destructive" | "outline" } | null {
  const s = m.economics.annual_saving_ghs;
  if (s === null) return null;
  if (s > 0) return { text: `Saves ~${ghs(s)}/yr`, variant: 'default' }; // green
  if (s < 0) return { text: `Costs ~${ghs(-s)}/yr`, variant: 'destructive' }; // orange/red
  return { text: 'Cost-neutral', variant: 'secondary' }; // gray
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
    <Card className="rounded-2xl border-gray-200 overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2 text-lg font-semibold text-gray-900">
            <Lightbulb className="h-5 w-5 text-moss" />
            Recommended next steps
          </CardTitle>
          <Link href={resultsHref} className="text-sm font-medium text-moss hover:text-spruce focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss/80 rounded-sm">
            View plan
          </Link>
        </div>
        <CardDescription className="text-sm">
          For {assessment?.title || assessment?.company_name || 'your latest assessment'}
          {data?.pending_review && ' · draft guidance'}
        </CardDescription>
      </CardHeader>

      <CardContent className="pb-4">
        {loading ? (
          <div className="flex items-center gap-2 text-gray-500 py-2">
            <Loader2 className="h-4 w-4 animate-spin" /> Finding steps…
          </div>
        ) : (
          <ul className="space-y-2">
            {top.map((m) => {
              const pill = savingPill(m);
              return (
                <li key={m.id} className="flex items-start justify-between gap-3 rounded-lg bg-gray-50/80 hover:bg-gray-50 transition-colors border border-gray-100 px-3 py-2">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-900">{m.title}</p>
                    <p className="truncate text-xs text-gray-500 mt-0.5">
                      {m.targets_source} · {Math.round(m.targets_share * 100)}% of impact
                    </p>
                  </div>
                  {pill && (
                    <Badge variant={pill.variant} className="shrink-0 font-medium">
                      {pill.text}
                    </Badge>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>

      {!loading && data && data.measures.length > top.length && (
        <CardFooter className="pt-0">
          <Link
            href={resultsHref}
            className="inline-flex items-center gap-1 text-sm font-medium text-moss hover:text-spruce focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss/80 rounded-sm"
          >
            See all {data.measures.length} steps <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </CardFooter>
      )}
    </Card>
  );
}
