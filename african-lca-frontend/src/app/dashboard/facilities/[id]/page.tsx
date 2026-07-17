'use client';

import React, { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  Loader2,
  MapPin,
  Pencil,
  Factory,
  Trash2,
  StickyNote,
  Building2,
  FileBarChart,
} from 'lucide-react';
import RequireAuth from '@/components/RequireAuth';
import DashboardShell from '@/components/DashboardShell';
import ConfirmDialog from '@/components/ConfirmDialog';
import { assessmentAPI, AssessmentSummary, Facility } from '@/lib/api';

export const dynamic = 'force-dynamic';

function FacilityProfileContent() {
  const params = useParams();
  const router = useRouter();
  const facilityId = typeof params.id === 'string' ? params.id : '';

  const [facility, setFacility] = useState<Facility | null>(null);
  const [assessments, setAssessments] = useState<AssessmentSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!facilityId) return;
    let active = true;
    (async () => {
      try {
        const [f, a] = await Promise.all([
          assessmentAPI.getFacility(facilityId),
          assessmentAPI.getMyAssessments(),
        ]);
        if (!active) return;
        setFacility(f);
        setAssessments(a.assessments.filter((row) => row.facility_id === facilityId));
      } catch (err) {
        if (active) setError(err instanceof Error ? err.message : 'Could not load this facility.');
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, [facilityId]);

  const locationLine = useMemo(() => {
    if (!facility) return '';
    return [facility.location, facility.region, facility.country].filter(Boolean).join(', ');
  }, [facility]);

  const confirmDelete = async () => {
    if (!facility) return;
    setDeleting(true);
    try {
      await assessmentAPI.deleteFacility(facility.id);
      router.push('/dashboard/facilities');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not delete the facility.');
      setPendingDelete(false);
    } finally {
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 text-gray-500">
        <Loader2 className="w-4 h-4 animate-spin" /> Loading facility profile…
      </div>
    );
  }

  if (error || !facility) {
    return (
      <div className="space-y-4">
        <Link
          href="/dashboard/facilities"
          className="inline-flex items-center gap-1 text-sm font-medium text-moss hover:text-spruce"
        >
          <ArrowLeft className="w-4 h-4" /> Back to facilities
        </Link>
        <div className="rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-700">
          {error || 'Facility not found.'}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <Link
            href="/dashboard/facilities"
            className="inline-flex items-center gap-1 text-sm font-medium text-moss hover:text-spruce"
          >
            <ArrowLeft className="w-4 h-4" /> Back to facilities
          </Link>
          <div className="mt-3 flex items-start gap-3">
            <div className="rounded-xl bg-moss/10 p-3 text-spruce">
              <Factory className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-2xl font-semibold text-gray-900">{facility.name}</h2>
              <p className="text-sm text-gray-500">Facility profile</p>
            </div>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={`/processing-assessment?facilityId=${facility.id}`}
            className="inline-flex items-center gap-2 rounded-lg bg-spruce px-4 py-2 text-sm font-medium text-white hover:bg-ink"
          >
            New assessment
          </Link>
          <Link
            href={`/dashboard/facilities?edit=${facility.id}`}
            className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            <Pencil className="w-4 h-4" /> Edit
          </Link>
          <button
            type="button"
            onClick={() => setPendingDelete(true)}
            className="inline-flex items-center gap-2 rounded-lg border border-red-200 bg-white px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50"
          >
            <Trash2 className="w-4 h-4" /> Delete
          </button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="lg:col-span-2 rounded-2xl border border-gray-200 bg-white p-6">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Profile details</h3>
          <dl className="mt-4 grid gap-4 sm:grid-cols-2">
            <ProfileField
              icon={Building2}
              label="Facility type"
              value={facility.facility_type || '—'}
            />
            <ProfileField icon={MapPin} label="Place" value={locationLine || '—'} />
            <ProfileField
              icon={StickyNote}
              label="Notes"
              value={facility.notes || '—'}
              className="sm:col-span-2"
            />
          </dl>
          <p className="mt-6 text-xs text-gray-400">
            Added {facility.created_at ? new Date(facility.created_at).toLocaleDateString() : '—'}
          </p>
        </section>

        <section className="rounded-2xl border border-gray-200 bg-white p-6">
          <div className="flex items-center gap-2">
            <FileBarChart className="w-4 h-4 text-moss" />
            <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">
              Assessments
            </h3>
          </div>
          <p className="mt-2 text-3xl font-bold text-gray-900">{assessments.length}</p>
          <p className="text-sm text-gray-500">linked to this facility</p>

          {assessments.length === 0 ? (
            <p className="mt-4 text-sm text-gray-500">No assessments yet.</p>
          ) : (
            <ul className="mt-4 space-y-2">
              {assessments.slice(0, 8).map((a) => (
                <li key={a.id}>
                  <Link
                    href={`/results?id=${a.id}&type=processing`}
                    className="block rounded-lg border border-gray-100 px-3 py-2 hover:border-moss/40 hover:bg-moss/5"
                  >
                    <div className="text-sm font-medium text-gray-900">
                      {a.title || a.company_name || 'Untitled'}
                    </div>
                    <div className="text-xs text-gray-500">
                      {a.created_at ? new Date(a.created_at).toLocaleDateString() : '—'}
                      {typeof a.single_score === 'number' ? ` · ${a.single_score.toFixed(3)}` : ''}
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
          {assessments.length > 8 && (
            <Link
              href="/dashboard/assessments"
              className="mt-3 inline-block text-sm font-medium text-moss hover:text-spruce"
            >
              View all assessments
            </Link>
          )}
        </section>
      </div>

      <ConfirmDialog
        open={pendingDelete}
        title="Delete this facility?"
        description={
          <>
            This removes <strong>{facility.name}</strong> from your dashboard. Saved assessments are
            kept but unlinked from this facility.
          </>
        }
        confirmLabel="Delete facility"
        requireText={facility.name}
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setPendingDelete(false)}
      />
    </div>
  );
}

function ProfileField({
  icon: Icon,
  label,
  value,
  className = '',
}: {
  icon: React.ElementType;
  label: string;
  value: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <dt className="flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-gray-400">
        <Icon className="w-3.5 h-3.5" />
        {label}
      </dt>
      <dd className="mt-1 text-sm text-gray-900 whitespace-pre-wrap">{value}</dd>
    </div>
  );
}

export default function FacilityProfilePage() {
  return (
    <RequireAuth roles={['processor']}>
      <DashboardShell active="facilities" title="Facility profile">
        <FacilityProfileContent />
      </DashboardShell>
    </RequireAuth>
  );
}
