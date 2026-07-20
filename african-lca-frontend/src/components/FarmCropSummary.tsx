'use client';

import React from 'react';
import Link from 'next/link';
import { Sprout } from 'lucide-react';
import type { FarmSnapshot } from '@/lib/farm-snapshot';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/ui/card';

const SEGMENT_COLORS = [
  'bg-moss',
  'bg-spruce',
  'bg-amber',
  'bg-clay',
  'bg-moss/70',
  'bg-spruce/70',
];

type EmptyKind = 'none' | 'legacy' | 'empty-crops';

type FarmCropSummaryProps =
  | {
      mode: 'loading';
    }
  | {
      mode: 'empty';
      emptyKind: EmptyKind;
      farmId: string;
    }
  | {
      mode: 'ready';
      snapshot: FarmSnapshot;
      assessmentId: string;
      assessmentDate?: string | null;
      assessmentTitle?: string | null;
    };

function formatHa(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—';
  return `${Number(n.toFixed(2))} ha`;
}

function formatKg(n: number | null | undefined): string {
  if (n == null || !Number.isFinite(n)) return '—';
  return `${Math.round(n).toLocaleString()} kg`;
}

function humanize(value: string | null | undefined): string {
  if (!value) return '—';
  return value.replace(/([a-z])([A-Z])/g, '$1 $2');
}

