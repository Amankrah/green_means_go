'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Loader2, Pencil, Trash2 } from 'lucide-react';
import RequireAuth from '@/components/RequireAuth';
import DashboardShell from '@/components/DashboardShell';
import NewAssessmentButton from '@/components/NewAssessmentButton';
import ConfirmDialog from '@/components/ConfirmDialog';
import { assessmentAPI, AssessmentSummary } from '@/lib/api';

export const dynamic = 'force-dynamic';

type Filter = 'all' | 'farm' | 'processing';

function AssessmentsContent() {
  const router = useRouter();
  const [rows, setRows] = useState<AssessmentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>('all');
  const [busyId, setBusyId] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<AssessmentSummary | null>(null);
  const [pendingRerun, setPendingRerun] = useState<AssessmentSummary | null>(null);

  const load = async () => {
    const data = await assessmentAPI.getMyAssessments();
    setRows(data.assessments);
  };

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        await load();
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

  const labelFor = (a: AssessmentSummary) => a.title || a.company_name || 'Untitled';

  const confirmDelete = async () => {
    if (!pendingDelete) return;
    setBusyId(pendingDelete.id);
    setError(null);
    try {
      await assessmentAPI.deleteAssessment(pendingDelete.id);
      setRows((prev) => prev.filter((r) => r.id !== pendingDelete.id));
      try {
        localStorage.removeItem(`assessment_${pendingDelete.id}`);
      } catch {
        /* ignore */
      }
      setPendingDelete(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete the assessment.');
    } finally {
      setBusyId(null);
    }
  };

  const confirmRerun = () => {
    if (!pendingRerun) return;
    const a = pendingRerun;
    setPendingRerun(null);
    if (a.type === 'processing') {
      router.push(`/processing-assessment?rerunFrom=${a.id}`);
    } else {
      router.push(
        `/assessment?rerunFrom=${a.id}${a.farm_id ? `&farmId=${a.farm_id}` : ''}`
      );
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <p className="text-gray-600">Every assessment you&apos;ve saved, newest first.</p>
        <NewAssessmentButton />
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
          <div className="mt-4 flex justify-center">
            <NewAssessmentButton label="Run an assessment" />
          </div>
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
                    <div className="font-medium text-gray-900">{labelFor(a)}</div>
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
                    <div className="inline-flex items-center gap-3">
                      <Link
                        href={`/results?id=${a.id}${a.type === 'processing' ? '&type=processing' : ''}`}
                        className="font-medium text-moss hover:text-spruce"
                      >
                        View
                      </Link>
                      {a.can_rerun && (
                        <button
                          type="button"
                          onClick={() => setPendingRerun(a)}
                          disabled={busyId === a.id}
                          className="inline-flex items-center gap-1 font-medium text-gray-600 hover:text-spruce disabled:opacity-50"
                          title="Update inputs and re-run"
                        >
                          <Pencil className="w-3.5 h-3.5" />
                          <span className="hidden lg:inline">Edit</span>
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => setPendingDelete(a)}
                        disabled={busyId === a.id}
                        className="inline-flex items-center gap-1 font-medium text-red-600 hover:text-red-700 disabled:opacity-50"
                        title="Delete assessment"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                        <span className="hidden lg:inline">Delete</span>
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={Boolean(pendingDelete)}
        title="Delete this assessment?"
        description={
          <>
            This permanently removes <strong>{pendingDelete ? labelFor(pendingDelete) : ''}</strong> and
            its scores, ISO draft, and chat grounding. This cannot be undone.
          </>
        }
        confirmLabel="Delete assessment"
        requireText={pendingDelete ? labelFor(pendingDelete) : undefined}
        busy={Boolean(pendingDelete && busyId === pendingDelete.id)}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(null)}
      />

      <ConfirmDialog
        open={Boolean(pendingRerun)}
        title="Update and re-run?"
        description={
          <>
            You can change the inputs for <strong>{pendingRerun ? labelFor(pendingRerun) : ''}</strong>.
            When you submit, the existing scores and report for this assessment will be{' '}
            <strong>replaced</strong> — the assessment id stays the same.
          </>
        }
        confirmLabel="Continue to editor"
        tone="warning"
        onConfirm={confirmRerun}
        onCancel={() => setPendingRerun(null)}
      />
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
