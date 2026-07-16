'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { ArrowRight, Loader2, Plus } from 'lucide-react';
import RequireAuth from '@/components/RequireAuth';
import DashboardShell from '@/components/DashboardShell';
import { useAuth } from '@/contexts/AuthContext';
import { assessmentAPI, AssessmentSummary } from '@/lib/api';

export const dynamic = 'force-dynamic';

type Filter = 'all' | 'farm' | 'processing';

function AssessmentsContent() {
  const { user } = useAuth();
  const isProcessor = user?.role === 'processor';
  const [rows, setRows] = useState<AssessmentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>('all');

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const data = await assessmentAPI.getMyAssessments();
        if (active) setRows(data.assessments);
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Could not load your assessments.');
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const hasBothTypes = useMemo(() => new Set(rows.map((r) => r.type)).size > 1, [rows]);
  const filtered = filter === 'all' ? rows : rows.filter((r) => r.type === filter);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <p className="text-gray-600">Every assessment you&apos;ve saved, newest first.</p>
        <Link
          href={isProcessor ? '/processing-assessment' : '/assessment'}
          className="inline-flex items-center gap-2 rounded-lg bg-spruce px-4 py-2.5 font-medium text-white hover:bg-ink transition-colors"
        >
          <Plus className="w-4 h-4" /> New assessment
        </Link>
      </div>

      {hasBothTypes && (
        <div className="flex gap-2">
          {(['all', 'farm', 'processing'] as Filter[]).map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={`rounded-full px-3 py-1 text-sm font-medium capitalize transition-colors ${
                filter === f ? 'bg-spruce text-white' : 'bg-white text-gray-600 border border-gray-200 hover:bg-gray-50'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      )}

      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">{error}</div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 text-gray-500">
          <Loader2 className="w-4 h-4 animate-spin" /> Loading…
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-gray-300 bg-white px-6 py-12 text-center">
          <p className="text-gray-600">No assessments to show.</p>
          <Link
            href={isProcessor ? '/processing-assessment' : '/assessment'}
            className="mt-4 inline-flex items-center gap-2 rounded-lg bg-spruce px-4 py-2 font-medium text-white hover:bg-ink transition-colors"
          >
            Run an assessment <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-gray-200 bg-white">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="px-4 py-3 font-medium">Assessment</th>
                <th className="px-4 py-3 font-medium hidden sm:table-cell">Type</th>
                <th className="px-4 py-3 font-medium hidden md:table-cell">Country</th>
                <th className="px-4 py-3 font-medium hidden md:table-cell">Date</th>
                <th className="px-4 py-3 font-medium">Score</th>
                <th className="px-4 py-3"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((a) => (
                <tr key={a.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div className="font-medium text-gray-900">{a.title || a.company_name || 'Untitled'}</div>
                    <div className="text-gray-400 sm:hidden capitalize">{a.type}</div>
                  </td>
                  <td className="px-4 py-3 hidden sm:table-cell capitalize text-gray-600">{a.type}</td>
                  <td className="px-4 py-3 hidden md:table-cell text-gray-600">{a.country || '—'}</td>
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
    </div>
  );
}

export default function AssessmentsPage() {
  return (
    <RequireAuth>
      <DashboardShell active="assessments" title="Assessments">
        <AssessmentsContent />
      </DashboardShell>
    </RequireAuth>
  );
}