export default function FarmCropSummary(props: FarmCropSummaryProps) {
  if (props.mode === 'loading') {
    return (
      <Card className="rounded-2xl border-gray-200">
        <CardHeader className="pb-2">
          <CardTitle className="text-sm font-semibold uppercase tracking-wide text-gray-500">
            Crops &amp; land use
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-500">Loading crop details…</p>
        </CardContent>
      </Card>
    );
  }

  if (props.mode === 'empty') {
    const copy =
      props.emptyKind === 'none'
        ? 'No crop data yet. Run an assessment to see your crop details and land use.'
        : props.emptyKind === 'legacy'
          ? 'Crop details aren’t available for assessments saved before edit/re-run support. Run a new assessment to capture them here.'
          : 'No crops were entered in your latest assessment.';

    return (
      <Card className="rounded-2xl border-gray-200">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
            <Sprout className="w-4 h-4 text-moss" />
            Crops &amp; land use
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-gray-600">{copy}</p>
          {(props.emptyKind === 'none' || props.emptyKind === 'legacy') && (
            <Link
              href={`/assessment?farmId=${props.farmId}`}
              className="mt-4 inline-flex text-sm font-medium text-moss hover:text-spruce focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss/80 rounded-sm"
            >
              Start an assessment
            </Link>
          )}
        </CardContent>
      </Card>
    );
  }

  const { snapshot, assessmentId, assessmentDate, assessmentTitle } = props;
  const totalForBar =
    snapshot.assessedSizeHa != null && snapshot.assessedSizeHa > 0
      ? Math.max(snapshot.assessedSizeHa, snapshot.allocatedHa)
      : snapshot.allocatedHa > 0
        ? snapshot.allocatedHa
        : 0;

  const segments = (() => {
    const items = snapshot.crops
      .filter((c) => (c.areaHa ?? 0) > 0)
      .map((c, i) => ({
        key: `${c.name}-${i}`,
        label: c.name,
        ha: c.areaHa ?? 0,
        color: SEGMENT_COLORS[i % SEGMENT_COLORS.length],
      }));
    if (snapshot.unallocatedHa > 0) {
      items.push({
        key: 'unallocated',
        label: 'Unallocated',
        ha: snapshot.unallocatedHa,
        color: 'bg-gray-200',
      });
    }
    return items;
  })();

  const dateLabel = assessmentDate
    ? new Date(assessmentDate).toLocaleDateString()
    : '—';

  return (
    <Card className="rounded-2xl border-gray-200">
      <CardHeader className="pb-2">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <CardTitle className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-gray-500">
            <Sprout className="w-4 h-4 text-moss" />
            Crops &amp; land use
          </CardTitle>
          <p className="text-xs text-gray-500">
            From assessment on {dateLabel}
            {assessmentTitle ? ` · ${assessmentTitle}` : ''}{' '}
            <Link
              href={`/results?id=${assessmentId}`}
              className="font-medium text-moss hover:text-spruce focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-moss/80 rounded-sm"
            >
              View results
            </Link>
          </p>
        </div>
      </CardHeader>
      
      <CardContent>
        {(snapshot.farmType || snapshot.primaryFarmingSystem || snapshot.assessedSizeHa != null) && (
          <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-2 text-sm text-gray-700">
            {snapshot.assessedSizeHa != null && (
              <div>
                <dt className="inline text-xs uppercase tracking-wide text-gray-400">
                  Assessed size{' '}
                </dt>
                <dd className="inline font-medium text-gray-900">
                  {formatHa(snapshot.assessedSizeHa)}
                </dd>
              </div>
            )}
            {snapshot.farmType && (
              <div>
                <dt className="inline text-xs uppercase tracking-wide text-gray-400">
                  Farm type{' '}
                </dt>
                <dd className="inline font-medium text-gray-900">
                  {humanize(snapshot.farmType)}
                </dd>
              </div>
            )}
            {snapshot.primaryFarmingSystem && (
              <div>
                <dt className="inline text-xs uppercase tracking-wide text-gray-400">
                  System{' '}
                </dt>
                <dd className="inline font-medium text-gray-900">
                  {humanize(snapshot.primaryFarmingSystem)}
                </dd>
              </div>
            )}
          </dl>
        )}

        {totalForBar > 0 && segments.length > 0 && (
          <div className="mt-5">
            <div
              className="flex h-3 w-full overflow-hidden rounded-full bg-gray-100"
              role="img"
              aria-label="Land use by crop area"
            >
              {segments.map((seg) => {
                const pct = (seg.ha / totalForBar) * 100;
                if (pct <= 0) return null;
                return (
                  <div
                    key={seg.key}
                    className={`${seg.color} min-w-[2px]`}
                    style={{ width: `${pct}%` }}
                    title={`${seg.label}: ${formatHa(seg.ha)}`}
                  />
                );
              })}
            </div>
            <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-gray-600">
              {segments.map((seg) => {
                const pct = totalForBar > 0 ? (seg.ha / totalForBar) * 100 : 0;
                return (
                  <li key={seg.key} className="inline-flex items-center gap-1.5">
                    <span className={`inline-block h-2.5 w-2.5 rounded-sm ${seg.color}`} />
                    <span>
                      {seg.label}: {formatHa(seg.ha)} ({pct.toFixed(0)}%)
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}

        {snapshot.crops.length === 0 ? (
          <p className="mt-4 text-sm text-gray-500">
            No crops were entered in your latest assessment.
          </p>
        ) : (
          <ul className="mt-5 divide-y divide-gray-100 border-t border-gray-100">
            {snapshot.crops.map((crop, i) => (
              <li
                key={`${crop.name}-${i}`}
                className="flex flex-col gap-1 py-3 sm:flex-row sm:items-baseline sm:justify-between"
              >
                <div>
                  <div className="text-sm font-medium text-gray-900">{crop.name}</div>
                  <div className="text-xs text-gray-500">
                    {humanize(crop.croppingPattern)}
                    {crop.productionSystem ? ` · ${humanize(crop.productionSystem)}` : ''}
                    {crop.partners?.length
                      ? ` · with ${crop.partners.join(', ')}`
                      : ''}
                  </div>
                </div>
                <div className="text-sm text-gray-700 sm:text-right mt-1 sm:mt-0">
                  <div>{formatHa(crop.areaHa)}</div>
                  <div className="text-xs text-gray-500">{formatKg(crop.productionKg)} / year</div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
