'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Sprout, Factory, FileBarChart, Loader2, Plus, Gauge } from 'lucide-react';
import RequireAuth from '@/components/RequireAuth';
import DashboardShell from '@/components/DashboardShell';
import { useAuth } from '@/contexts/AuthContext';
import { assessmentAPI, AssessmentSummary } from '@/lib/api';

export const dynamic = 'force-dynamic';

function OverviewContent() {
  const { user } = useAuth();
  const isProcessor = user?.role === 'processor';
  const isOfficer = user?.role === 'extension_officer';

  const [assessments, setAssessments] = useState<AssessmentSummary[]>([]);
  const [managedCount, setManagedCount] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const [a, managed] = await Promise.all([
          assessmentAPI.getMyAssessments(),
          isProcessor ? assessmentAPI.getFacilities() : assessmentAPI.getFarms(),
        ]);
        if (!active) return;
        setAssessments(a.assessments);
        setManagedCount(managed.length);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Could not load your dashboard.');
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [isProcessor]);

  const scored = assessments.filter((a) => typeof a.single_score === 'number');
  const avgScore =
    scored.length > 0 ? scored.reduce((s, a) => s + (a.single_score || 0), 0) / scored.length : null;

  const managedLabel = isProcessor ? 'Facilities' : isOfficer ? 'Client farms' : 'Farms';

  return (
    <div className="space-y-8">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">
            Welcome back, {user?.full_name?.split(' ')[0] || 'there'}
          </h2>
          <p className="text-gray-600">
            {isOfficer
              ? 'Track sustainability across every farm you support.'
              : isProcessor
                ? 'Measure and improve your facilities’ footprint.'
                : 'Measure and improve your farm’s footprint.'}
          </p>
        </div>
        <Link
          href={isProcessor ? '/processing-assessment' : '/assessment'}
          className="inline-flex items-center gap-2 rounded-lg bg-spruce px-4 py-2.5 font-medium text-white hover:bg-ink transition-colors"
        >
          <Plus className="w-4 h-4" /> New assessment
        </Link>
      </div>

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          icon={isProcessor ? Factory : Sprout}
          label={managedLabel}
          value={loading ? '—' : managedCount ?? 0}
          href={isProcessor ? '/dashboard/facilities' : '/dashboard/farms'}
        />
        <StatCard
          icon={FileBarChart}
          label="Saved assessments"
          value={loading ? '—' : assessments.length}
          href="/dashboard/assessments"
        />
        <StatCard
          icon={Gauge}
          label="Average single score"
          value={loading ? '—' : avgScore !== null ? avgScore.toFixed(3) : '—'}
        />
      </div>

      {/* Recent assessments */}
      <section>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">Recent assessments</h3>
          <Link href="/dashboard/assessments" className="text-sm font-medium text-moss hover:text-spruce">
            View all
          </Link>
        </div>

        {loading ? (
          <div className="mt-4 flex items-center gap-2 text-gray-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading…
          </div>
        ) : assessments.length === 0 ? (
          <div className="mt-4 rounded-2xl border border-dashed border-gray-300 bg-white px-6 py-10 text-center">
            <p className="text-gray-600">No assessments yet.</p>
            <Link
              href={isProcessor ? '/processing-assessment' : '/assessment'}
              className="mt-4 inline-flex items-center gap-2 rounded-lg bg-spruce px-4 py-2 font-medium text-white hover:bg-ink transition-colors"
            >
              Run your first assessment <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        ) : (
          <div className="mt-4 overflow-hidden rounded-2xl border border-gray-200 bg-white">
            <table className="w-full text-left text-sm">
              <thead className="bg-gray-50 text-gray-500">
                <tr>
                  <th className="px-4 py-3 font-medium">Assessment</th>
                  <th className="px-4 py-3 font-medium hidden sm:table-cell">Type</th>
                  <th className="px-4 py-3 font-medium hidden md:table-cell">Date</th>
                  <th className="px-4 py-3 font-medium">Score</th>
                  <th className="px-4 py-3"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {assessments.slice(0, 5).map((a) => (
                  <tr key={a.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{a.title || a.company_name || 'Untitled'}</div>
                      <div className="text-gray-400">{a.country}</div>
                    </td>
                    <td className="px-4 py-3 hidden sm:table-cell capitalize text-gray-600">{a.type}</td>
                    <td className="px-4 py-3 hidden md:table-cell text-gray-600">
                      {a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}
                    </td>
                    <td className="px-4 py-3 text-gray-900">
                      {typeof a.single_score === 'number' ? a.single_score.toFixed(3) : '—'}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Link href={`/results?id=${a.id}`} className="font-medium text-moss hover:text-spruce">
                        View
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

function StatCard({
  icon: Icon,
  label,
  value,
  href,
}: {
  icon: React.ElementType;
  label: string;
  value: React.ReactNode;
  href?: string;
}) {
  const inner = (
    <div className="rounded-2xl border border-gray-200 bg-white p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-gray-500">{label}</span>
        <Icon className="w-5 h-5 text-moss" />
      </div>
      <div className="mt-2 text-3xl font-bold text-gray-900">{value}</div>
    </div>
  );
  return href ? (
    <Link href={href} className="block hover:opacity-90 transition-opacity">
      {inner}
    </Link>
  ) : (
    inner
  );
}

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardShell active="overview" title="Dashboard">
        <OverviewContent />
      </DashboardShell>
    </RequireAuth>
  );
}
